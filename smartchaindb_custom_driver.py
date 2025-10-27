#!/usr/bin/env python3
"""
SmartChainDB Custom Driver Wrapper

This wrapper uses SmartChainDB's internal transaction classes to support
all custom transaction types like ADVERTISEMENT, BUY_OFFER, etc.
"""

import time
import sys
import os
import hashlib
import requests
import json
from datetime import datetime, timedelta
from typing import Dict, Any, Tuple

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import SmartChainDB's internal classes
try:
    from bigchaindb.common.transaction import Transaction, Input, Output, TransactionLink
    from bigchaindb.common.crypto import generate_key_pair
    print("✅ SmartChainDB internal classes imported successfully")
except ImportError as e:
    print(f"❌ Failed to import SmartChainDB classes: {e}")
    sys.exit(1)

class SmartChainDBDriver:
    """Custom driver that supports all SmartChainDB transaction types"""
    
    def __init__(self, bigchaindb_url: str = "http://localhost:9984"):
        self.bigchaindb_url = bigchaindb_url.rstrip('/')
        self.transactions_url = f"{self.bigchaindb_url}/api/v1/transactions/"
        
    def generate_keypair(self):
        """Generate a keypair using SmartChainDB's crypto"""
        return generate_key_pair()
    
    def prepare_create_transaction(self, signers, asset_data, metadata=None):
        """Prepare a CREATE transaction with proper SmartChainDB schema"""
        if metadata is None:
            metadata = {}
            
        # Add required timestamp
        metadata['requestCreationTimestamp'] = datetime.now().isoformat()
        
        # Create transaction using SmartChainDB's internal class
        tx = Transaction(
            operation=Transaction.CREATE,
            asset={'data': asset_data},
            metadata=metadata
        )
        
        # Add input (CREATE transactions need null input)
        input_obj = Input.generate([signers])
        tx.inputs = [input_obj]
        
        # Add output
        output_obj = Output.generate([signers], amount=1)
        tx.outputs = [output_obj]
        
        return tx.to_dict()
    
    def prepare_advertisement_transaction(self, signers, asset_id, metadata=None):
        """Prepare an ADVERTISEMENT transaction using SmartChainDB's internal class"""
        if metadata is None:
            metadata = {}
            
        # Add required timestamp
        metadata['requestCreationTimestamp'] = datetime.now().isoformat()
        
        # Generate input with proper fulfillment (ADVERTISEMENT transactions have fulfills: null)
        advertisement_input = Input.generate([signers])
        # ADVERTISEMENT transactions don't reference previous transactions
        advertisement_input.fulfills = None
        
        # Use SmartChainDB's advertisement method
        tx = Transaction.advertisement(
            inputs=[advertisement_input],
            asset_id=asset_id,
            metadata=metadata
        )
        
        tx_dict = tx.to_dict()
        print(f"🔍 ADVERTISEMENT transaction prepared:")
        print(f"   Operation: {tx_dict.get('operation', 'MISSING')}")
        print(f"   Asset: {tx_dict.get('asset', 'MISSING')}")
        print(f"   Metadata keys: {list(tx_dict.get('metadata', {}).keys())}")
        
        return tx_dict
    
    def prepare_buy_offer_transaction(self, signers, asset_id, advertisement_id, metadata=None):
        """Prepare a BUY_OFFER transaction using SmartChainDB's internal class"""
        if metadata is None:
            metadata = {}
            
        # Add required timestamp
        metadata['requestCreationTimestamp'] = datetime.now().isoformat()
        
        # Convert offer_amount to int for validation
        if 'offer_amount' in metadata:
            offer_amount_int = int(metadata['offer_amount'])
            # Keep as int for validation
            metadata['offer_amount'] = offer_amount_int
        
        # Generate input for the buyer's payment asset
        buy_offer_input = Input.generate([signers])
        
        # Use SmartChainDB's buy_offer method
        tx = Transaction.buy_offer(
            inputs=[buy_offer_input],
            asset_id=asset_id,
            advertisement_id=advertisement_id,
            metadata=metadata
        )
        
        # Convert offer_amount back to string for schema compliance
        if 'offer_amount' in tx.metadata:
            tx.metadata['offer_amount'] = str(tx.metadata['offer_amount'])
        
        tx_dict = tx.to_dict()
        print(f"🔍 BUY_OFFER transaction prepared:")
        print(f"   Operation: {tx_dict.get('operation', 'MISSING')}")
        print(f"   Asset: {tx_dict.get('asset', 'MISSING')}")
        print(f"   Metadata keys: {list(tx_dict.get('metadata', {}).keys())}")
        
        return tx_dict
    
    def prepare_sell_transaction(self, signers, asset_id, buy_offer_id, metadata=None):
        """Prepare a SELL transaction using SmartChainDB's internal class"""
        if metadata is None:
            metadata = {}
            
        # Add required timestamp
        metadata['requestCreationTimestamp'] = datetime.now().isoformat()
        
        # Convert sale_amount to int for validation
        if 'sale_amount' in metadata:
            sale_amount_int = int(metadata['sale_amount'])
            # Keep as int for validation
            metadata['sale_amount'] = sale_amount_int
        
        # Create proper input that references the seller's asset (from CREATE transaction)
        fulfills_link = TransactionLink.from_dict({
            'output_index': 0,
            'transaction_id': asset_id,  # The CREATE transaction ID
        })
        
        sell_input = Input.generate([signers])
        sell_input.fulfills = fulfills_link
        
        # Use SmartChainDB's validate_sell method to get inputs and outputs
        (inputs, outputs) = Transaction.validate_sell([sell_input], asset_id, buy_offer_id, metadata)
        
        # Create SELL transaction with correct asset structure
        tx = Transaction(
            Transaction.SELL,
            {"data": {"id": asset_id, "buy_offer_id": buy_offer_id}},
            inputs,
            outputs,
            metadata
        )
        
        # Convert sale_amount back to string for schema compliance
        if 'sale_amount' in tx.metadata:
            tx.metadata['sale_amount'] = str(tx.metadata['sale_amount'])
        
        tx_dict = tx.to_dict()
        print(f"🔍 SELL transaction prepared:")
        print(f"   Operation: {tx_dict.get('operation', 'MISSING')}")
        print(f"   Asset: {tx_dict.get('asset', 'MISSING')}")
        print(f"   Metadata keys: {list(tx_dict.get('metadata', {}).keys())}")
        
        return tx_dict
    
    def prepare_request_return_transaction(self, signers, asset_id, sell_transaction_id, metadata=None):
        """Prepare a REQUEST_RETURN transaction using SmartChainDB's internal class"""
        if metadata is None:
            metadata = {}
            
        # Add required timestamp
        metadata['requestCreationTimestamp'] = datetime.now().isoformat()
        
        # REQUEST_RETURN transactions don't reference previous transactions (schema requires fulfills: null)
        request_return_input = Input.generate([signers])
        request_return_input.fulfills = None
        
        # Use SmartChainDB's validate_request_return method to get inputs
        (inputs, _) = Transaction.validate_request_return([request_return_input], asset_id, sell_transaction_id, metadata)
        
        # Create output for the return request (required by schema)
        return_output = Output.generate([signers], amount=1)
        
        # Create REQUEST_RETURN transaction with correct asset structure
        tx = Transaction(
            Transaction.REQUEST_RETURN,
            {"data": {"id": asset_id, "sell_transaction_id": sell_transaction_id}},
            inputs,
            [return_output],
            metadata
        )
        
        tx_dict = tx.to_dict()
        print(f"🔍 REQUEST_RETURN transaction prepared:")
        print(f"   Operation: {tx_dict.get('operation', 'MISSING')}")
        print(f"   Asset: {tx_dict.get('asset', 'MISSING')}")
        print(f"   Metadata keys: {list(tx_dict.get('metadata', {}).keys())}")
        
        return tx_dict
    
    def prepare_seller_accept_return_transaction(self, signers, asset_id, request_return_id, metadata=None):
        """Prepare a SELLER_ACCEPT_RETURN transaction using SmartChainDB's internal class"""
        if metadata is None:
            metadata = {}
            
        # Add required timestamp
        metadata['requestCreationTimestamp'] = datetime.now().isoformat()
        
        # Convert refund_amount to float for schema validation
        if 'refund_details' in metadata and 'refund_amount' in metadata['refund_details']:
            refund_amount_float = float(metadata['refund_details']['refund_amount'])
            metadata['refund_details']['refund_amount'] = refund_amount_float
        
        # Generate input for the seller
        seller_accept_input = Input.generate([signers])
        
        # Create transaction without validation method (schema mismatch between validation and schema)
        inputs = [seller_accept_input]
        
        # Create outputs for the seller accept return (asset back to seller, refund to buyer)
        seller_output = Output.generate([signers], amount=1)
        
        # Create SELLER_ACCEPT_RETURN transaction with correct asset structure
        tx = Transaction(
            Transaction.SELLER_ACCEPT_RETURN,
            {"data": {"id": asset_id, "request_return_id": request_return_id}},
            inputs,
            [seller_output],
            metadata
        )
        
        # Keep refund_amount as float for schema compliance
        
        tx_dict = tx.to_dict()
        print(f"🔍 SELLER_ACCEPT_RETURN transaction prepared:")
        print(f"   Operation: {tx_dict.get('operation', 'MISSING')}")
        print(f"   Asset: {tx_dict.get('asset', 'MISSING')}")
        print(f"   Metadata keys: {list(tx_dict.get('metadata', {}).keys())}")
        
        return tx_dict
    
    def prepare_update_adv_transaction(self, signers, asset_id, advertisement_id, metadata=None):
        """Prepare an UPDATE_ADV transaction using SmartChainDB's internal class"""
        if metadata is None:
            metadata = {}
            
        # Add required timestamp
        metadata['requestCreationTimestamp'] = datetime.now().isoformat()
        
        # Generate input for the advertiser
        update_adv_input = Input.generate([signers])
        
        # Use SmartChainDB's validate_update_adv method to get inputs
        (inputs, _) = Transaction.validate_update_adv([update_adv_input], advertisement_id, metadata)
        
        # Create output for the update advertisement
        update_output = Output.generate([signers], amount=1)
        
        # Create UPDATE_ADV transaction with correct asset structure
        tx = Transaction(
            Transaction.UPDATE_ADV,
            {"data": {"id": asset_id}},
            inputs,
            [update_output],
            metadata
        )
        
        tx_dict = tx.to_dict()
        print(f"🔍 UPDATE_ADV transaction prepared:")
        print(f"   Operation: {tx_dict.get('operation', 'MISSING')}")
        print(f"   Asset: {tx_dict.get('asset', 'MISSING')}")
        print(f"   Metadata keys: {list(tx_dict.get('metadata', {}).keys())}")
        
        return tx_dict
    
    def prepare_transfer_transaction(self, asset_id, inputs, recipients, metadata=None):
        """Prepare a TRANSFER transaction"""
        if metadata is None:
            metadata = {}
            
        # Add required timestamp
        metadata['requestCreationTimestamp'] = datetime.now().isoformat()
        
        # Create transaction
        tx = Transaction(
            operation=Transaction.TRANSFER,
            asset={'id': asset_id},
            inputs=inputs,
            metadata=metadata
        )
        
        # Add output for recipient
        output_obj = Output.generate([recipients], amount=1)
        tx.outputs = [output_obj]
        
        return tx.to_dict()
    
    def fulfill_transaction(self, tx_dict, private_keys):
        """Fulfill a transaction with private keys"""
        # Convert back to Transaction object
        tx = Transaction.from_dict(tx_dict)
        
        # Sign the transaction (private_keys must be a list)
        if isinstance(private_keys, str):
            private_keys = [private_keys]
        tx.sign(private_keys)
        
        return tx.to_dict()
    
    def send_transaction(self, tx_dict):
        """Send transaction to SmartChainDB"""
        try:
            print(f"📤 Sending transaction to server:")
            print(f"   Operation: {tx_dict.get('operation', 'MISSING')}")
            print(f"   Transaction ID: {tx_dict.get('id', 'MISSING')}")
            
            response = requests.post(
                self.transactions_url,
                json=tx_dict,
                headers={'Content-Type': 'application/json'},
                timeout=30
            )
            
            if response.status_code == 202:  # Accepted
                return response.json()
            elif response.status_code == 400:  # Bad Request
                error_msg = response.text
                print(f"❌ Transaction validation failed: {error_msg}")
                return None
            else:
                print(f"❌ Unexpected response: {response.status_code} - {response.text}")
                return None
                
        except requests.exceptions.RequestException as e:
            print(f"❌ Network error: {e}")
            return None
    
    def wait_for_transaction_confirmation(self, tx_id, max_wait_seconds=30):
        """Wait for a transaction to be confirmed and available"""
        import time
        start_time = time.time()
        
        while time.time() - start_time < max_wait_seconds:
            try:
                response = requests.get(f"{self.bigchaindb_url}/api/v1/transactions/{tx_id}")
                if response.status_code == 200:
                    tx_data = response.json()
                    print(f"✅ Transaction {tx_id} confirmed and available")
                    return tx_data
                elif response.status_code == 404:
                    print(f"⏳ Transaction {tx_id} not yet available, waiting...")
                    time.sleep(1)
                else:
                    print(f"❌ Error checking transaction: {response.status_code}")
                    time.sleep(1)
            except requests.exceptions.RequestException as e:
                print(f"❌ Network error checking transaction: {e}")
                time.sleep(1)
        
        print(f"⏰ Timeout waiting for transaction {tx_id}")
        return None

