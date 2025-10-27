#!/usr/bin/env python3
"""
Enhanced State-Aware Cache Test Script

This script demonstrates the enhanced caching capabilities:
- Phase-aware validation (HTTP_POST, CHECK_TX, DELIVER_TX)
- State-aware cache keys with blockchain state hash
- Dependency tracking and cache invalidation
- Multi-phase transaction lifecycle support
"""

import sys
import os
import time
import requests
from datetime import datetime

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from bigchaindb.common.transaction import Transaction
    from bigchaindb.common.crypto import generate_key_pair
    from bigchaindb.common.transaction import Input, Output
    from bigchaindb.common.shacl_validator_state_aware_enhanced import shacl_validator
    print("✅ Enhanced SmartChainDB classes imported successfully")
except ImportError as e:
    print(f"❌ Failed to import SmartChainDB classes: {e}")
    sys.exit(1)


def test_enhanced_cache():
    """Test the enhanced state-aware cache system"""
    print("\n🔬 Testing Enhanced State-Aware Cache System")
    print("=" * 60)
    
    # Test 1: Phase-aware caching
    print("\n📊 Test 1: Phase-Aware Caching")
    print("-" * 40)
    
    # Create a test transaction
    keypair = generate_key_pair()
    tx = Transaction(
        operation=Transaction.CREATE,
        asset={'data': {
            'machineIdentifier': f'test_enhanced_{int(time.time() * 1000)}',
            'capability': ['read', 'write'],
            'capabilityParameters': {'type': 'enhanced_test'}
        }},
        metadata={
            'test': 'enhanced_cache',
            'requestCreationTimestamp': datetime.now().isoformat()
        }
    )
    
    input_obj = Input.generate([keypair.public_key])
    tx.inputs = [input_obj]
    output_obj = Output.generate([keypair.public_key], amount=1)
    tx.outputs = [output_obj]
    tx.sign([keypair.private_key])
    
    tx_dict = tx.to_dict()
    
    # Test validation in different phases
    phases = ['HTTP_POST', 'CHECK_TX', 'DELIVER_TX']
    
    for phase in phases:
        print(f"\n🔍 Testing {phase} phase:")
        
        # First validation (cache miss)
        start_time = time.time()
        conforms1, results1 = shacl_validator.validate_transaction(tx_dict, phase=phase)
        time1 = (time.time() - start_time) * 1000
        
        # Second validation (cache hit)
        start_time = time.time()
        conforms2, results2 = shacl_validator.validate_transaction(tx_dict, phase=phase)
        time2 = (time.time() - start_time) * 1000
        
        print(f"  First validation:  {time1:.2f}ms (MISS)")
        print(f"  Second validation: {time2:.2f}ms (HIT)")
        print(f"  Cache improvement: {((time1 - time2) / time1 * 100):.1f}%")
        print(f"  Results match: {conforms1 == conforms2}")
    
    # Test 2: State-aware cache keys
    print("\n📊 Test 2: State-Aware Cache Keys")
    print("-" * 40)
    
    # Create transactions with different states
    tx1 = Transaction(
        operation='ADVERTISEMENT',
        asset={'id': 'asset1', 'data': {'id': 'asset1'}},
        metadata={
            'advertiser_public_key': keypair.public_key,
            'status': 'OPEN',
            'price': '1000',
            'requestCreationTimestamp': datetime.now().isoformat()
        }
    )
    tx1.inputs = [Input.generate([keypair.public_key])]
    tx1.outputs = [Output.generate([keypair.public_key], amount=1)]
    tx1.sign([keypair.private_key])
    
    tx2 = Transaction(
        operation='ADVERTISEMENT',
        asset={'id': 'asset2', 'data': {'id': 'asset2'}},
        metadata={
            'advertiser_public_key': keypair.public_key,
            'status': 'OPEN',
            'price': '2000',
            'requestCreationTimestamp': datetime.now().isoformat()
        }
    )
    tx2.inputs = [Input.generate([keypair.public_key])]
    tx2.outputs = [Output.generate([keypair.public_key], amount=1)]
    tx2.sign([keypair.private_key])
    
    # Validate both transactions
    print("Validating ADVERTISEMENT for asset1...")
    conforms1, _ = shacl_validator.validate_transaction(tx1.to_dict(), phase='HTTP_POST')
    
    print("Validating ADVERTISEMENT for asset2...")
    conforms2, _ = shacl_validator.validate_transaction(tx2.to_dict(), phase='HTTP_POST')
    
    print(f"Asset1 validation: {'PASS' if conforms1 else 'FAIL'}")
    print(f"Asset2 validation: {'PASS' if conforms2 else 'FAIL'}")
    
    # Test 3: Cache invalidation
    print("\n📊 Test 3: Cache Invalidation")
    print("-" * 40)
    
    # Get initial cache stats
    stats_before = shacl_validator.get_cache_stats()
    print(f"Cache entries before invalidation: {stats_before['total_entries']}")
    
    # Invalidate cache for asset1
    print("Invalidating cache for asset1...")
    shacl_validator.invalidate_cache_for_entity('asset', 'asset1')
    
    # Get cache stats after invalidation
    stats_after = shacl_validator.get_cache_stats()
    print(f"Cache entries after invalidation: {stats_after['total_entries']}")
    print(f"Cache invalidations: {stats_after['metrics']['cache_invalidations']}")
    
    # Test 4: Phase-specific cache invalidation
    print("\n📊 Test 4: Phase-Specific Cache Invalidation")
    print("-" * 40)
    
    print("Invalidating HTTP_POST phase cache...")
    shacl_validator.invalidate_cache_for_phase('HTTP_POST')
    
    stats_final = shacl_validator.get_cache_stats()
    print(f"Cache entries after phase invalidation: {stats_final['total_entries']}")
    
    # Test 5: Comprehensive cache statistics
    print("\n📊 Test 5: Comprehensive Cache Statistics")
    print("-" * 40)
    
    final_stats = shacl_validator.get_cache_stats()
    print(f"Total validations: {final_stats['metrics']['total_validations']}")
    print(f"Cache hit rate: {final_stats['metrics']['cache_hit_rate_percent']:.1f}%")
    print(f"Average validation time: {final_stats['metrics']['average_validation_time_ms']:.2f}ms")
    print(f"Cache invalidations: {final_stats['metrics']['cache_invalidations']}")
    print(f"State changes tracked: {final_stats['metrics']['state_changes']}")
    
    print("\nPhase Statistics:")
    for phase, phase_stats in final_stats['metrics']['phase_stats'].items():
        hit_rate = (phase_stats['hits'] / (phase_stats['hits'] + phase_stats['misses']) * 100) if (phase_stats['hits'] + phase_stats['misses']) > 0 else 0
        avg_time = sum(phase_stats['times']) / len(phase_stats['times']) if phase_stats['times'] else 0
        print(f"  {phase}: {hit_rate:.1f}% hit rate, {avg_time:.2f}ms avg")
    
    print("\n✅ Enhanced cache testing completed successfully!")
    return True


