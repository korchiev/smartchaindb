#!/usr/bin/env python3
"""
Quick test for BUY_OFFER transaction type

This is a simple test to quickly verify BUY_OFFER is working.
Run this first to check basic functionality.
"""

import sys
import os
from datetime import datetime, timedelta

# Add the parent directory to the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bigchaindb.common.transaction import Transaction
from bigchaindb.common.crypto import generate_keypair

def quick_test():
    """Quick test of BUY_OFFER functionality"""
    print("🚀 Quick BUY_OFFER Test\n")
    
    try:
        # Generate keypairs
        buyer_keypair = generate_keypair()
        escrow_keypair = generate_keypair()
        
        print("✅ Keypairs generated")
        
        # Create simple input
        asset_input = Transaction.Input.generate([buyer_keypair.public_key])
        
        # Create metadata
        metadata = {
            'buyer_public_key': buyer_keypair.public_key,
            'offer_amount': 100.0,
            'offer_currency': 'USD',
            'offer_timestamp': datetime.utcnow().isoformat() + 'Z',
            'offer_expiry': (datetime.utcnow() + timedelta(days=1)).isoformat() + 'Z',
            'escrow_public_key': escrow_keypair.public_key
        }
        
        print("✅ Metadata created")
        
        # Create BUY_OFFER transaction
        buy_offer_tx = Transaction.buy_offer(
            inputs=[asset_input],
            asset_id='test_asset',
            advertisement_id='test_ad',
            metadata=metadata
        )
        
        print("✅ BUY_OFFER transaction created!")
        print(f"   ID: {buy_offer_tx.id}")
        print(f"   Operation: {buy_offer_tx.operation}")
        print(f"   Outputs: {len(buy_offer_tx.outputs)}")
        
        if len(buy_offer_tx.outputs) == 1:
            output = buy_offer_tx.outputs[0]
            print(f"   Output amount: {output.amount}")
            print(f"   Output public keys: {len(output.public_keys)}")
            print("✅ Transaction structure looks correct!")
        else:
            print(f"❌ Expected 1 output, got {len(buy_offer_tx.outputs)}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    success = quick_test()
    if success:
        print("\n🎉 BUY_OFFER is working!")
    else:
        print("\n💥 BUY_OFFER has issues!")
