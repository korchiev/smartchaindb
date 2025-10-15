#!/usr/bin/env python3
"""
Synchronous Real SmartChainDB Experiments with Custom Driver

This version uses SmartChainDB's internal transaction classes to support
all custom transaction types like ADVERTISEMENT, BUY_OFFER, etc.
"""

import time
import json
import logging
import hashlib
from datetime import datetime
from typing import Dict, Any, Tuple, List
import sys
import os

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import SmartChainDB custom driver
try:
    from smartchaindb_custom_driver import SmartChainDBDriver
    print("✅ SmartChainDB custom driver loaded successfully")
except ImportError as e:
    print(f"❌ SmartChainDB custom driver import failed: {e}")
    sys.exit(1)

logger = logging.getLogger(__name__)

class SyncRealSmartChainDBSubmitter:
    """Synchronous SmartChainDB submitter with full transaction type support"""
    
    def __init__(self, bigchaindb_url: str = "http://localhost:9984"):
        self.driver = SmartChainDBDriver(bigchaindb_url)
        self.generate_keypair = self.driver.generate_keypair
        
    def create_and_submit_transfer(self, sender_idx: int, receiver_idx: int, asset_id: str = None) -> Tuple[bool, float, Dict[str, Any]]:
        """Create and submit a TRANSFER transaction (CREATE + TRANSFER)"""
        try:
            sender = self.generate_keypair()
            receiver = self.generate_keypair()
            
            if asset_id is None:
                asset_id = f"asset_{int(time.time())}_{sender_idx}"
            
            start_time = time.time()
            
            # First, create an asset
            create_tx_dict = self.driver.prepare_create_transaction(
                signers=sender.public_key,
                asset_data={
                    'machineIdentifier': f'machine_{asset_id}',
                    'capability': ['read', 'write'],
                    'capabilityParameters': {'type': 'test_asset', 'id': asset_id}
                },
                metadata={
                    'created_at': datetime.now().isoformat(),
                    'test_transaction': True
                }
            )
            
            create_tx_signed = self.driver.fulfill_transaction(create_tx_dict, sender.private_key)
            create_response = self.driver.send_transaction(create_tx_signed)
            
            end_time = time.time()
            latency_ms = (end_time - start_time) * 1000
            
            if create_response:
                logger.info(f"✅ CREATE transaction submitted: {create_response.get('id', 'Unknown')}")
                
                # Now create a TRANSFER transaction
                transfer_start = time.time()
                
                # Create proper TRANSFER input referencing the CREATE transaction
                transfer_input = {
                    "fulfillment": None,  # Will be filled by fulfill()
                    "fulfills": {
                        "output_index": 0,
                        "transaction_id": create_response['id'],
                    },
                    "owners_before": [sender.public_key],
                }
                
                transfer_tx_dict = self.driver.prepare_transfer_transaction(
                    asset_id=create_response['id'],
                    inputs=[transfer_input],
                    recipients=receiver.public_key,
                    metadata={
                        'transferred_at': datetime.now().isoformat(),
                        'test_transfer': True
                    }
                )
                
                transfer_tx_signed = self.driver.fulfill_transaction(transfer_tx_dict, sender.private_key)
                transfer_response = self.driver.send_transaction(transfer_tx_signed)
                
                transfer_end = time.time()
                total_latency_ms = (transfer_end - start_time) * 1000
                
                if transfer_response:
                    logger.info(f"✅ TRANSFER transaction submitted: {transfer_response.get('id', 'Unknown')}")
                    return True, total_latency_ms, {
                        'create_tx_id': create_response['id'],
                        'transfer_tx_id': transfer_response['id'],
                        'operation': 'TRANSFER',
                        'asset_id': asset_id
                    }
                else:
                    logger.error("❌ TRANSFER transaction failed")
                    return False, total_latency_ms, {"error": "Transfer failed"}
            else:
                logger.error("❌ CREATE transaction failed")
                return False, latency_ms, {"error": "Create failed"}
                
        except Exception as e:
            logger.error(f"❌ Error in transfer transaction: {e}")
            return False, 0, {"error": str(e)}
    
    def create_and_submit_advertisement(self, advertiser_idx: int) -> Tuple[bool, float, Dict[str, Any]]:
        """Create and submit an ADVERTISEMENT transaction"""
        try:
            advertiser = self.generate_keypair()
            
            start_time = time.time()
            
            # Generate proper sha3_hexdigest for advertisement asset
            asset_id = hashlib.sha3_256(f"advertisement_asset_{int(time.time())}_{advertiser_idx}".encode()).hexdigest()
            
            # Create ADVERTISEMENT transaction using SmartChainDB's internal method
            adv_tx_dict = self.driver.prepare_advertisement_transaction(
                signers=advertiser.public_key,
                asset_id=asset_id,
                metadata={
                    'status': 'OPEN',
                    'advertiser_public_key': advertiser.public_key,
                    'price': '100.50',
                    'expiry_date': (datetime.now().replace(hour=23, minute=59, second=59)).isoformat(),
                    'contact_info': 'test@example.com',
                    'location': 'Test City',
                    'created_at': datetime.now().isoformat(),
                    'test_advertisement': True
                }
            )
            
            adv_tx_signed = self.driver.fulfill_transaction(adv_tx_dict, advertiser.private_key)
            adv_response = self.driver.send_transaction(adv_tx_signed)
            
            end_time = time.time()
            latency_ms = (end_time - start_time) * 1000
            
            if adv_response:
                logger.info(f"✅ ADVERTISEMENT transaction submitted: {adv_response.get('id', 'Unknown')}")
                return True, latency_ms, {
                    'tx_id': adv_response['id'],
                    'operation': 'ADVERTISEMENT',
                    'asset_id': asset_id
                }
            else:
                logger.error("❌ ADVERTISEMENT transaction failed")
                return False, latency_ms, {"error": "Advertisement failed"}
                
        except Exception as e:
            logger.error(f"❌ Error creating advertisement: {e}")
            return False, 0, {"error": str(e)}
    
    def create_and_submit_create(self, sender_idx: int) -> Tuple[bool, float, Dict[str, Any]]:
        """Create and submit a CREATE transaction"""
        try:
            sender = self.generate_keypair()
            
            start_time = time.time()
            
            asset_id = f"asset_{int(time.time())}_{sender_idx}"
            
            create_tx_dict = self.driver.prepare_create_transaction(
                signers=sender.public_key,
                asset_data={
                    'machineIdentifier': f'machine_{asset_id}',
                    'capability': ['read', 'write'],
                    'capabilityParameters': {'type': 'test_asset', 'id': asset_id}
                },
                metadata={
                    'created_at': datetime.now().isoformat(),
                    'test_transaction': True
                }
            )
            
            create_tx_signed = self.driver.fulfill_transaction(create_tx_dict, sender.private_key)
            create_response = self.driver.send_transaction(create_tx_signed)
            
            end_time = time.time()
            latency_ms = (end_time - start_time) * 1000
            
            if create_response:
                logger.info(f"✅ CREATE transaction submitted: {create_response.get('id', 'Unknown')}")
                return True, latency_ms, {
                    'tx_id': create_response['id'],
                    'operation': 'CREATE',
                    'asset_id': asset_id
                }
            else:
                logger.error("❌ CREATE transaction failed")
                return False, latency_ms, {"error": "Create failed"}
                
        except Exception as e:
            logger.error(f"❌ Error creating asset: {e}")
            return False, 0, {"error": str(e)}

