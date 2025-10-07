#!/usr/bin/env python3
"""
Enhanced Metrics Integration Example

This example shows how to integrate the enhanced metrics system into BigchainDB
for comparing SHACL vs traditional validation performance.
"""

import time
import json
from datetime import datetime
from bigchaindb.enhanced_metrics import (
    start_transaction_tracking,
    mark_lifecycle_event,
    validation_context,
    track_shacl_phase,
    track_traditional_validation,
    track_validation_details,
    get_performance_summary
)

def simulate_shacl_validation(tx_id: str, operation: str):
    """Simulate SHACL validation with detailed phase tracking"""
    
    with validation_context(tx_id, 'SHACL') as validation_metrics:
        # Simulate Phase 1: Syntactic/Semantic validation
        phase1_start = time.time()
        time.sleep(0.01)  # Simulate SHACL syntactic validation
        phase1_duration = (time.time() - phase1_start) * 1000
        track_shacl_phase(tx_id, 'phase1', phase1_duration)
        
        # Simulate Phase 2: State consistency validation
        phase2_start = time.time()
        time.sleep(0.005)  # Simulate database queries for state validation
        phase2_duration = (time.time() - phase2_start) * 1000
        track_shacl_phase(tx_id, 'phase2', phase2_duration)
        
        # Track validation details
        track_validation_details(
            tx_id,
            metadata_fields_validated=8,
            asset_fields_validated=3,
            input_output_checks=2,
            database_queries=3,
            cache_hits=1,
            cache_misses=2
        )
        
        return True

def simulate_traditional_validation(tx_id: str, operation: str):
    """Simulate traditional validation with component tracking"""
    
    with validation_context(tx_id, 'TRADITIONAL') as validation_metrics:
        # Simulate schema validation
        schema_start = time.time()
        time.sleep(0.003)  # Simulate JSON schema validation
        schema_duration = (time.time() - schema_start) * 1000
        track_traditional_validation(tx_id, 'schema', schema_duration)
        
        # Simulate business logic validation
        business_start = time.time()
        time.sleep(0.008)  # Simulate business rule validation
        business_duration = (time.time() - business_start) * 1000
        track_traditional_validation(tx_id, 'business_logic', business_duration)
        
        # Simulate signature validation
        signature_start = time.time()
        time.sleep(0.002)  # Simulate cryptographic signature validation
        signature_duration = (time.time() - signature_start) * 1000
        track_traditional_validation(tx_id, 'signature', signature_duration)
        
        # Track validation details
        track_validation_details(
            tx_id,
            metadata_fields_validated=6,
            asset_fields_validated=2,
            input_output_checks=1,
            database_queries=1,
            cache_hits=0,
            cache_misses=1
        )
        
        return True

def simulate_transaction_lifecycle(tx_id: str, operation: str, validation_type: str):
    """Simulate complete transaction lifecycle with metrics tracking"""
    
    request_timestamp = datetime.now().isoformat()
    
    # Start transaction tracking
    metrics = start_transaction_tracking(tx_id, operation, validation_type, request_timestamp)
    
    # Simulate transaction processing phases
    mark_lifecycle_event(tx_id, 'before_tendermint')
    time.sleep(0.001)  # Simulate preprocessing
    
    mark_lifecycle_event(tx_id, 'check_tx')
    time.sleep(0.002)  # Simulate Tendermint check_tx
    
    # Perform validation based on type
    if validation_type == 'SHACL':
        validation_success = simulate_shacl_validation(tx_id, operation)
    else:
        validation_success = simulate_traditional_validation(tx_id, operation)
    
    mark_lifecycle_event(tx_id, 'deliver_tx')
    time.sleep(0.003)  # Simulate Tendermint deliver_tx
    
    mark_lifecycle_event(tx_id, 'end_block')
    time.sleep(0.001)  # Simulate end block processing
    
    mark_lifecycle_event(tx_id, 'commit')
    time.sleep(0.002)  # Simulate commit processing
    
    return validation_success

def run_comparison_experiment():
    """Run a comparison experiment between SHACL and traditional validation"""
    
    print("🚀 Starting Enhanced Metrics Comparison Experiment")
    print("=" * 60)
    
    # Test different transaction types
    operations = ['CREATE', 'TRANSFER', 'BUY_OFFER', 'SELL', 'REQUEST_RETURN', 'ACCEPT_RETURN']
    validation_types = ['SHACL', 'TRADITIONAL']
    
    # Generate test transactions
    transaction_count = 0
    
    for operation in operations:
        for validation_type in validation_types:
            # Run multiple transactions of each type
            for i in range(5):  # 5 transactions per operation/validation type
                tx_id = f"tx_{transaction_count:04d}_{operation}_{validation_type}"
                
                print(f"Processing {tx_id}...")
                
                try:
                    success = simulate_transaction_lifecycle(tx_id, operation, validation_type)
                    status = "✅ SUCCESS" if success else "❌ FAILED"
                    print(f"  {status}")
                except Exception as e:
                    print(f"  ❌ ERROR: {e}")
                
                transaction_count += 1
                
                # Small delay between transactions
                time.sleep(0.01)
    
    print("\n" + "=" * 60)
    print("📊 EXPERIMENT COMPLETE")
    
    # Print performance summary
    summary = get_performance_summary()
    print(f"\nPerformance Summary:")
    print(f"  Total Transactions: {summary['counters']['total_transactions']}")
    print(f"  SHACL Transactions: {summary['counters']['shacl_transactions']}")
    print(f"  Traditional Transactions: {summary['counters']['traditional_transactions']}")
    print(f"  Average SHACL Time: {summary['counters']['avg_shacl_time_ms']:.2f} ms")
    print(f"  Average Traditional Time: {summary['counters']['avg_traditional_time_ms']:.2f} ms")
    print(f"  Average Total Latency: {summary['counters']['avg_total_latency_ms']:.2f} ms")
    
    print(f"\n📁 Metrics saved to:")
    print(f"  - enhanced-metrics.jsonl (detailed logs)")
    print(f"  - enhanced-metrics.csv (structured data)")
    
    print(f"\n🔍 To analyze the results, run:")
    print(f"  python analyze_metrics.py --plots")

def demonstrate_real_time_monitoring():
    """Demonstrate real-time monitoring capabilities"""
    
    print("\n🔍 REAL-TIME MONITORING DEMO")
    print("=" * 40)
    
    # Run a few transactions
    for i in range(3):
        tx_id = f"monitor_tx_{i:03d}"
        operation = 'CREATE'
        validation_type = 'SHACL' if i % 2 == 0 else 'TRADITIONAL'
        
        simulate_transaction_lifecycle(tx_id, operation, validation_type)
        
        # Show real-time summary
        summary = get_performance_summary()
        print(f"Transaction {i+1}: {summary['counters']['total_transactions']} total, "
              f"{summary['counters']['shacl_transactions']} SHACL, "
              f"{summary['counters']['traditional_transactions']} Traditional")
        
        time.sleep(0.1)

if __name__ == "__main__":
    # Run the comparison experiment
    run_comparison_experiment()
    
    # Demonstrate real-time monitoring
    demonstrate_real_time_monitoring()
    
    print("\n✨ Enhanced metrics system demonstration complete!")
    print("Check the generated files for detailed analysis.")
