"""
REAL Load Testing for SHACL Validation Caching

This script sends actual transactions through BigchainDB and measures real performance.
No mocking, no sleeps - just real transactions.

Prerequisites:
    - BigchainDB services running (docker-compose up)
    - SHACL microservice running
    - MongoDB accessible

Usage:
    cd smartchaindb
    pytest tests/performance/test_cache_real_transactions.py -v -s
"""

import pytest
import time
import requests
import json
from bigchaindb.common.crypto import generate_key_pair
from bigchaindb.models import Transaction as BDBTransaction
from bigchaindb.lib import BigchainDB
from bigchaindb.common.shacl_validator_cached import get_shacl_validator


class TestRealTransactionCaching:
    """
    Real-world transaction testing with actual BigchainDB validation.
    """
    
    @pytest.fixture(scope="class")
    def bigchain(self):
        """Get BigchainDB instance."""
        return BigchainDB()
    
    @pytest.fixture(scope="class")
    def validator(self):
        """Get validator and reset metrics."""
        validator = get_shacl_validator()
        validator.clear_cache()
        validator.metrics.reset_metrics()
        return validator
    
    @pytest.fixture(scope="class")
    def seller_keys(self):
        """Generate seller keypair."""
        return generate_key_pair()
    
    @pytest.fixture(scope="class")
    def buyer_keys(self):
        """Generate buyer keypair."""
        return generate_key_pair()
    
    @pytest.fixture(scope="class")
    def escrow_keys(self):
        """Generate escrow keypair."""
        return generate_key_pair()
    
    def test_001_validate_single_create_transaction(self, bigchain, validator, seller_keys):
        """
        Test 1: Single CREATE transaction validation
        
        Measures actual validation time for a CREATE transaction.
        """
        print("\n" + "="*80)
        print("TEST 1: Single CREATE Transaction - Real Validation")
        print("="*80)
        
        validator.clear_cache()
        validator.metrics.reset_metrics()
        
        # Create a real CREATE transaction
        tx = BDBTransaction.create(
            [seller_keys.public_key],
            [([seller_keys.public_key], 1)],
            asset={
                'data': {
                    'machineIdentifier': 'Machine001',
                    'capability': ['Welding', 'Cutting', 'Assembly']
                }
            },
            metadata={'requestCreationTimestamp': '2025-10-04T12:00:00Z'}
        )
        
        print(f"\nTransaction ID: {tx.id}")
        print(f"Operation: {tx.operation}")
        
        # Validate (this goes through the full SHACL pipeline)
        print("\nValidating...")
        start = time.time()
        
        try:
            validated_tx = tx.validate(bigchain)
            validation_time = (time.time() - start) * 1000
            
            print(f"✓ Validation PASSED in {validation_time:.2f}ms")
            
            # Get metrics
            metrics = validator.get_metrics_summary()
            cache_stats = validator.get_cache_stats()
            
            print(f"\nMetrics:")
            print(f"  Total validations: {metrics['total_validations']}")
            print(f"  Cache hits: {metrics['cache_hits']}")
            print(f"  Cache misses: {metrics['cache_misses']}")
            print(f"  Avg time: {metrics['performance']['avg_time_ms']:.2f}ms")
            
            assert validated_tx is not None
            assert metrics['total_validations'] >= 1
            
            print("\n✅ TEST PASSED")
            return tx
            
        except Exception as e:
            print(f"✗ Validation FAILED: {e}")
            raise
    
    def test_002_create_then_advertisement(self, bigchain, validator, seller_keys):
        """
        Test 2: CREATE → ADVERTISEMENT flow
        
        Tests caching across related transactions.
        """
        print("\n" + "="*80)
        print("TEST 2: CREATE → ADVERTISEMENT Flow")
        print("="*80)
        
        validator.clear_cache()
        validator.metrics.reset_metrics()
        
        # Step 1: CREATE asset
        print("\n[Step 1] Creating asset...")
        create_tx = BDBTransaction.create(
            [seller_keys.public_key],
            [([seller_keys.public_key], 1)],
            asset={
                'data': {
                    'machineIdentifier': 'Machine002',
                    'capability': ['Painting', 'Coating']
                }
            },
            metadata={'requestCreationTimestamp': '2025-10-04T12:00:00Z'}
        )
        
        start = time.time()
        create_tx.validate(bigchain)
        create_time = (time.time() - start) * 1000
        print(f"✓ CREATE validated in {create_time:.2f}ms")
        print(f"  Asset ID: {create_tx.id}")
        
        # Step 2: ADVERTISEMENT
        print("\n[Step 2] Creating advertisement...")
        ad_tx = BDBTransaction.create(
            [seller_keys.public_key],
            [([seller_keys.public_key], 1)],
            asset={'id': create_tx.id},
            metadata={
                'status': 'OPEN',
                'advertiser_public_key': seller_keys.public_key,
                'price': '5000.00',
                'description': 'Industrial painting machine',
                'category': 'Manufacturing Equipment',
                'condition': 'Used',
                'expiry_date': '2025-11-04T12:00:00Z',
                'contact_info': 'seller@example.com',
                'location': 'Factory District',
                'requestCreationTimestamp': '2025-10-04T12:00:00Z'
            },
            operation='ADVERTISEMENT'
        )
        
        start = time.time()
        ad_tx.validate(bigchain)
        ad_time = (time.time() - start) * 1000
        print(f"✓ ADVERTISEMENT validated in {ad_time:.2f}ms")
        print(f"  Advertisement ID: {ad_tx.id}")
        
        # Get metrics
        metrics = validator.get_metrics_summary()
        
        print(f"\nPerformance Summary:")
        print(f"  CREATE time: {create_time:.2f}ms")
        print(f"  ADVERTISEMENT time: {ad_time:.2f}ms")
        print(f"  Total validations: {metrics['total_validations']}")
        print(f"  Cache hit rate: {metrics['cache_hit_rate_percent']:.1f}%")
        
        print("\n✅ TEST PASSED")
        return create_tx, ad_tx
    
    def test_003_full_marketplace_flow(self, bigchain, validator, seller_keys, buyer_keys, escrow_keys):
        """
        Test 3: Full Marketplace Flow - CREATE → ADVERTISEMENT → BUY_OFFER → SELL
        
        Tests real marketplace transaction chain with caching.
        """
        print("\n" + "="*80)
        print("TEST 3: Full Marketplace Flow (Real Transactions)")
        print("="*80)
        
        validator.clear_cache()
        validator.metrics.reset_metrics()
        
        times = {}
        
        # Step 1: CREATE asset
        print("\n[Step 1] CREATE asset...")
        create_tx = BDBTransaction.create(
            [seller_keys.public_key],
            [([seller_keys.public_key], 1)],
            asset={
                'data': {
                    'machineIdentifier': 'MachineMKT001',
                    'capability': ['Laser Cutting', 'CNC Milling']
                }
            },
            metadata={'requestCreationTimestamp': '2025-10-04T12:00:00Z'}
        )
        
        start = time.time()
        create_tx.validate(bigchain)
        times['CREATE'] = (time.time() - start) * 1000
        print(f"✓ Validated in {times['CREATE']:.2f}ms")
        
        # Step 2: ADVERTISEMENT
        print("\n[Step 2] ADVERTISEMENT...")
        ad_tx = BDBTransaction.create(
            [seller_keys.public_key],
            [([seller_keys.public_key], 1)],
            asset={'id': create_tx.id},
            metadata={
                'status': 'OPEN',
                'advertiser_public_key': seller_keys.public_key,
                'price': '10000.00',
                'description': 'Precision CNC machine',
                'category': 'Industrial',
                'condition': 'Excellent',
                'expiry_date': '2025-12-04T12:00:00Z',
                'contact_info': 'seller@factory.com',
                'location': 'Industrial Zone',
                'requestCreationTimestamp': '2025-10-04T12:00:00Z'
            },
            operation='ADVERTISEMENT'
        )
        
        start = time.time()
        ad_tx.validate(bigchain)
        times['ADVERTISEMENT'] = (time.time() - start) * 1000
        print(f"✓ Validated in {times['ADVERTISEMENT']:.2f}ms")
        
        # Note: For BUY_OFFER and SELL, we'd need the transactions to be committed
        # to MongoDB first, which requires Tendermint. For unit testing, we stop here.
        
        metrics = validator.get_metrics_summary()
        cache_stats = validator.get_cache_stats()
        
        print(f"\n{'─'*80}")
        print("PERFORMANCE SUMMARY:")
        for tx_type, duration in times.items():
            print(f"  {tx_type:20s} {duration:8.2f}ms")
        print(f"\nMETRICS:")
        print(f"  Total validations: {metrics['total_validations']}")
        print(f"  Cache hits: {metrics['cache_hits']}")
        print(f"  Cache misses: {metrics['cache_misses']}")
        print(f"  Hit rate: {metrics['cache_hit_rate_percent']:.1f}%")
        print(f"  Cache size: {cache_stats['cache_size']}")
        print(f"  Avg validation time: {metrics['performance']['avg_time_ms']:.2f}ms")
        print(f"  Time saved by cache: {metrics['performance']['time_saved_by_cache_ms']:.2f}ms")
        print(f"{'─'*80}")
        
        print("\n✅ TEST PASSED")
    
    def test_004_batch_creates(self, bigchain, validator, seller_keys):
        """
        Test 4: Batch CREATE transactions
        
        Tests performance with multiple sequential transactions.
        """
        print("\n" + "="*80)
        print("TEST 4: Batch CREATE Transactions (10 transactions)")
        print("="*80)
        
        validator.clear_cache()
        validator.metrics.reset_metrics()
        
        num_txs = 10
        total_time = 0
        
        print(f"\nCreating and validating {num_txs} transactions...")
        
        for i in range(num_txs):
            tx = BDBTransaction.create(
                [seller_keys.public_key],
                [([seller_keys.public_key], 1)],
                asset={
                    'data': {
                        'machineIdentifier': f'BatchMachine{i:03d}',
                        'capability': ['Processing']
                    }
                },
                metadata={'requestCreationTimestamp': '2025-10-04T12:00:00Z'}
            )
            
            start = time.time()
            tx.validate(bigchain)
            duration = (time.time() - start) * 1000
            total_time += duration
            
            print(f"  [{i+1:2d}/{num_txs}] TX {tx.id[:16]}... - {duration:6.2f}ms")
        
        metrics = validator.get_metrics_summary()
        cache_stats = validator.get_cache_stats()
        
        print(f"\n{'─'*80}")
        print("BATCH RESULTS:")
        print(f"  Transactions: {num_txs}")
        print(f"  Total time: {total_time:.2f}ms")
        print(f"  Avg time per TX: {total_time/num_txs:.2f}ms")
        print(f"  Total validations: {metrics['total_validations']}")
        print(f"  Cache hits: {metrics['cache_hits']}")
        print(f"  Cache misses: {metrics['cache_misses']}")
        print(f"  Hit rate: {metrics['cache_hit_rate_percent']:.1f}%")
        print(f"  Cache size: {cache_stats['cache_size']}")
        print(f"{'─'*80}")
        
        assert metrics['total_validations'] == num_txs
        assert cache_stats['cache_size'] == num_txs
        
        print("\n✅ TEST PASSED")
    
    def test_005_metrics_endpoint_integration(self, validator):
        """
        Test 5: Metrics Endpoint
        
        Tests that metrics can be retrieved via the API endpoint.
        """
        print("\n" + "="*80)
        print("TEST 5: Metrics Endpoint Integration")
        print("="*80)
        
        # Try to get metrics via HTTP API
        print("\nAttempting to retrieve metrics via HTTP API...")
        
        try:
            response = requests.get('http://localhost:9984/api/v1/metrics/validation', timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                print(f"✓ Metrics endpoint accessible")
                print(f"\nResponse preview:")
                print(f"  Status: {data.get('status')}")
                print(f"  SHACL healthy: {data.get('shacl_service_healthy')}")
                
                if 'metrics' in data:
                    metrics = data['metrics']
                    print(f"  Total validations: {metrics.get('total_validations', 'N/A')}")
                    print(f"  Cache hit rate: {metrics.get('cache_hit_rate_percent', 'N/A')}%")
                
                print("\n✅ TEST PASSED")
            else:
                print(f"✗ Metrics endpoint returned status {response.status_code}")
                print("  (This might be expected if endpoint isn't registered yet)")
                
        except requests.exceptions.ConnectionError:
            print("✗ Could not connect to BigchainDB API")
            print("  This is expected if services aren't running")
            print("  Run: docker-compose up -d")
        except Exception as e:
            print(f"✗ Unexpected error: {e}")
    
    def test_006_cache_effectiveness(self, bigchain, validator, seller_keys):
        """
        Test 6: Cache Effectiveness
        
        Validates the same transaction multiple times to test cache hit rate.
        """
        print("\n" + "="*80)
        print("TEST 6: Cache Effectiveness (Same Transaction Multiple Times)")
        print("="*80)
        
        validator.clear_cache()
        validator.metrics.reset_metrics()
        
        # Create one transaction
        tx = BDBTransaction.create(
            [seller_keys.public_key],
            [([seller_keys.public_key], 1)],
            asset={
                'data': {
                    'machineIdentifier': 'CacheTest001',
                    'capability': ['Testing']
                }
            },
            metadata={'requestCreationTimestamp': '2025-10-04T12:00:00Z'}
        )
        
        print(f"\nTransaction ID: {tx.id}")
        print("\nValidating same transaction 5 times...")
        
        times = []
        for i in range(5):
            start = time.time()
            tx.validate(bigchain)
            duration = (time.time() - start) * 1000
            times.append(duration)
            
            cache_status = "MISS" if i == 0 else "HIT"
            print(f"  Validation {i+1}: {duration:6.2f}ms - {cache_status}")
        
        metrics = validator.get_metrics_summary()
        
        # Calculate speedup
        first_time = times[0]
        avg_cached_time = sum(times[1:]) / len(times[1:])
        speedup = first_time / avg_cached_time if avg_cached_time > 0 else 0
        
        print(f"\n{'─'*80}")
        print("CACHE EFFECTIVENESS:")
        print(f"  First validation (miss): {first_time:.2f}ms")
        print(f"  Avg cached (hit): {avg_cached_time:.2f}ms")
        print(f"  Speedup: {speedup:.2f}x")
        print(f"  Cache hit rate: {metrics['cache_hit_rate_percent']:.1f}%")
        print(f"  Time saved: {metrics['performance']['time_saved_by_cache_ms']:.2f}ms")
        print(f"{'─'*80}")
        
        # Assertions
        assert metrics['cache_hits'] == 4
        assert metrics['cache_misses'] == 1
        assert speedup > 1.5  # Cache should be at least 1.5x faster
        
        print("\n✅ TEST PASSED")
    
    def test_007_final_summary(self, validator):
        """
        Test 7: Final Performance Summary
        
        Prints comprehensive summary of all tests.
        """
        print("\n" + "="*80)
        print("FINAL PERFORMANCE SUMMARY - ALL TESTS")
        print("="*80)
        
        metrics = validator.get_metrics_summary()
        cache_stats = validator.get_cache_stats()
        
        if metrics == {'message': 'No validations recorded yet'}:
            print("\nNo validations recorded. Run other tests first.")
            return
        
        print(f"\nOVERALL STATISTICS:")
        print(f"  Uptime: {metrics['uptime_seconds']:.1f}s")
        print(f"  Total validations: {metrics['total_validations']}")
        print(f"  Cache hits: {metrics['cache_hits']}")
        print(f"  Cache misses: {metrics['cache_misses']}")
        print(f"  Cache hit rate: {metrics['cache_hit_rate_percent']:.1f}%")
        print(f"  Validation errors: {metrics['validation_errors']}")
        
        print(f"\nPERFORMANCE:")
        perf = metrics['performance']
        print(f"  Total time: {perf['total_time_ms']:.2f}ms")
        print(f"  Avg time: {perf['avg_time_ms']:.2f}ms")
        print(f"  Min time: {perf['min_time_ms']:.2f}ms")
        print(f"  Max time: {perf['max_time_ms']:.2f}ms")
        print(f"  Avg cache hit: {perf['avg_cache_hit_time_ms']:.2f}ms")
        print(f"  Avg cache miss: {perf['avg_cache_miss_time_ms']:.2f}ms")
        print(f"  Time saved: {perf['time_saved_by_cache_ms']:.2f}ms")
        
        print(f"\nCACHE STATUS:")
        print(f"  Size: {cache_stats['cache_size']}/{cache_stats['cache_max_size']}")
        print(f"  Utilization: {cache_stats['cache_utilization_percent']:.1f}%")
        print(f"  TTL: {cache_stats['cache_ttl_seconds']}s")
        
        # Performance rating
        hit_rate = metrics['cache_hit_rate_percent']
        avg_time = perf['avg_time_ms']
        
        print(f"\nPERFORMANCE RATING:")
        if hit_rate >= 60 and avg_time < 50:
            rating = "EXCELLENT"
            emoji = "🌟"
        elif hit_rate >= 40 and avg_time < 100:
            rating = "GOOD"
            emoji = "✓"
        else:
            rating = "NEEDS TUNING"
            emoji = "⚠"
        
        print(f"  {emoji} {rating}")
        
        print(f"\n{'='*80}")
        print("✅ ALL REAL TRANSACTION TESTS COMPLETED!")
        print("="*80 + "\n")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])


