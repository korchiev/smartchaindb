#!/usr/bin/env python3
"""
Sequential Performance Test for BigchainDB SHACL
Similar to Hardhat's perf.sequential.test.js but for BigchainDB

Usage:
    N=10 K=5 M=8 RETURNS=0.1 python test_sequential_perf.py
"""

import sys
import os
import time
import csv
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from smartchaindb_custom_driver import SmartChainDBDriver
from bigchaindb.common.crypto import generate_key_pair
from bigchaindb.common.transaction import Transaction, Input, Output

def hrtime_ms():
    """High-resolution time in milliseconds"""
    return time.time() * 1000

def main():
    # Get configuration from environment
    N = int(os.getenv('N', 50))  # number of assets
    K = int(os.getenv('K', 2))   # offers per ad
    M = int(os.getenv('M', int(N * 0.8)))  # sales
    RETURNS_P = float(os.getenv('RETURNS', 0.0))  # return probability (0-1)
    BDB_URL = os.getenv('BDB_URL', 'http://localhost:9984')
    
    print(f"Starting BigchainDB SHACL Sequential Performance Test")
    print(f"Parameters: N={N}, K={K}, M={M}, RETURNS_P={RETURNS_P}")
    print(f"Expected transactions: {N} CREATE + {N} ADVERTISEMENT + {N*K} BUY_OFFER + {M} SELL")
    if RETURNS_P > 0:
        print(f"Returns: ~{int(M * RETURNS_P)} REQUEST_RETURN + ~{int(M * RETURNS_P)} ACCEPT_RETURN")
    
    # Initialize driver
    driver = SmartChainDBDriver(BDB_URL)
    
    # Generate keypairs
    seller = driver.generate_keypair()
    buyer = driver.generate_keypair()
    
    csv_data = []
    t_start = hrtime_ms()
    
    def send_and_measure(tx_type, tx_dict, private_key):
        """Send transaction and measure timing"""
        t_send_0 = hrtime_ms()
        
        # Fulfill (sign) the transaction
        signed_tx = driver.fulfill_transaction(tx_dict, private_key)
        
        t_send_1 = hrtime_ms()
        
        # Send to BigchainDB
        response = driver.send_transaction(signed_tx)
        
        if not response:
            print(f"❌ Failed to send {tx_type}")
            return None
            
        tx_id = response.get('id', tx_dict.get('id', ''))
        
        t_send_2 = hrtime_ms()
        
        # Wait for confirmation
        driver.wait_for_transaction_confirmation(tx_id, max_wait_seconds=60)
        
        t_mine_1 = hrtime_ms()
        
        submit_ms = t_send_1 - t_send_0
        mine_ms = t_mine_1 - t_send_2
        total_ms = t_mine_1 - t_send_0
        
        csv_data.append([tx_type, tx_id, f"{total_ms:.3f}", f"{submit_ms:.3f}", f"{mine_ms:.3f}"])
        print(f"✓ {tx_type}: {total_ms:.2f}ms")
        
        return response
    
    # Workload: N assets, each goes through full lifecycle
    assets = []
    advertisements = []
    
    for i in range(N):
        # CREATE asset
        asset_data = {
            'machineIdentifier': f'asset_{i}_{int(time.time() * 1000)}',
            'capability': ['read', 'write'],
            'capabilityParameters': {'type': 'performance_test'}
        }
        create_tx = driver.prepare_create_transaction(
            seller.public_key,
            asset_data,
            metadata={
                'test_id': i,
                'test_type': 'CREATE',
                'requestCreationTimestamp': datetime.now().isoformat()
            }
        )
        create_resp = send_and_measure('CREATE', create_tx, seller.private_key)
        asset_id = create_resp.get('id', f'asset_id_{i}') if create_resp else f'asset_id_{i}'
        assets.append(asset_id)
        
        # ADVERTISE
        ad_metadata = {
            'advertiser_public_key': seller.public_key,
            'status': 'OPEN',
            'price': '100',
            'advertisement_timestamp': datetime.now().isoformat(),
            'requestCreationTimestamp': datetime.now().isoformat(),
            'test_type': 'ADVERTISEMENT',
            'test_id': i
        }
        ad_tx = driver.prepare_advertisement_transaction(
            seller.public_key,
            asset_id,
            metadata=ad_metadata
        )
        ad_resp = send_and_measure('ADVERTISEMENT', ad_tx, seller.private_key)
        ad_id = ad_resp.get('id', f'ad_id_{i}') if ad_resp else f'ad_id_{i}'
        advertisements.append({'id': ad_id, 'asset_id': asset_id})
        
        # BUY_OFFER (K offers per advertisement)
        buy_offers = []
        for j in range(K):
            # Use driver's prepare_buy_offer_transaction method
            buy_offer_tx = driver.prepare_buy_offer_transaction(
                buyer.public_key,
                asset_id,
                ad_id,
                metadata={
                    'buyer_public_key': buyer.public_key,
                    'offer_amount': '100',
                    'offer_currency': 'USD',
                    'offer_expiry': (datetime.now() + timedelta(days=7)).isoformat(),
                    'escrow_public_key': buyer.public_key,
                    'offer_timestamp': datetime.now().isoformat(),
                    'test_type': 'BUY_OFFER',
                    'test_id': f'{i}_{j}'
                }
            )
            
            buy_offer_resp = send_and_measure('BUY_OFFER', buy_offer_tx, buyer.private_key)
            buy_offers.append(buy_offer_resp)
        
        # SELL (only for first M advertisements)
        if i < M and len(buy_offers) > 0:
            # Find the last valid buy_offer with an ID
            buy_offer_id = None
            for buy_offer in reversed(buy_offers):
                if buy_offer and isinstance(buy_offer, dict):
                    buy_offer_id = buy_offer.get('id')
                    if buy_offer_id and buy_offer_id != '':
                        break
            
            if not buy_offer_id or buy_offer_id == '':
                print(f"⚠️ Skipping SELL for asset {i}: No valid buy_offer_id found")
                continue
                
            sell_tx = driver.prepare_sell_transaction(
                seller.public_key,
                asset_id,
                buy_offer_id,
                metadata={
                    'seller_public_key': seller.public_key,
                    'buyer_public_key': buyer.public_key,
                    'sale_amount': 100,
                    'sale_currency': 'USD',
                    'sale_timestamp': datetime.now().isoformat(),
                    'test_type': 'SELL',
                    'test_id': i
                }
            )
            sell_resp = send_and_measure('SELL', sell_tx, seller.private_key)
            sale_id = sell_resp.get('id', '') if sell_resp else ''
            
            # Optional: REQUEST_RETURN + ACCEPT_RETURN
            if RETURNS_P > 0 and sell_resp and (hash(f'{i}{j}') % 100) / 100.0 < RETURNS_P:
                sale_id = sell_resp.get('id', '') if sell_resp else ''
                if sale_id:
                    # REQUEST_RETURN
                    req_return_tx = driver.prepare_request_return_transaction(
                        buyer.public_key,
                        asset_id,
                        sale_id,  # sell_transaction_id parameter
                        metadata={'reason': 'Performance test return'}
                    )
                    req_return_resp = send_and_measure('REQUEST_RETURN', req_return_tx, buyer.private_key)
                    
                    if req_return_resp:
                        req_return_id = req_return_resp.get('id', '')
                        # ACCEPT_RETURN
                        accept_return_tx = driver.prepare_seller_accept_return_transaction(
                            seller.public_key,
                            asset_id,
                            req_return_id if req_return_id else sale_id,  # request_return_id or fallback
                            metadata={'refund_amount': 100.0}
                        )
                        accept_return_resp = send_and_measure('SELLER_ACCEPT_RETURN', accept_return_tx, seller.private_key)
    
    # Output CSV
    t_end = hrtime_ms()
    total_ms = t_end - t_start
    total_tx = len(csv_data)
    tps = (total_tx / total_ms) * 1000
    
    print(f"\n{'='*70}")
    print(f"RESULTS SUMMARY")
    print(f"{'='*70}")
    print(f"Total transactions: {total_tx}")
    print(f"Total duration: {total_ms:.2f}ms ({total_ms/1000:.2f}s)")
    print(f"Throughput: {tps:.2f} TPS")
    print(f"{'='*70}\n")
    
    # Output CSV format
    print("TYPE,ID,LAT_MS,SUBMIT_MS,MINE_MS")
    for row in csv_data:
        print(','.join(row))
    print(f"SUMMARY,{total_tx},{total_ms:.3f},{tps:.3f}")

if __name__ == '__main__':
    main()

