#!/usr/bin/env python3
"""
Automatic Metrics Demo

This script demonstrates how the enhanced metrics system automatically tracks
all transactions when BigchainDB server is running, without any changes to external drivers.
"""

import os
import time
import requests
import json
from datetime import datetime

def create_sample_transaction(operation="CREATE", validation_type="TRADITIONAL"):
    """Create a sample transaction for testing"""
    tx = {
        "operation": operation,
        "asset": {
            "data": {
                "test_data": f"Sample {operation} transaction",
                "timestamp": datetime.now().isoformat()
            }
        },
        "metadata": {
            "requestCreationTimestamp": datetime.now().isoformat(),
            "test_metadata": True
        },
        "outputs": [
            {
                "condition": {
                    "details": {
                        "type": "ed25519-sha-256",
                        "public_key": "test_public_key"
                    },
                    "uri": "ni:///sha-256;test_hash"
                },
                "amount": "1",
                "public_keys": ["test_public_key"]
            }
        ],
        "inputs": [
            {
                "fulfillment": "test_fulfillment",
                "fulfills": None,
                "owners_before": ["test_public_key"]
            }
        ],
        "version": "2.0",
        "id": f"test_tx_{operation}_{validation_type}_{int(time.time())}"
    }
    return tx

def send_transaction_to_server(tx, server_url="http://localhost:9984"):
    """Send transaction to BigchainDB server"""
    try:
        response = requests.post(
            f"{server_url}/api/v1/transactions",
            json=tx,
            headers={"Content-Type": "application/json"}
        )
        return response.status_code, response.json() if response.content else None
    except Exception as e:
        return None, str(e)

def simulate_driver_requests(num_transactions=50, server_url="http://localhost:9984"):
    """Simulate external driver sending requests to BigchainDB server"""
    print(f"🚀 Simulating {num_transactions} transactions from external driver...")
    print(f"   Server URL: {server_url}")
    print(f"   SHACL Enabled: {os.environ.get('BIGCHAINDB_SHACL_ENABLED', 'false')}")
    print(f"   Metrics Enabled: {os.environ.get('BIGCHAINDB_ENHANCED_METRICS_ENABLED', 'true')}")
    print()
    
    operations = ['CREATE', 'TRANSFER', 'BUY_OFFER', 'SELL', 'REQUEST_RETURN']
    success_count = 0
    error_count = 0
    
    for i in range(num_transactions):
        # Alternate between SHACL and traditional validation
        use_shacl = (i % 2 == 0)
        validation_type = 'SHACL' if use_shacl else 'TRADITIONAL'
        
        # Select operation
        operation = operations[i % len(operations)]
        
        # Create transaction
        tx = create_sample_transaction(operation, validation_type)
        
        # Send to server
        status_code, response = send_transaction_to_server(tx, server_url)
        
        if status_code == 202:
            success_count += 1
            print(f"✅ Transaction {i+1:3d}: {operation:15s} ({validation_type:12s}) - SUCCESS")
        else:
            error_count += 1
            print(f"❌ Transaction {i+1:3d}: {operation:15s} ({validation_type:12s}) - FAILED ({status_code})")
        
        # Small delay between requests
        time.sleep(0.1)
        
        # Progress update every 10 transactions
        if (i + 1) % 10 == 0:
            print(f"   Progress: {i+1}/{num_transactions} (Success: {success_count}, Errors: {error_count})")
    
    print(f"\n📊 Simulation Complete:")
    print(f"   Total Transactions: {num_transactions}")
    print(f"   Successful: {success_count}")
    print(f"   Failed: {error_count}")
    print(f"   Success Rate: {(success_count/num_transactions)*100:.1f}%")
    
    return success_count, error_count

def check_server_status(server_url="http://localhost:9984"):
    """Check if BigchainDB server is running"""
    try:
        response = requests.get(f"{server_url}/api/v1/")
        return response.status_code == 200
    except:
        return False

def main():
    """Main function"""
    print("🔬 Automatic Metrics Demo")
    print("=" * 50)
    
    # Check server status
    server_url = "http://localhost:9984"
    if not check_server_status(server_url):
        print(f"❌ BigchainDB server is not running at {server_url}")
        print("   Please start the server first:")
        print("   bigchaindb start")
        return
    
    print(f"✅ BigchainDB server is running at {server_url}")
    
    # Set environment variables for demonstration
    os.environ['BIGCHAINDB_ENHANCED_METRICS_ENABLED'] = 'true'
    os.environ['BIGCHAINDB_EXPERIMENT_NAME'] = 'Automatic_Metrics_Demo'
    
    print(f"\n📊 Environment Configuration:")
    print(f"   Enhanced Metrics: {os.environ.get('BIGCHAINDB_ENHANCED_METRICS_ENABLED')}")
    print(f"   SHACL Enabled: {os.environ.get('BIGCHAINDB_SHACL_ENABLED', 'false')}")
    print(f"   Experiment Name: {os.environ.get('BIGCHAINDB_EXPERIMENT_NAME')}")
    
    # Simulate driver requests
    print(f"\n🚀 Starting simulation...")
    success_count, error_count = simulate_driver_requests(50, server_url)
    
    print(f"\n📁 Results will be automatically saved to:")
    print(f"   experiment_results/session_XXXXX/")
    print(f"   - session_metadata.json")
    print(f"   - metrics_XXXXX.jsonl")
    print(f"   - metrics_XXXXX.csv")
    print(f"   - summary_report.json")
    print(f"   - summary_report.txt")
    print(f"   - plots/ (visualizations)")
    
    print(f"\n✨ Demo complete! Check the experiment_results directory for detailed analysis.")

if __name__ == "__main__":
    main()
