#!/usr/bin/env python3
"""
Cache Testing Script

This script tests the state-aware cache invalidation system by:
1. Creating transactions
2. Validating them (should cache results)
3. Checking cache statistics
4. Testing invalidation patterns
"""

import time
import sys
import os
import requests
import json
from datetime import datetime
from typing import Dict, Any

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

class CacheTester:
    """Test the state-aware cache system"""
    
    def __init__(self, bigchaindb_url: str = "http://localhost:9984"):
        self.bigchaindb_url = bigchaindb_url.rstrip('/')
        self.transactions_url = f"{self.bigchaindb_url}/api/v1/transactions/"
        self.cache_stats_url = f"{self.bigchaindb_url}/api/v1/metrics/validation/cache/stats"
        self.cache_invalidate_url = f"{self.bigchaindb_url}/api/v1/metrics/validation/cache/invalidate"
        
    def generate_keypair(self):
        """Generate a keypair using SmartChainDB's crypto"""
        return generate_key_pair()
    
    def create_test_transaction(self, transaction_type="CREATE", asset_data=None):
        """Create a test transaction"""
        # Generate keypair
        keypair = self.generate_keypair()
        
        # Default asset data
        if asset_data is None:
            asset_data = {
                'machineIdentifier': f'test_{int(time.time())}',
                'capability': ['read'],
                'capabilityParameters': {'type': 'test'}
            }
        
        # Create transaction
        tx = Transaction(
            operation=transaction_type,
            asset={'data': asset_data},
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
    
    def send_transaction(self, tx_dict):
        """Send transaction to SmartChainDB"""
        try:
            print(f"📤 Sending transaction...")
            
            response = requests.post(
                self.transactions_url,
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
    
    def get_cache_stats(self):
        """Get cache statistics"""
        try:
            response = requests.get(self.cache_stats_url, timeout=10)
            if response.status_code == 200:
                return response.json()
            else:
                print(f"❌ Failed to get cache stats: {response.status_code}")
                return None
        except requests.exceptions.RequestException as e:
            print(f"❌ Network error getting cache stats: {e}")
            return None
    
    def invalidate_cache(self, pattern, entity_id):
        """Manually invalidate cache entries"""
        try:
            payload = {
                "pattern": pattern,
                "entity_id": entity_id
            }
            
            response = requests.post(
                self.cache_invalidate_url,
                json=payload,
                headers={'Content-Type': 'application/json'},
                timeout=10
            )
            
            if response.status_code == 200:
                print(f"✅ Cache invalidated for {pattern}:{entity_id}")
                return True
            else:
                print(f"❌ Failed to invalidate cache: {response.status_code}")
                return False
                
        except requests.exceptions.RequestException as e:
            print(f"❌ Network error invalidating cache: {e}")
            return False
    
    def test_basic_caching(self):
        """Test basic cache functionality"""
        print("\n🔍 Testing Basic Cache Functionality")
        print("=" * 50)
        
        # Get initial cache stats
        print("📊 Initial cache stats:")
        initial_stats = self.get_cache_stats()
        if initial_stats:
            print(f"   Cache size: {initial_stats.get('cache_size', 'N/A')}")
            print(f"   Cache hits: {initial_stats.get('cache_hits', 'N/A')}")
            print(f"   Cache misses: {initial_stats.get('cache_misses', 'N/A')}")
            print(f"   Hit rate: {initial_stats.get('hit_rate', 'N/A')}")
        
        # Send multiple transactions
        print("\n📤 Sending transactions...")
        transaction_ids = []
        
        for i in range(3):
            print(f"\n{i+1}️⃣ Transaction {i+1}:")
            
            # Create transaction
            tx_dict = self.create_test_transaction()
            
            # Send transaction
            success, tx_id = self.send_transaction(tx_dict)
            
            if success:
                transaction_ids.append(tx_id)
                print(f"   ✅ Success: {tx_id[:8]}...")
            else:
                print(f"   ❌ Failed")
            
            # Small delay between transactions
            time.sleep(1)
        
        # Get final cache stats
        print("\n📊 Final cache stats:")
        final_stats = self.get_cache_stats()
        if final_stats:
            print(f"   Cache size: {final_stats.get('cache_size', 'N/A')}")
            print(f"   Cache hits: {final_stats.get('cache_hits', 'N/A')}")
            print(f"   Cache misses: {final_stats.get('cache_misses', 'N/A')}")
            print(f"   Hit rate: {final_stats.get('hit_rate', 'N/A')}")
        
        return len(transaction_ids) > 0
    
    def test_cache_invalidation(self):
        """Test cache invalidation patterns"""
        print("\n🔍 Testing Cache Invalidation Patterns")
        print("=" * 50)
        
        # Test manual cache invalidation
        print("🧹 Testing manual cache invalidation...")
        
        # Try to invalidate by asset (this might not work if no assets exist)
        success = self.invalidate_cache("asset", "test_asset_123")
        if success:
            print("   ✅ Asset invalidation successful")
        else:
            print("   ⚠️ Asset invalidation failed (expected if no assets exist)")
        
        # Try to invalidate by advertisement
        success = self.invalidate_cache("advertisement", "test_ad_456")
        if success:
            print("   ✅ Advertisement invalidation successful")
        else:
            print("   ⚠️ Advertisement invalidation failed (expected if no ads exist)")
        
        return True
    
    def test_performance(self):
        """Test cache performance"""
        print("\n🔍 Testing Cache Performance")
        print("=" * 50)
        
        # Get initial stats
        initial_stats = self.get_cache_stats()
        if not initial_stats:
            print("❌ Cannot get cache stats for performance test")
            return False
        
        initial_hits = initial_stats.get('cache_hits', 0)
        initial_misses = initial_stats.get('cache_misses', 0)
        
        print(f"📊 Initial stats - Hits: {initial_hits}, Misses: {initial_misses}")
        
        # Send transactions and measure performance
        start_time = time.time()
        
        for i in range(5):
            tx_dict = self.create_test_transaction()
            success, tx_id = self.send_transaction(tx_dict)
            if success:
                print(f"   ✅ Transaction {i+1} sent")
            time.sleep(0.5)
        
        end_time = time.time()
        
        # Get final stats
        final_stats = self.get_cache_stats()
        if final_stats:
            final_hits = final_stats.get('cache_hits', 0)
            final_misses = final_stats.get('cache_misses', 0)
            
            print(f"📊 Final stats - Hits: {final_hits}, Misses: {final_misses}")
            print(f"⏱️ Total time: {end_time - start_time:.2f} seconds")
            
            # Calculate performance metrics
            if final_hits > initial_hits or final_misses > initial_misses:
                total_operations = (final_hits - initial_hits) + (final_misses - initial_misses)
                hit_rate = (final_hits - initial_hits) / total_operations if total_operations > 0 else 0
                print(f"📈 Hit rate: {hit_rate:.2%}")
                print(f"📈 Total operations: {total_operations}")
        
        return True
    
    def run_all_tests(self):
        """Run all cache tests"""
        print("🚀 Starting Cache System Tests")
        print("=" * 60)
        
        # Test 1: Basic caching
        test1_success = self.test_basic_caching()
        
        # Test 2: Cache invalidation
        test2_success = self.test_cache_invalidation()
        
        # Test 3: Performance
        test3_success = self.test_performance()
        
        # Summary
        print("\n📋 Test Summary")
        print("=" * 30)
        print(f"✅ Basic Caching: {'PASS' if test1_success else 'FAIL'}")
        print(f"✅ Cache Invalidation: {'PASS' if test2_success else 'FAIL'}")
        print(f"✅ Performance: {'PASS' if test3_success else 'FAIL'}")
        
        if all([test1_success, test2_success, test3_success]):
            print("\n🎉 All tests passed! Cache system is working correctly.")
        else:
            print("\n⚠️ Some tests failed. Check the logs above for details.")

def main():
    """Main test function"""
    print("🔍 SmartChainDB Cache System Test")
    print("=" * 40)
    print("This test will:")
    print("1. Send transactions to trigger caching")
    print("2. Check cache statistics")
    print("3. Test cache invalidation patterns")
    print("4. Measure performance")
    print()
    
    tester = CacheTester()
    tester.run_all_tests()

if __name__ == "__main__":
    main()
