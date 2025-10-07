# Single Validation Type Experiments Guide

This guide shows how to run separate experiments for SHACL and traditional validation, rather than comparing them in the same experiment.

## 🚀 Quick Setup

### **Option 1: SHACL Experiment Only**

```bash
# Set environment variables for SHACL experiment
export BIGCHAINDB_ENHANCED_METRICS_ENABLED=true
export BIGCHAINDB_EXPERIMENT_NAME="SHACL_Experiment"
export BIGCHAINDB_SHACL_ENABLED=true

# Start BigchainDB server
bigchaindb start

# Send requests from your external driver (no changes needed)
# ... your driver sends transactions ...

# Stop server when done (results automatically saved)
# Check experiment_results/session_XXXXX/ for SHACL analysis
```

### **Option 2: Traditional Experiment Only**

```bash
# Set environment variables for traditional experiment
export BIGCHAINDB_ENHANCED_METRICS_ENABLED=true
export BIGCHAINDB_EXPERIMENT_NAME="Traditional_Experiment"
export BIGCHAINDB_SHACL_ENABLED=false

# Start BigchainDB server
bigchaindb start

# Send requests from your external driver (no changes needed)
# ... your driver sends transactions ...

# Stop server when done (results automatically saved)
# Check experiment_results/session_YYYYY/ for traditional analysis
```

### **Option 3: Both Experiments (Separate)**

```bash
# Run SHACL experiment
export BIGCHAINDB_EXPERIMENT_NAME="SHACL_Experiment"
export BIGCHAINDB_SHACL_ENABLED=true
bigchaindb start
# ... run your driver ...
# Stop server

# Wait a bit, then run traditional experiment
export BIGCHAINDB_EXPERIMENT_NAME="Traditional_Experiment"
export BIGCHAINDB_SHACL_ENABLED=false
bigchaindb start
# ... run your driver ...
# Stop server

# Compare results from both experiment_results/session_XXXXX/ directories
```

## 🔧 Using the Experiment Runner Script

For easier management, use the provided script:

```bash
python run_single_experiments.py
```

This will give you options to:
1. Run SHACL experiment only
2. Run traditional experiment only
3. Run both experiments separately
4. Exit

## 📊 What Gets Tracked in Each Experiment

### **SHACL Experiment:**
- Phase 1 (syntactic/semantic) validation time
- Phase 2 (state consistency) validation time
- SHACL-specific field validation
- Database query performance
- Success/failure rates

### **Traditional Experiment:**
- Schema validation time
- Business logic validation time
- Signature validation time
- Traditional validation components
- Success/failure rates

### **Both Experiments Track:**
- Total transaction latency
- Tendermint overhead
- Transaction lifecycle events
- Field validation counts
- Error patterns and analysis

## 📁 Results Structure

Each experiment creates its own results directory:

```
experiment_results/
├── session_abc12345/          # SHACL experiment
│   ├── session_metadata.json
│   ├── metrics_abc12345.jsonl
│   ├── metrics_abc12345.csv
│   ├── summary_report.json
│   ├── summary_report.txt
│   └── plots/
│       ├── latency_analysis.png
│       ├── validation_time_analysis.png
│       ├── operation_breakdown.png
│       ├── shacl_phase_analysis.png
│       └── error_rate_analysis.png
│
└── session_def67890/          # Traditional experiment
    ├── session_metadata.json
    ├── metrics_def67890.jsonl
    ├── metrics_def67890.csv
    ├── summary_report.json
    ├── summary_report.txt
    └── plots/
        ├── latency_analysis.png
        ├── validation_time_analysis.png
        ├── operation_breakdown.png
        ├── traditional_component_analysis.png
        └── error_rate_analysis.png
```

## 🔍 Analyzing Results

### **Analyze Individual Experiments:**

```bash
# Analyze SHACL experiment
python analyze_metrics.py --csv experiment_results/session_abc12345/metrics_abc12345.csv --plots

# Analyze traditional experiment
python analyze_metrics.py --csv experiment_results/session_def67890/metrics_def67890.csv --plots
```

