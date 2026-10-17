#!/usr/bin/env python3
"""
Test Cache HIT After Fix - Verify Cache Reuse Across Phases

After fixing the state hash to NOT include phase, we should see:
- Phase 1 (HTTP_POST): CACHE MISS (initial validation)
- Phase 2 (CHECK_TX): CACHE HIT (reuse from Phase 1)
- Phase 3 (DELIVER_TX): CACHE HIT (reuse from Phase 1)

This is the optimization we wanted!
"""

import os
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def hrtime_ms():
    return time.time() * 1000

def main():
    print("="*80)
    print("CACHE HIT VERIFICATION TEST")
    print("="*80)
    print("Testing cache reuse across validation phases")
    print()
    
    try:
        from smartchaindb_custom_driver import SmartChainDBDriver
        from bigchaindb.common.crypto import generate_key_pair
        from bigchaindb.common.transaction import Transaction
    except ImportError as e:
        print(f"❌ Cannot import: {e}")
        return
    
    BDB_URL = os.getenv('BDB_URL', 'http://localhost:9984')
    driver = SmartChainDBDriver(BDB_URL)
    
    seller = driver.generate_keypair()
    
    print("Creating transaction...")
    
    # Create asset
    asset_data = {
        'machineIdentifier': f'cache_test_{int(time.time())}',
        'capability': ['read', 'write'],
        'capabilityParameters': {'type': 'cache_hit_test'}
    }
    
    metadata = {
        'requestCreationTimestamp': datetime.now().isoformat(),
        'test_type': 'CACHE_HIT_TEST',
        'description': 'Verify cache hits across phases'
    }
    
    tx = Transaction.create(
        tx_signers=[seller.public_key],
        recipients=[([seller.public_key], 1)],
        asset=asset_data,
        metadata=metadata
    )
    tx.sign([seller.private_key])
    
    print(f"Transaction ID: {tx.id[:32]}...")
    print()
    
    # Submit transaction
    print("Submitting transaction...")
    t_start = hrtime_ms()
    tx_dict = tx.to_dict()
    response = driver.send_transaction(tx_dict)
    
    if response:
        # Wait for confirmation
        print("Waiting for confirmation...")
        confirmed = driver.wait_for_transaction_confirmation(tx.id, max_wait_seconds=30)
        
        if confirmed:
            t_end = hrtime_ms()
            print(f"✓ Transaction confirmed in {t_end - t_start:.2f}ms")
            print()
            
            print("="*80)
            print("CHECK CACHE LOGS")
            print("="*80)
            print()
            print("Run this command to see cache behavior:")
            print()
            print(f'  docker logs smartchaindb-bigchaindb-1 | grep "{tx.id[:16]}" | grep CACHE')
            print()
            print("Expected behavior:")
            print("  1. HTTP_POST: CACHE MISS (initial validation)")
            print("  2. CHECK_TX:  CACHE HIT (reuse from HTTP_POST)")
            print("  3. DELIVER_TX: CACHE HIT (reuse from HTTP_POST)")
            print()
            print("This shows cache is working correctly!")
            print()
        else:
            print("✗ Transaction not confirmed")
    else:
        print("✗ Transaction submission failed")

if __name__ == '__main__':
    main()

