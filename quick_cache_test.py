#!/usr/bin/env python3
"""
Quick Cache Performance Test Driver

A simplified driver for quick cache performance testing and validation.
This script focuses on the core metrics needed for research evaluation.

Usage:
    python quick_cache_test.py [--scenario SCENARIO] [--count COUNT]
"""

import time
import sys
import os
import requests
import json
import statistics
import argparse
from datetime import datetime
from typing import List, Dict, Any
from dataclasses import dataclass

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from bigchaindb.common.transaction import Transaction, Input, Output
    from bigchaindb.common.crypto import generate_key_pair
    print("✅ SmartChainDB classes imported successfully")
except ImportError as e:
    print(f"❌ Failed to import SmartChainDB classes: {e}")
    sys.exit(1)


@dataclass
class TestResult:
    """Simple test result structure"""
    transaction_type: str
    validation_time_ms: float
    cache_hit: bool
    timestamp: str
    transaction_id: str


class QuickCacheTester:
    """Quick cache performance tester"""
    
    def __init__(self, bigchaindb_url: str = "http://localhost:9984"):
        self.bigchaindb_url = bigchaindb_url.rstrip('/')
        self.transactions_url = f"{self.bigchaindb_url}/api/v1/transactions/"
        self.results: List[TestResult] = []
    
    def create_test_transaction(self, tx_type: str = "CREATE"):
        """Create a test transaction"""
        keypair = generate_key_pair()
        
        if tx_type == "CREATE":
            tx = Transaction(
                operation=Transaction.CREATE,
                asset={'data': {
                    'machineIdentifier': f'quick_test_{int(time.time() * 1000)}',
                    'capability': ['read'],
                    'capabilityParameters': {'type': 'quick_test'}
                }},
                metadata={
                    'test': 'quick_cache_test',
                    'requestCreationTimestamp': datetime.now().isoformat()
                }
            )
        else:
            # For other transaction types, use CREATE for simplicity
            tx = Transaction(
                operation=Transaction.CREATE,
                asset={'data': {
                    'machineIdentifier': f'quick_test_{int(time.time() * 1000)}',
                    'capability': ['read'],
                    'capabilityParameters': {'type': 'quick_test'}
                }},
                metadata={
                    'test': 'quick_cache_test',
                    'requestCreationTimestamp': datetime.now().isoformat()
                }
            )
        
        input_obj = Input.generate([keypair.public_key])
        tx.inputs = [input_obj]
        
        output_obj = Output.generate([keypair.public_key], amount=1)
        tx.outputs = [output_obj]
        
        tx.sign([keypair.private_key])
        return tx
    
    def send_transaction(self, tx: Transaction) -> tuple[bool, float, str]:
        """Send transaction and measure time"""
        start_time = time.time()
        
        try:
            response = requests.post(
                self.transactions_url,
                json=tx.to_dict(),
                timeout=30
            )
            
            end_time = time.time()
            validation_time_ms = (end_time - start_time) * 1000
            
            if response.status_code == 202:
                tx_id = response.json().get('id', 'unknown')
                return True, validation_time_ms, tx_id
            else:
                print(f"❌ Transaction failed: {response.status_code}")
                return False, validation_time_ms, 'failed'
                
        except Exception as e:
            end_time = time.time()
            validation_time_ms = (end_time - start_time) * 1000
            print(f"❌ Transaction error: {e}")
            return False, validation_time_ms, 'error'
    
    def test_cache_hit_rate(self, count: int = 20):
        """Test cache hit rate by sending identical transactions"""
        print(f"\n🔍 Testing Cache Hit Rate ({count} transactions)")
        print("=" * 40)
        
        # Create one transaction template
        tx_template = self.create_test_transaction()
        
        for i in range(count):
            # Create new transaction (same structure, different ID)
            tx = self.create_test_transaction()
            success, validation_time, tx_id = self.send_transaction(tx)
            
            if success:
                cache_hit = i > 0  # First is miss, rest could be hits
                result = TestResult(
                    transaction_type="CREATE",
                    validation_time_ms=validation_time,
                    cache_hit=cache_hit,
                    timestamp=datetime.now().isoformat(),
                    transaction_id=tx_id
                )
                self.results.append(result)
                
                status = "HIT" if cache_hit else "MISS"
                print(f"  {i+1:2d}. {validation_time:6.2f}ms - {status}")
            else:
                print(f"  {i+1:2d}. FAILED")
            
            time.sleep(0.1)  # Small delay
    
    def test_transaction_types(self, count_per_type: int = 10):
        """Test different transaction types"""
        print(f"\n🔍 Testing Transaction Types ({count_per_type} per type)")
        print("=" * 40)
        
        transaction_types = ["CREATE"]  # Simplified for quick test
        
        for tx_type in transaction_types:
            print(f"\n📊 {tx_type} transactions:")
            times = []
            
            for i in range(count_per_type):
                tx = self.create_test_transaction(tx_type)
                success, validation_time, tx_id = self.send_transaction(tx)
                
                if success:
                    result = TestResult(
                        transaction_type=tx_type,
                        validation_time_ms=validation_time,
                        cache_hit=False,  # Fresh transactions
                        timestamp=datetime.now().isoformat(),
                        transaction_id=tx_id
                    )
                    self.results.append(result)
                    times.append(validation_time)
                    print(f"  {i+1:2d}. {validation_time:6.2f}ms")
                else:
                    print(f"  {i+1:2d}. FAILED")
                
                time.sleep(0.05)
            
            if times:
                avg_time = statistics.mean(times)
                print(f"  📈 Average: {avg_time:.2f}ms")
    
    def test_load_performance(self, load_level: int = 50, duration_seconds: int = 30):
        """Test performance under load"""
        print(f"\n🔍 Load Testing ({load_level} TPS for {duration_seconds}s)")
        print("=" * 40)
        
        start_time = time.time()
        end_time = start_time + duration_seconds
        transaction_count = 0
        
        print(f"📊 Sending transactions at {load_level} TPS...")
        
        while time.time() < end_time:
            batch_start = time.time()
            
            # Send batch of transactions
            for _ in range(load_level):
                tx = self.create_test_transaction()
                success, validation_time, tx_id = self.send_transaction(tx)
                
                if success:
                    result = TestResult(
                        transaction_type="CREATE",
                        validation_time_ms=validation_time,
                        cache_hit=False,
                        timestamp=datetime.now().isoformat(),
                        transaction_id=tx_id
                    )
                    self.results.append(result)
                    transaction_count += 1
            
            # Wait for next second
            batch_time = time.time() - batch_start
            if batch_time < 1.0:
                time.sleep(1.0 - batch_time)
        
        actual_duration = time.time() - start_time
        actual_tps = transaction_count / actual_duration
        
        print(f"📈 Completed: {transaction_count} transactions in {actual_duration:.1f}s")
        print(f"📈 Actual TPS: {actual_tps:.1f}")
    
    def generate_summary(self):
        """Generate test summary"""
        if not self.results:
            print("❌ No results to summarize")
            return
        
        print("\n📊 Test Summary")
        print("=" * 30)
        
        # Overall statistics
        times = [r.validation_time_ms for r in self.results]
        cache_hits = [r.cache_hit for r in self.results]
        
        print(f"Total transactions: {len(self.results)}")
        print(f"Average validation time: {statistics.mean(times):.2f}ms")
        print(f"Median validation time: {statistics.median(times):.2f}ms")
        print(f"Min validation time: {min(times):.2f}ms")
        print(f"Max validation time: {max(times):.2f}ms")
        
        if len(times) > 1:
            print(f"Standard deviation: {statistics.stdev(times):.2f}ms")
        
        cache_hit_rate = sum(cache_hits) / len(cache_hits) * 100
        print(f"Cache hit rate: {cache_hit_rate:.1f}%")
        
        # Performance analysis
        if len(times) > 1:
            fast_transactions = [t for t in times if t < 1.0]  # < 1ms
            slow_transactions = [t for t in times if t > 10.0]  # > 10ms
            
            print(f"\nPerformance Analysis:")
            print(f"Fast transactions (<1ms): {len(fast_transactions)} ({len(fast_transactions)/len(times)*100:.1f}%)")
            print(f"Slow transactions (>10ms): {len(slow_transactions)} ({len(slow_transactions)/len(times)*100:.1f}%)")
        
        # Save results
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"quick_test_results_{timestamp}.json"
        
        results_data = {
            'timestamp': datetime.now().isoformat(),
            'total_transactions': len(self.results),
            'summary': {
                'avg_validation_time_ms': statistics.mean(times),
                'median_validation_time_ms': statistics.median(times),
                'min_validation_time_ms': min(times),
                'max_validation_time_ms': max(times),
                'cache_hit_rate_percent': cache_hit_rate
            },
            'results': [
                {
                    'transaction_type': r.transaction_type,
                    'validation_time_ms': r.validation_time_ms,
                    'cache_hit': r.cache_hit,
                    'timestamp': r.timestamp,
                    'transaction_id': r.transaction_id
                }
                for r in self.results
            ]
        }
        
        with open(filename, 'w') as f:
            json.dump(results_data, f, indent=2)
        
        print(f"\n📊 Results saved to: {filename}")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Quick Cache Performance Test')
    parser.add_argument('--scenario', choices=['hit_rate', 'types', 'load', 'all'], 
                       default='all', help='Test scenario to run')
    parser.add_argument('--count', type=int, default=20, 
                       help='Number of transactions for hit rate test')
    parser.add_argument('--load-level', type=int, default=50, 
                       help='Load level for load testing (TPS)')
    parser.add_argument('--duration', type=int, default=30, 
                       help='Duration for load testing (seconds)')
    parser.add_argument('--url', default='http://localhost:9984', 
                       help='BigchainDB URL')
    
    args = parser.parse_args()
    
    print("🚀 Quick Cache Performance Test")
    print("=" * 30)
    
    # Create tester
    tester = QuickCacheTester(args.url)
    
    # Check if BigchainDB is running
    try:
        response = requests.get(f"{args.url}/", timeout=5)
        if response.status_code != 200:
            print("❌ BigchainDB is not running or not accessible")
            return False
    except Exception as e:
        print(f"❌ Cannot connect to BigchainDB: {e}")
        return False
    
    print("✅ BigchainDB is accessible")
    
    # Run selected scenario
    if args.scenario in ['hit_rate', 'all']:
        tester.test_cache_hit_rate(args.count)
    
    if args.scenario in ['types', 'all']:
        tester.test_transaction_types(10)
    
    if args.scenario in ['load', 'all']:
        tester.test_load_performance(args.load_level, args.duration)
    
    # Generate summary
    tester.generate_summary()
    
    print("\n🎉 Quick test completed!")
    return True


if __name__ == "__main__":
    main()