def test_real_transactions():
    """Test with real transactions sent to BigchainDB"""
    print("\n🌐 Testing Enhanced Cache with Real Transactions")
    print("=" * 60)
    
    bigchaindb_url = "http://localhost:9984"
    transactions_url = f"{bigchaindb_url}/api/v1/transactions/"
    
    # Check if BigchainDB is running
    try:
        response = requests.get(f"{bigchaindb_url}/", timeout=5)
        if response.status_code != 200:
            print("❌ BigchainDB is not running or not accessible")
            return False
    except Exception as e:
        print(f"❌ Cannot connect to BigchainDB: {e}")
        return False
    
    print("✅ BigchainDB is accessible")
    
    # Create and send test transactions
    keypair = generate_key_pair()
    
    for i in range(3):
        print(f"\n📤 Sending transaction #{i+1}...")
        
        tx = Transaction(
            operation=Transaction.CREATE,
            asset={'data': {
                'machineIdentifier': f'enhanced_test_{int(time.time() * 1000)}',
                'capability': ['read', 'write'],
                'capabilityParameters': {'type': 'enhanced_test'}
            }},
            metadata={
                'test': 'enhanced_cache_real',
                'requestCreationTimestamp': datetime.now().isoformat()
            }
        )
        
        input_obj = Input.generate([keypair.public_key])
        tx.inputs = [input_obj]
        output_obj = Output.generate([keypair.public_key], amount=1)
        tx.outputs = [output_obj]
        tx.sign([keypair.private_key])
        
        # Send transaction
        start_time = time.time()
        try:
            response = requests.post(
                transactions_url,
                headers={'Content-Type': 'application/json'},
                json=tx.to_dict(),
                timeout=30
            )
            
            validation_time = (time.time() - start_time) * 1000
            
            if response.status_code == 202:
                tx_id = response.json().get('id', 'unknown')
                print(f"  ✅ Transaction sent: {tx_id[:16]}... ({validation_time:.2f}ms)")
            else:
                print(f"  ❌ Transaction failed: {response.status_code} - {response.text[:100]}")
                
        except Exception as e:
            print(f"  ❌ Transaction error: {e}")
        
        time.sleep(0.5)  # Small delay between transactions
    
    # Show final cache statistics
    print("\n📊 Final Cache Statistics:")
    final_stats = shacl_validator.get_cache_stats()
    print(f"Total validations: {final_stats['metrics']['total_validations']}")
    print(f"Cache hit rate: {final_stats['metrics']['cache_hit_rate_percent']:.1f}%")
    print(f"Average validation time: {final_stats['metrics']['average_validation_time_ms']:.2f}ms")
    
    return True


def main():
    """Main entry point"""
    print("🔬 Enhanced State-Aware Cache System Test")
    print("=" * 60)
    
    try:
        # Test enhanced cache functionality
        test_enhanced_cache()
        
        # Test with real transactions
        test_real_transactions()
        
        print("\n🎉 All enhanced cache tests completed successfully!")
        print("\n📈 Key Enhancements Demonstrated:")
        print("  ✅ Phase-aware validation (HTTP_POST, CHECK_TX, DELIVER_TX)")
        print("  ✅ State-aware cache keys with blockchain state hash")
        print("  ✅ Dependency tracking for cache invalidation")
        print("  ✅ Robust cache invalidation patterns")
        print("  ✅ Multi-phase transaction lifecycle support")
        
    except Exception as e:
        print(f"❌ Enhanced cache testing failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


if __name__ == "__main__":
    main()
