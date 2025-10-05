#!/usr/bin/env python3
"""
Quick Cache Benchmark - Standalone Script

Run this directly to test validation caching performance.
No pytest required.

Usage:
    cd smartchaindb
    python tests/performance/run_cache_benchmark.py
"""

import sys
import time
from bigchaindb.common.crypto import generate_key_pair
from bigchaindb.models import Transaction as BDBTransaction
from bigchaindb.lib import BigchainDB
from bigchaindb.common.shacl_validator_cached import get_shacl_validator


def print_header(title):
    """Print formatted section header."""
    print("\n" + "="*80)
    print(title.center(80))
    print("="*80)


def print_metrics(validator):
    """Print current validator metrics."""
    metrics = validator.get_metrics_summary()
    cache_stats = validator.get_cache_stats()
    
    if metrics == {'message': 'No validations recorded yet'}:
        print("\n  No validations recorded yet.")
        return
    
    print(f"\n  Total validations: {metrics['total_validations']}")
    print(f"  Cache hits: {metrics['cache_hits']}")
    print(f"  Cache misses: {metrics['cache_misses']}")
    print(f"  Hit rate: {metrics['cache_hit_rate_percent']:.1f}%")
    print(f"  Cache size: {cache_stats['cache_size']}")
    print(f"  Avg time: {metrics['performance']['avg_time_ms']:.2f}ms")
    print(f"  Time saved: {metrics['performance']['time_saved_by_cache_ms']:.2f}ms")


def benchmark_single_transaction():
    """Benchmark 1: Single transaction validation."""
    print_header("Benchmark 1: Single Transaction Validation")
    
    bigchain = BigchainDB()
    validator = get_shacl_validator()
    validator.clear_cache()
    validator.metrics.reset_metrics()
    
    # Create transaction
    keys = generate_key_pair()
    tx = BDBTransaction.create(
        [keys.public_key],
        [([keys.public_key], 1)],
        asset={
            'data': {
                'machineIdentifier': 'BenchMark001',
                'capability': ['Laser Cutting']
            }
        },
        metadata={'requestCreationTimestamp': '2025-10-04T12:00:00Z'}
    )
    
    print(f"\nTransaction: {tx.id}")
    print("Validating...")
    
    start = time.time()
    try:
        tx.validate(bigchain)
        duration = (time.time() - start) * 1000
        print(f"✓ Validation passed in {duration:.2f}ms")
        print_metrics(validator)
        return True
    except Exception as e:
        print(f"✗ Validation failed: {e}")
        return False


def benchmark_cache_effectiveness():
    """Benchmark 2: Cache effectiveness (same transaction multiple times)."""
    print_header("Benchmark 2: Cache Effectiveness")
    
    bigchain = BigchainDB()
    validator = get_shacl_validator()
    validator.clear_cache()
    validator.metrics.reset_metrics()
    
    # Create one transaction
    keys = generate_key_pair()
    tx = BDBTransaction.create(
        [keys.public_key],
        [([keys.public_key], 1)],
        asset={
            'data': {
                'machineIdentifier': 'CacheBench001',
                'capability': ['Testing']
            }
        },
        metadata={'requestCreationTimestamp': '2025-10-04T12:00:00Z'}
    )
    
    print(f"\nValidating same transaction 5 times...")
    
    times = []
    for i in range(5):
        start = time.time()
        try:
            tx.validate(bigchain)
            duration = (time.time() - start) * 1000
            times.append(duration)
            
            status = "MISS (expected)" if i == 0 else "HIT (expected)"
            print(f"  Validation {i+1}: {duration:7.2f}ms - {status}")
        except Exception as e:
            print(f"  Validation {i+1}: FAILED - {e}")
            return False
    
    # Analysis
    first_time = times[0]
    avg_cached = sum(times[1:]) / len(times[1:]) if len(times) > 1 else 0
    speedup = first_time / avg_cached if avg_cached > 0 else 0
    
    print(f"\nAnalysis:")
    print(f"  First (uncached): {first_time:.2f}ms")
    print(f"  Avg (cached): {avg_cached:.2f}ms")
    print(f"  Speedup: {speedup:.2f}x")
    
    print_metrics(validator)
    
    if speedup > 1.5:
        print(f"\n✓ Cache is working effectively!")
        return True
    else:
        print(f"\n✗ Cache not providing expected speedup")
        return False


