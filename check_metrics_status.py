#!/usr/bin/env python3
"""
Check the current status of the enhanced metrics system
"""

import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'bigchaindb'))

from bigchaindb.enhanced_metrics import (
    is_session_active,
    get_current_session,
    save_current_results,
    get_performance_summary
)

def main():
    print("🔍 Enhanced Metrics Status Check")
    print("=" * 50)
    
    # Check if session is active
    session_active = is_session_active()
    print(f"Session Active: {session_active}")
    
    if session_active:
        # Get current session info
        session = get_current_session()
        if session:
            print(f"Session ID: {session.session_id}")
            print(f"Experiment Name: {session.experiment_name}")
            print(f"Start Time: {session.start_time}")
            print(f"Validation Types: {session.validation_types}")
            print(f"Operations Tested: {session.operations_tested}")
            print(f"Total Transactions: {session.total_transactions}")
        
        # Get performance summary
        summary = get_performance_summary()
        print(f"\nPerformance Summary:")
        for key, value in summary.items():
            print(f"  {key}: {value}")
        
        # Try to save current results
        print(f"\n💾 Attempting to save current results...")
        try:
            results_file = save_current_results("manual_checkpoint")
            print(f"✅ Results saved to: {results_file}")
        except Exception as e:
            print(f"❌ Failed to save results: {e}")
            
        # Check if experiment_results directory exists
        results_dir = "experiment_results"
        if os.path.exists(results_dir):
            print(f"\n📁 Results directory exists: {os.path.abspath(results_dir)}")
            files = os.listdir(results_dir)
            print(f"Files in results directory: {files}")
        else:
            print(f"\n❌ Results directory does not exist: {os.path.abspath(results_dir)}")
            print(f"Current working directory: {os.getcwd()}")
            
    else:
        print("❌ No active session found")
        print("The enhanced metrics system may not be initialized properly")

if __name__ == "__main__":
    main()
