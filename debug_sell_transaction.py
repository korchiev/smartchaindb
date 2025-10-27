#!/usr/bin/env python3
"""
Quick SELL Transaction Test

Test SELL transaction specifically to debug the 500 error.
"""

import sys
import os
sys.path.append('/usr/src/app')

from bigchaindb_driver import BigchainDB
from bigchaindb_driver.crypto import generate_keypair
from bigchaindb_driver.transaction import Transaction
from bigchaindb_driver.models import Input, Output
from datetime import datetime, timedelta
import time

def test_sell_transaction():
    """Test SELL transaction specifically"""
    
    # Initialize BigchainDB connection
    bdb = BigchainDB('http://localhost:9984')
    
    print("🔬 Testing SELL Transaction")
    print("=" * 50)
    
    # Generate keypairs
    seller_keypair = generate_keypair()
    buyer_keypair = generate_keypair()
    
    print(f"Seller: {seller_keypair.public_key[:16]}...")
    print(f"Buyer: {buyer_keypair.public_key[:16]}...")
    
    # Step 1: Create an asset
    print("\n1. Creating asset...")
    asset_tx = Transaction(
        operation='CREATE',
        asset={'data': {
            'machineIdentifier': 'test_asset_sell_debug',
            'capability': ['read', 'write'],
            'capabilityParameters': {'type': 'test'}
        }},
        metadata={
            'test': 'sell_debug',
            'requestCreationTimestamp': datetime.now().isoformat()
        }
    )
    
    input_obj = Input.generate([seller_keypair.public_key])
    asset_tx.inputs = [input_obj]
    output_obj = Output.generate([seller_keypair.public_key], amount=1)
    asset_tx.outputs = [output_obj]
    asset_tx.sign([seller_keypair.private_key])
    
    # Send CREATE transaction
    try:
        response = bdb.transactions.send(asset_tx)
        asset_id = response['id']
        print(f"   ✅ Asset created: {asset_id[:16]}...")
        
        # Wait for commitment
        time.sleep(2)
        
    except Exception as e:
        print(f"   ❌ Asset creation failed: {e}")
        return
    
    # Step 2: Create advertisement
    print("\n2. Creating advertisement...")
    adv_tx = Transaction(
        operation='ADVERTISEMENT',
        asset={'id': asset_id, 'data': {
            'id': asset_id,
            'advertisement_id': f"adv_{int(time.time())}"
        }},
        metadata={
            'advertiser_public_key': seller_keypair.public_key,
            'advertisement_status': 'OPEN',
            'advertisement_timestamp': datetime.now().isoformat(),
            'requestCreationTimestamp': datetime.now().isoformat()
        }
    )
    
    input_obj = Input.generate([seller_keypair.public_key])
    adv_tx.inputs = [input_obj]
    output_obj = Output.generate([seller_keypair.public_key], amount=1)
    adv_tx.outputs = [output_obj]
    adv_tx.sign([seller_keypair.private_key])
    
    try:
        response = bdb.transactions.send(adv_tx)
        adv_id = response['id']
        print(f"   ✅ Advertisement created: {adv_id[:16]}...")
        
        # Wait for commitment
        time.sleep(2)
        
    except Exception as e:
        print(f"   ❌ Advertisement creation failed: {e}")
        return
    
    # Step 3: Create buy offer
    print("\n3. Creating buy offer...")
    buy_tx = Transaction(
        operation='BUY_OFFER',
        asset={'id': asset_id, 'data': {
            'id': asset_id,
            'advertisement_id': adv_id
        }},
        metadata={
            'buyer_public_key': buyer_keypair.public_key,
            'offer_amount': '1000',
            'offer_expiry': (datetime.now() + timedelta(days=7)).isoformat(),
            'escrow_public_key': seller_keypair.public_key,
            'offer_timestamp': datetime.now().isoformat(),
            'requestCreationTimestamp': datetime.now().isoformat()
        }
    )
    
    input_obj = Input.generate([buyer_keypair.public_key])
    buy_tx.inputs = [input_obj]
    output_obj = Output.generate([seller_keypair.public_key], amount=1)
    buy_tx.outputs = [output_obj]
    buy_tx.sign([buyer_keypair.private_key])
    
    try:
        response = bdb.transactions.send(buy_tx)
        buy_id = response['id']
        print(f"   ✅ Buy offer created: {buy_id[:16]}...")
        
        # Wait for commitment
        time.sleep(2)
        
    except Exception as e:
        print(f"   ❌ Buy offer creation failed: {e}")
        return
    
    # Step 4: Create SELL transaction
    print("\n4. Creating SELL transaction...")
    sell_tx = Transaction(
        operation='SELL',
        asset={'id': asset_id, 'data': {
            'id': asset_id,
            'buy_offer_id': buy_id
        }},
        metadata={
            'seller_public_key': seller_keypair.public_key,
            'sale_amount': '1000',
            'sale_timestamp': datetime.now().isoformat(),
            'requestCreationTimestamp': datetime.now().isoformat()
        }
    )
    
    # Use advertiser's output as input (fulfills the ADVERTISEMENT)
    input_obj = Input.generate([seller_keypair.public_key])
    sell_tx.inputs = [input_obj]
    output_obj = Output.generate([buyer_keypair.public_key], amount=1)
    sell_tx.outputs = [output_obj]
    sell_tx.sign([seller_keypair.private_key])
    
    try:
        print(f"   📤 Sending SELL transaction...")
        print(f"   Asset ID: {asset_id[:16]}...")
        print(f"   Buy Offer ID: {buy_id[:16]}...")
        print(f"   Seller: {seller_keypair.public_key[:16]}...")
        print(f"   Buyer: {buyer_keypair.public_key[:16]}...")
        
        response = bdb.transactions.send(sell_tx)
        sell_id = response['id']
        print(f"   ✅ SELL transaction created: {sell_id[:16]}...")
        
    except Exception as e:
        print(f"   ❌ SELL transaction failed: {e}")
        print(f"   Error details: {str(e)}")
        
        # Try to get more details
        try:
            import requests
            response = requests.post(
                'http://localhost:9984/api/v1/transactions/',
                headers={'Content-Type': 'application/json'},
                json=sell_tx.to_dict(),
                timeout=30
            )
            print(f"   HTTP Status: {response.status_code}")
            print(f"   Response: {response.text[:200]}...")
        except Exception as req_e:
            print(f"   Request error: {req_e}")

if __name__ == "__main__":
    test_sell_transaction()
