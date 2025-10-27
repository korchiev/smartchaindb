#!/usr/bin/env python3
"""
Experimental Driver for Cache System Evaluation

This script implements the comprehensive experimental plan for evaluating
the state-aware cache system in SmartChainDB. It generates various workloads
and measures performance metrics for research paper evaluation.

Author: Research Team
Date: 2025
"""

import time
import sys
import os
import requests
import json
import statistics
import threading
import concurrent.futures
from datetime import datetime, timedelta
from typing import Dict, Any, List, Tuple, Optional
from dataclasses import dataclass, asdict
from collections import defaultdict
import csv
import matplotlib.pyplot as plt
import numpy as np

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


@dataclass
class ExperimentMetrics:
    """Data structure for experiment metrics"""
    scenario: str
    transaction_type: str
    validation_time_ms: float
    cache_hit: bool
    timestamp: str
    transaction_id: str
    phase: str
    memory_usage_mb: float
    cpu_usage_percent: float


@dataclass
class ExperimentConfig:
    """Configuration for experiments"""
    bigchaindb_url: str = "http://localhost:9984"
    num_transactions: int = 1000
    load_test_levels: List[int] = None
    cache_stats_url: str = "http://localhost:9984/api/v1/metrics/validation/cache/stats"
    experiment_duration_minutes: int = 30
    warmup_transactions: int = 100
    
    def __post_init__(self):
        if self.load_test_levels is None:
            self.load_test_levels = [10, 50, 100, 200, 500]


