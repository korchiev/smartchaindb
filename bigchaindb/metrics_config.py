"""
Enhanced Metrics Configuration

This file contains configuration settings for the enhanced metrics system.
You can modify these settings to customize how metrics are collected and saved.
"""

import os
from typing import Dict, Any

# Default configuration
DEFAULT_CONFIG = {
    # File paths
    'log_file': 'enhanced-metrics.jsonl',
    'csv_file': 'enhanced-metrics.csv',
    'results_directory': 'experiment_results',
    
    # Logging settings
    'log_level': 'INFO',
    'log_format': '%(message)s',
    
    # Session settings
    'auto_generate_reports': True,
    'save_intermediate_results': True,
    'checkpoint_interval': 100,  # Save checkpoint every N transactions
    
    # Analysis settings
    'generate_plots': True,
    'plot_format': 'png',
    'plot_dpi': 300,
    
    # Performance settings
    'max_active_transactions': 1000,
    'cleanup_interval': 1000,  # Cleanup old data every N transactions
    
    # Output settings
    'include_system_metrics': True,
    'include_detailed_timing': True,
    'include_validation_details': True,
}

def get_config() -> Dict[str, Any]:
    """Get configuration with environment variable overrides"""
    config = DEFAULT_CONFIG.copy()
    
    # Override with environment variables if they exist
    env_mappings = {
        'BIGCHAINDB_METRICS_LOG_FILE': 'log_file',
        'BIGCHAINDB_METRICS_CSV_FILE': 'csv_file',
        'BIGCHAINDB_METRICS_RESULTS_DIR': 'results_directory',
        'BIGCHAINDB_METRICS_LOG_LEVEL': 'log_level',
        'BIGCHAINDB_METRICS_AUTO_REPORTS': 'auto_generate_reports',
        'BIGCHAINDB_METRICS_SAVE_INTERMEDIATE': 'save_intermediate_results',
        'BIGCHAINDB_METRICS_CHECKPOINT_INTERVAL': 'checkpoint_interval',
        'BIGCHAINDB_METRICS_GENERATE_PLOTS': 'generate_plots',
        'BIGCHAINDB_METRICS_PLOT_DPI': 'plot_dpi',
    }
    
    for env_var, config_key in env_mappings.items():
        if env_var in os.environ:
            value = os.environ[env_var]
            
            # Convert string values to appropriate types
            if config_key in ['auto_generate_reports', 'save_intermediate_results', 'generate_plots', 'include_system_metrics', 'include_detailed_timing', 'include_validation_details']:
                config[config_key] = value.lower() in ('true', '1', 'yes', 'on')
            elif config_key in ['checkpoint_interval', 'max_active_transactions', 'cleanup_interval', 'plot_dpi']:
                config[config_key] = int(value)
            else:
                config[config_key] = value
    
    return config

def setup_metrics_environment():
    """Setup the metrics environment based on configuration"""
    config = get_config()
    
    # Create results directory
    os.makedirs(config['results_directory'], exist_ok=True)
    
    # Set up logging
    import logging
    logging.basicConfig(
        level=getattr(logging, config['log_level']),
        format=config['log_format']
    )
    
    return config

# Environment setup for easy import
METRICS_CONFIG = get_config()
