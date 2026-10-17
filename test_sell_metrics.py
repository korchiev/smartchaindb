#!/usr/bin/env python3
"""
Test SELL Transaction - Capture Server Metrics
"""

import os
import sys
import time
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def main():
    print("="*80)
    print("TESTING SELL TRANSACTION - SERVER METRICS")
    print("="*80)
    
    try:
        from smartchaindb_custom_driver import SmartChainDBDriver
        from bigchaindb.common.transaction import Transaction
        from bigchaindb.common.crypto import generate_key_pair
        from bigchaindb.common.input import Input
        from bigchaindb.common.output import Output
    except ImportError as e:
        print(f"❌ Cannot import: {e}")
        return
    
    BDB_URL = os.getenv('BDB_URL', 'http://localhost:9984')
    driver = SmartChainDBDriver(BDB_URL)
    
    # Generate keypairs
    seller = driver.generate_keypair()
    buyer = driver.generate_keypair()
    
    # 1. CREATE an asset
    print("\n1. Creating asset...")
    asset_data = {
        'machineIdentifier': f'test_sell_asset_{int(time.time())}',
        'capability': ['read', 'write']
    }
    metadata = {'requestCreationTimestamp': datetime.now().isoformat()}
    
    create_tx = Transaction.create(
        tx_signers=[seller.public_key],
        recipients=[([seller.public_key], 1)],
        asset=asset_data,
        metadata=metadata
    )
    create_tx.sign([seller.private_key])
    
    response = driver.send_transaction(create_tx.to_dict())
    if response:
        confirmed = driver.wait_for_transaction_confirmation(create_tx.id, max_wait_seconds=30)
        if confirmed:
            print(f"   ✓ CREATE confirmed")
            asset_id = create_tx.id
        else:
            print(f"   ✗ CREATE failed")
            return
    else:
        print(f"   ✗ CREATE failed")
        return
    
    # 2. ADVERTISEMENT
    print("\n2. Creating ADVERTISEMENT...")
    metadata = {
        'advertiser_public_key': seller.public_key,
        'status': 'OPEN',
        'price': '100',
        'advertisement_timestamp': datetime.now().isoformat(),
        'requestCreationTimestamp': datetime.now().isoformat(),
        'is_new_advertisement': True
    }
    
    # Create ADVERTISEMENT transaction
    advertise_tx = Transaction(
        Transaction.ADVERTISEMENT,
        {'id': asset_id},
        [Input.generate([seller.public_key])],
        [],
        metadata
    )
    advertise_tx.sign([seller.private_key])
    
    response = driver.send_transaction(advertise_tx.to_dict())
    if response:
        confirmed = driver.wait_for_transaction_confirmation(advertise_tx.id, max_wait_seconds=30)
        if confirmed:
            print(f"   ✓ ADVERTISEMENT confirmed")
            ad_id = advertise_tx.id
        else:
            print(f"   ✗ ADVERTISEMENT failed")
            return
    else:
        print(f"   ✗ ADVERTISEMENT failed")
        return
    
    # 3. BUY_OFFER
    print("\n3. Creating BUY_OFFER...")
    metadata = {
        'buyer_public_key': buyer.public_key,
        'offer_amount': '100',
        'offer_currency': 'USD',
        'offer_expiry': (datetime.now() + timedelta(days=7)).isoformat(),
        'escrow_public_key': buyer.public_key,
        'offer_timestamp': datetime.now().isoformat(),
        'requestCreationTimestamp': datetime.now().isoformat()
    }
    
    asset_data = {
        'id': asset_id,
        'data': {
            'id': asset_id,
            'advertisement_id': ad_id
        }
    }
    
    buy_offer_tx = Transaction(
        Transaction.BUY_OFFER,
        asset_data,
        [Input.generate([buyer.public_key])],
        [Output.generate([buyer.public_key], amount=1)],
        metadata
    )
    buy_offer_tx.sign([buyer.private_key])
    
    response = driver.send_transaction(buy_offer_tx.to_dict())
    if response:
        confirmed = driver.wait_for_transaction_confirmation(buy_offer_tx.id, max_wait_seconds=30)
        if confirmed:
            print(f"   ✓ BUY_OFFER confirmed")
            buy_offer_id = buy_offer_tx.id
        else:
            print(f"   ✗ BUY_OFFER failed")
            return
    else:
        print(f"   ✗ BUY_OFFER failed")
        return
    
    # 4. SELL (this is where we get metrics)
    print("\n4. Creating SELL transaction...")
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
            'requestCreationTimestamp': datetime.now().isoformat()
        }
    )
    
    sell_tx_obj = Transaction.from_dict(sell_tx)
    sell_tx_obj.sign([seller.private_key])
    
    print(f"📤 Submitting SELL transaction to server...")
    response = driver.send_transaction(sell_tx_obj.to_dict())
    if response:
        confirmed = driver.wait_for_transaction_confirmation(sell_tx_obj.id, max_wait_seconds=30)
        if confirmed:
            print(f"   ✓ SELL confirmed: {sell_tx_obj.id[:32]}")
            print(f"\n📊 Metrics captured - check logs for:")
            print(f"   - HTTP_POST validation time")
            print(f"   - CHECK_TX validation time")
            print(f"   - DELIVER_TX validation time")
            print(f"   - Cache behavior (hit/miss)")
        else:
            print(f"   ✗ SELL failed")
    else:
        print(f"   ✗ SELL submission failed")

if __name__ == '__main__':
    main()

