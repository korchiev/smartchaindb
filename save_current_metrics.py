#!/usr/bin/env python3
"""
Manually save current metrics data from the enhanced metrics system
"""

import os
import sys
import json
import csv
from datetime import datetime

# Add the bigchaindb directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'bigchaindb'))

def extract_metrics_from_logs():
    """Extract metrics data from the server logs"""
    log_file = "scdb-server.log"
    
    if not os.path.exists(log_file):
        print(f"❌ Log file not found: {log_file}")
        return None
    
    print(f"📖 Reading metrics from: {log_file}")
    
    # Extract enhanced_metrics entries
    metrics_data = []
    
    with open(log_file, 'r') as f:
        for line in f:
            if 'enhanced_metrics' in line and 'INFO' in line:
                try:
                    # Extract the JSON part from the log line
                    json_start = line.find('{')
                    if json_start != -1:
                        json_str = line[json_start:]
                        # Remove any trailing characters after the JSON
                        json_end = json_str.rfind('}')
                        if json_end != -1:
                            json_str = json_str[:json_end + 1]
                            
                        # Parse the JSON
                        metric = json.loads(json_str)
                        metrics_data.append(metric)
                except json.JSONDecodeError as e:
                    print(f"⚠️  Warning: Could not parse JSON from line: {e}")
                    continue
    
    print(f"✅ Extracted {len(metrics_data)} metrics entries")
    return metrics_data

def save_metrics_to_files(metrics_data):
    """Save metrics data to JSON and CSV files"""
    if not metrics_data:
        print("❌ No metrics data to save")
        return
    
    # Create experiment_results directory
    results_dir = "experiment_results"
    os.makedirs(results_dir, exist_ok=True)
    
    # Create session directory
    session_id = f"manual_session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    session_dir = os.path.join(results_dir, f"session_{session_id}")
    os.makedirs(session_dir, exist_ok=True)
    
    print(f"📁 Created session directory: {session_dir}")
    
    # Save JSON file
    json_file = os.path.join(session_dir, f"metrics_{session_id}.json")
    with open(json_file, 'w') as f:
        json.dump(metrics_data, f, indent=2)
    print(f"💾 Saved JSON metrics: {json_file}")
    
    # Save CSV file
    csv_file = os.path.join(session_dir, f"metrics_{session_id}.csv")
    
    if metrics_data:
        # Get all unique keys from all metrics
        all_keys = set()
        for metric in metrics_data:
            all_keys.update(metric.keys())
        
        # Write CSV header
        with open(csv_file, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=sorted(all_keys))
            writer.writeheader()
            
            # Write data rows
            for metric in metrics_data:
                writer.writerow(metric)
        
        print(f"💾 Saved CSV metrics: {csv_file}")
    
    # Create summary report
    summary_file = os.path.join(session_dir, "summary_report.txt")
    with open(summary_file, 'w') as f:
        f.write("Enhanced Metrics Summary Report\n")
        f.write("=" * 40 + "\n\n")
        f.write(f"Session ID: {session_id}\n")
        f.write(f"Generated: {datetime.now().isoformat()}\n")
        f.write(f"Total Transactions: {len(metrics_data)}\n\n")
        
        if metrics_data:
            # Analyze transaction types
            operations = {}
            validation_types = {}
            total_latency = 0
            validation_times = []
            
            for metric in metrics_data:
                tx = metric.get('transaction', {})
                op = tx.get('operation', 'UNKNOWN')
                val_type = tx.get('validation_type', 'UNKNOWN')
                
                operations[op] = operations.get(op, 0) + 1
                validation_types[val_type] = validation_types.get(val_type, 0) + 1
                
                total_latency += tx.get('total_latency_ms', 0)
                validation_times.append(tx.get('validation_overhead_ms', 0))
            
            f.write("Transaction Operations:\n")
            for op, count in sorted(operations.items()):
                f.write(f"  {op}: {count}\n")
            
            f.write(f"\nValidation Types:\n")
            for val_type, count in sorted(validation_types.items()):
                f.write(f"  {val_type}: {count}\n")
            
            if validation_times:
                avg_validation = sum(validation_times) / len(validation_times)
                f.write(f"\nPerformance Metrics:\n")
                f.write(f"  Average Validation Time: {avg_validation:.2f} ms\n")
                f.write(f"  Average Total Latency: {total_latency / len(metrics_data):.2f} ms\n")
    
    print(f"📊 Created summary report: {summary_file}")
    
    return session_dir

def main():
    print("🔍 Enhanced Metrics Data Extraction")
    print("=" * 50)
    
    # Extract metrics from logs
    metrics_data = extract_metrics_from_logs()
    
    if metrics_data:
        # Save to files
        session_dir = save_metrics_to_files(metrics_data)
        print(f"\n✅ Successfully saved metrics to: {session_dir}")
        print(f"\n📁 Files created:")
        print(f"  - metrics_{session_dir.split('_')[-1]}.json")
        print(f"  - metrics_{session_dir.split('_')[-1]}.csv") 
        print(f"  - summary_report.txt")
    else:
        print("❌ No metrics data found in logs")

if __name__ == "__main__":
    main()