### **Compare Results Manually:**

1. **View Summary Reports:**
   ```bash
   cat experiment_results/session_abc12345/summary_report.txt
   cat experiment_results/session_def67890/summary_report.txt
   ```

2. **Compare Key Metrics:**
   - Average latency
   - Validation time
   - Success rates
   - Error patterns

3. **Visual Comparison:**
   - Compare plots from both experiments
   - Look at latency distributions
   - Analyze validation time breakdowns

## 🎯 Example Workflows

### **Workflow 1: SHACL Performance Test**

```bash
# Set up SHACL experiment
export BIGCHAINDB_EXPERIMENT_NAME="SHACL_Performance_Test"
export BIGCHAINDB_SHACL_ENABLED=true
export BIGCHAINDB_METRICS_CHECKPOINT_INTERVAL=50

# Start server
bigchaindb start

# Run your driver with high transaction volume
# ... your driver sends many transactions ...

# Stop server
# Results automatically saved to experiment_results/session_XXXXX/
```

### **Workflow 2: Traditional Validation Baseline**

```bash
# Set up traditional experiment
export BIGCHAINDB_EXPERIMENT_NAME="Traditional_Baseline"
export BIGCHAINDB_SHACL_ENABLED=false
export BIGCHAINDB_METRICS_CHECKPOINT_INTERVAL=100

# Start server
bigchaindb start

# Run your driver with same workload
# ... your driver sends transactions ...

# Stop server
# Results automatically saved to experiment_results/session_YYYYY/
```

### **Workflow 3: Load Testing Both**

```bash
# Test SHACL under load
export BIGCHAINDB_EXPERIMENT_NAME="SHACL_Load_Test"
export BIGCHAINDB_SHACL_ENABLED=true
bigchaindb start
# ... run load test ...
# Stop server

# Test traditional under same load
export BIGCHAINDB_EXPERIMENT_NAME="Traditional_Load_Test"
export BIGCHAINDB_SHACL_ENABLED=false
bigchaindb start
# ... run same load test ...
# Stop server

# Compare performance under load
```

## ⚙️ Configuration Options

### **Environment Variables:**

| Variable | Default | Description |
|----------|---------|-------------|
| `BIGCHAINDB_ENHANCED_METRICS_ENABLED` | `true` | Enable/disable automatic metrics |
| `BIGCHAINDB_EXPERIMENT_NAME` | `Server_Startup_Experiment` | Name of the experiment session |
| `BIGCHAINDB_SHACL_ENABLED` | `false` | Enable SHACL validation (true) or traditional (false) |
| `BIGCHAINDB_METRICS_CHECKPOINT_INTERVAL` | `100` | Save checkpoint every N transactions |
| `BIGCHAINDB_METRICS_RESULTS_DIR` | `experiment_results` | Directory for results |

### **Single Experiment Benefits:**

1. **Focused Analysis**: Each experiment focuses on one validation type
2. **Cleaner Data**: No mixing of validation types in the same dataset
3. **Easier Comparison**: Compare results from separate experiments
4. **Flexible Timing**: Run experiments at different times
5. **Isolated Results**: Each experiment has its own results directory

## 🚨 Important Notes

1. **Separate Experiments**: Each experiment runs independently
2. **No Comparison**: The system doesn't compare SHACL vs traditional in the same experiment
3. **Manual Comparison**: You need to manually compare results from different experiments
4. **Consistent Workload**: Use the same driver and workload for fair comparison
5. **Environment Variables**: Make sure to set the correct validation type for each experiment

## 🎉 Benefits of Single Experiments

1. **Cleaner Data**: Each experiment focuses on one validation type
2. **Easier Analysis**: Simpler to analyze individual validation performance
3. **Flexible Timing**: Run experiments when convenient
4. **Isolated Results**: No cross-contamination between validation types
5. **Focused Insights**: Get detailed insights into each validation approach

This approach gives you clean, focused experiments for each validation type, making it easier to analyze and compare SHACL vs traditional validation performance! 🚀