def test_smartchaindb_driver():
    """Test the custom SmartChainDB driver"""
    print("🧪 Testing SmartChainDB Custom Driver...")
    
    driver = SmartChainDBDriver()
    
    # Test 1: CREATE transaction
    print("\n1. Testing CREATE Transaction...")
    sender = driver.generate_keypair()
    
    create_tx_dict = driver.prepare_create_transaction(
        signers=sender.public_key,
        asset_data={
            'machineIdentifier': f'machine_{int(time.time())}',
            'capability': ['read', 'write'],
            'capabilityParameters': {'type': 'test_asset'}
        },
        metadata={'test': 'true'}
    )
    
    create_tx_signed = driver.fulfill_transaction(create_tx_dict, sender.private_key)
    create_response = driver.send_transaction(create_tx_signed)
    
    if create_response:
        print(f"✅ CREATE transaction successful: {create_response.get('id', 'Unknown ID')}")
        
        # Wait for CREATE transaction to be confirmed and available
        create_tx_id = create_response['id']
        print(f"⏳ Waiting for CREATE transaction {create_tx_id} to be confirmed...")
        confirmed_tx = driver.wait_for_transaction_confirmation(create_tx_id)
        
        if confirmed_tx:
            # Test 2: ADVERTISEMENT transaction
            print("\n2. Testing ADVERTISEMENT Transaction...")
            # Use the same sender who created the asset to advertise it
            advertiser = sender
            # Use the confirmed CREATE transaction's asset ID for the ADVERTISEMENT
            asset_id = create_tx_id
            
            adv_tx_dict = driver.prepare_advertisement_transaction(
                signers=advertiser.public_key,
                asset_id=asset_id,
                metadata={
                    'status': 'OPEN',
                    'advertiser_public_key': advertiser.public_key,
                    'price': '100.50',
                    'description': 'Test advertisement'
                }
            )
            
            adv_tx_signed = driver.fulfill_transaction(adv_tx_dict, advertiser.private_key)
            adv_response = driver.send_transaction(adv_tx_signed)
            
            if adv_response:
                print(f"✅ ADVERTISEMENT transaction successful: {adv_response.get('id', 'Unknown ID')}")
                
                # Test 3: BUY_OFFER transaction
                print("\n3. Testing BUY_OFFER Transaction...")
                buyer = driver.generate_keypair()
                escrow = driver.generate_keypair()
                
                # Wait for ADVERTISEMENT to be confirmed
                adv_tx_id = adv_response['id']
                print(f"⏳ Waiting for ADVERTISEMENT transaction {adv_tx_id} to be confirmed...")
                confirmed_adv = driver.wait_for_transaction_confirmation(adv_tx_id)
                
                if confirmed_adv:
                    buy_offer_tx_dict = driver.prepare_buy_offer_transaction(
                        signers=buyer.public_key,
                        asset_id=asset_id,
                        advertisement_id=adv_tx_id,
                        metadata={
                            'buyer_public_key': buyer.public_key,
                            'offer_amount': '1000',
                            'offer_currency': 'USD',
                            'offer_timestamp': datetime.now().isoformat(),
                            'offer_expiry': (datetime.now() + timedelta(days=7)).isoformat(),
                            'escrow_public_key': escrow.public_key,
                            'offer_notes': 'Interested in purchasing this asset'
                        }
                    )
                    
                    buy_offer_tx_signed = driver.fulfill_transaction(buy_offer_tx_dict, buyer.private_key)
                    buy_offer_response = driver.send_transaction(buy_offer_tx_signed)
                    
                    if buy_offer_response:
                        print(f"✅ BUY_OFFER transaction successful: {buy_offer_response.get('id', 'Unknown ID')}")
                        
                        # Test 4: SELL transaction
                        print("\n4. Testing SELL Transaction...")
                        
                        # Wait for BUY_OFFER to be confirmed
                        buy_offer_tx_id = buy_offer_response['id']
                        print(f"⏳ Waiting for BUY_OFFER transaction {buy_offer_tx_id} to be confirmed...")
                        confirmed_buy_offer = driver.wait_for_transaction_confirmation(buy_offer_tx_id)
                        
                        if confirmed_buy_offer:
                            # Use the original advertiser (seller) to accept the buy offer
                            seller = advertiser  # Same person who created and advertised the asset
                            
                            sell_tx_dict = driver.prepare_sell_transaction(
                                signers=seller.public_key,
                                asset_id=asset_id,
                                buy_offer_id=buy_offer_tx_id,
                                metadata={
                                    'seller_public_key': seller.public_key,
                                    'buyer_public_key': buyer.public_key,
                                    'sale_amount': '1000',
                                    'sale_currency': 'USD',
                                    'sale_timestamp': datetime.now().isoformat(),
                                    'sale_notes': 'Asset sold to buyer via buy offer acceptance'
                                }
                            )
                            
                            sell_tx_signed = driver.fulfill_transaction(sell_tx_dict, seller.private_key)
                            sell_response = driver.send_transaction(sell_tx_signed)
                            
                            if sell_response:
                                print(f"✅ SELL transaction successful: {sell_response.get('id', 'Unknown ID')}")
                                
                                # Test 5: REQUEST_RETURN transaction
                                print("\n5. Testing REQUEST_RETURN Transaction...")
                                
                                # Wait for SELL to be confirmed
                                sell_tx_id = sell_response['id']
                                print(f"⏳ Waiting for SELL transaction {sell_tx_id} to be confirmed...")
                                confirmed_sell = driver.wait_for_transaction_confirmation(sell_tx_id)
                                
                                if confirmed_sell:
                                    # Use the buyer to request a return
                                    requester = buyer  # Buyer wants to return the asset
                                    
                                    request_return_tx_dict = driver.prepare_request_return_transaction(
                                        signers=requester.public_key,
                                        asset_id=asset_id,
                                        sell_transaction_id=sell_tx_id,
                                        metadata={
                                            'requester_public_key': requester.public_key,
                                            'return_reason': 'Item not as described',
                                            'return_request_timestamp': datetime.now().isoformat(),
                                            'return_policy_details': {
                                                'return_window_days': 30,
                                                'return_conditions': 'Item must be in original condition',
                                                'return_status': 'PENDING'
                                            }
                                        }
                                    )
                                    
                                    request_return_tx_signed = driver.fulfill_transaction(request_return_tx_dict, requester.private_key)
                                    request_return_response = driver.send_transaction(request_return_tx_signed)
                                    
                                    if request_return_response:
                                        print(f"✅ REQUEST_RETURN transaction successful: {request_return_response.get('id', 'Unknown ID')}")
                                        
                                        # Test 6: SELLER_ACCEPT_RETURN transaction
                                        print("\n6. Testing SELLER_ACCEPT_RETURN Transaction...")
                                        
                                        # Wait for REQUEST_RETURN to be confirmed
                                        request_return_tx_id = request_return_response['id']
                                        print(f"⏳ Waiting for REQUEST_RETURN transaction {request_return_tx_id} to be confirmed...")
                                        confirmed_request_return = driver.wait_for_transaction_confirmation(request_return_tx_id)
                                        
                                        if confirmed_request_return:
                                            # Use the seller to accept the return
                                            seller_accepter = seller  # Seller accepts the return
                                            
                                            seller_accept_return_tx_dict = driver.prepare_seller_accept_return_transaction(
                                                signers=seller_accepter.public_key,
                                                asset_id=asset_id,
                                                request_return_id=request_return_tx_id,
                                                metadata={
                                                    'seller_public_key': seller_accepter.public_key,
                                                    'refund_details': {
                                                        'refund_amount': 1000.0,
                                                        'refund_currency': 'USD',
                                                        'refund_method': 'BANK_TRANSFER'
                                                    },
                                                    'acceptance_timestamp': datetime.now().isoformat(),
                                                    'processing_notes': 'Return accepted, processing refund'
                                                }
                                            )
                                            
                                            seller_accept_return_tx_signed = driver.fulfill_transaction(seller_accept_return_tx_dict, seller_accepter.private_key)
                                            seller_accept_return_response = driver.send_transaction(seller_accept_return_tx_signed)
                                            
                                            if seller_accept_return_response:
                                                print(f"✅ SELLER_ACCEPT_RETURN transaction successful: {seller_accept_return_response.get('id', 'Unknown ID')}")
                                                
                                                # Test 7: UPDATE_ADV transaction
                                                print("\n7. Testing UPDATE_ADV Transaction...")
                                                
                                                # Use the original advertiser to update the advertisement
                                                advertiser_updater = advertiser  # Original advertiser updates the ad
                                                
                                                update_adv_tx_dict = driver.prepare_update_adv_transaction(
                                                    signers=advertiser_updater.public_key,
                                                    asset_id=adv_tx_id,  # Use advertisement transaction ID as asset_id for SHACL validation
                                                    advertisement_id=adv_tx_id,
                                                    metadata={
                                                        'advertiser_public_key': advertiser_updater.public_key,
                                                        'status': 'CLOSED',
                                                        'new_status': 'CLOSED',
                                                        'new_value': '1200',
                                                        'new_expiry_date': (datetime.now() + timedelta(days=30)).isoformat(),
                                                        'update_timestamp': datetime.now().isoformat(),
                                                        'update_reason': 'Item sold and returned, closing advertisement'
                                                    }
                                                )
                                                
                                                update_adv_tx_signed = driver.fulfill_transaction(update_adv_tx_dict, advertiser_updater.private_key)
                                                update_adv_response = driver.send_transaction(update_adv_tx_signed)
                                                
                                                if update_adv_response:
                                                    print(f"✅ UPDATE_ADV transaction successful: {update_adv_response.get('id', 'Unknown ID')}")
                                                    print("\n🎉 SUCCESS! Custom driver works with ALL transaction types!")
                                                    print("Complete marketplace flow with returns:")
                                                    print("CREATE → ADVERTISEMENT → BUY_OFFER → SELL → REQUEST_RETURN → SELLER_ACCEPT_RETURN → UPDATE_ADV")
                                                    return True
                                                else:
                                                    print("❌ UPDATE_ADV transaction failed")
                                                    return False
                                            else:
                                                print("❌ SELLER_ACCEPT_RETURN transaction failed")
                                                return False
                                        else:
                                            print("❌ REQUEST_RETURN transaction not confirmed in time")
                                            return False
                                    else:
                                        print("❌ REQUEST_RETURN transaction failed")
                                        return False
                                else:
                                    print("❌ SELL transaction not confirmed in time")
                                    return False
                            else:
                                print("❌ SELL transaction failed")
                                return False
                        else:
                            print("❌ BUY_OFFER transaction not confirmed in time")
                            return False
                    else:
                        print("❌ BUY_OFFER transaction failed")
                        return False
                else:
                    print("❌ ADVERTISEMENT transaction not confirmed in time")
                    return False
            else:
                print("❌ ADVERTISEMENT transaction failed")
                return False
        else:
            print("❌ CREATE transaction not confirmed in time")
            return False
    else:
        print("❌ CREATE transaction failed")
        return False

if __name__ == "__main__":
    print("🔍 SmartChainDB Custom Driver Test")
    print("=" * 50)
    
    success = test_smartchaindb_driver()
    
    if success:
        print("\n🎉 SUCCESS! Custom driver works with all transaction types!")
    else:
        print("\n❌ Some tests failed")
