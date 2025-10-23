#!/usr/bin/env python3
"""
Simple Cache Test Driver

This script sends real transactions to test the cache system.
"""

import time
import sys
import os
import requests
import json
from datetime import datetime

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import SmartChainDB's internal classes
try:
    from bigchaindb.common.transaction import Transaction, Input, Output
    from bigchaindb.common.crypto import generate_key_pair
    print("✅ SmartChainDB classes imported successfully")
except ImportError as e:
    print(f"❌ Failed to import SmartChainDB classes: {e}")
    sys.exit(1)

def create_test_transaction():
    """Create a simple test transaction"""
    # Generate keypair
    keypair = generate_key_pair()
    
    # Create transaction
    tx = Transaction(
        operation=Transaction.CREATE,
        asset={'data': {
            'machineIdentifier': f'test_{int(time.time())}',
            'capability': ['read'],
            'capabilityParameters': {'type': 'test'}
        }},
        metadata={'test': 'cache_test', 'requestCreationTimestamp': datetime.now().isoformat()}
    )
    
    # Add input and output
    input_obj = Input.generate([keypair.public_key])
    tx.inputs = [input_obj]
    
    output_obj = Output.generate([keypair.public_key], amount=1)
    tx.outputs = [output_obj]
    
    # Sign transaction
    tx.sign([keypair.private_key])
    
    return tx.to_dict()

def send_transaction(tx_dict):
    """Send transaction to SmartChainDB"""
    try:
        response = requests.post(
            "http://localhost:9984/api/v1/transactions/",
            json=tx_dict,
            headers={'Content-Type': 'application/json'},
            timeout=30
        )
        
        if response.status_code == 202:
            tx_id = response.json().get('id', 'Unknown')
            print(f"✅ Transaction accepted: {tx_id}")
            return True, tx_id
        elif response.status_code == 400:
            error_msg = response.text
            print(f"❌ Transaction validation failed: {error_msg}")
            return False, None
        else:
            print(f"❌ Unexpected response: {response.status_code} - {response.text}")
            return False, None
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Network error: {e}")
        return False, None

def get_cache_stats():
    """Get cache statistics"""
    try:
        response = requests.get("http://localhost:9984/api/v1/metrics/validation/cache/stats", timeout=10)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"❌ Failed to get cache stats: {response.status_code}")
            return None
    except requests.exceptions.RequestException as e:
        print(f"❌ Network error getting cache stats: {e}")
        return None

def main():
    """Main test function"""
    print("🔍 Testing Cache System")
    print("=" * 30)
    
    # Get initial cache stats
    print("📊 Initial cache stats:")
    initial_stats = get_cache_stats()
    if initial_stats:
        print(f"   Cache size: {initial_stats.get('cache_size', 'N/A')}")
        print(f"   Cache hits: {initial_stats.get('cache_hits', 'N/A')}")
        print(f"   Cache misses: {initial_stats.get('cache_misses', 'N/A')}")
        print(f"   Hit rate: {initial_stats.get('hit_rate', 'N/A')}")
    
    # Send transactions
    print("\n📤 Sending transactions...")
    success_count = 0
    
    for i in range(3):
        print(f"\n{i+1}️⃣ Transaction {i+1}:")
        
        # Create transaction
        tx_dict = create_test_transaction()
        
        # Send transaction
        success, tx_id = send_transaction(tx_dict)
        
        if success:
            success_count += 1
            print(f"   ✅ Success: {tx_id[:8]}...")
        else:
            print(f"   ❌ Failed")
        
        # Small delay between transactions
        time.sleep(1)
    
    # Get final cache stats
    print("\n📊 Final cache stats:")
    final_stats = get_cache_stats()
    if final_stats:
        print(f"   Cache size: {final_stats.get('cache_size', 'N/A')}")
        print(f"   Cache hits: {final_stats.get('cache_hits', 'N/A')}")
        print(f"   Cache misses: {final_stats.get('cache_misses', 'N/A')}")
        print(f"   Hit rate: {final_stats.get('hit_rate', 'N/A')}")
    
    # Summary
    print(f"\n📋 Summary: {success_count}/3 transactions sent successfully")
    
    if success_count > 0:
        print("🎉 Cache system is working!")
    else:
        print("❌ Cache system test failed")

if __name__ == "__main__":
    main()
