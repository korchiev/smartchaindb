#!/usr/bin/env python3
"""
Quick Transaction Phase Analyzer

Quickly analyze specific transaction IDs or get recent transaction timings.
Usage:
    python quick_phase_analyzer.py [transaction_id]
    python quick_phase_analyzer.py --recent
    python quick_phase_analyzer.py --all-types
"""

import sys
import subprocess
from typing import Dict, List, Optional
from extract_transaction_phases import TransactionPhaseExtractor

def analyze_specific_transaction(tx_id: str):
    """Analyze a specific transaction ID"""
    extractor = TransactionPhaseExtractor()
    
    print(f"Analyzing transaction: {tx_id}")
    print("=" * 60)
    
    tx_data = extractor.extract_transaction_phases(tx_id)
    if tx_data:
        extractor.print_transaction_breakdown(tx_data)
    else:
        print(f"Transaction {tx_id} not found in metrics log")

def analyze_recent_transactions():
    """Analyze the most recent transactions of each type"""
    extractor = TransactionPhaseExtractor()
    
    print("Analyzing most recent transactions by type...")
    print("=" * 60)
    
    all_data = extractor.extract_all_transaction_types(limit_per_type=1)
    
    for operation, tx_list in all_data.items():
        if tx_list:
            latest_tx = tx_list[-1]
            print(f"\nMost recent {operation} transaction:")
            extractor.print_transaction_breakdown(latest_tx)

def analyze_all_types():
    """Analyze all transaction types with summary"""
    extractor = TransactionPhaseExtractor()
    extractor.run_analysis(limit_per_type=3)

def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python quick_phase_analyzer.py <transaction_id>  # Analyze specific transaction")
        print("  python quick_phase_analyzer.py --recent          # Analyze recent transactions")
        print("  python quick_phase_analyzer.py --all-types       # Analyze all types")
        print("\nExample transaction IDs:")
        print("  fd614fe90c5779e28b37d086a85691f2c40fe133a70acfdb7d08621ba3b012a1")
        print("  ba0a063e53a768f95f7958a1554a0821e53ac36065e2460d41a8e9885a9358e1")
        return
    
    arg = sys.argv[1]
    
    if arg == "--recent":
        analyze_recent_transactions()
    elif arg == "--all-types":
        analyze_all_types()
    else:
        # Assume it's a transaction ID
        analyze_specific_transaction(arg)

if __name__ == "__main__":
    main()
