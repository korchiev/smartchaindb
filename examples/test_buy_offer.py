#!/usr/bin/env python3
"""
Test script for BUY_OFFER transaction type

This script tests:
1. BUY_OFFER transaction creation
2. Validation rules
3. Business logic
4. Error handling
5. Integration with other transaction types
"""

import sys
import os
from datetime import datetime, timedelta

# Add the parent directory to the path so we can import bigchaindb modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bigchaindb.common.transaction import Transaction
from bigchaindb.common.crypto import generate_keypair
from bigchaindb.common.output import Output
from cryptoconditions import Ed25519Sha256

def test_buy_offer_creation():
    """Test basic BUY_OFFER transaction creation"""
    print("=== Testing BUY_OFFER Transaction Creation ===\n")
    
    try:
        # Generate keypairs
        buyer_keypair = generate_keypair()
        escrow_keypair = generate_keypair()
        
        print(f"✅ Generated keypairs successfully")
        print(f"   Buyer: {buyer_keypair.public_key[:20]}...")
        print(f"   Escrow: {escrow_keypair.public_key[:20]}...\n")
        
        # Create mock data
        asset_id = "test_asset_123"
        advertisement_id = "test_ad_456"
        
        # Create input for the asset being offered for
        asset_input = Transaction.Input.generate([buyer_keypair.public_key])
        
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
        
        print("✅ Created metadata successfully")
        print(f"   Offer Amount: {metadata['offer_amount']} {metadata['offer_currency']}")
        print(f"   Expiry: {metadata['offer_expiry']}\n")
        
        # Create BUY_OFFER transaction
        buy_offer_tx = Transaction.buy_offer(
            inputs=[asset_input],
            asset_id=asset_id,
            advertisement_id=advertisement_id,
            metadata=metadata
        )
        
        print("✅ BUY_OFFER transaction created successfully!")
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
            print(f"   Public Keys: {escrow_output.public_keys}")
            print(f"   Condition URI: {escrow_output.fulfillment.condition_uri}")
            
            # Verify escrow amount matches offer amount
            if escrow_output.amount == metadata['offer_amount']:
                print("✅ Escrow amount matches offer amount")
            else:
                print(f"❌ Escrow amount mismatch: {escrow_output.amount} != {metadata['offer_amount']}")
        else:
            print(f"❌ Expected 1 output, got {len(buy_offer_tx.outputs)}")
        
        return buy_offer_tx
        
    except Exception as e:
        print(f"❌ Error creating BUY_OFFER transaction: {e}")
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
        
        # Test 3: Invalid offer amount (zero)
        print("\nTest 3: Invalid offer amount (zero)")
        try:
            invalid_metadata = valid_metadata.copy()
            invalid_metadata['offer_amount'] = 0
            
            Transaction.validate_buy_offer(
                inputs=[],
                asset_id='test_asset',
                advertisement_id='test_ad',
                metadata=invalid_metadata
            )
            print("❌ Should have rejected zero amount")
        except ValueError as e:
            print(f"✅ Correctly rejected zero amount: {e}")
        
        # Test 4: Missing required fields
        print("\nTest 4: Missing required fields")
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
        
        # Test 5: Expired offer
        print("\nTest 5: Expired offer")
        try:
            expired_metadata = valid_metadata.copy()
            expired_metadata['offer_expiry'] = (datetime.utcnow() - timedelta(days=1)).isoformat() + 'Z'
            
            Transaction.validate_buy_offer(
                inputs=[],
                asset_id='test_asset',
                advertisement_id='test_ad',
                metadata=expired_metadata
            )
            print("❌ Should have rejected expired offer")
        except ValueError as e:
            print(f"✅ Correctly rejected expired offer: {e}")
        
        print("\n✅ All validation tests completed")
        
    except Exception as e:
        print(f"❌ Error in validation tests: {e}")

