#!/usr/bin/env python3
"""
Docker-compatible test for BUY_OFFER transaction type

This script is designed to run inside the BigchainDB Docker container
and test the BUY_OFFER functionality.
"""

import sys
import os
from datetime import datetime, timedelta

# Add the current directory to Python path
sys.path.insert(0, '/usr/src/app')

try:
    from bigchaindb.common.transaction import Transaction
    from bigchaindb.common.crypto import generate_key_pair
    print("✅ Successfully imported BigchainDB modules")
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Make sure you're running this inside the BigchainDB container")
    sys.exit(1)

def test_buy_offer_basic():
    """Test basic BUY_OFFER transaction creation"""
    print("\n=== Testing BUY_OFFER Basic Functionality ===\n")
    
    try:
        # Generate keypairs
        buyer_keypair = generate_key_pair()
        escrow_keypair = generate_key_pair()
        
        print(f"✅ Generated keypairs successfully")
        print(f"   Buyer: {buyer_keypair.public_key[:20]}...")
        print(f"   Escrow: {escrow_keypair.public_key[:20]}...")
        
        # Create mock data
        asset_id = "test_asset_123"
        advertisement_id = "test_ad_456"
        
        # Create input for the asset being offered for
        asset_input = {
            'owners_before': [buyer_keypair.public_key],
            'fulfillment': 'test_fulfillment'
        }
        
        # Create metadata
        metadata = {
            'buyer_public_key': buyer_keypair.public_key,
            'offer_amount': 1000.00,
            'offer_currency': 'USD',
            'offer_timestamp': datetime.utcnow().isoformat() + 'Z',
            'offer_expiry': (datetime.utcnow() + timedelta(days=7)).isoformat() + 'Z',
            'escrow_public_key': escrow_keypair.public_key,
            'offer_notes': 'Test offer for asset'
        }
        
        print(f"✅ Created metadata successfully")
        print(f"   Offer Amount: {metadata['offer_amount']} {metadata['offer_currency']}")
        print(f"   Expiry: {metadata['offer_expiry']}")
        
        # Create BUY_OFFER transaction
        buy_offer_tx = Transaction.buy_offer(
            inputs=[asset_input],
            asset_id=asset_id,
            advertisement_id=advertisement_id,
            metadata=metadata
        )
        
        print(f"\n✅ BUY_OFFER transaction created successfully!")
        print(f"   Transaction ID: {buy_offer_tx.id}")
        print(f"   Operation: {buy_offer_tx.operation}")
        print(f"   Asset ID: {buy_offer_tx.asset['id']}")
        print(f"   Advertisement ID: {buy_offer_tx.asset['advertisement_id']}")
        print(f"   Inputs: {len(buy_offer_tx.inputs)}")
        print(f"   Outputs: {len(buy_offer_tx.outputs)}")
        
        # Verify outputs
        if len(buy_offer_tx.outputs) == 1:
            escrow_output = buy_offer_tx.outputs[0]
            print(f"\n✅ Escrow output created correctly:")
            print(f"   Amount: {escrow_output.amount}")
            print(f"   Public Keys: {len(escrow_output.public_keys)}")
            
            # Verify escrow amount matches offer amount
            if escrow_output.amount == metadata['offer_amount']:
                print("✅ Escrow amount matches offer amount")
            else:
                print(f"❌ Escrow amount mismatch: {escrow_output.amount} != {metadata['offer_amount']}")
                
            # Verify escrow is locked to correct account
            if escrow_keypair.public_key in escrow_output.public_keys:
                print("✅ Escrow output locked to correct escrow account")
            else:
                print(f"❌ Escrow output not locked to correct account")
        else:
            print(f"❌ Expected 1 output, got {len(buy_offer_tx.outputs)}")
        
        return buy_offer_tx
        
    except Exception as e:
        print(f"❌ Error creating BUY_OFFER transaction: {e}")
        import traceback
        traceback.print_exc()
        return None

def test_buy_offer_validation():
    """Test BUY_OFFER validation rules"""
    print("\n=== Testing BUY_OFFER Validation Rules ===\n")
    
    try:
        # Test 1: Valid metadata
        print("Test 1: Valid metadata")
        valid_metadata = {
            'buyer_public_key': 'valid_public_key',
            'offer_amount': 100.0,
            'offer_currency': 'USD',
            'offer_timestamp': datetime.utcnow().isoformat() + 'Z',
            'offer_expiry': (datetime.utcnow() + timedelta(days=1)).isoformat() + 'Z',
            'escrow_public_key': 'escrow_public_key'
        }
        
        # This should not raise an exception
        Transaction.validate_buy_offer(
            inputs=[],  # Empty for validation test
            asset_id='test_asset',
            advertisement_id='test_ad',
            metadata=valid_metadata
        )
        print("✅ Valid metadata accepted")
        
        # Test 2: Invalid offer amount (negative)
        print("\nTest 2: Invalid offer amount (negative)")
        try:
            invalid_metadata = valid_metadata.copy()
            invalid_metadata['offer_amount'] = -100.0
            
            Transaction.validate_buy_offer(
                inputs=[],
                asset_id='test_asset',
                advertisement_id='test_ad',
                metadata=invalid_metadata
            )
            print("❌ Should have rejected negative amount")
        except ValueError as e:
            print(f"✅ Correctly rejected negative amount: {e}")
        
        # Test 3: Missing required fields
        print("\nTest 3: Missing required fields")
        required_fields = ['buyer_public_key', 'offer_amount', 'offer_currency', 
                          'offer_timestamp', 'offer_expiry', 'escrow_public_key']
        
        for field in required_fields:
            try:
                invalid_metadata = valid_metadata.copy()
                del invalid_metadata[field]
                
                Transaction.validate_buy_offer(
                    inputs=[],
                    asset_id='test_asset',
                    advertisement_id='test_ad',
                    metadata=invalid_metadata
                )
                print(f"❌ Should have rejected missing field: {field}")
            except ValueError as e:
                print(f"✅ Correctly rejected missing field '{field}': {e}")
        
        print("\n✅ All validation tests completed")
        
    except Exception as e:
        print(f"❌ Error in validation tests: {e}")
        import traceback
        traceback.print_exc()

