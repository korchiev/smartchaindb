#!/usr/bin/env python3
"""
Driver Integration Example with Automatic Results Saving

This example shows how to integrate the enhanced metrics system with your driver
to automatically save results when experiments finish.
"""

import time
import json
import os
from datetime import datetime
from bigchaindb.enhanced_metrics import (
    start_experiment_session,
    end_experiment_session,
    save_current_results,
    start_transaction_tracking,
    mark_lifecycle_event,
    validation_context,
    track_shacl_phase,
    track_traditional_validation,
    track_validation_details,
    get_performance_summary,
    is_session_active,
    get_current_session
)

class ExperimentDriver:
    """Example driver that demonstrates automatic results saving"""
    
    def __init__(self, experiment_name: str = "SHACL_vs_Traditional_Comparison"):
        self.experiment_name = experiment_name
        self.session_id = None
        self.results_saved = False
    
    def start_experiment(self, validation_types: list = None, operations: list = None, 
                        configuration: dict = None, notes: str = ""):
        """Start a new experiment session"""
        print(f"🚀 Starting experiment: {self.experiment_name}")
        
        self.session_id = start_experiment_session(
            experiment_name=self.experiment_name,
            validation_types=validation_types or ['SHACL', 'TRADITIONAL'],
            operations_tested=operations or ['CREATE', 'TRANSFER', 'BUY_OFFER', 'SELL'],
            configuration=configuration or {},
            notes=notes
        )
        
        print(f"✅ Experiment session started: {self.session_id}")
        return self.session_id
    
    def run_transactions(self, num_transactions: int = 100, 
                        shacl_percentage: float = 0.5):
        """Run a batch of transactions with mixed validation types"""
        print(f"\n📊 Running {num_transactions} transactions...")
        print(f"   SHACL percentage: {shacl_percentage * 100:.1f}%")
        
        operations = ['CREATE', 'TRANSFER', 'BUY_OFFER', 'SELL', 'REQUEST_RETURN']
        
        for i in range(num_transactions):
            # Determine validation type based on percentage
            use_shacl = (i / num_transactions) < shacl_percentage
            validation_type = 'SHACL' if use_shacl else 'TRADITIONAL'
            
            # Select random operation
            operation = operations[i % len(operations)]
            
            # Generate transaction ID
            tx_id = f"driver_tx_{i:04d}_{operation}_{validation_type}"
            
            # Simulate transaction processing
            self._simulate_transaction(tx_id, operation, validation_type)
            
            # Progress update every 10 transactions
            if (i + 1) % 10 == 0:
                summary = get_performance_summary()
                print(f"   Progress: {i + 1}/{num_transactions} "
                      f"(SHACL: {summary['counters']['shacl_transactions']}, "
                      f"Traditional: {summary['counters']['traditional_transactions']})")
            
            # Small delay to simulate real processing
            time.sleep(0.001)
    
    def _simulate_transaction(self, tx_id: str, operation: str, validation_type: str):
        """Simulate a single transaction with metrics tracking"""
        request_timestamp = datetime.now().isoformat()
        
        # Start transaction tracking
        start_transaction_tracking(tx_id, operation, validation_type, request_timestamp)
        
        # Simulate transaction lifecycle
        mark_lifecycle_event(tx_id, 'before_tendermint')
        time.sleep(0.0001)
        
        mark_lifecycle_event(tx_id, 'check_tx')
        time.sleep(0.0002)
        
        # Perform validation based on type
        with validation_context(tx_id, validation_type) as validation_metrics:
            if validation_type == 'SHACL':
                self._simulate_shacl_validation(tx_id)
            else:
                self._simulate_traditional_validation(tx_id)
            
            validation_metrics.validation_success = True
        
        mark_lifecycle_event(tx_id, 'deliver_tx')
        time.sleep(0.0003)
        
        mark_lifecycle_event(tx_id, 'end_block')
        time.sleep(0.0001)
        
        mark_lifecycle_event(tx_id, 'commit')
        time.sleep(0.0002)
    
    def _simulate_shacl_validation(self, tx_id: str):
        """Simulate SHACL validation with phase tracking"""
        # Phase 1: Syntactic/Semantic validation
        phase1_start = time.time()
        time.sleep(0.01)  # Simulate SHACL validation
        phase1_duration = (time.time() - phase1_start) * 1000
        track_shacl_phase(tx_id, 'phase1', phase1_duration)
        
        # Phase 2: State consistency validation
        phase2_start = time.time()
        time.sleep(0.005)  # Simulate database queries
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
    
    def _simulate_traditional_validation(self, tx_id: str):
        """Simulate traditional validation with component tracking"""
        # Schema validation
        schema_start = time.time()
        time.sleep(0.003)
        schema_duration = (time.time() - schema_start) * 1000
        track_traditional_validation(tx_id, 'schema', schema_duration)
        
        # Business logic validation
        business_start = time.time()
        time.sleep(0.008)
        business_duration = (time.time() - business_start) * 1000
        track_traditional_validation(tx_id, 'business_logic', business_duration)
        
        # Signature validation
        signature_start = time.time()
        time.sleep(0.002)
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
    
    def save_intermediate_results(self, checkpoint_name: str = None):
        """Save intermediate results during long experiments"""
        if not checkpoint_name:
            checkpoint_name = f"checkpoint_{datetime.now().strftime('%H%M%S')}"
        
        results_file = save_current_results(checkpoint_name)
        print(f"💾 Intermediate results saved: {results_file}")
        return results_file
    
    def end_experiment(self, generate_reports: bool = True):
        """End the experiment and automatically save all results"""
        if not is_session_active():
            print("⚠️  No active experiment session to end")
            return None
        
        print(f"\n🏁 Ending experiment session: {self.session_id}")
        
        # Get final performance summary
        final_summary = get_performance_summary()
        print(f"📊 Final Statistics:")
        print(f"   Total Transactions: {final_summary['counters']['total_transactions']}")
        print(f"   SHACL Transactions: {final_summary['counters']['shacl_transactions']}")
        print(f"   Traditional Transactions: {final_summary['counters']['traditional_transactions']}")
        print(f"   Average SHACL Time: {final_summary['counters']['avg_shacl_time_ms']:.2f} ms")
        print(f"   Average Traditional Time: {final_summary['counters']['avg_traditional_time_ms']:.2f} ms")
        
        # End session and save results
        results_summary = end_experiment_session(generate_reports)
        
        self.results_saved = True
        print(f"✅ Experiment completed and results saved!")
        
        return results_summary
    
    def run_comparison_experiment(self, num_transactions: int = 200):
        """Run a complete comparison experiment"""
        print("🔬 Starting SHACL vs Traditional Validation Comparison Experiment")
        print("=" * 70)
        
        # Start experiment
        self.start_experiment(
            experiment_name="SHACL_vs_Traditional_Comparison",
            validation_types=['SHACL', 'TRADITIONAL'],
            operations=['CREATE', 'TRANSFER', 'BUY_OFFER', 'SELL', 'REQUEST_RETURN'],
            configuration={
                'num_transactions': num_transactions,
                'shacl_percentage': 0.5,
                'experiment_type': 'comparison'
            },
            notes="Automated comparison experiment between SHACL and traditional validation"
        )
        
        try:
            # Run transactions with 50/50 split
            self.run_transactions(num_transactions, shacl_percentage=0.5)
            
            # Save intermediate results
            self.save_intermediate_results("mid_experiment")
            
            # End experiment and save results
            results = self.end_experiment(generate_reports=True)
            
            if results and 'error' not in results:
                print(f"\n📈 Reports generated:")
                print(f"   Summary: {results.get('summary_file', 'N/A')}")
                print(f"   Text Report: {results.get('text_summary_file', 'N/A')}")
                print(f"   Plots: {results.get('plots_directory', 'N/A')}")
            
            return results
            
        except Exception as e:
            print(f"❌ Experiment failed: {e}")
            # Still try to save results
            try:
                self.end_experiment(generate_reports=False)
            except:
                pass
            raise
    
    def run_load_test_experiment(self, num_transactions: int = 500):
        """Run a load test experiment"""
        print("⚡ Starting Load Test Experiment")
        print("=" * 50)
        
        self.start_experiment(
            experiment_name="Load_Test_Experiment",
            validation_types=['SHACL', 'TRADITIONAL'],
            operations=['CREATE', 'TRANSFER'],
            configuration={
                'num_transactions': num_transactions,
                'experiment_type': 'load_test'
            },
            notes="Load test to measure performance under high transaction volume"
        )
        
        try:
            # Run transactions with 70% SHACL, 30% traditional
            self.run_transactions(num_transactions, shacl_percentage=0.7)
            
            # Save intermediate results every 100 transactions
            for i in range(100, num_transactions, 100):
                self.save_intermediate_results(f"load_test_checkpoint_{i}")
            
            results = self.end_experiment(generate_reports=True)
            return results
            
        except Exception as e:
            print(f"❌ Load test failed: {e}")
            try:
                self.end_experiment(generate_reports=False)
            except:
                pass
            raise

def main():
    """Main function demonstrating driver usage"""
    print("🚀 Enhanced Metrics Driver Integration Demo")
    print("=" * 60)
    
    # Create driver instance
    driver = ExperimentDriver("Demo_Experiment")
    
    try:
        # Run comparison experiment
        print("\n1️⃣ Running Comparison Experiment...")
        comparison_results = driver.run_comparison_experiment(num_transactions=100)
        
        # Wait a bit between experiments
        time.sleep(2)
        
        # Run load test experiment
        print("\n2️⃣ Running Load Test Experiment...")
        load_test_results = driver.run_load_test_experiment(num_transactions=200)
        
        print("\n✨ All experiments completed successfully!")
        print("📁 Check the 'experiment_results' directory for detailed results")
        
    except KeyboardInterrupt:
        print("\n⏹️  Experiment interrupted by user")
        if is_session_active():
            print("💾 Saving current results...")
            driver.end_experiment(generate_reports=True)
    
    except Exception as e:
        print(f"\n❌ Experiment failed: {e}")
        if is_session_active():
            print("💾 Attempting to save partial results...")
            try:
                driver.end_experiment(generate_reports=False)
            except:
                print("⚠️  Could not save results")

if __name__ == "__main__":
    main()
