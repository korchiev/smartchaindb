"""
Enhanced Metrics System for BigchainDB

This module provides comprehensive metrics capture for comparing SHACL vs traditional validation.
It tracks detailed performance metrics, validation times, and system behavior.
"""

import time
import logging
import json
import csv
import shutil
from datetime import datetime
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from contextlib import contextmanager
import os
import uuid

# Enhanced metrics logger
enhanced_metrics_logger = logging.getLogger("enhanced_metrics")

@dataclass
class ValidationMetrics:
    """Detailed validation metrics for a single transaction"""
    tx_id: str
    operation: str
    validation_type: str  # 'SHACL' or 'TRADITIONAL'
    validation_start_time: float
    validation_end_time: float
    validation_duration_ms: float
    validation_success: bool
    validation_errors: List[str]
    shacl_phase1_time_ms: Optional[float] = None  # Syntactic/semantic validation
    shacl_phase2_time_ms: Optional[float] = None  # State consistency validation
    shacl_total_time_ms: Optional[float] = None
    traditional_validation_time_ms: Optional[float] = None
    schema_validation_time_ms: Optional[float] = None
    business_logic_time_ms: Optional[float] = None
    signature_validation_time_ms: Optional[float] = None
    metadata_fields_validated: int = 0
    asset_fields_validated: int = 0
    input_output_checks: int = 0
    database_queries: int = 0
    cache_hits: int = 0
    cache_misses: int = 0

@dataclass
class TransactionLifecycleMetrics:
    """Complete transaction lifecycle metrics"""
    tx_id: str
    operation: str
    validation_type: str
    request_timestamp: str
    
    # Lifecycle timestamps
    received_time: float
    before_tendermint_time: float
    check_tx_time: float
    deliver_tx_time: float
    end_block_time: float
    commit_time: float
    
    # Calculated durations
    total_latency_ms: float
    tendermint_overhead_ms: float
    validation_overhead_ms: float
    commit_overhead_ms: float
    
    # Validation details
    validation_metrics: Optional[ValidationMetrics] = None
    
    # System metrics
    memory_usage_mb: Optional[float] = None
    cpu_usage_percent: Optional[float] = None
    database_connection_time_ms: Optional[float] = None

@dataclass
class ExperimentSession:
    """Experiment session metadata"""
    session_id: str
    start_time: str
    end_time: Optional[str] = None
    experiment_name: str = "default"
    validation_types: List[str] = None
    operations_tested: List[str] = None
    total_transactions: int = 0
    shacl_transactions: int = 0
    traditional_transactions: int = 0
    configuration: Dict[str, Any] = None
    notes: str = ""
    
    def __post_init__(self):
        if self.validation_types is None:
            self.validation_types = ['SHACL', 'TRADITIONAL']
        if self.operations_tested is None:
            self.operations_tested = []
        if self.configuration is None:
            self.configuration = {}