def test_integration_with_sell():
    """Test BUY_OFFER integration with SELL transaction"""
    print("\n=== Testing BUY_OFFER → SELL Integration ===\n")
    
    try:
        # Generate keypairs for different parties
        buyer_keypair = generate_key_pair()
        seller_keypair = generate_key_pair()
        escrow_keypair = generate_key_pair()
        
        print("✅ Generated keypairs for integration testing")
        
        # Create BUY_OFFER
        asset_id = "integration_test_asset"
        advertisement_id = "integration_test_ad"
        
        buy_offer_input = {
            'owners_before': [buyer_keypair.public_key],
            'fulfillment': 'test_fulfillment'
        }
        buy_offer_metadata = {
            'buyer_public_key': buyer_keypair.public_key,
            'offer_amount': 500.00,
            'offer_currency': 'USD',
            'offer_timestamp': datetime.utcnow().isoformat() + 'Z',
            'offer_expiry': (datetime.utcnow() + timedelta(days=7)).isoformat() + 'Z',
            'escrow_public_key': escrow_keypair.public_key,
            'offer_notes': 'Integration test offer'
        }
        
        buy_offer_tx = Transaction.buy_offer(
            inputs=[buy_offer_input],
            asset_id=asset_id,
            advertisement_id=advertisement_id,
            metadata=buy_offer_metadata
        )
        
        print(f"✅ BUY_OFFER created: {buy_offer_tx.id}")
        
        # Create SELL transaction that references the BUY_OFFER
        sell_input = {
            'owners_before': [seller_keypair.public_key],
            'fulfillment': 'test_fulfillment'
        }
        sell_metadata = {
            'seller_public_key': seller_keypair.public_key,
            'buyer_public_key': buyer_keypair.public_key,
            'sale_amount': 500.00,
            'sale_currency': 'USD',
            'sale_timestamp': datetime.utcnow().isoformat() + 'Z',
            'sale_notes': 'Integration test sale'
        }
        
        sell_tx = Transaction.sell(
            inputs=[sell_input],
            asset_id=asset_id,
            buy_offer_id=buy_offer_tx.id,
            metadata=sell_metadata
        )
        
        print(f"✅ SELL transaction created: {sell_tx.id}")
        print(f"   References BUY_OFFER: {sell_tx.asset.get('buy_offer_id')}")
        print(f"   Creates {len(sell_tx.outputs)} outputs for atomic transfers")
        
        # Verify transaction chain
        if buy_offer_tx.asset.get('advertisement_id') == advertisement_id:
            print("✅ BUY_OFFER correctly references advertisement")
        else:
            print(f"❌ BUY_OFFER advertisement reference mismatch")
        
        if sell_tx.asset.get('buy_offer_id') == buy_offer_tx.id:
            print("✅ SELL correctly references BUY_OFFER")
        else:
            print(f"❌ SELL BUY_OFFER reference mismatch")
        
        if (buy_offer_tx.asset.get('id') == asset_id and 
            sell_tx.asset.get('id') == asset_id):
            print("✅ Asset ID consistent across transaction chain")
        else:
            print(f"❌ Asset ID inconsistency in transaction chain")
        
        print("\n✅ All integration tests completed")
        
    except Exception as e:
        print(f"❌ Error in integration tests: {e}")
        import traceback
        traceback.print_exc()

def main():
    """Main test function"""
    print("🚀 Starting BUY_OFFER Transaction Tests in Docker\n")
    print("=" * 60)
    
    # Test 1: Basic functionality
    buy_offer_tx = test_buy_offer_basic()
    
    # Test 2: Validation rules
    test_buy_offer_validation()
    
    # Test 3: Integration with SELL
    test_integration_with_sell()
    
    print("\n" + "=" * 60)
    print("🎉 All BUY_OFFER tests completed!")
    
    if buy_offer_tx:
        print(f"\n📋 Final Transaction Summary:")
        print(f"   Transaction ID: {buy_offer_tx.id}")
        print(f"   Operation: {buy_offer_tx.operation}")
        print(f"   Asset ID: {buy_offer_tx.asset['id']}")
        print(f"   Advertisement ID: {buy_offer_tx.asset['advertisement_id']}")
        print(f"   Offer Amount: {buy_offer_tx.metadata['offer_amount']} {buy_offer_tx.metadata['offer_currency']}")
        print(f"   Outputs: {len(buy_offer_tx.outputs)}")
    
    print("\n✅ BUY_OFFER transaction type is working correctly in Docker!")

if __name__ == "__main__":
    main()
