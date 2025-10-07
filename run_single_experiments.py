#!/usr/bin/env python3
"""
Single Validation Type Experiment Runner

This script helps you run separate experiments for SHACL and traditional validation,
rather than comparing them in the same experiment.
"""

import os
import subprocess
import time
import requests
import json
from datetime import datetime

def check_server_status(server_url="http://localhost:9984"):
    """Check if BigchainDB server is running"""
    try:
        response = requests.get(f"{server_url}/api/v1/")
        return response.status_code == 200
    except:
        return False

def stop_server():
    """Stop BigchainDB server"""
    try:
        # Try to find and kill the bigchaindb process
        subprocess.run(["pkill", "-f", "bigchaindb"], check=False)
        time.sleep(2)
        print("✅ BigchainDB server stopped")
        return True
    except Exception as e:
        print(f"⚠️  Could not stop server gracefully: {e}")
        return False

def start_server_with_config(experiment_name, shacl_enabled=True):
    """Start BigchainDB server with specific configuration"""
    print(f"🚀 Starting BigchainDB server for {experiment_name}...")
    
    # Set environment variables
    env = os.environ.copy()
    env['BIGCHAINDB_ENHANCED_METRICS_ENABLED'] = 'true'
    env['BIGCHAINDB_EXPERIMENT_NAME'] = experiment_name
    env['BIGCHAINDB_SHACL_ENABLED'] = 'true' if shacl_enabled else 'false'
    env['BIGCHAINDB_METRICS_CHECKPOINT_INTERVAL'] = '50'
    
    print(f"   Configuration:")
    print(f"   - Experiment Name: {experiment_name}")
    print(f"   - SHACL Enabled: {shacl_enabled}")
    print(f"   - Validation Type: {'SHACL' if shacl_enabled else 'TRADITIONAL'}")
    
    # Start server in background
    try:
        process = subprocess.Popen(
            ["bigchaindb", "start"],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        # Wait for server to start
        print("   Waiting for server to start...")
        for i in range(30):  # Wait up to 30 seconds
            if check_server_status():
                print("   ✅ Server started successfully")
                return process
            time.sleep(1)
        
        print("   ❌ Server failed to start")
        process.terminate()
        return None
        
    except Exception as e:
        print(f"   ❌ Failed to start server: {e}")
        return None

def run_shacl_experiment(experiment_name="SHACL_Experiment", duration_minutes=10):
    """Run SHACL validation experiment"""
    print(f"\n🔬 Running SHACL Validation Experiment")
    print("=" * 50)
    
    # Start server with SHACL enabled
    process = start_server_with_config(experiment_name, shacl_enabled=True)
    if not process:
        return False
    
    try:
        print(f"\n📊 Experiment running for {duration_minutes} minutes...")
        print("   Send requests from your external driver now!")
        print("   The server will automatically track all metrics.")
        
        # Wait for experiment duration
        time.sleep(duration_minutes * 60)
        
        print(f"\n⏰ Experiment time completed ({duration_minutes} minutes)")
        
    except KeyboardInterrupt:
        print(f"\n⏹️  Experiment interrupted by user")
    
    finally:
        # Stop server
        print(f"\n🛑 Stopping server...")
        process.terminate()
        time.sleep(3)
        
        print(f"✅ SHACL experiment completed!")
        print(f"📁 Results saved to: experiment_results/session_XXXXX/")
    
    return True

def run_traditional_experiment(experiment_name="Traditional_Experiment", duration_minutes=10):
    """Run traditional validation experiment"""
    print(f"\n🔬 Running Traditional Validation Experiment")
    print("=" * 50)
    
    # Start server with traditional validation
    process = start_server_with_config(experiment_name, shacl_enabled=False)
    if not process:
        return False
    
    try:
        print(f"\n📊 Experiment running for {duration_minutes} minutes...")
        print("   Send requests from your external driver now!")
        print("   The server will automatically track all metrics.")
        
        # Wait for experiment duration
        time.sleep(duration_minutes * 60)
        
        print(f"\n⏰ Experiment time completed ({duration_minutes} minutes)")
        
    except KeyboardInterrupt:
        print(f"\n⏹️  Experiment interrupted by user")
    
    finally:
        # Stop server
        print(f"\n🛑 Stopping server...")
        process.terminate()
        time.sleep(3)
        
        print(f"✅ Traditional experiment completed!")
        print(f"📁 Results saved to: experiment_results/session_XXXXX/")
    
    return True

def run_both_experiments(shacl_duration=10, traditional_duration=10):
    """Run both SHACL and traditional experiments separately"""
    print("🔬 Running Separate SHACL and Traditional Experiments")
    print("=" * 60)
    
    # Run SHACL experiment
    shacl_success = run_shacl_experiment("SHACL_Experiment", shacl_duration)
    
    if not shacl_success:
        print("❌ SHACL experiment failed")
        return False
    
    # Wait between experiments
    print(f"\n⏳ Waiting 30 seconds between experiments...")
    time.sleep(30)
    
    # Run traditional experiment
    traditional_success = run_traditional_experiment("Traditional_Experiment", traditional_duration)
    
    if not traditional_success:
        print("❌ Traditional experiment failed")
        return False
    
    print(f"\n🎉 Both experiments completed successfully!")
    print(f"📁 Results saved to:")
    print(f"   - experiment_results/session_XXXXX/ (SHACL)")
    print(f"   - experiment_results/session_YYYYY/ (Traditional)")
    print(f"\n🔍 To analyze results:")
    print(f"   python analyze_metrics.py --csv experiment_results/session_XXXXX/metrics_XXXXX.csv --plots")
    print(f"   python analyze_metrics.py --csv experiment_results/session_YYYYY/metrics_YYYYY.csv --plots")
    
    return True

def main():
    """Main function"""
    print("🚀 Single Validation Type Experiment Runner")
    print("=" * 50)
    
    print("Choose experiment type:")
    print("1. SHACL validation only")
    print("2. Traditional validation only") 
    print("3. Both (separate experiments)")
    print("4. Exit")
    
    choice = input("\nEnter your choice (1-4): ").strip()
    
    if choice == "1":
        duration = int(input("Enter experiment duration in minutes (default 10): ") or "10")
        run_shacl_experiment("SHACL_Experiment", duration)
        
    elif choice == "2":
        duration = int(input("Enter experiment duration in minutes (default 10): ") or "10")
        run_traditional_experiment("Traditional_Experiment", duration)
        
    elif choice == "3":
        shacl_duration = int(input("Enter SHACL experiment duration in minutes (default 10): ") or "10")
        traditional_duration = int(input("Enter traditional experiment duration in minutes (default 10): ") or "10")
        run_both_experiments(shacl_duration, traditional_duration)
        
    elif choice == "4":
        print("👋 Goodbye!")
        return
        
    else:
        print("❌ Invalid choice")
        return

if __name__ == "__main__":
    main()