def benchmark_batch_transactions():
    """Benchmark 3: Batch of unique transactions."""
    print_header("Benchmark 3: Batch Transactions (20 unique)")
    
    bigchain = BigchainDB()
    validator = get_shacl_validator()
    validator.clear_cache()
    validator.metrics.reset_metrics()
    
    num_txs = 20
    keys = generate_key_pair()
    
    print(f"\nCreating and validating {num_txs} transactions...")
    
    total_time = 0
    success_count = 0
    
    for i in range(num_txs):
        tx = BDBTransaction.create(
            [keys.public_key],
            [([keys.public_key], 1)],
            asset={
                'data': {
                    'machineIdentifier': f'BatchBench{i:03d}',
                    'capability': ['Processing']
                }
            },
            metadata={'requestCreationTimestamp': '2025-10-04T12:00:00Z'}
        )
        
        start = time.time()
        try:
            tx.validate(bigchain)
            duration = (time.time() - start) * 1000
            total_time += duration
            success_count += 1
            
            if (i + 1) % 5 == 0:
                print(f"  Progress: {i+1}/{num_txs} - Avg: {total_time/success_count:.2f}ms")
        except Exception as e:
            print(f"  TX {i+1} failed: {e}")
    
    print(f"\nResults:")
    print(f"  Successful: {success_count}/{num_txs}")
    print(f"  Total time: {total_time:.2f}ms")
    print(f"  Avg per TX: {total_time/success_count:.2f}ms" if success_count > 0 else "  N/A")
    
    print_metrics(validator)
    
    return success_count == num_txs


def benchmark_marketplace_flow():
    """Benchmark 4: Marketplace transaction flow."""
    print_header("Benchmark 4: Marketplace Flow (CREATE → ADVERTISEMENT)")
    
    bigchain = BigchainDB()
    validator = get_shacl_validator()
    validator.clear_cache()
    validator.metrics.reset_metrics()
    
    seller = generate_key_pair()
    
    # Step 1: CREATE
    print("\n[1/2] CREATE asset...")
    create_tx = BDBTransaction.create(
        [seller.public_key],
        [([seller.public_key], 1)],
        asset={
            'data': {
                'machineIdentifier': 'MarketBench001',
                'capability': ['Welding', 'Cutting']
            }
        },
        metadata={'requestCreationTimestamp': '2025-10-04T12:00:00Z'}
    )
    
    start = time.time()
    try:
        create_tx.validate(bigchain)
        create_time = (time.time() - start) * 1000
        print(f"  ✓ Validated in {create_time:.2f}ms")
        print(f"  Asset ID: {create_tx.id}")
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        return False
    
    # Step 2: ADVERTISEMENT
    print("\n[2/2] ADVERTISEMENT...")
    ad_tx = BDBTransaction.create(
        [seller.public_key],
        [([seller.public_key], 1)],
        asset={'id': create_tx.id},
        metadata={
            'status': 'OPEN',
            'advertiser_public_key': seller.public_key,
            'price': '8000.00',
            'description': 'Industrial welding machine',
            'category': 'Manufacturing',
            'condition': 'Used',
            'expiry_date': '2025-12-04T12:00:00Z',
            'contact_info': 'seller@example.com',
            'location': 'Factory District',
            'requestCreationTimestamp': '2025-10-04T12:00:00Z'
        },
        operation='ADVERTISEMENT'
    )
    
    start = time.time()
    try:
        ad_tx.validate(bigchain)
        ad_time = (time.time() - start) * 1000
        print(f"  ✓ Validated in {ad_time:.2f}ms")
        print(f"  Advertisement ID: {ad_tx.id}")
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        return False
    
    print(f"\nTiming:")
    print(f"  CREATE: {create_time:.2f}ms")
    print(f"  ADVERTISEMENT: {ad_time:.2f}ms")
    
    print_metrics(validator)
    
    return True


def main():
    """Run all benchmarks."""
    print("\n" + "╔" + "="*78 + "╗")
    print("║" + " SHACL Validation Cache Benchmark ".center(78) + "║")
    print("╚" + "="*78 + "╝")
    
    results = {}
    
    # Run benchmarks
    benchmarks = [
        ("Single Transaction", benchmark_single_transaction),
        ("Cache Effectiveness", benchmark_cache_effectiveness),
        ("Batch Transactions", benchmark_batch_transactions),
        ("Marketplace Flow", benchmark_marketplace_flow)
    ]
    
    for name, func in benchmarks:
        try:
            results[name] = func()
        except Exception as e:
            print(f"\n✗ Benchmark '{name}' crashed: {e}")
            results[name] = False
    
    # Final summary
    print_header("FINAL SUMMARY")
    
    print("\nBenchmark Results:")
    for name, passed in results.items():
        status = "✓ PASSED" if passed else "✗ FAILED"
        print(f"  {name:25s} {status}")
    
    total = len(results)
    passed = sum(1 for v in results.values() if v)
    
    print(f"\nOverall: {passed}/{total} benchmarks passed")
    
    if passed == total:
        print("\n🎉 All benchmarks completed successfully!")
        return 0
    else:
        print(f"\n⚠ {total - passed} benchmark(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())


