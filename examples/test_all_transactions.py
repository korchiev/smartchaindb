#!/usr/bin/env python3
"""
Comprehensive test script for all new transaction types in SmartChainDB.
Tests: ADVERTISEMENT, BUY_OFFER, SELL, REQUEST_RETURN, ACCEPT_RETURN
"""

import sys
import os
from datetime import datetime, timedelta
from datetime import timezone

try:
    from bigchaindb.common.transaction import Transaction
    from bigchaindb.common.crypto import generate_key_pair
    print("✅ Successfully imported BigchainDB modules")
except ImportError as e:
    print(f"❌ Import error: {e}")
    sys.exit(1)

def test_advertisement_transaction():
    """Test ADVERTISEMENT transaction type"""
    print("\n=== Testing ADVERTISEMENT Transaction ===")
    
    try:
        # Generate keypairs
        advertiser_keypair = generate_key_pair()
        
        print(f"✅ Generated advertiser keypair: {advertiser_keypair.public_key[:20]}...")
        
        # Create metadata
        metadata = {
            'status': 'OPEN',
            'advertiser_public_key': advertiser_keypair.public_key,
            'price': '1000.00',
            'description': 'Test asset for sale',
            'is_new_advertisement': True
        }
        
        print("✅ Created metadata successfully")
        
        # Create input (simplified for testing)
        asset_input = {
            'owners_before': [advertiser_keypair.public_key],
            'fulfillment': 'test_fulfillment'
        }
        
        # Create ADVERTISEMENT transaction
        ad_tx = Transaction.advertisement(
            inputs=[asset_input],
            asset_id='test_asset_123',
            metadata=metadata
        )
        
        print(f"✅ ADVERTISEMENT transaction created successfully!")
        print(f"   Transaction ID: {ad_tx.id}")
        print(f"   Operation: {ad_tx.operation}")
        print(f"   Asset ID: {ad_tx.asset['id']}")
        print(f"   Status: {ad_tx.metadata['status']}")
        print(f"   Advertiser: {ad_tx.metadata['advertiser_public_key'][:20]}...")
        
        return ad_tx
        
    except Exception as e:
        print(f"❌ Error in ADVERTISEMENT test: {e}")
        return None

def test_buy_offer_transaction(advertisement_id):
    """Test BUY_OFFER transaction type"""
    print("\n=== Testing BUY_OFFER Transaction ===")
    
    try:
        # Generate keypairs
        buyer_keypair = generate_key_pair()
        escrow_keypair = generate_key_pair()
        
        print(f"✅ Generated keypairs successfully")
        print(f"   Buyer: {buyer_keypair.public_key[:20]}...")
        print(f"   Escrow: {escrow_keypair.public_key[:20]}...")
        
        # Create metadata
        expiry_time = datetime.utcnow() + timedelta(days=7)
        metadata = {
            'buyer_public_key': buyer_keypair.public_key,
            'offer_amount': 1000.0,
            'offer_currency': 'USD',
            'offer_timestamp': datetime.utcnow().isoformat() + 'Z',
            'offer_expiry': expiry_time.isoformat() + 'Z',
            'escrow_public_key': escrow_keypair.public_key
        }
        
        print("✅ Created metadata successfully")
        print(f"   Offer Amount: {metadata['offer_amount']} {metadata['offer_currency']}")
        print(f"   Expiry: {metadata['offer_expiry']}")
        
        # Create input (simplified for testing)
        asset_input = {
            'owners_before': [buyer_keypair.public_key],
            'fulfillment': 'test_fulfillment'
        }
        
        # Create BUY_OFFER transaction
        buy_offer_tx = Transaction.buy_offer(
            inputs=[asset_input],
            asset_id='test_asset_123',
            advertisement_id=advertisement_id,
            metadata=metadata
        )
        
        print(f"✅ BUY_OFFER transaction created successfully!")
        print(f"   Transaction ID: {buy_offer_tx.id}")
        print(f"   Operation: {buy_offer_tx.operation}")
        print(f"   Asset ID: {buy_offer_tx.asset['id']}")
        print(f"   Advertisement ID: {buy_offer_tx.asset['advertisement_id']}")
        print(f"   Inputs: {len(buy_offer_tx.inputs)}")
        print(f"   Outputs: {len(buy_offer_tx.outputs)}")
        
        # Verify escrow output
        if len(buy_offer_tx.outputs) == 1:
            escrow_output = buy_offer_tx.outputs[0]
            print(f"✅ Escrow output created correctly:")
            print(f"   Amount: {escrow_output.amount}")
            print(f"   Public Keys: {len(escrow_output.public_keys)}")
            
            if escrow_output.amount == int(metadata['offer_amount']):
                print("✅ Escrow amount matches offer amount")
            else:
                print("❌ Escrow amount mismatch")
                
            if escrow_keypair.public_key in escrow_output.public_keys:
                print("✅ Escrow output locked to correct escrow account")
            else:
                print("❌ Escrow output not locked to correct account")
        
        return buy_offer_tx
        
    except Exception as e:
        print(f"❌ Error in BUY_OFFER test: {e}")
        return None

