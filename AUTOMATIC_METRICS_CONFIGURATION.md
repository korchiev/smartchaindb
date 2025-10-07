# Automatic Metrics Configuration Guide

This guide shows how to configure BigchainDB to automatically track metrics when external drivers send requests, without any changes to the drivers themselves.

## 🚀 Quick Setup

### 1. Set Environment Variables

Before starting BigchainDB server, set these environment variables:

```bash
# Enable enhanced metrics (default: true)
export BIGCHAINDB_ENHANCED_METRICS_ENABLED=true

# Set experiment name (default: Server_Startup_Experiment)
export BIGCHAINDB_EXPERIMENT_NAME="My_SHACL_Experiment"

# Enable/disable SHACL validation (default: false)
export BIGCHAINDB_SHACL_ENABLED=true

# Optional: Set checkpoint interval (default: 100)
export BIGCHAINDB_METRICS_CHECKPOINT_INTERVAL=100

# Optional: Set results directory (default: experiment_results)
export BIGCHAINDB_METRICS_RESULTS_DIR="my_experiment_results"
```

### 2. Start BigchainDB Server

```bash
bigchaindb start
```

The server will automatically:
- Start an experiment session
- Track all incoming transactions
- Save results automatically
- Generate reports when the server stops

### 3. Send Requests from External Drivers

Your external drivers can send requests normally - no changes needed! The server will automatically:

- Track transaction lifecycle events
- Measure validation performance
- Compare SHACL vs traditional validation
- Save detailed metrics

## 📊 What Gets Automatically Tracked

### **Transaction Lifecycle:**
- `received_tx` - When transaction is received
- `before_tendermint` - Before Tendermint processing
- `check_tx` - During Tendermint check_tx
- `deliver_tx` - During Tendermint deliver_tx
- `end_block` - End block processing
- `commit` - Transaction commit

### **Validation Performance:**
- **SHACL Transactions**: Phase 1 (syntactic/semantic) and Phase 2 (state consistency) timing
- **Traditional Transactions**: Schema, business logic, and signature validation timing
- **Field Validation**: Number of metadata and asset fields validated
- **Database Performance**: Query counts and cache hit/miss ratios

### **Quality Metrics:**
- Success/failure rates by validation type
- Error patterns and failure analysis
- Performance by transaction operation type

## 🔧 Configuration Options

### **Environment Variables:**

| Variable | Default | Description |
|----------|---------|-------------|
| `BIGCHAINDB_ENHANCED_METRICS_ENABLED` | `true` | Enable/disable automatic metrics |
| `BIGCHAINDB_EXPERIMENT_NAME` | `Server_Startup_Experiment` | Name of the experiment session |
| `BIGCHAINDB_SHACL_ENABLED` | `false` | Enable SHACL validation |
| `BIGCHAINDB_METRICS_CHECKPOINT_INTERVAL` | `100` | Save checkpoint every N transactions |
| `BIGCHAINDB_METRICS_RESULTS_DIR` | `experiment_results` | Directory for results |
| `BIGCHAINDB_METRICS_LOG_FILE` | `enhanced-metrics.jsonl` | Log file name |
| `BIGCHAINDB_METRICS_CSV_FILE` | `enhanced-metrics.csv` | CSV file name |

### **Automatic Session Management:**

The system automatically:
- Starts an experiment session when the server starts
- Tracks all transactions without driver changes
- Saves checkpoints periodically
- Generates reports when the server stops

## 📁 Results Structure

When your experiment finishes, results are automatically saved to:

```
experiment_results/
└── session_abc12345/
    ├── session_metadata.json          # Session configuration and stats
    ├── metrics_abc12345.jsonl         # Detailed transaction logs
    ├── metrics_abc12345.csv           # Structured data for analysis
    ├── summary_report.json            # Comprehensive analysis
    ├── summary_report.txt             # Human-readable summary
    └── plots/                         # Visualization charts
        ├── latency_comparison.png
        ├── validation_time_analysis.png
        ├── operation_breakdown.png
        ├── shacl_phase_analysis.png
        ├── traditional_component_analysis.png
        └── error_rate_analysis.png
```

## 🔍 Analyzing Results

### **Automatic Analysis:**
Results are automatically analyzed when the server stops. Check `summary_report.txt` for a human-readable summary.

### **Manual Analysis:**
```bash
# Analyze specific session
python analyze_metrics.py --csv experiment_results/session_abc12345/metrics_abc12345.csv --plots

# View summary
cat experiment_results/session_abc12345/summary_report.txt
```

## 🎯 Example Workflows

### **Workflow 1: SHACL vs Traditional Comparison**

```bash
# Start server with SHACL enabled
export BIGCHAINDB_SHACL_ENABLED=true
export BIGCHAINDB_EXPERIMENT_NAME="SHACL_Comparison"
bigchaindb start

# Send requests from your driver (no changes needed)
# ... your driver sends transactions ...

# Stop server (results automatically saved)
# Check experiment_results/session_XXXXX/ for analysis
```

### **Workflow 2: Load Testing**

```bash
# Start server for load test
export BIGCHAINDB_EXPERIMENT_NAME="Load_Test"
export BIGCHAINDB_METRICS_CHECKPOINT_INTERVAL=50
bigchaindb start

# Run your load test driver
# ... high volume of transactions ...

# Results automatically saved with checkpoints
```

### **Workflow 3: Multiple Experiments**

```bash
# Experiment 1: SHACL enabled
export BIGCHAINDB_SHACL_ENABLED=true
export BIGCHAINDB_EXPERIMENT_NAME="SHACL_Test"
bigchaindb start
# ... run your driver ...
# Stop server

# Experiment 2: Traditional validation
export BIGCHAINDB_SHACL_ENABLED=false
export BIGCHAINDB_EXPERIMENT_NAME="Traditional_Test"
bigchaindb start
# ... run your driver ...
# Stop server

# Compare results in experiment_results/
```

## 🚨 Troubleshooting

### **No Results Saved:**
- Check that `BIGCHAINDB_ENHANCED_METRICS_ENABLED=true`
- Verify the server started successfully
- Check server logs for metrics initialization messages

### **Missing Transaction Data:**
- Ensure transactions are being sent to the correct endpoint (`/api/v1/transactions`)
- Check that transactions have valid structure
- Verify server is processing transactions successfully

### **Analysis Errors:**
- Make sure you have enough transaction data (at least 10 transactions recommended)
- Check that both SHACL and traditional transactions are present for comparison
- Verify CSV files are not corrupted

## 🎉 Benefits

1. **Zero Driver Changes**: External drivers work without any modifications
2. **Automatic Tracking**: All transactions are tracked automatically
3. **Comprehensive Analysis**: Detailed comparison of SHACL vs traditional validation
4. **Easy Setup**: Just set environment variables and start the server
5. **Rich Visualizations**: Automatic generation of charts and reports
6. **Flexible Configuration**: Easy to customize via environment variables

This automatic metrics system gives you comprehensive insights into SHACL vs traditional validation performance without any changes to your existing drivers! 🚀
