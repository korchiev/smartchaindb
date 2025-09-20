# SmartChainDB SHACL Validation System

This project implements SHACL (Shapes Constraint Language) validation for SmartChainDB transactions, focusing on ADVERTISE and BUY transaction types. The system demonstrates the benefits of declarative validation over imperative approaches, including compositionality, middleware drop-in capability, and batch validation potential.

## Project Overview

### Key Features

- **SHACL-based Validation**: Declarative rule definition using W3C SHACL standard
- **Three-Phase Validation Lifecycle**: Pre-commit, block proposal, and commit validation phases
- **Optimization Strategies**: Support-set hashing and delta/invalidation approaches
- **Batch Validation**: Multi-transaction validation in single SHACL pass
- **Middleware Architecture**: Non-invasive integration with existing BigchainDB

### Transaction Types

- **ADVERTISE**: Asset advertisement with ownership, uniqueness, expiry, and price validation
- **BUY**: Purchase transaction with advertisement validation, payment matching, and availability checks

## Documentation

### Core Documentation

- **[Why SHACL](docs/why_shacl.md)**: Justification for SHACL over direct MongoDB queries
- **[Validation Lifecycle](docs/validation_lifecycle.md)**: Three-phase validation process explanation
- **[Transaction Rules](docs/transaction_rules.md)**: Detailed validation rules for ADVERTISE and BUY
- **[Invalidating Patterns](docs/invalidating_patterns.md)**: Event-driven invalidation patterns
- **[Experiment Matrix](docs/experiment_matrix.md)**: Experimental setup and evaluation metrics

### Implementation

- **[SHACL Validator](bigchaindb/shacl_validator.py)**: Core SHACL validation implementation
- **[Baseline Demo](examples/baseline_validation_demo.py)**: Demonstration of baseline validation
- **[Transaction Extensions](bigchaindb/common/transaction.py)**: Extended transaction types and validation

## Quick Start

### Prerequisites

```bash
pip install pyshacl rdflib python-dateutil
```

### Running the Demo

```bash
python examples/baseline_validation_demo.py
```

### Using SHACL Validation

```python
from bigchaindb import BigchainDB
from bigchaindb.shacl_validator import SHACLValidationMiddleware

# Initialize BigchainDB
bdb = BigchainDB()

# Initialize SHACL validation middleware
middleware = SHACLValidationMiddleware(bdb, enable_shacl=True)

# Validate a transaction
is_valid, errors = middleware.validate_transaction(tx_dict, phase="pre_commit")

# Validate multiple transactions in batch
results = middleware.validate_batch(transaction_list, phase="pre_commit")
```

## Architecture

### Validation Phases

1. **Pre-commit**: Individual transaction validation
2. **Block Proposal**: Cross-transaction validation within block
3. **Commit**: Final validation against committed state

### Optimization Approaches

#### Opt-1: Support-Set Hashing
- Hash complete support sets for each phase
- Skip SHACL validation if hash unchanged
- Reduces computation but still requires DB queries

#### Opt-2: Delta/Invalidation (Preferred)
- Track invalidating patterns in memory
- Only re-validate when relevant events occur
- Minimal database overhead for unchanged state

### SHACL Rules

The system uses SHACL rules for declarative validation:

```turtle
# Example: ADVERTISE ownership rule
sc:AdvertiseOwnershipRule a sh:NodeShape ;
    sh:targetClass sc:AdvertiseTransaction ;
    sh:sparql [
        sh:select """
            SELECT ?tx ?assetId ?advertiser ?currentOwner
            WHERE {
                ?tx a sc:AdvertiseTransaction ;
                    sc:assetId ?assetId ;
                    sc:advertiser ?advertiser .
                ?assetId sc:currentOwner ?currentOwner .
                FILTER (?advertiser != ?currentOwner)
            }
        """ ;
        sh:message "Advertiser must own the asset being advertised" ;
    ] .
```

## Performance Goals

### Target Metrics

- **Latency**: < 25ms p95 for single transactions
- **Throughput**: > 500 TPS for single transactions
- **DB Reduction**: > 80% reduction in database queries
- **SHACL Reduction**: > 85% reduction in SHACL calls
- **Batch Performance**: > 1000 TPS for batch validation

### Optimization Benefits

- **Compositionality**: Rules can be combined and reused
- **Middleware**: Non-invasive integration with existing systems
- **Batching**: Multi-transaction validation in single pass
- **Performance**: Significant reduction in database queries and validation calls

## Research Context

This project addresses the research question: **"How can SHACL-based validation improve transaction validation in distributed ledger systems?"**

### Key Research Contributions

1. **Compositional Rule Design**: Demonstrates how SHACL enables reusable, combinable validation rules
2. **Middleware Integration**: Shows how SHACL can be added to existing systems without backend replacement
3. **Batch Optimization**: Proves that SHACL enables efficient multi-transaction validation
4. **Performance Analysis**: Provides quantitative comparison of imperative vs declarative validation

### Paper Structure

1. **Introduction**: Problem statement and motivation
2. **Related Work**: Existing validation approaches in blockchain systems
3. **System Design**: Three-phase validation lifecycle and SHACL integration
4. **Implementation**: Baseline and optimized validation approaches
5. **Evaluation**: Performance analysis and comparison
6. **Discussion**: Benefits, limitations, and future work
7. **Conclusion**: Summary of contributions and impact

## Development Status

### Completed ✅

- [x] Codebase analysis and understanding
- [x] Why SHACL documentation
- [x] Three-phase validation lifecycle
- [x] ADVERTISE and BUY transaction rules
- [x] Invalidating patterns definition
- [x] Baseline validation implementation
- [x] Experiment matrix and metrics

### In Progress 🚧

- [ ] Opt-1: Support-set hashing optimization
- [ ] Opt-2: Delta/invalidation watcher
- [ ] Instrumentation and performance monitoring
- [ ] Event source implementation

### Planned 📋

- [ ] Performance testing and evaluation
- [ ] Research paper writing
- [ ] Integration with existing BigchainDB
- [ ] Production deployment considerations

## Contributing

This is a research project focused on demonstrating SHACL benefits for transaction validation. Contributions are welcome in the following areas:

- Additional transaction types and validation rules
- Performance optimizations
- Test cases and validation scenarios
- Documentation improvements

## License

This project is licensed under the Apache License 2.0 - see the LICENSE file for details.

## Acknowledgments

- BigchainDB team for the underlying blockchain infrastructure
- W3C for the SHACL specification
- Python SHACL community for the pyshacl library