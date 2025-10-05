#!/usr/bin/env python3
"""
Test script to reproduce the hexadecimal decoding issue with BUY_OFFER transactions
"""

import sys
import os
from datetime import datetime, timedelta

# Add the bigchaindb directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'bigchaindb', 'common'))

def test_buy_offer_id_issue():
    """Test the BUY_OFFER transaction ID issue"""
    print("Testing BUY_OFFER transaction ID issue...")
    
    try:
        from transaction import Transaction
        from crypto import generate_key_pair
        
        # Generate keypairs
        buyer_keypair = generate_key_pair()
        escrow_keypair = generate_key_pair()
        
        print(f"SUCCESS: Generated keypairs successfully")
        
        # Create input
        asset_input = Transaction.Input.generate([buyer_keypair.public_key])
        
        # Create metadata
        metadata = {
            'buyer_public_key': buyer_keypair.public_key,
            'offer_amount': 1000.0,
            'offer_currency': 'USD',
            'offer_timestamp': datetime.utcnow().isoformat() + 'Z',
            'offer_expiry': (datetime.utcnow() + timedelta(days=7)).isoformat() + 'Z',
            'escrow_public_key': escrow_keypair.public_key,
            'requestCreationTimestamp': datetime.utcnow().isoformat()
        }
        
        # Create BUY_OFFER transaction
        buy_offer_tx = Transaction.buy_offer(
            inputs=[asset_input],
            asset_id='test_asset_123',
            advertisement_id='test_ad_456',
            metadata=metadata
        )
        
        print(f"SUCCESS: BUY_OFFER transaction created successfully!")
        print(f"   Transaction ID: {buy_offer_tx.id}")
        print(f"   Transaction ID type: {type(buy_offer_tx.id)}")
        print(f"   Transaction ID length: {len(buy_offer_tx.id)}")
        
        # Test the to_dict method
        tx_dict = buy_offer_tx.to_dict()
        print(f"   Dict ID: {tx_dict['id']}")
        print(f"   Dict ID type: {type(tx_dict['id'])}")
        print(f"   Dict ID length: {len(tx_dict['id'])}")
        
        # Test the memoize issue
        from memoize import HDict
        try:
            hdict = HDict(tx_dict)
            print(f"SUCCESS: HDict created successfully")
            print(f"   HDict hash: {hash(hdict)}")
        except Exception as e:
            print(f"ERROR: HDict creation failed: {e}")
            
        # Test the from_dict method
        try:
            tx_from_dict = Transaction.from_dict(tx_dict)
            print(f"SUCCESS: Transaction.from_dict() succeeded")
            print(f"   Recreated ID: {tx_from_dict.id}")
        except Exception as e:
            print(f"ERROR: Transaction.from_dict() failed: {e}")
            
    except Exception as e:
        print(f"ERROR: Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_buy_offer_id_issue()
