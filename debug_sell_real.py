#!/usr/bin/env python3
"""
Test SELL transaction with real transaction IDs from the blockchain
"""

import sys
import os
sys.path.append('/usr/src/app')

from bigchaindb.common.transaction import Transaction, TransactionLink
from bigchaindb.common.crypto import generate_key_pair
from bigchaindb.common.transaction import Input, Output
from datetime import datetime, timedelta
import requests
import json
import time

def test_sell_with_real_ids():
    """Test SELL transaction with real transaction IDs from the blockchain"""
    print("🔍 Testing SELL Transaction with Real Transaction IDs")
    print("=" * 60)
    
    # First, let's get some real transaction IDs from the blockchain
    print("📋 Getting recent transactions from blockchain...")
    
    try:
        # Get recent transactions
        response = requests.get("http://localhost:9984/api/v1/transactions", timeout=10)
        if response.status_code == 200:
            transactions = response.json()
            print(f"✅ Found {len(transactions)} transactions")
            
            # Find CREATE, ADVERTISEMENT, and BUY_OFFER transactions
            create_txs = [tx for tx in transactions if tx.get('operation') == 'CREATE']
            adv_txs = [tx for tx in transactions if tx.get('operation') == 'ADVERTISEMENT']
            buy_offer_txs = [tx for tx in transactions if tx.get('operation') == 'BUY_OFFER']
            
            print(f"   CREATE transactions: {len(create_txs)}")
            print(f"   ADVERTISEMENT transactions: {len(adv_txs)}")
            print(f"   BUY_OFFER transactions: {len(buy_offer_txs)}")
            
            if not create_txs or not adv_txs or not buy_offer_txs:
                print("❌ Not enough transaction types found. Need CREATE, ADVERTISEMENT, and BUY_OFFER.")
                return
            
            # Use the most recent transactions
            create_tx = create_txs[-1]
            adv_tx = adv_txs[-1]
            buy_offer_tx = buy_offer_txs[-1]
            
            print(f"\n📋 Using transactions:")
            print(f"   CREATE: {create_tx['id'][:16]}...")
            print(f"   ADVERTISEMENT: {adv_tx['id'][:16]}...")
            print(f"   BUY_OFFER: {buy_offer_tx['id'][:16]}...")
            
            # Extract asset IDs
            asset_id = create_tx['asset']['data']['id'] if 'data' in create_tx['asset'] else create_tx['asset']['id']
            adv_id = adv_tx['id']
            buy_offer_id = buy_offer_tx['id']
            
            print(f"\n🔍 Extracted IDs:")
            print(f"   Asset ID: {asset_id[:16]}...")
            print(f"   Advertisement ID: {adv_id[:16]}...")
            print(f"   Buy Offer ID: {buy_offer_id[:16]}...")
            
            # Now create a SELL transaction
            print(f"\n🔧 Creating SELL transaction...")
            
            seller_keypair = generate_key_pair()
            buyer_keypair = generate_key_pair()
            
            metadata = {
                'seller_public_key': seller_keypair.public_key,
                'buyer_public_key': buyer_keypair.public_key,
                'sale_amount': 1000,
                'sale_currency': 'USD',
                'sale_timestamp': datetime.now().isoformat(),
                'requestCreationTimestamp': datetime.now().isoformat(),
                'test_type': 'SELL',
                'test_id': 1
            }
            
            # Create proper input that references the seller's asset (from CREATE transaction)
            fulfills_link = TransactionLink.from_dict({
                'output_index': 0,
                'transaction_id': asset_id,
            })
            
            sell_input = Input.generate([seller_keypair.public_key])
            sell_input.fulfills = fulfills_link
            
            # Create transaction with correct asset structure
            asset = {
                "id": asset_id,
                "data": {
                    "buy_offer_id": buy_offer_id
                }
            }
            
            # Use validate_sell to get inputs and outputs
            (inputs, outputs) = Transaction.validate_sell([sell_input], asset_id, buy_offer_id, metadata)
            
            # Convert sale_amount to string for schema compliance
            metadata['sale_amount'] = str(metadata['sale_amount'])
            
            # Create the transaction
            tx = Transaction(
                Transaction.SELL,
                asset,
                inputs,
                outputs,
                metadata
            )
            
            # Sign the transaction
            tx.sign([seller_keypair.private_key])
            
            print(f"✅ SELL transaction created successfully!")
            print(f"   Transaction ID: {tx.id[:16]}...")
            
            # Test sending to server
            print(f"\n📤 Testing transaction sending...")
            url = "http://localhost:9984/api/v1/transactions/"
            headers = {"Content-Type": "application/json"}
            
            response = requests.post(url, data=json.dumps(tx.to_dict()), headers=headers)
            print(f"   Status Code: {response.status_code}")
            print(f"   Response: {response.text[:200]}...")
            
            if response.status_code == 202:
                print("✅ Transaction sent successfully!")
            else:
                print("❌ Transaction failed to send")
                
        else:
            print(f"❌ Failed to get transactions: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_sell_with_real_ids()

