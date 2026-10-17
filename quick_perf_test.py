#!/usr/bin/env python3
"""
Quick Performance Test - N=5 assets for fast results
"""

import os
import sys
import time
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from smartchaindb_custom_driver import SmartChainDBDriver
from bigchaindb.common.crypto import generate_key_pair

def hrtime_ms():
    """High-resolution time in milliseconds"""
    return time.time() * 1000

def main():
    print("="*80)
    print("QUICK PERFORMANCE TEST (N=5)")
    print("="*80)
    
    N = 5  # Number of assets
    K = 2  # Number of BUY_OFFER per asset
    M = 4  # Number of SELL transactions
    
    BDB_URL = os.getenv('BDB_URL', 'http://localhost:9984')
    driver = SmartChainDBDriver(BDB_URL)
    
    results = {
        'CREATE': [],
        'ADVERTISEMENT': [],
        'BUY_OFFER': [],
        'SELL': []
    }
    
    total_start = hrtime_ms()
    
    try:
        for i in range(N):
            # Generate keypairs
            seller = driver.generate_keypair()
            buyer = driver.generate_keypair()
            
            # 1. CREATE
            print(f"\n[{i+1}/{N}] Creating asset {i+1}...")
            create_result = driver.create_asset(
                signers=[seller],
                metadata={'test_type': 'CREATE', 'test_id': i},
                data={'machineIdentifier': f'test_asset_{i}'}
            )
            if create_result['status'] == 'success':
                results['CREATE'].append(create_result['latency_ms'])
                asset_id = create_result['tx_id']
            else:
                print(f"❌ CREATE failed: {create_result.get('error')}")
                continue
            
            # 2. ADVERTISEMENT
            print(f"  Creating ADVERTISEMENT...")
            adv_result = driver.create_advertisement(
                asset_id=asset_id,
                signers=[seller],
                metadata={
                    'advertiser_public_key': seller.public_key,
                    'status': 'OPEN',
                    'price': '100',
                    'advertisement_timestamp': datetime.now().isoformat(),
                    'requestCreationTimestamp': datetime.now().isoformat(),
                    'test_type': 'ADVERTISEMENT',
                    'test_id': i
                }
            )
            if adv_result['status'] == 'success':
                results['ADVERTISEMENT'].append(adv_result['latency_ms'])
                ad_id = adv_result['tx_id']
            else:
                print(f"❌ ADVERTISEMENT failed")
                continue
            
            # 3. BUY_OFFER (K times)
            for k in range(K):
                print(f"  Creating BUY_OFFER {k+1}/{K}...")
                buy_result = driver.create_buy_offer(
                    asset_id=asset_id,
                    advertisement_id=ad_id,
                    signers=[buyer],
                    metadata={
                        'buyer_public_key': buyer.public_key,
                        'offer_amount': '100',
                        'offer_currency': 'USD',
                        'offer_expiry': (datetime.now() + timedelta(days=7)).isoformat(),
                        'escrow_public_key': buyer.public_key,
                        'offer_timestamp': datetime.now().isoformat(),
                        'requestCreationTimestamp': datetime.now().isoformat(),
                        'test_type': 'BUY_OFFER',
                        'test_id': f'{i}_{k}'
                    }
                )
                if buy_result['status'] == 'success':
                    results['BUY_OFFER'].append(buy_result['latency_ms'])
                    buy_offer_id = buy_result['tx_id']
                else:
                    print(f"❌ BUY_OFFER {k+1} failed")
                    continue
            
            # 4. SELL (if we haven't reached M yet)
            if i < M:
                print(f"  Creating SELL...")
                sell_result = driver.create_sell(
                    asset_id=asset_id,
                    buy_offer_id=buy_offer_id,
                    seller=seller,
                    buyer=buyer,
                    metadata={
                        'seller_public_key': seller.public_key,
                        'buyer_public_key': buyer.public_key,
                        'sale_amount': 100,
                        'sale_currency': 'USD',
                        'sale_timestamp': datetime.now().isoformat(),
                        'requestCreationTimestamp': datetime.now().isoformat(),
                        'test_type': 'SELL',
                        'test_id': i
                    }
                )
                if sell_result['status'] == 'success':
                    results['SELL'].append(sell_result['latency_ms'])
                else:
                    print(f"❌ SELL failed: {sell_result.get('error')}")
    
    except KeyboardInterrupt:
        print("\n⚠️ Test interrupted by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    total_time = hrtime_ms() - total_start
    
    # Print results
    print("\n" + "="*80)
    print("RESULTS SUMMARY")
    print("="*80)
    
    for tx_type in ['CREATE', 'ADVERTISEMENT', 'BUY_OFFER', 'SELL']:
        if results[tx_type]:
            avg = sum(results[tx_type]) / len(results[tx_type])
            print(f"{tx_type:20} Count: {len(results[tx_type]):3}  Avg: {avg:7.2f}ms")
        else:
            print(f"{tx_type:20} Count: {len(results[tx_type]):3}  Avg: N/A")
    
    print(f"\nTotal time: {total_time/1000:.2f}s")
    print(f"Total transactions: {sum(len(v) for v in results.values())}")
    
    # Save to file
    output_file = f"quick_perf_results_{int(time.time())}.txt"
    with open(output_file, 'w') as f:
        f.write(f"Quick Performance Test Results\n")
        f.write(f"Time: {datetime.now().isoformat()}\n")
        f.write(f"Parameters: N={N}, K={K}, M={M}\n\n")
        for tx_type, latencies in results.items():
            f.write(f"{tx_type}: {latencies}\n")
    
    print(f"\nResults saved to: {output_file}")

if __name__ == '__main__':
    main()