class EnhancedMetricsCollector:
    """Enhanced metrics collector for SHACL vs traditional validation comparison"""
    
    def __init__(self, log_file: str = "enhanced-metrics.jsonl", csv_file: str = "enhanced-metrics.csv", 
                 results_dir: str = "experiment_results"):
        self.log_file = log_file
        self.csv_file = csv_file
        self.results_dir = results_dir
        self.active_transactions: Dict[str, TransactionLifecycleMetrics] = {}
        self.validation_contexts: Dict[str, Dict[str, Any]] = {}
        
        # Experiment session management
        self.current_session: Optional[ExperimentSession] = None
        self.session_started = False
        
        # Setup enhanced logging
        self._setup_enhanced_logging()
        
        # Performance counters
        self.counters = {
            'total_transactions': 0,
            'shacl_transactions': 0,
            'traditional_transactions': 0,
            'validation_failures': 0,
            'shacl_failures': 0,
            'traditional_failures': 0,
            'avg_shacl_time_ms': 0,
            'avg_traditional_time_ms': 0,
            'avg_total_latency_ms': 0
        }
        
        # Ensure results directory exists
        os.makedirs(self.results_dir, exist_ok=True)
    
    def _setup_enhanced_logging(self):
        """Setup enhanced metrics logging"""
        handler = logging.FileHandler(self.log_file)
        handler.setFormatter(logging.Formatter('%(message)s'))
        enhanced_metrics_logger.addHandler(handler)
        enhanced_metrics_logger.setLevel(logging.INFO)
    
    def start_transaction_tracking(self, tx_id: str, operation: str, validation_type: str, 
                                 request_timestamp: str) -> TransactionLifecycleMetrics:
        """Start tracking a transaction's complete lifecycle"""
        current_time = time.time()
        
        metrics = TransactionLifecycleMetrics(
            tx_id=tx_id,
            operation=operation,
            validation_type=validation_type,
            request_timestamp=request_timestamp,
            received_time=current_time,
            before_tendermint_time=0,
            check_tx_time=0,
            deliver_tx_time=0,
            end_block_time=0,
            commit_time=0,
            total_latency_ms=0,
            tendermint_overhead_ms=0,
            validation_overhead_ms=0,
            commit_overhead_ms=0
        )
        
        self.active_transactions[tx_id] = metrics
        self.counters['total_transactions'] += 1
        
        if validation_type == 'SHACL':
            self.counters['shacl_transactions'] += 1
        else:
            self.counters['traditional_transactions'] += 1
        
        return metrics
    
    def mark_lifecycle_event(self, tx_id: str, event: str):
        """Mark a lifecycle event timestamp"""
        if tx_id not in self.active_transactions:
            return
        
        current_time = time.time()
        metrics = self.active_transactions[tx_id]
        
        if event == 'before_tendermint':
            metrics.before_tendermint_time = current_time
        elif event == 'check_tx':
            metrics.check_tx_time = current_time
        elif event == 'deliver_tx':
            metrics.deliver_tx_time = current_time
        elif event == 'end_block':
            metrics.end_block_time = current_time
        elif event == 'commit':
            metrics.commit_time = current_time
            self._finalize_transaction_metrics(metrics)
    
    @contextmanager
    def validation_context(self, tx_id: str, validation_type: str):
        """Context manager for tracking validation performance"""
        start_time = time.time()
        validation_metrics = ValidationMetrics(
            tx_id=tx_id,
            operation=self.active_transactions[tx_id].operation if tx_id in self.active_transactions else 'UNKNOWN',
            validation_type=validation_type,
            validation_start_time=start_time,
            validation_end_time=0,
            validation_duration_ms=0,
            validation_success=False,
            validation_errors=[]
        )
        
        self.validation_contexts[tx_id] = {
            'metrics': validation_metrics,
            'start_time': start_time,
            'phase_times': {}
        }
        
        try:
            yield validation_metrics
            validation_metrics.validation_success = True
        except Exception as e:
            validation_metrics.validation_errors.append(str(e))
            validation_metrics.validation_success = False
            raise
        finally:
            end_time = time.time()
            validation_metrics.validation_end_time = end_time
            validation_metrics.validation_duration_ms = (end_time - start_time) * 1000
            
            # Update counters
            if validation_type == 'SHACL':
                self.counters['avg_shacl_time_ms'] = self._update_avg(
                    self.counters['avg_shacl_time_ms'], 
                    validation_metrics.validation_duration_ms,
                    self.counters['shacl_transactions']
                )
                if not validation_metrics.validation_success:
                    self.counters['shacl_failures'] += 1
            else:
                self.counters['avg_traditional_time_ms'] = self._update_avg(
                    self.counters['avg_traditional_time_ms'],
                    validation_metrics.validation_duration_ms,
                    self.counters['traditional_transactions']
                )
                if not validation_metrics.validation_success:
                    self.counters['traditional_failures'] += 1
            
            if not validation_metrics.validation_success:
                self.counters['validation_failures'] += 1
            
            # Attach to transaction metrics
            if tx_id in self.active_transactions:
                self.active_transactions[tx_id].validation_metrics = validation_metrics
    
    def track_shacl_phase(self, tx_id: str, phase: str, duration_ms: float):
        """Track SHACL validation phases"""
        if tx_id not in self.validation_contexts:
            return
        
        validation_metrics = self.validation_contexts[tx_id]['metrics']
        
        if phase == 'phase1':
            validation_metrics.shacl_phase1_time_ms = duration_ms
        elif phase == 'phase2':
            validation_metrics.shacl_phase2_time_ms = duration_ms
        
        validation_metrics.shacl_total_time_ms = (
            (validation_metrics.shacl_phase1_time_ms or 0) + 
            (validation_metrics.shacl_phase2_time_ms or 0)
        )
    
    def track_traditional_validation(self, tx_id: str, component: str, duration_ms: float):
        """Track traditional validation components"""
        if tx_id not in self.validation_contexts:
            return
        
        validation_metrics = self.validation_contexts[tx_id]['metrics']
        
        if component == 'schema':
            validation_metrics.schema_validation_time_ms = duration_ms
        elif component == 'business_logic':
            validation_metrics.business_logic_time_ms = duration_ms
        elif component == 'signature':
            validation_metrics.signature_validation_time_ms = duration_ms
        
        validation_metrics.traditional_validation_time_ms = (
            (validation_metrics.schema_validation_time_ms or 0) +
            (validation_metrics.business_logic_time_ms or 0) +
            (validation_metrics.signature_validation_time_ms or 0)
        )
    
    def track_validation_details(self, tx_id: str, **kwargs):
        """Track detailed validation metrics"""
        if tx_id not in self.validation_contexts:
            return
        
        validation_metrics = self.validation_contexts[tx_id]['metrics']
        
        for key, value in kwargs.items():
            if hasattr(validation_metrics, key):
                setattr(validation_metrics, key, value)
    
    def _finalize_transaction_metrics(self, metrics: TransactionLifecycleMetrics):
        """Calculate final metrics and log the complete transaction"""
        if metrics.before_tendermint_time > 0:
            metrics.tendermint_overhead_ms = (metrics.deliver_tx_time - metrics.before_tendermint_time) * 1000
        
        if metrics.validation_metrics:
            metrics.validation_overhead_ms = metrics.validation_metrics.validation_duration_ms
        
        if metrics.commit_time > 0:
            metrics.commit_overhead_ms = (metrics.commit_time - metrics.deliver_tx_time) * 1000
            metrics.total_latency_ms = (metrics.commit_time - metrics.received_time) * 1000
        
        # Update average latency
        self.counters['avg_total_latency_ms'] = self._update_avg(
            self.counters['avg_total_latency_ms'],
            metrics.total_latency_ms,
            self.counters['total_transactions']
        )
        
        # Log complete transaction metrics
        self._log_transaction_metrics(metrics)
        
        # Write to CSV
        self._write_to_csv(metrics)
        
        # Cleanup
        if metrics.tx_id in self.active_transactions:
            del self.active_transactions[metrics.tx_id]
        if metrics.tx_id in self.validation_contexts:
            del self.validation_contexts[metrics.tx_id]
    
    def _log_transaction_metrics(self, metrics: TransactionLifecycleMetrics):
        """Log transaction metrics to JSONL file"""
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'transaction': asdict(metrics),
            'counters': self.counters.copy()
        }
        
        enhanced_metrics_logger.info(json.dumps(log_entry))
    
    def _write_to_csv(self, metrics: TransactionLifecycleMetrics):
        """Write metrics to CSV file"""
        file_exists = os.path.exists(self.csv_file)
        
        with open(self.csv_file, 'a', newline='') as csvfile:
            fieldnames = [
                'timestamp', 'tx_id', 'operation', 'validation_type',
                'total_latency_ms', 'validation_duration_ms', 'tendermint_overhead_ms',
                'validation_success', 'validation_errors_count',
                'shacl_phase1_time_ms', 'shacl_phase2_time_ms', 'shacl_total_time_ms',
                'traditional_validation_time_ms', 'schema_validation_time_ms',
                'business_logic_time_ms', 'signature_validation_time_ms',
                'metadata_fields_validated', 'asset_fields_validated',
                'input_output_checks', 'database_queries', 'cache_hits', 'cache_misses'
            ]
            
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            
            if not file_exists:
                writer.writeheader()
            
            row = {
                'timestamp': datetime.now().isoformat(),
                'tx_id': metrics.tx_id,
                'operation': metrics.operation,
                'validation_type': metrics.validation_type,
                'total_latency_ms': metrics.total_latency_ms,
                'validation_duration_ms': metrics.validation_metrics.validation_duration_ms if metrics.validation_metrics else 0,
                'tendermint_overhead_ms': metrics.tendermint_overhead_ms,
                'validation_success': metrics.validation_metrics.validation_success if metrics.validation_metrics else False,
                'validation_errors_count': len(metrics.validation_metrics.validation_errors) if metrics.validation_metrics else 0,
                'shacl_phase1_time_ms': metrics.validation_metrics.shacl_phase1_time_ms if metrics.validation_metrics else None,
                'shacl_phase2_time_ms': metrics.validation_metrics.shacl_phase2_time_ms if metrics.validation_metrics else None,
                'shacl_total_time_ms': metrics.validation_metrics.shacl_total_time_ms if metrics.validation_metrics else None,
                'traditional_validation_time_ms': metrics.validation_metrics.traditional_validation_time_ms if metrics.validation_metrics else None,
                'schema_validation_time_ms': metrics.validation_metrics.schema_validation_time_ms if metrics.validation_metrics else None,
                'business_logic_time_ms': metrics.validation_metrics.business_logic_time_ms if metrics.validation_metrics else None,
                'signature_validation_time_ms': metrics.validation_metrics.signature_validation_time_ms if metrics.validation_metrics else None,
                'metadata_fields_validated': metrics.validation_metrics.metadata_fields_validated if metrics.validation_metrics else 0,
                'asset_fields_validated': metrics.validation_metrics.asset_fields_validated if metrics.validation_metrics else 0,
                'input_output_checks': metrics.validation_metrics.input_output_checks if metrics.validation_metrics else 0,
                'database_queries': metrics.validation_metrics.database_queries if metrics.validation_metrics else 0,
                'cache_hits': metrics.validation_metrics.cache_hits if metrics.validation_metrics else 0,
                'cache_misses': metrics.validation_metrics.cache_misses if metrics.validation_metrics else 0,
            }
            
            writer.writerow(row)
    
    def _update_avg(self, current_avg: float, new_value: float, count: int) -> float:
        """Update running average"""
        if count <= 1:
            return new_value
        return (current_avg * (count - 1) + new_value) / count
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get current performance summary"""
        return {
            'counters': self.counters.copy(),
            'active_transactions': len(self.active_transactions),
            'active_validations': len(self.validation_contexts),
            'timestamp': datetime.now().isoformat()
        }
    
    def reset_counters(self):
        """Reset performance counters"""
        for key in self.counters:
            self.counters[key] = 0
    
    def start_experiment_session(self, experiment_name: str = "default", 
                                validation_types: List[str] = None,
                                operations_tested: List[str] = None,
                                configuration: Dict[str, Any] = None,
                                notes: str = "") -> str:
        """Start a new experiment session"""
        session_id = str(uuid.uuid4())[:8]
        start_time = datetime.now().isoformat()
        
        self.current_session = ExperimentSession(
            session_id=session_id,
            start_time=start_time,
            experiment_name=experiment_name,
            validation_types=validation_types or ['SHACL', 'TRADITIONAL'],
            operations_tested=operations_tested or [],
            configuration=configuration or {},
            notes=notes
        )
        
        self.session_started = True
        
        # Create session-specific files
        session_dir = os.path.join(self.results_dir, f"session_{session_id}")
        os.makedirs(session_dir, exist_ok=True)
        
        self.session_log_file = os.path.join(session_dir, f"metrics_{session_id}.jsonl")
        self.session_csv_file = os.path.join(session_dir, f"metrics_{session_id}.csv")
        
        # Update logging to use session-specific file
        self._setup_session_logging()
        
        print(f"🚀 Started experiment session: {session_id}")
        print(f"   Experiment: {experiment_name}")
        print(f"   Validation types: {self.current_session.validation_types}")
        print(f"   Results directory: {session_dir}")
        
        return session_id
    
    def end_experiment_session(self, generate_reports: bool = True) -> Dict[str, Any]:
        """End the current experiment session and save results"""
        if not self.current_session or not self.session_started:
            print("⚠️  No active experiment session to end")
            return {}
        
        end_time = datetime.now().isoformat()
        self.current_session.end_time = end_time
        
        # Update session statistics
        self.current_session.total_transactions = self.counters['total_transactions']
        self.current_session.shacl_transactions = self.counters['shacl_transactions']
        self.current_session.traditional_transactions = self.counters['traditional_transactions']
        
        # Save session metadata
        session_dir = os.path.join(self.results_dir, f"session_{self.current_session.session_id}")
        session_metadata_file = os.path.join(session_dir, "session_metadata.json")
        
        with open(session_metadata_file, 'w') as f:
            json.dump(asdict(self.current_session), f, indent=2)
        
        # Copy current metrics files to session directory
        if os.path.exists(self.log_file):
            shutil.copy2(self.log_file, self.session_log_file)
        if os.path.exists(self.csv_file):
            shutil.copy2(self.csv_file, self.session_csv_file)
        
        # Generate comprehensive reports
        results_summary = {}
        if generate_reports:
            results_summary = self._generate_session_reports(session_dir)
        
        # Print session summary
        print(f"\n📊 Experiment session {self.current_session.session_id} completed!")
        print(f"   Duration: {self._calculate_session_duration()}")
        print(f"   Total transactions: {self.current_session.total_transactions}")
        print(f"   SHACL transactions: {self.current_session.shacl_transactions}")
        print(f"   Traditional transactions: {self.current_session.traditional_transactions}")
        print(f"   Results saved to: {session_dir}")
        
        # Reset for next session
        self.session_started = False
        self.current_session = None
        
        return results_summary
    
    def _setup_session_logging(self):
        """Setup session-specific logging"""
        # Remove existing handlers
        for handler in enhanced_metrics_logger.handlers[:]:
            enhanced_metrics_logger.removeHandler(handler)
        
        # Add session-specific handler
        handler = logging.FileHandler(self.session_log_file)
        handler.setFormatter(logging.Formatter('%(message)s'))
        enhanced_metrics_logger.addHandler(handler)
        enhanced_metrics_logger.setLevel(logging.INFO)
    
    def _calculate_session_duration(self) -> str:
        """Calculate session duration"""
        if not self.current_session or not self.current_session.end_time:
            return "Unknown"
        
        start_dt = datetime.fromisoformat(self.current_session.start_time)
        end_dt = datetime.fromisoformat(self.current_session.end_time)
        duration = end_dt - start_dt
        
        hours, remainder = divmod(duration.total_seconds(), 3600)
        minutes, seconds = divmod(remainder, 60)
        
        if hours > 0:
            return f"{int(hours)}h {int(minutes)}m {int(seconds)}s"
        elif minutes > 0:
            return f"{int(minutes)}m {int(seconds)}s"
        else:
            return f"{int(seconds)}s"
    
    def _generate_session_reports(self, session_dir: str) -> Dict[str, Any]:
        """Generate comprehensive reports for the session"""
        reports = {}
        
        try:
            # Import analysis tool
            from analyze_metrics import MetricsAnalyzer
            
            # Analyze session data
            analyzer = MetricsAnalyzer(self.session_csv_file)
            summary_report = analyzer.generate_summary_report()
            
            # Save summary report
            summary_file = os.path.join(session_dir, "summary_report.json")
            with open(summary_file, 'w') as f:
                json.dump(summary_report, f, indent=2)
            
            # Generate visualizations
            plots_dir = os.path.join(session_dir, "plots")
            analyzer.generate_visualizations(plots_dir)
            
            # Generate text summary
            text_summary_file = os.path.join(session_dir, "summary_report.txt")
            with open(text_summary_file, 'w') as f:
                f.write(self._format_text_summary(summary_report))
            
            reports = {
                'summary_report': summary_report,
                'plots_directory': plots_dir,
                'summary_file': summary_file,
                'text_summary_file': text_summary_file
            }
            
            print(f"   📈 Generated reports and visualizations")
            
        except Exception as e:
            print(f"   ⚠️  Error generating reports: {e}")
            reports = {'error': str(e)}
        
        return reports
    
    def _format_text_summary(self, summary_report: Dict[str, Any]) -> str:
        """Format summary report as text"""
        if 'error' in summary_report:
            return f"Error generating summary: {summary_report['error']}"
        
        text = []
        text.append("=" * 80)
        text.append("EXPERIMENT SESSION SUMMARY REPORT")
        text.append("=" * 80)
        
        # Overview
        if 'overview' in summary_report:
            overview = summary_report['overview']
            text.append(f"\n📊 OVERVIEW:")
            text.append(f"   Total Transactions: {overview['total_transactions']}")
            text.append(f"   SHACL Transactions: {overview['shacl_transactions']} ({overview['shacl_percentage']:.1f}%)")
            text.append(f"   Traditional Transactions: {overview['traditional_transactions']}")
        
        # Latency comparison
        if 'latency_comparison' in summary_report and 'performance_difference' in summary_report['latency_comparison']:
            diff = summary_report['latency_comparison']['performance_difference']
            text.append(f"\n⚡ LATENCY COMPARISON:")
            text.append(f"   SHACL Average Latency: {summary_report['latency_comparison']['shacl']['avg_total_latency_ms']:.2f} ms")
            text.append(f"   Traditional Average Latency: {summary_report['latency_comparison']['traditional']['avg_total_latency_ms']:.2f} ms")
            text.append(f"   Performance Difference: {diff['shacl_vs_traditional_ms']:.2f} ms ({diff['shacl_vs_traditional_percent']:.1f}%)")
            text.append(f"   Faster Method: {diff['faster_method']}")
        
        # Validation performance
        text.append(f"\n🔍 VALIDATION PERFORMANCE:")
        if 'validation_performance' in summary_report:
            perf = summary_report['validation_performance']
            if 'shacl' in perf:
                text.append(f"   SHACL Validation Time: {perf['shacl']['avg_validation_time_ms']:.2f} ms")
                text.append(f"   SHACL Success Rate: {perf['shacl']['success_rate']:.1f}%")
            if 'traditional' in perf:
                text.append(f"   Traditional Validation Time: {perf['traditional']['avg_validation_time_ms']:.2f} ms")
                text.append(f"   Traditional Success Rate: {perf['traditional']['success_rate']:.1f}%")
        
        # Error analysis
        if 'error_analysis' in summary_report:
            error_analysis = summary_report['error_analysis']
            text.append(f"\n❌ ERROR ANALYSIS:")
            text.append(f"   Total Failures: {error_analysis['total_failures']}")
            text.append(f"   SHACL Failures: {error_analysis['shacl_failures']}")
            text.append(f"   Traditional Failures: {error_analysis['traditional_failures']}")
        
        text.append("\n" + "=" * 80)
        
        return "\n".join(text)
    
    def save_current_results(self, filename_prefix: str = None) -> str:
        """Save current results without ending session"""
        if not filename_prefix:
            filename_prefix = f"results_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        results_file = os.path.join(self.results_dir, f"{filename_prefix}.json")
        
        results_data = {
            'timestamp': datetime.now().isoformat(),
            'session': asdict(self.current_session) if self.current_session else None,
            'counters': self.counters.copy(),
            'active_transactions': len(self.active_transactions),
            'active_validations': len(self.validation_contexts)
        }
        
        with open(results_file, 'w') as f:
            json.dump(results_data, f, indent=2)
        
        print(f"💾 Current results saved to: {results_file}")
        return results_file

# Global metrics collector instance
enhanced_metrics_collector = EnhancedMetricsCollector()

# Convenience functions for easy integration
def start_transaction_tracking(tx_id: str, operation: str, validation_type: str, request_timestamp: str):
    """Start tracking a transaction"""
    return enhanced_metrics_collector.start_transaction_tracking(tx_id, operation, validation_type, request_timestamp)

def mark_lifecycle_event(tx_id: str, event: str):
    """Mark a lifecycle event"""
    enhanced_metrics_collector.mark_lifecycle_event(tx_id, event)

def validation_context(tx_id: str, validation_type: str):
    """Get validation context manager"""
    return enhanced_metrics_collector.validation_context(tx_id, validation_type)

def track_shacl_phase(tx_id: str, phase: str, duration_ms: float):
    """Track SHACL validation phase"""
    enhanced_metrics_collector.track_shacl_phase(tx_id, phase, duration_ms)

def track_traditional_validation(tx_id: str, component: str, duration_ms: float):
    """Track traditional validation component"""
    enhanced_metrics_collector.track_traditional_validation(tx_id, component, duration_ms)

def track_validation_details(tx_id: str, **kwargs):
    """Track detailed validation metrics"""
    enhanced_metrics_collector.track_validation_details(tx_id, **kwargs)

def get_performance_summary():
    """Get current performance summary"""
    return enhanced_metrics_collector.get_performance_summary()

def start_experiment_session(experiment_name: str = "default", 
                           validation_types: List[str] = None,
                           operations_tested: List[str] = None,
                           configuration: Dict[str, Any] = None,
                           notes: str = "") -> str:
    """Start a new experiment session"""
    return enhanced_metrics_collector.start_experiment_session(
        experiment_name, validation_types, operations_tested, configuration, notes
    )

def end_experiment_session(generate_reports: bool = True) -> Dict[str, Any]:
    """End the current experiment session and save results"""
    return enhanced_metrics_collector.end_experiment_session(generate_reports)

def save_current_results(filename_prefix: str = None) -> str:
    """Save current results without ending session"""
    return enhanced_metrics_collector.save_current_results(filename_prefix)

def is_session_active() -> bool:
    """Check if an experiment session is currently active"""
    return enhanced_metrics_collector.session_started

def get_current_session() -> Optional[ExperimentSession]:
    """Get the current experiment session"""
    return enhanced_metrics_collector.current_session