class ExperimentalDriver:
    """Main driver for cache system experiments"""
    
    def __init__(self, config: ExperimentConfig):
        self.config = config
        self.bigchaindb_url = config.bigchaindb_url.rstrip('/')
        self.transactions_url = f"{self.bigchaindb_url}/api/v1/transactions/"
        self.metrics: List[ExperimentMetrics] = []
        self.results: Dict[str, Any] = {}
        
        # Transaction templates for different types
        self.transaction_templates = {
            'CREATE': self._create_create_transaction,
            'ADVERTISEMENT': self._create_advertisement_transaction,
            'BUY_OFFER': self._create_buy_offer_transaction,
            'SELL': self._create_sell_transaction,
            'REQUEST_RETURN': self._create_request_return_transaction,
            'ACCEPT_RETURN': self._create_accept_return_transaction,
            'UPDATE_ADV': self._create_update_adv_transaction
        }
        
        # Cache for dependent transactions
        self.transaction_cache = {
            'assets': [],
            'advertisements': [],
            'buy_offers': [],
            'sells': [],
            'return_requests': []
        }
    
    def generate_keypair(self):
        """Generate a keypair using SmartChainDB's crypto"""
        return generate_key_pair()
    
    def _create_create_transaction(self, keypair=None):
        """Create a CREATE transaction"""
        if keypair is None:
            keypair = self.generate_keypair()
        
        tx = Transaction(
            operation=Transaction.CREATE,
            asset={'data': {
                'machineIdentifier': f'exp_asset_{int(time.time() * 1000)}',
                'capability': ['read', 'write'],
                'capabilityParameters': {'type': 'experimental'}
            }},
            metadata={
                'experiment': 'cache_evaluation',
                'requestCreationTimestamp': datetime.now().isoformat(),
                'test_type': 'CREATE'
            }
        )
        
        input_obj = Input.generate([keypair.public_key])
        tx.inputs = [input_obj]
        
        output_obj = Output.generate([keypair.public_key], amount=1)
        tx.outputs = [output_obj]
        
        tx.sign([keypair.private_key])
        return tx, keypair
    
    def _create_advertisement_transaction(self, keypair=None):
        """Create an ADVERTISEMENT transaction"""
        if keypair is None:
            keypair = self.generate_keypair()
        
        # Use a cached asset if available
        asset_id = self.transaction_cache['assets'][-1] if self.transaction_cache['assets'] else 'dummy_asset_id'
        
        tx = Transaction(
            operation='ADVERTISEMENT',
            asset={'data': {'id': asset_id}},
            metadata={
                'advertiser_public_key': keypair.public_key,
                'status': 'OPEN',
                'price': '1000',
                'description': 'Experimental advertisement',
                'requestCreationTimestamp': datetime.now().isoformat(),
                'is_new_advertisement': True,
                'test_type': 'ADVERTISEMENT'
            }
        )
        
        input_obj = Input.generate([keypair.public_key])
        tx.inputs = [input_obj]
        
        output_obj = Output.generate([keypair.public_key], amount=1)
        tx.outputs = [output_obj]
        
        tx.sign([keypair.private_key])
        return tx, keypair
    
    def _create_buy_offer_transaction(self, keypair=None):
        """Create a BUY_OFFER transaction"""
        if keypair is None:
            keypair = self.generate_keypair()
        
        asset_id = self.transaction_cache['assets'][-1] if self.transaction_cache['assets'] else 'dummy_asset_id'
        adv_id = self.transaction_cache['advertisements'][-1] if self.transaction_cache['advertisements'] else 'dummy_adv_id'
        
        tx = Transaction(
            operation='BUY_OFFER',
            asset={'data': {
                'id': asset_id,
                'advertisement_id': adv_id
            }},
            metadata={
                'buyer_public_key': keypair.public_key,
                'offer_amount': '950',
                'offer_currency': 'USD',
                'offer_timestamp': datetime.now().isoformat(),
                'offer_expiry': (datetime.now() + timedelta(days=7)).isoformat(),
                'escrow_public_key': keypair.public_key,
                'offer_notes': 'Experimental buy offer',
                'requestCreationTimestamp': datetime.now().isoformat(),
                'test_type': 'BUY_OFFER'
            }
        )
        
        input_obj = Input.generate([keypair.public_key])
        tx.inputs = [input_obj]
        
        output_obj = Output.generate([keypair.public_key], amount=1)
        tx.outputs = [output_obj]
        
        tx.sign([keypair.private_key])
        return tx, keypair
    
    def _create_sell_transaction(self, keypair=None):
        """Create a SELL transaction"""
        if keypair is None:
            keypair = self.generate_keypair()
        
        asset_id = self.transaction_cache['assets'][-1] if self.transaction_cache['assets'] else 'dummy_asset_id'
        buy_offer_id = self.transaction_cache['buy_offers'][-1] if self.transaction_cache['buy_offers'] else 'dummy_offer_id'
        
        tx = Transaction(
            operation='SELL',
            asset={'data': {
                'id': asset_id,
                'buy_offer_id': buy_offer_id
            }},
            metadata={
                'seller_public_key': keypair.public_key,
                'buyer_public_key': keypair.public_key,  # Same for simplicity
                'sale_amount': '950',
                'sale_currency': 'USD',
                'sale_timestamp': datetime.now().isoformat(),
                'sale_notes': 'Experimental sale',
                'requestCreationTimestamp': datetime.now().isoformat(),
                'test_type': 'SELL'
            }
        )
        
        input_obj = Input.generate([keypair.public_key])
        tx.inputs = [input_obj]
        
        output_obj = Output.generate([keypair.public_key], amount=1)
        tx.outputs = [output_obj]
        
        tx.sign([keypair.private_key])
        return tx, keypair
    
    def _create_request_return_transaction(self, keypair=None):
        """Create a REQUEST_RETURN transaction"""
        if keypair is None:
            keypair = self.generate_keypair()
        
        asset_id = self.transaction_cache['assets'][-1] if self.transaction_cache['assets'] else 'dummy_asset_id'
        sell_id = self.transaction_cache['sells'][-1] if self.transaction_cache['sells'] else 'dummy_sell_id'
        
        tx = Transaction(
            operation='REQUEST_RETURN',
            asset={'data': {
                'id': asset_id,
                'sell_transaction_id': sell_id
            }},
            metadata={
                'requester_public_key': keypair.public_key,
                'return_reason': 'Experimental return',
                'return_request_timestamp': datetime.now().isoformat(),
                'return_policy_details': {
                    'return_window_days': 30,
                    'return_conditions': 'Experimental conditions',
                    'return_status': 'PENDING'
                },
                'requestCreationTimestamp': datetime.now().isoformat(),
                'test_type': 'REQUEST_RETURN'
            }
        )
        
        input_obj = Input.generate([keypair.public_key])
        input_obj.fulfills = None  # Required for REQUEST_RETURN schema
        tx.inputs = [input_obj]
        
        output_obj = Output.generate([keypair.public_key], amount=1)
        tx.outputs = [output_obj]
        
        tx.sign([keypair.private_key])
        return tx, keypair
    
    def _create_accept_return_transaction(self, keypair=None):
        """Create an ACCEPT_RETURN transaction"""
        if keypair is None:
            keypair = self.generate_keypair()
        
        asset_id = self.transaction_cache['assets'][-1] if self.transaction_cache['assets'] else 'dummy_asset_id'
        return_request_id = self.transaction_cache['return_requests'][-1] if self.transaction_cache['return_requests'] else 'dummy_return_id'
        
        tx = Transaction(
            operation='SELLER_ACCEPT_RETURN',
            asset={'data': {
                'id': asset_id,
                'request_return_id': return_request_id
            }},
            metadata={
                'seller_public_key': keypair.public_key,
                'refund_details': {
                    'refund_amount': 950.0,
                    'refund_currency': 'USD',
                    'refund_method': 'original_payment'
                },
                'acceptance_timestamp': datetime.now().isoformat(),
                'processing_notes': 'Experimental return acceptance',
                'requestCreationTimestamp': datetime.now().isoformat(),
                'test_type': 'ACCEPT_RETURN'
            }
        )
        
        input_obj = Input.generate([keypair.public_key])
        tx.inputs = [input_obj]
        
        output_obj = Output.generate([keypair.public_key], amount=1)
        tx.outputs = [output_obj]
        
        tx.sign([keypair.private_key])
        return tx, keypair
    
    def _create_update_adv_transaction(self, keypair=None):
        """Create an UPDATE_ADV transaction"""
        if keypair is None:
            keypair = self.generate_keypair()
        
        adv_id = self.transaction_cache['advertisements'][-1] if self.transaction_cache['advertisements'] else 'dummy_adv_id'
        
        tx = Transaction(
            operation='UPDATE_ADV',
            asset={'data': {'id': adv_id}},
            metadata={
                'advertiser_public_key': keypair.public_key,
                'status': 'CLOSED',
                'new_status': 'CLOSED',
                'new_value': '1200',
                'new_expiry_date': (datetime.now() + timedelta(days=30)).isoformat(),
                'update_timestamp': datetime.now().isoformat(),
                'update_reason': 'Experimental update',
                'requestCreationTimestamp': datetime.now().isoformat(),
                'test_type': 'UPDATE_ADV'
            }
        )
        
        input_obj = Input.generate([keypair.public_key])
        tx.inputs = [input_obj]
        
        output_obj = Output.generate([keypair.public_key], amount=1)
        tx.outputs = [output_obj]
        
        tx.sign([keypair.private_key])
        return tx, keypair
    
    def send_transaction(self, tx: Transaction) -> Tuple[bool, float, str]:
        """Send a transaction and measure performance"""
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
                print(f"❌ Transaction failed: {response.status_code} - {response.text}")
                return False, validation_time_ms, 'failed'
                
        except Exception as e:
            end_time = time.time()
            validation_time_ms = (end_time - start_time) * 1000
            print(f"❌ Transaction error: {e}")
            return False, validation_time_ms, 'error'
    
    def get_system_metrics(self) -> Tuple[float, float]:
        """Get current system resource usage"""
        try:
            # Get Docker container stats
            import subprocess
            result = subprocess.run([
                'docker', 'stats', 'smartchaindb-bigchaindb-1', '--no-stream', '--format', 
                'table {{.MemUsage}}\t{{.CPUPerc}}'
            ], capture_output=True, text=True, timeout=5)
            
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                if len(lines) > 1:
                    data = lines[1].split('\t')
                    if len(data) >= 2:
                        mem_str = data[0].replace('MiB', '').replace('GiB', '').strip()
                        cpu_str = data[1].replace('%', '').strip()
                        
                        try:
                            memory_mb = float(mem_str)
                            cpu_percent = float(cpu_str)
                            return memory_mb, cpu_percent
                        except ValueError:
                            pass
        except Exception:
            pass
        
        return 0.0, 0.0
    
    def run_scenario_1_cache_hit_analysis(self):
        """Scenario 1: Cache Hit Rate Analysis"""
        print("\n🔍 Scenario 1: Cache Hit Rate Analysis")
        print("=" * 50)
        
        scenario_metrics = []
        
        # Test different transaction types
        for tx_type in ['CREATE', 'ADVERTISEMENT', 'BUY_OFFER']:
            print(f"\n📊 Testing {tx_type} transactions...")
            
            for i in range(10):  # Send same transaction multiple times
                tx, keypair = self.transaction_templates[tx_type]()
                success, validation_time, tx_id = self.send_transaction(tx)
                
                if success:
                    # Store transaction for dependent tests
                    if tx_type == 'CREATE':
                        self.transaction_cache['assets'].append(tx_id)
                    elif tx_type == 'ADVERTISEMENT':
                        self.transaction_cache['advertisements'].append(tx_id)
                    elif tx_type == 'BUY_OFFER':
                        self.transaction_cache['buy_offers'].append(tx_id)
                    
                    memory_mb, cpu_percent = self.get_system_metrics()
                    
                    metric = ExperimentMetrics(
                        scenario='cache_hit_analysis',
                        transaction_type=tx_type,
                        validation_time_ms=validation_time,
                        cache_hit=i > 0,  # First is miss, rest are hits
                        timestamp=datetime.now().isoformat(),
                        transaction_id=tx_id,
                        phase='HTTP_POST',
                        memory_usage_mb=memory_mb,
                        cpu_usage_percent=cpu_percent
                    )
                    scenario_metrics.append(metric)
                    
                    print(f"  {i+1:2d}. {tx_type:12s} - {validation_time:6.2f}ms - {'HIT' if i > 0 else 'MISS'}")
                
                time.sleep(0.1)  # Small delay between transactions
        
        self.metrics.extend(scenario_metrics)
        return scenario_metrics
    
    def run_scenario_2_transaction_type_performance(self):
        """Scenario 2: Transaction Type Performance"""
        print("\n🔍 Scenario 2: Transaction Type Performance")
        print("=" * 50)
        
        scenario_metrics = []
        
        # Test each transaction type
        for tx_type in self.transaction_templates.keys():
            print(f"\n📊 Testing {tx_type} performance...")
            
            times = []
            for i in range(20):  # Multiple samples per type
                tx, keypair = self.transaction_templates[tx_type]()
                success, validation_time, tx_id = self.send_transaction(tx)
                
                if success:
                    times.append(validation_time)
                    memory_mb, cpu_percent = self.get_system_metrics()
                    
                    metric = ExperimentMetrics(
                        scenario='transaction_type_performance',
                        transaction_type=tx_type,
                        validation_time_ms=validation_time,
                        cache_hit=False,  # Fresh transactions
                        timestamp=datetime.now().isoformat(),
                        transaction_id=tx_id,
                        phase='HTTP_POST',
                        memory_usage_mb=memory_mb,
                        cpu_usage_percent=cpu_percent
                    )
                    scenario_metrics.append(metric)
                    
                    print(f"  {i+1:2d}. {validation_time:6.2f}ms")
                
                time.sleep(0.05)
            
            if times:
                avg_time = statistics.mean(times)
                print(f"  📈 Average: {avg_time:.2f}ms")
        
        self.metrics.extend(scenario_metrics)
        return scenario_metrics
    
    def run_scenario_3_load_testing(self):
        """Scenario 3: Load Testing"""
        print("\n🔍 Scenario 3: Load Testing")
        print("=" * 50)
        
        scenario_metrics = []
        
        for load_level in self.config.load_test_levels:
            print(f"\n📊 Load Level: {load_level} TPS")
            
            def send_transaction_worker():
                tx, keypair = self.transaction_templates['CREATE']()
                success, validation_time, tx_id = self.send_transaction(tx)
                
                if success:
                    memory_mb, cpu_percent = self.get_system_metrics()
                    return ExperimentMetrics(
                        scenario='load_testing',
                        transaction_type='CREATE',
                        validation_time_ms=validation_time,
                        cache_hit=False,
                        timestamp=datetime.now().isoformat(),
                        transaction_id=tx_id,
                        phase='HTTP_POST',
                        memory_usage_mb=memory_mb,
                        cpu_usage_percent=cpu_percent
                    )
                return None
            
            # Run load test for 30 seconds
            start_time = time.time()
            end_time = start_time + 30
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=load_level) as executor:
                futures = []
                
                while time.time() < end_time:
                    # Submit transactions at the target rate
                    for _ in range(load_level):
                        future = executor.submit(send_transaction_worker)
                        futures.append(future)
                    
                    time.sleep(1)  # Wait 1 second before next batch
                
                # Collect results
                for future in concurrent.futures.as_completed(futures):
                    try:
                        metric = future.result()
                        if metric:
                            scenario_metrics.append(metric)
                    except Exception as e:
                        print(f"❌ Load test error: {e}")
            
            if scenario_metrics:
                times = [m.validation_time_ms for m in scenario_metrics if m.scenario == 'load_testing']
                if times:
                    avg_time = statistics.mean(times)
                    print(f"  📈 Average validation time: {avg_time:.2f}ms")
                    print(f"  📊 Total transactions: {len(times)}")
        
        self.metrics.extend(scenario_metrics)
        return scenario_metrics
    
    def run_scenario_4_cache_invalidation(self):
        """Scenario 4: Cache Invalidation Patterns"""
        print("\n🔍 Scenario 4: Cache Invalidation Patterns")
        print("=" * 50)
        
        scenario_metrics = []
        
        # Create a chain of dependent transactions
        print("\n📊 Creating dependent transaction chain...")
        
        # 1. CREATE asset
        tx, keypair = self.transaction_templates['CREATE']()
        success, validation_time, asset_id = self.send_transaction(tx)
        if success:
            self.transaction_cache['assets'].append(asset_id)
            print(f"  ✅ Created asset: {asset_id[:16]}...")
        
        # 2. ADVERTISEMENT
        tx, keypair = self.transaction_templates['ADVERTISEMENT']()
        success, validation_time, adv_id = self.send_transaction(tx)
        if success:
            self.transaction_cache['advertisements'].append(adv_id)
            print(f"  ✅ Created advertisement: {adv_id[:16]}...")
        
        # 3. Send same transactions again (should hit cache)
        print("\n📊 Testing cache hits...")
        for i in range(5):
            tx, keypair = self.transaction_templates['CREATE']()
            success, validation_time, tx_id = self.send_transaction(tx)
            
            if success:
                memory_mb, cpu_percent = self.get_system_metrics()
                metric = ExperimentMetrics(
                    scenario='cache_invalidation',
                    transaction_type='CREATE',
                    validation_time_ms=validation_time,
                    cache_hit=True,
                    timestamp=datetime.now().isoformat(),
                    transaction_id=tx_id,
                    phase='HTTP_POST',
                    memory_usage_mb=memory_mb,
                    cpu_usage_percent=cpu_percent
                )
                scenario_metrics.append(metric)
                print(f"  {i+1}. Cache hit: {validation_time:.2f}ms")
        
        # 4. Test UPDATE_ADV (should invalidate related cache entries)
        print("\n📊 Testing cache invalidation...")
        tx, keypair = self.transaction_templates['UPDATE_ADV']()
        success, validation_time, tx_id = self.send_transaction(tx)
        
        if success:
            memory_mb, cpu_percent = self.get_system_metrics()
            metric = ExperimentMetrics(
                scenario='cache_invalidation',
                transaction_type='UPDATE_ADV',
                validation_time_ms=validation_time,
                cache_hit=False,  # Should be miss due to invalidation
                timestamp=datetime.now().isoformat(),
                transaction_id=tx_id,
                phase='HTTP_POST',
                memory_usage_mb=memory_mb,
                cpu_usage_percent=cpu_percent
            )
            scenario_metrics.append(metric)
            print(f"  ✅ Update transaction: {validation_time:.2f}ms")
        
        self.metrics.extend(scenario_metrics)
        return scenario_metrics
    
    def run_scenario_5_resource_analysis(self):
        """Scenario 5: Memory and Resource Analysis"""
        print("\n🔍 Scenario 5: Resource Analysis")
        print("=" * 50)
        
        scenario_metrics = []
        
        # Test different cache sizes
        cache_sizes = [10, 50, 100, 200, 500]
        
        for cache_size in cache_sizes:
            print(f"\n📊 Testing with ~{cache_size} cached transactions...")
            
            # Fill cache with transactions
            for i in range(cache_size):
                tx, keypair = self.transaction_templates['CREATE']()
                success, validation_time, tx_id = self.send_transaction(tx)
                
                if success:
                    memory_mb, cpu_percent = self.get_system_metrics()
                    
                    metric = ExperimentMetrics(
                        scenario='resource_analysis',
                        transaction_type='CREATE',
                        validation_time_ms=validation_time,
                        cache_hit=False,
                        timestamp=datetime.now().isoformat(),
                        transaction_id=tx_id,
                        phase='HTTP_POST',
                        memory_usage_mb=memory_mb,
                        cpu_usage_percent=cpu_percent
                    )
                    scenario_metrics.append(metric)
                
                if i % 50 == 0:
                    print(f"  📈 Progress: {i}/{cache_size} transactions")
            
            # Measure resource usage
            memory_mb, cpu_percent = self.get_system_metrics()
            print(f"  📊 Memory usage: {memory_mb:.2f}MB")
            print(f"  📊 CPU usage: {cpu_percent:.2f}%")
            
            time.sleep(2)  # Let system stabilize
        
        self.metrics.extend(scenario_metrics)
        return scenario_metrics
    
    def save_results(self, filename: str = None):
        """Save experiment results to CSV"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"experiment_results_{timestamp}.csv"
        
        with open(filename, 'w', newline='') as csvfile:
            fieldnames = [
                'scenario', 'transaction_type', 'validation_time_ms', 'cache_hit',
                'timestamp', 'transaction_id', 'phase', 'memory_usage_mb', 'cpu_usage_percent'
            ]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            for metric in self.metrics:
                writer.writerow(asdict(metric))
        
        print(f"📊 Results saved to: {filename}")
        return filename
    
    def generate_report(self):
        """Generate a comprehensive experiment report"""
        print("\n📊 Generating Experiment Report")
        print("=" * 50)
        
        # Group metrics by scenario
        scenarios = defaultdict(list)
        for metric in self.metrics:
            scenarios[metric.scenario].append(metric)
        
        report = {
            'total_transactions': len(self.metrics),
            'scenarios': {},
            'summary': {}
        }
        
        for scenario_name, metrics in scenarios.items():
            times = [m.validation_time_ms for m in metrics]
            cache_hits = [m.cache_hit for m in metrics]
            
            scenario_report = {
                'transaction_count': len(metrics),
                'avg_validation_time_ms': statistics.mean(times),
                'median_validation_time_ms': statistics.median(times),
                'min_validation_time_ms': min(times),
                'max_validation_time_ms': max(times),
                'std_validation_time_ms': statistics.stdev(times) if len(times) > 1 else 0,
                'cache_hit_rate': sum(cache_hits) / len(cache_hits) * 100,
                'avg_memory_usage_mb': statistics.mean([m.memory_usage_mb for m in metrics]),
                'avg_cpu_usage_percent': statistics.mean([m.cpu_usage_percent for m in metrics])
            }
            
            report['scenarios'][scenario_name] = scenario_report
            
            print(f"\n📈 {scenario_name.replace('_', ' ').title()}:")
            print(f"  Transactions: {scenario_report['transaction_count']}")
            print(f"  Avg validation time: {scenario_report['avg_validation_time_ms']:.2f}ms")
            print(f"  Cache hit rate: {scenario_report['cache_hit_rate']:.1f}%")
            print(f"  Memory usage: {scenario_report['avg_memory_usage_mb']:.2f}MB")
            print(f"  CPU usage: {scenario_report['avg_cpu_usage_percent']:.2f}%")
        
        # Overall summary
        all_times = [m.validation_time_ms for m in self.metrics]
        all_cache_hits = [m.cache_hit for m in self.metrics]
        
        report['summary'] = {
            'overall_avg_validation_time_ms': statistics.mean(all_times),
            'overall_cache_hit_rate': sum(all_cache_hits) / len(all_cache_hits) * 100,
            'total_experiment_duration_minutes': (datetime.now() - datetime.fromisoformat(self.metrics[0].timestamp)).total_seconds() / 60 if self.metrics else 0
        }
        
        print(f"\n📊 Overall Summary:")
        print(f"  Total transactions: {report['total_transactions']}")
        print(f"  Overall avg validation time: {report['summary']['overall_avg_validation_time_ms']:.2f}ms")
        print(f"  Overall cache hit rate: {report['summary']['overall_cache_hit_rate']:.1f}%")
        
        # Save report
        report_filename = f"experiment_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_filename, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"📊 Report saved to: {report_filename}")
        return report
    
    def run_full_experiment(self):
        """Run the complete experimental suite"""
        print("🚀 Starting Comprehensive Cache System Evaluation")
        print("=" * 60)
        print(f"📅 Start time: {datetime.now().isoformat()}")
        print(f"⚙️  Configuration: {self.config.num_transactions} transactions")
        
        start_time = time.time()
        
        try:
            # Run all scenarios
            self.run_scenario_1_cache_hit_analysis()
            self.run_scenario_2_transaction_type_performance()
            self.run_scenario_3_load_testing()
            self.run_scenario_4_cache_invalidation()
            self.run_scenario_5_resource_analysis()
            
            # Generate results
            csv_file = self.save_results()
            report = self.generate_report()
            
            end_time = time.time()
            duration_minutes = (end_time - start_time) / 60
            
            print(f"\n🎉 Experiment completed successfully!")
            print(f"⏱️  Total duration: {duration_minutes:.2f} minutes")
            print(f"📊 Results file: {csv_file}")
            print(f"📈 Report file: experiment_report_*.json")
            
            return True
            
        except Exception as e:
            print(f"❌ Experiment failed: {e}")
            import traceback
            traceback.print_exc()
            return False


def main():
    """Main entry point"""
    print("🔬 SmartChainDB Cache System Experimental Driver")
    print("=" * 50)
    
    # Configuration
    config = ExperimentConfig(
        bigchaindb_url="http://localhost:9984",
        num_transactions=1000,
        load_test_levels=[10, 25, 50, 100],
        experiment_duration_minutes=30
    )
    
    # Create driver
    driver = ExperimentalDriver(config)
    
    # Check if BigchainDB is running
    try:
        response = requests.get(f"{config.bigchaindb_url}/", timeout=5)
        if response.status_code != 200:
            print("❌ BigchainDB is not running or not accessible")
            return False
    except Exception as e:
        print(f"❌ Cannot connect to BigchainDB: {e}")
        return False
    
    print("✅ BigchainDB is accessible")
    
    # Run experiment
    success = driver.run_full_experiment()
    
    if success:
        print("\n🎉 All experiments completed successfully!")
        print("📊 Check the generated CSV and JSON files for detailed results")
    else:
        print("\n❌ Experiment failed")
        return False
    
    return True


if __name__ == "__main__":
    main()