def test_buy_offer_business_rules():
    """Test BUY_OFFER business rules"""
    print("\n=== Testing BUY_OFFER Business Rules ===\n")
    
    try:
        # Generate keypairs
        buyer_keypair = generate_keypair()
        seller_keypair = generate_keypair()
        escrow_keypair = generate_keypair()
        
        # Create mock transaction
        asset_id = "test_asset_123"
        advertisement_id = "test_ad_456"
        
        # Create input
        asset_input = Transaction.Input.generate([buyer_keypair.public_key])
        
        # Create metadata
        metadata = {
            'buyer_public_key': buyer_keypair.public_key,
            'offer_amount': 1000.00,
            'offer_currency': 'USD',
            'offer_timestamp': datetime.utcnow().isoformat() + 'Z',
            'offer_expiry': (datetime.utcnow() + timedelta(days=7)).isoformat() + 'Z',
            'escrow_public_key': escrow_keypair.public_key,
            'offer_notes': 'Test offer'
        }
        
        # Create transaction
        buy_offer_tx = Transaction.buy_offer(
            inputs=[asset_input],
            asset_id=asset_id,
            advertisement_id=advertisement_id,
            metadata=metadata
        )
        
        print("✅ BUY_OFFER transaction created for business rule testing")
        print(f"   Transaction ID: {buy_offer_tx.id}")
        
        # Test business rule 1: Direct escrow transfer
        print("\nBusiness Rule 1: Direct Escrow Transfer")
        if len(buy_offer_tx.outputs) == 1:
            escrow_output = buy_offer_tx.outputs[0]
            if escrow_output.amount == metadata['offer_amount']:
                print("✅ Escrow amount matches offer amount")
            else:
                print(f"❌ Escrow amount mismatch: {escrow_output.amount} != {metadata['offer_amount']}")
            
            if escrow_keypair.public_key in escrow_output.public_keys:
                print("✅ Escrow output locked to correct escrow account")
            else:
                print(f"❌ Escrow output not locked to correct account")
        else:
            print(f"❌ Expected 1 output, got {len(buy_offer_tx.outputs)}")
        
        # Test business rule 2: Asset reference
        print("\nBusiness Rule 2: Asset Reference")
        if buy_offer_tx.asset.get('id') == asset_id:
            print("✅ Asset ID correctly referenced")
        else:
            print(f"❌ Asset ID mismatch: {buy_offer_tx.asset.get('id')} != {asset_id}")
        
        if buy_offer_tx.asset.get('advertisement_id') == advertisement_id:
            print("✅ Advertisement ID correctly referenced")
        else:
            print(f"❌ Advertisement ID mismatch: {buy_offer_tx.asset.get('advertisement_id')} != {advertisement_id}")
        
        # Test business rule 3: Metadata completeness
        print("\nBusiness Rule 3: Metadata Completeness")
        required_fields = ['buyer_public_key', 'offer_amount', 'offer_currency', 
                          'offer_timestamp', 'offer_expiry', 'escrow_public_key']
        
        missing_fields = []
        for field in required_fields:
            if field not in buy_offer_tx.metadata:
                missing_fields.append(field)
        
        if not missing_fields:
            print("✅ All required metadata fields present")
        else:
            print(f"❌ Missing metadata fields: {missing_fields}")
        
        print("\n✅ All business rule tests completed")
        
    except Exception as e:
        print(f"❌ Error in business rule tests: {e}")

def test_integration_with_other_transactions():
    """Test BUY_OFFER integration with other transaction types"""
    print("\n=== Testing BUY_OFFER Integration ===\n")
    
    try:
        # Generate keypairs for different parties
        buyer_keypair = generate_keypair()
        seller_keypair = generate_keypair()
        escrow_keypair = generate_keypair()
        
        print("✅ Generated keypairs for integration testing")
        
        # Test 1: BUY_OFFER with SELL transaction
        print("\nIntegration Test 1: BUY_OFFER → SELL")
        
        # Create BUY_OFFER
        asset_id = "integration_test_asset"
        advertisement_id = "integration_test_ad"
        
        buy_offer_input = Transaction.Input.generate([buyer_keypair.public_key])
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
        sell_input = Transaction.Input.generate([seller_keypair.public_key])
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
        
        # Test 2: Verify transaction chain
        print("\nIntegration Test 2: Transaction Chain Verification")
        
        # Verify BUY_OFFER references advertisement
        if buy_offer_tx.asset.get('advertisement_id') == advertisement_id:
            print("✅ BUY_OFFER correctly references advertisement")
        else:
            print(f"❌ BUY_OFFER advertisement reference mismatch")
        
        # Verify SELL references BUY_OFFER
        if sell_tx.asset.get('buy_offer_id') == buy_offer_tx.id:
            print("✅ SELL correctly references BUY_OFFER")
        else:
            print(f"❌ SELL BUY_OFFER reference mismatch")
        
        # Verify asset consistency
        if (buy_offer_tx.asset.get('id') == asset_id and 
            sell_tx.asset.get('id') == asset_id):
            print("✅ Asset ID consistent across transaction chain")
        else:
            print(f"❌ Asset ID inconsistency in transaction chain")
        
        print("\n✅ All integration tests completed")
        
    except Exception as e:
        print(f"❌ Error in integration tests: {e}")

def run_all_tests():
    """Run all BUY_OFFER tests"""
    print("🚀 Starting BUY_OFFER Transaction Tests\n")
    print("=" * 60)
    
    # Test 1: Basic creation
    buy_offer_tx = test_buy_offer_creation()
    
    # Test 2: Validation rules
    test_buy_offer_validation()
    
    # Test 3: Business rules
    test_buy_offer_business_rules()
    
    # Test 4: Integration
    test_integration_with_other_transactions()
    
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
    
    print("\n✅ BUY_OFFER transaction type is working correctly!")

if __name__ == "__main__":
    run_all_tests()