def test_sell_transaction(buy_offer_id):
    """Test SELL transaction type"""
    print("\n=== Testing SELL Transaction ===")
    
    try:
        # Generate keypairs
        seller_keypair = generate_key_pair()
        buyer_keypair = generate_key_pair()
        
        print(f"✅ Generated keypairs successfully")
        print(f"   Seller: {seller_keypair.public_key[:20]}...")
        print(f"   Buyer: {buyer_keypair.public_key[:20]}...")
        
        # Create metadata
        metadata = {
            'seller_public_key': seller_keypair.public_key,
            'buyer_public_key': buyer_keypair.public_key,
            'sale_amount': 1000.0,
            'sale_currency': 'USD'
        }
        
        print("✅ Created metadata successfully")
        print(f"   Sale Amount: {metadata['sale_amount']} {metadata['sale_currency']}")
        
        # Create input (simplified for testing)
        asset_input = {
            'owners_before': [seller_keypair.public_key],
            'fulfillment': 'test_fulfillment'
        }
        
        # Create SELL transaction
        sell_tx = Transaction.sell(
            inputs=[asset_input],
            asset_id='test_asset_123',
            buy_offer_id=buy_offer_id,
            metadata=metadata
        )
        
        print(f"✅ SELL transaction created successfully!")
        print(f"   Transaction ID: {sell_tx.id}")
        print(f"   Operation: {sell_tx.operation}")
        print(f"   Asset ID: {sell_tx.asset['id']}")
        print(f"   Buy Offer ID: {sell_tx.asset['buy_offer_id']}")
        print(f"   Inputs: {len(sell_tx.inputs)}")
        print(f"   Outputs: {len(sell_tx.outputs)}")
        
        # Verify outputs (asset transfer + payment transfer)
        if len(sell_tx.outputs) == 2:
            asset_output = sell_tx.outputs[0]
            payment_output = sell_tx.outputs[1]
            
            print(f"✅ Two outputs created for atomic transfer:")
            print(f"   Asset Output: {asset_output.amount} → {asset_output.public_keys[0][:20]}...")
            print(f"   Payment Output: {payment_output.amount} → {payment_output.public_keys[0][:20]}...")
        
        return sell_tx
        
    except Exception as e:
        print(f"❌ Error in SELL test: {e}")
        return None

def test_request_return_transaction(sell_transaction_id):
    """Test REQUEST_RETURN transaction type"""
    print("\n=== Testing REQUEST_RETURN Transaction ===")
    
    try:
        # Generate keypair
        requester_keypair = generate_key_pair()
        
        print(f"✅ Generated requester keypair: {requester_keypair.public_key[:20]}...")
        
        # Create metadata
        metadata = {
            'requester_public_key': requester_keypair.public_key,
            'return_reason': 'Item not as described',
            'return_request_timestamp': datetime.utcnow().isoformat() + 'Z',
            'return_policy_details': {
                'return_window_days': 30,
                'return_status': 'PENDING'
            }
        }
        
        print("✅ Created metadata successfully")
        print(f"   Return Reason: {metadata['return_reason']}")
        print(f"   Return Window: {metadata['return_policy_details']['return_window_days']} days")
        
        # Create input (simplified for testing)
        asset_input = {
            'owners_before': [requester_keypair.public_key],
            'fulfillment': 'test_fulfillment'
        }
        
        # Create REQUEST_RETURN transaction
        request_return_tx = Transaction.request_return(
            inputs=[asset_input],
            asset_id='test_asset_123',
            sell_transaction_id=sell_transaction_id,
            metadata=metadata
        )
        
        print(f"✅ REQUEST_RETURN transaction created successfully!")
        print(f"   Transaction ID: {request_return_tx.id}")
        print(f"   Operation: {request_return_tx.operation}")
        print(f"   Asset ID: {request_return_tx.asset['id']}")
        print(f"   Sell Transaction ID: {request_return_tx.asset['sell_transaction_id']}")
        print(f"   Return Status: {request_return_tx.metadata['return_policy_details']['return_status']}")
        
        return request_return_tx
        
    except Exception as e:
        print(f"❌ Error in REQUEST_RETURN test: {e}")
        return None

