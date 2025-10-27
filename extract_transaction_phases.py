#!/usr/bin/env python3
"""
Transaction Phase Timing Extractor

Extracts detailed timing breakdown for all transaction types by ID from BigchainDB metrics log.
Shows the complete lifecycle timing for each transaction across all phases.
"""

import subprocess
import json
import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import statistics

class TransactionPhaseExtractor:
    def __init__(self, container_name: str = "smartchaindb-bigchaindb-1"):
        self.container_name = container_name
        self.metrics_file = "/usr/src/app/bigchaindb-metrics.log"
        
    def extract_metrics_log(self) -> List[str]:
        """Extract the metrics log from Docker container"""
        try:
            result = subprocess.run([
                "docker", "exec", self.container_name, 
                "cat", self.metrics_file
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            
            if result.returncode != 0:
                print(f"Error extracting metrics: {result.stderr}")
                return []
                
            return result.stdout.strip().split('\n')
        except Exception as e:
            print(f"Error running docker command: {e}")
            return []
    
    def parse_metric_line(self, line: str) -> Optional[Dict]:
        """Parse a single metric line into structured data"""
        # Format: phase,time_ms,operation,tx_id,block_height,timestamp
        parts = line.split(',')
        if len(parts) < 6:
            return None
            
        try:
            return {
                'phase': parts[0],
                'time_ms': int(parts[1]),
                'operation': parts[2],
                'tx_id': parts[3],
                'block_height': parts[4] if parts[4] != 'None' else None,
                'timestamp': float(parts[5])
            }
        except (ValueError, IndexError):
            return None
    
    def group_metrics_by_transaction(self, metrics: List[str]) -> Dict[str, List[Dict]]:
        """Group metrics by transaction ID"""
        transactions = {}
        
        for line in metrics:
            if not line.strip():
                continue
                
            metric = self.parse_metric_line(line)
            if not metric:
                continue
                
            tx_id = metric['tx_id']
            if tx_id not in transactions:
                transactions[tx_id] = []
            transactions[tx_id].append(metric)
            
        return transactions
    
    def calculate_phase_timings(self, tx_metrics: List[Dict]) -> Dict:
        """Calculate timing breakdown for a single transaction"""
        # Sort by timestamp to get chronological order
        tx_metrics.sort(key=lambda x: x['timestamp'])
        
        phases = {}
        for metric in tx_metrics:
            phase = metric['phase']
            phases[phase] = {
                'time_ms': metric['time_ms'],
                'timestamp': metric['timestamp'],
                'operation': metric['operation']
            }
        
        # Calculate durations between phases
        timings = {}
        if 'received_tx' in phases:
            base_time = phases['received_tx']['timestamp']
            
            for phase, data in phases.items():
                duration_ms = (data['timestamp'] - base_time) * 1000
                timings[phase] = {
                    'duration_ms': round(duration_ms, 2),
                    'phase_time_ms': data['time_ms'],
                    'timestamp': data['timestamp']
                }
        
        return timings
    
    def extract_transaction_phases(self, tx_id: str) -> Optional[Dict]:
        """Extract phase timings for a specific transaction ID"""
        metrics = self.extract_metrics_log()
        if not metrics:
            return None
            
        transactions = self.group_metrics_by_transaction(metrics)
        
        if tx_id not in transactions:
            print(f"Transaction {tx_id} not found in metrics")
            return None
            
        tx_metrics = transactions[tx_id]
        timings = self.calculate_phase_timings(tx_metrics)
        
        return {
            'tx_id': tx_id,
            'operation': tx_metrics[0]['operation'] if tx_metrics else 'UNKNOWN',
            'phases': timings,
            'total_phases': len(tx_metrics)
        }
    
    def extract_all_transaction_types(self, limit_per_type: int = 5) -> Dict[str, List[Dict]]:
        """Extract phase timings for all transaction types"""
        metrics = self.extract_metrics_log()
        if not metrics:
            return {}
            
        transactions = self.group_metrics_by_transaction(metrics)
        
        # Group by operation type
        by_operation = {}
        for tx_id, tx_metrics in transactions.items():
            if not tx_metrics:
                continue
                
            operation = tx_metrics[0]['operation']
            if operation not in by_operation:
                by_operation[operation] = []
                
            timings = self.calculate_phase_timings(tx_metrics)
            by_operation[operation].append({
                'tx_id': tx_id,
                'operation': operation,
                'phases': timings,
                'total_phases': len(tx_metrics)
            })
        
        # Limit results per operation type
        for operation in by_operation:
            by_operation[operation] = by_operation[operation][-limit_per_type:]
            
        return by_operation
    
    def print_transaction_breakdown(self, tx_data: Dict):
        """Print detailed breakdown for a single transaction"""
        print(f"\n{'='*80}")
        print(f"TRANSACTION: {tx_data['tx_id'][:16]}...")
        print(f"OPERATION: {tx_data['operation']}")
        print(f"TOTAL PHASES: {tx_data['total_phases']}")
        print(f"{'='*80}")
        
        phases = tx_data['phases']
        
        # Define expected phase order
        phase_order = ['received_tx', 'before_tendermint', 'check_tx', 'deliver_tx', 'end_block', 'commit_tx']
        
        print(f"{'Phase':<20} {'Duration (ms)':<15} {'Phase Time (ms)':<15} {'Timestamp':<20}")
        print(f"{'-'*80}")
        
        total_duration = 0
        for phase in phase_order:
            if phase in phases:
                data = phases[phase]
                duration = data['duration_ms']
                phase_time = data['phase_time_ms']
                timestamp = data['timestamp']
                
                print(f"{phase:<20} {duration:<15} {phase_time:<15} {timestamp:<20}")
                
                if phase == 'commit_tx':
                    total_duration = duration
        
        print(f"{'-'*80}")
        print(f"{'TOTAL PROCESSING TIME':<20} {total_duration:<15} ms")
        
        # Calculate phase breakdown percentages
        if total_duration > 0:
            print(f"\nPhase Breakdown (% of total time):")
            for phase in phase_order:
                if phase in phases:
                    percentage = (phases[phase]['duration_ms'] / total_duration) * 100
                    print(f"  {phase:<20}: {percentage:.1f}%")
    
    def print_operation_summary(self, operation_data: List[Dict]):
        """Print summary statistics for an operation type"""
        if not operation_data:
            return
            
        operation = operation_data[0]['operation']
        print(f"\n{'='*60}")
        print(f"OPERATION TYPE: {operation}")
        print(f"SAMPLE SIZE: {len(operation_data)} transactions")
        print(f"{'='*60}")
        
        # Calculate average timings across all phases
        phase_totals = {}
        phase_counts = {}
        
        for tx_data in operation_data:
            for phase, data in tx_data['phases'].items():
                if phase not in phase_totals:
                    phase_totals[phase] = 0
                    phase_counts[phase] = 0
                phase_totals[phase] += data['duration_ms']
                phase_counts[phase] += 1
        
        print(f"{'Phase':<20} {'Avg Duration (ms)':<18} {'Samples':<10}")
        print(f"{'-'*50}")
        
        phase_order = ['received_tx', 'before_tendermint', 'check_tx', 'deliver_tx', 'end_block', 'commit_tx']
        total_avg = 0
        
        for phase in phase_order:
            if phase in phase_totals:
                avg_duration = phase_totals[phase] / phase_counts[phase]
                samples = phase_counts[phase]
                print(f"{phase:<20} {avg_duration:<18.2f} {samples:<10}")
                
                if phase == 'commit_tx':
                    total_avg = avg_duration
        
        print(f"{'-'*50}")
        print(f"{'AVERAGE TOTAL TIME':<20} {total_avg:<18.2f} ms")
    
    def run_analysis(self, specific_tx_id: Optional[str] = None, limit_per_type: int = 3):
        """Run the complete analysis"""
        print("BigchainDB Transaction Phase Timing Analysis")
        print("=" * 60)
        
        if specific_tx_id:
            # Analyze specific transaction
            tx_data = self.extract_transaction_phases(specific_tx_id)
            if tx_data:
                self.print_transaction_breakdown(tx_data)
            else:
                print(f"Could not find transaction: {specific_tx_id}")
        else:
            # Analyze all transaction types
            all_data = self.extract_all_transaction_types(limit_per_type)
            
            if not all_data:
                print("No transaction data found in metrics log")
                return
            
            print(f"Found {len(all_data)} operation types:")
            for operation in all_data.keys():
                print(f"  - {operation}")
            
            # Print summary for each operation type
            for operation, tx_list in all_data.items():
                self.print_operation_summary(tx_list)
            
            # Print overall comparison
            print(f"\n{'='*80}")
            print("OVERALL COMPARISON ACROSS OPERATION TYPES")
            print(f"{'='*80}")
            
            operation_totals = {}
            for operation, tx_list in all_data.items():
                total_times = []
                for tx_data in tx_list:
                    if 'commit_tx' in tx_data['phases']:
                        total_times.append(tx_data['phases']['commit_tx']['duration_ms'])
                
                if total_times:
                    operation_totals[operation] = {
                        'avg': statistics.mean(total_times),
                        'min': min(total_times),
                        'max': max(total_times),
                        'count': len(total_times)
                    }
            
            print(f"{'Operation':<15} {'Avg (ms)':<12} {'Min (ms)':<12} {'Max (ms)':<12} {'Samples':<10}")
            print(f"{'-'*70}")
            
            for operation, stats in sorted(operation_totals.items()):
                print(f"{operation:<15} {stats['avg']:<12.2f} {stats['min']:<12.2f} {stats['max']:<12.2f} {stats['count']:<10}")

def main():
    extractor = TransactionPhaseExtractor()
    
    # Example usage - analyze all transaction types
    print("Analyzing all transaction types...")
    extractor.run_analysis(limit_per_type=2)
    
    # Show detailed breakdown for specific transactions
    print("\n" + "="*80)
    print("DETAILED TRANSACTION BREAKDOWNS")
    print("="*80)
    
    # Get recent transactions for detailed analysis
    all_data = extractor.extract_all_transaction_types(limit_per_type=1)
    
    for operation, tx_list in all_data.items():
        if tx_list:
            # Show the most recent transaction for each type
            latest_tx = tx_list[-1]
            extractor.print_transaction_breakdown(latest_tx)

if __name__ == "__main__":
    main()