def run_real_experiment():
    """Run a real SmartChainDB experiment with all transaction types"""
    print("🚀 Starting SYNCHRONOUS Real SmartChainDB experiment...")
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    submitter = SyncRealSmartChainDBSubmitter()
    
    # Test all transaction types
    transaction_types = ['TRANSFER', 'ADVERTISEMENT', 'CREATE']
    results = []
    
    for i, tx_type in enumerate(transaction_types, 1):
        logger.info(f"Submitting transaction {i}/{len(transaction_types)}: {tx_type}")
        
        if tx_type == 'TRANSFER':
            success, latency, data = submitter.create_and_submit_transfer(i, i+1)
        elif tx_type == 'ADVERTISEMENT':
            success, latency, data = submitter.create_and_submit_advertisement(i)
        elif tx_type == 'CREATE':
            success, latency, data = submitter.create_and_submit_create(i)
        else:
            logger.error(f"Unknown transaction type: {tx_type}")
            continue
        
        results.append({
            'type': tx_type,
            'success': success,
            'latency_ms': latency,
            'data': data
        })
        
        if success:
            logger.info(f"✅ Transaction {i} succeeded: {latency:.2f}ms")
        else:
            logger.error(f"❌ Transaction {i} failed: {data.get('error', 'Unknown error')}")
        
        # Small delay between transactions
        time.sleep(0.5)
    
    # Calculate summary statistics
    successful_txs = sum(1 for r in results if r['success'])
    total_txs = len(results)
    success_rate = (successful_txs / total_txs) * 100 if total_txs > 0 else 0
    
    latencies = [r['latency_ms'] for r in results if r['success']]
    avg_latency = sum(latencies) / len(latencies) if latencies else 0
    
    logger.info(f"🎉 Real experiment completed: {success_rate:.1f}% success rate, {avg_latency:.2f}ms avg latency")
    
    # Print detailed results
    print("\n📊 DETAILED RESULTS:")
    for i, result in enumerate(results, 1):
        status = "✅ SUCCESS" if result['success'] else "❌ FAILED"
        print(f"  {i}. {result['type']}: {status} ({result['latency_ms']:.2f}ms)")
        if not result['success']:
            print(f"     Error: {result['data'].get('error', 'Unknown')}")
    
    return results

if __name__ == "__main__":
    results = run_real_experiment()
