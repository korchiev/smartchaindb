#!/usr/bin/env python3
"""
Compare performance across all three branches:
1. transaction-testing (Python validation without SHACL)
2. with_shacl (SHACL without optimization)
3. caching_with_shacl (SHACL with optimizations)

Usage:
    N=10 K=2 M=8 python compare_all_branches.py
"""

import os
import sys
import time
import subprocess
import json
from datetime import datetime

def run_test_on_branch(branch_name, test_params):
    """Run the sequential test on a specific branch"""
    print(f"\n{'='*80}")
    print(f"Testing branch: {branch_name}")
    print(f"{'='*80}\n")
    
    # Checkout the branch
    result = subprocess.run(['git', 'checkout', branch_name], 
                          capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error checking out {branch_name}: {result.stderr}")
        return None
    
    print(f"Checked out branch: {branch_name}")
    
    # Copy files to container
    print("Copying files to container...")
    subprocess.run(['docker', 'cp', 'test_sequential_perf.py', 
                    'smartchaindb-bigchaindb-1:/usr/src/app/'], check=True)
    subprocess.run(['docker', 'cp', 'smartchaindb_custom_driver.py',
                    'smartchaindb-bigchaindb-1:/usr/src/app/'], check=True)
    
    # Run the test
    print(f"Running test with N={test_params['N']}, K={test_params['K']}, M={test_params['M']}...")
    
    env_vars = f"-e N={test_params['N']} -e K={test_params['K']} -e M={test_params['M']} -e RETURNS=0"
    
    with open(f'bdb_perf_{branch_name}.log', 'w') as log_file:
        result = subprocess.run(
            f'docker exec {env_vars} -w /usr/src/app smartchaindb-bigchaindb-1 timeout 180 python test_sequential_perf.py',
            shell=True,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            text=True
        )
    
    if result.returncode == 0:
        print(f"Test completed successfully on {branch_name}")
    else:
        print(f"Test completed with exit code {result.returncode} on {branch_name}")
    
    return f'bdb_perf_{branch_name}.log'

def analyze_results(filename, branch_name):
    """Analyze results from a log file"""
    try:
        with open(filename, 'r', encoding='utf-8', errors='ignore') as f:
            lines = [l.strip() for l in f.readlines() if l.strip()]
        
        transactions = []
        for line in lines:
            if line.startswith('SUMMARY'):
                parts = line.split(',')
                return {
                    'branch': branch_name,
                    'total_tx': int(parts[1]) if len(parts) > 1 else 0,
                    'total_ms': float(parts[2]) if len(parts) > 2 else 0,
                    'tps': float(parts[3]) if len(parts) > 3 else 0,
                    'transactions': transactions
                }
            
            parts = line.split(',')
            if len(parts) >= 4:
                txn_type = parts[0].strip()
                if txn_type in ['CREATE', 'ADVERTISEMENT', 'BUY_OFFER', 'SELL']:
                    try:
                        lat_ms = float(parts[2].strip())
                        submit_ms = float(parts[3].strip()) if len(parts) > 3 and parts[3].strip() else 0
                        mine_ms = float(parts[4].strip()) if len(parts) > 4 and parts[4].strip() else 0
                        transactions.append((txn_type, lat_ms, submit_ms, mine_ms))
                    except (ValueError, IndexError):
                        pass
    except Exception as e:
        print(f"Error analyzing {filename}: {e}")
        return None
    
    return None

def main():
    # Get test parameters
    N = int(os.getenv('N', 10))
    K = int(os.getenv('K', 2))
    M = int(os.getenv('M', 8))
    
    test_params = {'N': N, 'K': K, 'M': M}
    
    print(f"\n{'='*80}")
    print(f"BIGCHAINDB PERFORMANCE COMPARISON")
    print(f"{'='*80}")
    print(f"\nTest Parameters: N={N}, K={K}, M={M}")
    print(f"Expected: {N} CREATE + {N} ADVERTISEMENT + {N*K} BUY_OFFER + {M} SELL")
    
    branches = ['transaction-testing', 'with_shacl', 'caching_with_shacl']
    results = []
    
    # Run tests on each branch
    for branch in branches:
        log_file = run_test_on_branch(branch, test_params)
        if log_file:
            result = analyze_results(log_file, branch)
            if result:
                results.append(result)
        
        # Wait a bit between tests
        time.sleep(2)
    
    # Checkout back to caching_with_shacl
    subprocess.run(['git', 'checkout', 'caching_with_shacl'], 
                  capture_output=True)
    
    # Print comparison
    print(f"\n\n{'='*80}")
    print("COMPARISON RESULTS")
    print(f"{'='*80}\n")
    
    if not results:
        print("No results collected!")
        return
    
    print(f"{'Branch':<25} {'Total TX':<12} {'Duration (s)':<15} {'TPS':<10}")
    print("-" * 80)
    
    for result in results:
        duration_s = result['total_ms'] / 1000
        print(f"{result['branch']:<25} {result['total_tx']:<12} {duration_s:<15.2f} {result['tps']:<10.2f}")
    
    print("\n" + "="*80)
    print("DETAILED LATENCY BY TRANSACTION TYPE")
    print("="*80)
    
    # Group by transaction type
    for tx_type in ['CREATE', 'ADVERTISEMENT', 'BUY_OFFER', 'SELL']:
        print(f"\n{tx_type} Transaction Latency:")
        print(f"{'Branch':<25} {'Avg Latency (ms)':<20} {'Samples':<10}")
        print("-" * 60)
        
        for result in results:
            txns = [t for t in result['transactions'] if t[0] == tx_type]
            if txns:
                avg_lat = sum(t[1] for t in txns) / len(txns)
                print(f"{result['branch']:<25} {avg_lat:<20.2f} {len(txns):<10}")

if __name__ == '__main__':
    main()