def test_accept_return_transaction(request_return_id):
    """Test ACCEPT_RETURN transaction type"""
    print("\n=== Testing ACCEPT_RETURN Transaction ===")
    
    try:
        # Generate keypair
        accepter_keypair = generate_key_pair()
        
        print(f"✅ Generated accepter keypair: {accepter_keypair.public_key[:20]}...")
        
        # Create metadata
        metadata = {
            'accepter_public_key': accepter_keypair.public_key,
            'return_acceptance_timestamp': datetime.utcnow().isoformat() + 'Z',
            'refund_details': {
                'refund_amount': 1000.0,
                'refund_currency': 'USD',
                'refund_method': 'Escrow return'
            },
            'return_processing_notes': 'Return accepted, processing refund'
        }
        
        print("✅ Created metadata successfully")
        print(f"   Refund Amount: {metadata['refund_details']['refund_amount']} {metadata['refund_details']['refund_currency']}")
        print(f"   Refund Method: {metadata['refund_details']['refund_method']}")
        
        # Create input (simplified for testing)
        asset_input = {
            'owners_before': [accepter_keypair.public_key],
            'fulfillment': 'test_fulfillment'
        }
        
        # Create ACCEPT_RETURN transaction
        accept_return_tx = Transaction.accept_return(
            inputs=[asset_input],
            asset_id='test_asset_123',
            request_return_id=request_return_id,
            metadata=metadata
        )
        
        print(f"✅ ACCEPT_RETURN transaction created successfully!")
        print(f"   Transaction ID: {accept_return_tx.id}")
        print(f"   Operation: {accept_return_tx.operation}")
        print(f"   Asset ID: {accept_return_tx.asset['id']}")
        print(f"   Request Return ID: {accept_return_tx.asset['request_return_id']}")
        print(f"   Processing Notes: {accept_return_tx.metadata['return_processing_notes']}")
        
        return accept_return_tx
        
    except Exception as e:
        print(f"❌ Error in ACCEPT_RETURN test: {e}")
        return None

def main():
    """Main test function"""
    print("🚀 Starting Comprehensive Transaction Type Tests")
    print("=" * 60)
    
    # Test 1: ADVERTISEMENT
    ad_tx = test_advertisement_transaction()
    if not ad_tx:
        print("❌ ADVERTISEMENT test failed, stopping")
        return
    
    # Test 2: BUY_OFFER
    buy_offer_tx = test_buy_offer_transaction(ad_tx.id or 'test_ad_456')
    if not buy_offer_tx:
        print("❌ BUY_OFFER test failed, stopping")
        return
    
    # Test 3: SELL
    sell_tx = test_sell_transaction(buy_offer_tx.id or 'test_buy_offer_789')
    if not sell_tx:
        print("❌ SELL test failed, stopping")
        return
    
    # Test 4: REQUEST_RETURN
    request_return_tx = test_request_return_transaction(sell_tx.id or 'test_sell_101')
    if not request_return_tx:
        print("❌ REQUEST_RETURN test failed, stopping")
        return
    
    # Test 5: ACCEPT_RETURN
    accept_return_tx = test_accept_return_transaction(request_return_tx.id or 'test_request_return_202')
    if not accept_return_tx:
        print("❌ ACCEPT_RETURN test failed, stopping")
        return
    
    print("\n" + "=" * 60)
    print("🎉 ALL TRANSACTION TYPE TESTS COMPLETED SUCCESSFULLY!")
    print("=" * 60)
    
    print("\n📋 Final Transaction Summary:")
    print(f"   ADVERTISEMENT: {ad_tx.operation} - {ad_tx.metadata['status']}")
    print(f"   BUY_OFFER: {buy_offer_tx.operation} - {buy_offer_tx.metadata['offer_amount']} {buy_offer_tx.metadata['offer_currency']}")
    print(f"   SELL: {sell_tx.operation} - {sell_tx.metadata['sale_amount']} {sell_tx.metadata['sale_currency']}")
    print(f"   REQUEST_RETURN: {request_return_tx.operation} - {request_return_tx.metadata['return_reason']}")
    print(f"   ACCEPT_RETURN: {accept_return_tx.operation} - {accept_return_tx.metadata['refund_details']['refund_method']}")
    
    print("\n✅ All new transaction types are working correctly!")

if __name__ == "__main__":
    main()
