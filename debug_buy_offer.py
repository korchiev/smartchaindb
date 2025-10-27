#!/usr/bin/env python3
"""
Debug script to test BUY_OFFER transaction creation
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

def test_buy_offer_creation():
    """Test BUY_OFFER transaction creation step by step"""
    print("🔍 Testing BUY_OFFER Transaction Creation")
    print("=" * 50)
    
    # Generate keypairs
    buyer_keypair = generate_key_pair()
    escrow_keypair = generate_key_pair()
    
    print(f"✅ Generated keypairs")
    print(f"   Buyer: {buyer_keypair.public_key[:20]}...")
    print(f"   Escrow: {escrow_keypair.public_key[:20]}...")
    
    # Test data - use proper 64-character hex IDs
    asset_id = "a" * 64  # 64-character hex string
    advertisement_id = "b" * 64  # 64-character hex string
    
    metadata = {
        'buyer_public_key': buyer_keypair.public_key,
        'offer_amount': 1000,  # Convert to int for validation
        'offer_currency': 'USD',
        'offer_timestamp': datetime.now().isoformat(),
        'offer_expiry': (datetime.now() + timedelta(days=7)).isoformat(),
        'escrow_public_key': escrow_keypair.public_key,
        'requestCreationTimestamp': datetime.now().isoformat(),
        'test_type': 'BUY_OFFER',
        'test_id': 1
    }
    
    print(f"✅ Created metadata with {len(metadata)} fields")
    
    try:
        # Generate input for the buyer's payment asset
        buy_offer_input = Input.generate([buyer_keypair.public_key])
        print(f"✅ Generated input: {buy_offer_input}")
        
        # Create transaction with correct asset structure for schema compliance
        print("🔧 Creating transaction with correct asset structure...")
        
        # Create the asset structure that matches the schema
        asset = {
            "id": asset_id,
            "data": {
                "advertisement_id": advertisement_id
            }
        }
        
        # Use validate_buy_offer to get inputs and outputs
        (inputs, outputs) = Transaction.validate_buy_offer([buy_offer_input], asset_id, advertisement_id, metadata)
        
        # Create the transaction manually with correct structure
        tx = Transaction(
            Transaction.BUY_OFFER,
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
        tx.sign([buyer_keypair.private_key])
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
        print(f"❌ Error creating BUY_OFFER transaction: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_buy_offer_creation()
