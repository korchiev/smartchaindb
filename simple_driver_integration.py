#!/usr/bin/env python3
"""
Simple Driver Integration Script

This is a minimal integration script that you can easily add to your existing driver
to enable automatic results saving when experiments finish.
"""

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
    is_session_active
)

class SimpleMetricsIntegration:
    """Simple integration class for existing drivers"""
    
    def __init__(self):
        self.session_id = None
        self.experiment_started = False
    
    def start_experiment(self, experiment_name: str = "Driver_Experiment", 
                        notes: str = ""):
        """Start metrics collection for your experiment"""
        self.session_id = start_experiment_session(
            experiment_name=experiment_name,
            validation_types=['SHACL', 'TRADITIONAL'],
            operations_tested=['CREATE', 'TRANSFER', 'BUY_OFFER', 'SELL'],
            configuration={'driver_integration': True},
            notes=notes
        )
        self.experiment_started = True
        print(f"📊 Started metrics collection: {self.session_id}")
        return self.session_id
    
    def track_transaction(self, tx_id: str, operation: str, validation_type: str):
        """Track a single transaction - call this for each transaction you process"""
        from datetime import datetime
        
        # Start tracking
        start_transaction_tracking(tx_id, operation, validation_type, datetime.now().isoformat())
        
        # Mark lifecycle events (you can customize these based on your driver)
        mark_lifecycle_event(tx_id, 'before_tendermint')
        mark_lifecycle_event(tx_id, 'check_tx')
        
        # Track validation (you can customize the validation tracking)
        with validation_context(tx_id, validation_type) as validation_metrics:
            # Your validation logic here
            validation_metrics.validation_success = True
        
        mark_lifecycle_event(tx_id, 'deliver_tx')
        mark_lifecycle_event(tx_id, 'end_block')
        mark_lifecycle_event(tx_id, 'commit')
    
    def save_checkpoint(self, checkpoint_name: str = None):
        """Save intermediate results during long experiments"""
        if not self.experiment_started:
            print("⚠️  No experiment started")
            return None
        
        results_file = save_current_results(checkpoint_name)
        print(f"💾 Checkpoint saved: {results_file}")
        return results_file
    
    def end_experiment(self, generate_reports: bool = True):
        """End experiment and save all results - call this when your driver finishes"""
        if not self.experiment_started:
            print("⚠️  No experiment started")
            return None
        
        # Get final summary
        summary = get_performance_summary()
        print(f"📊 Final Results:")
        print(f"   Total Transactions: {summary['counters']['total_transactions']}")
        print(f"   SHACL: {summary['counters']['shacl_transactions']}")
        print(f"   Traditional: {summary['counters']['traditional_transactions']}")
        
        # End session and save results
        results = end_experiment_session(generate_reports)
        
        self.experiment_started = False
        print(f"✅ Experiment completed and results saved!")
        
        return results

# Global instance for easy use
metrics = SimpleMetricsIntegration()

# Convenience functions for your driver
def start_driver_experiment(experiment_name: str = "Driver_Experiment", notes: str = ""):
    """Start metrics collection - call this at the beginning of your driver"""
    return metrics.start_experiment(experiment_name, notes)

def track_driver_transaction(tx_id: str, operation: str, validation_type: str):
    """Track a transaction - call this for each transaction"""
    return metrics.track_transaction(tx_id, operation, validation_type)

def save_driver_checkpoint(checkpoint_name: str = None):
    """Save checkpoint - call this during long experiments"""
    return metrics.save_checkpoint(checkpoint_name)

def end_driver_experiment(generate_reports: bool = True):
    """End experiment - call this when your driver finishes"""
    return metrics.end_experiment(generate_reports)

# Example usage in your driver:
"""
# At the beginning of your driver:
start_driver_experiment("My_SHACL_Experiment", "Testing SHACL vs traditional validation")

# For each transaction you process:
track_driver_transaction("tx_001", "CREATE", "SHACL")
track_driver_transaction("tx_002", "TRANSFER", "TRADITIONAL")

# During long experiments (optional):
save_driver_checkpoint("mid_experiment")

# At the end of your driver:
end_driver_experiment(generate_reports=True)
"""
