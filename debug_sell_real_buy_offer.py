#!/usr/bin/env python3
"""
Debug script to test SELL transaction creation with real transaction IDs
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

def test_sell_with_real_buy_offer():
    """Test SELL transaction creation with real buy offer ID"""
    print("🔍 Testing SELL Transaction with Real Buy Offer ID")
    print("=" * 60)
    
    # Use the real buy offer ID from the test
    asset_id = "8d604af489fdd3e488558eab812f9757ef5b5b27952153a405191e5f2637be15"
    buy_offer_id = "08c332b134a20f90a13c796f4ba5c4c5936d2aeec69a4d8af6931bc5cf2fcecb"
    
    print(f"📋 Using real transaction IDs:")
    print(f"   Asset ID: {asset_id[:16]}...")
    print(f"   Buy Offer ID: {buy_offer_id[:16]}...")
    
    # Generate keypairs
    seller_keypair = generate_key_pair()
    buyer_keypair = generate_key_pair()
    
    print(f"✅ Generated keypairs")
    print(f"   Seller: {seller_keypair.public_key[:20]}...")
    print(f"   Buyer: {buyer_keypair.public_key[:20]}...")
    
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
    
    print(f"✅ Created metadata with {len(metadata)} fields")
    
    try:
        # Create proper input that references the seller's asset (from CREATE transaction)
        fulfills_link = TransactionLink.from_dict({
            'output_index': 0,
            'transaction_id': asset_id,
        })
        
        sell_input = Input.generate([seller_keypair.public_key])
        sell_input.fulfills = fulfills_link
        print(f"✅ Generated input with fulfills link: {sell_input.fulfills}")
        
        # Create transaction with correct asset structure for schema compliance
        asset = {
            "id": asset_id,
            "data": {
                "buy_offer_id": buy_offer_id
            }
        }
        
        print("🔧 Creating transaction with correct asset structure...")
        
        # Use validate_sell to get inputs and outputs
        (inputs, outputs) = Transaction.validate_sell([sell_input], asset_id, buy_offer_id, metadata)
        print(f"✅ Validation successful - {len(inputs)} inputs, {len(outputs)} outputs")
        
        # Convert sale_amount to string for schema compliance
        metadata['sale_amount'] = str(metadata['sale_amount'])
        
        # Create the transaction manually with correct structure
        tx = Transaction(
            Transaction.SELL,
            asset,
            inputs,
            outputs,
            metadata
        )
        
        print(f"✅ Transaction created successfully!")
        print(f"   Operation: {tx.operation}")
        print(f"   Asset: {tx.asset}")
        print(f"   Inputs: {len(tx.inputs)}")
        print(f"   Outputs: {len(tx.outputs)}")
        print(f"   Metadata keys: {list(tx.metadata.keys())}")
        
        # Sign the transaction
        print("🔐 Signing transaction...")
        tx.sign([seller_keypair.private_key])
        print(f"✅ Transaction signed successfully!")
        print(f"   Transaction ID: {tx.id}")
        
        # Convert to dict to see the full structure
        tx_dict = tx.to_dict()
        print(f"\n📋 Transaction Dictionary:")
        print(f"   Operation: {tx_dict.get('operation')}")
        print(f"   Asset: {tx_dict.get('asset')}")
        print(f"   Metadata: {list(tx_dict.get('metadata', {}).keys())}")
        
        # Test sending to server
        print(f"\n📤 Testing transaction sending...")
        url = "http://localhost:9984/api/v1/transactions/"
        headers = {"Content-Type": "application/json"}
        
        response = requests.post(url, data=json.dumps(tx_dict), headers=headers)
        print(f"   Status Code: {response.status_code}")
        print(f"   Response: {response.text[:200]}...")
        
        if response.status_code == 202:
            print("✅ Transaction sent successfully!")
        else:
            print("❌ Transaction failed to send")
            
    except Exception as e:
        print(f"❌ Error creating SELL transaction: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_sell_with_real_buy_offer()

