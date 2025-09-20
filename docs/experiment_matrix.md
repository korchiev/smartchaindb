# Experiment Matrix and Evaluation Metrics

## Overview

This document defines the experimental setup for evaluating SHACL-based transaction validation in SmartChainDB, including baseline measurements, optimization strategies, and success criteria.

## Experimental Design

### Baseline Implementation
**Approach**: Imperative validation + plain SHACL (no caching)
**Description**: 
- Uses existing BigchainDB imperative validation methods
- Adds SHACL validation on top without any optimizations
- Re-validates all transactions in each phase
- No caching or event-driven invalidation

### Optimization Approaches

#### Opt-1: Support-Set Hashing
**Approach**: Hash support sets and compare across phases
**Description**:
- For each phase, fetch all required data and build support set
- Hash the complete support set
- Skip SHACL validation if hash unchanged from previous phase
- Still requires database queries each phase

**Benefits**:
- Reduces SHACL computation when data unchanged
- Maintains validation correctness
- Easy to implement and verify

**Limitations**:
- Still hits database each phase
- Hash computation overhead
- Memory usage for support sets

#### Opt-2: Delta/Invalidation Watcher (Preferred)
**Approach**: Event-driven invalidation with in-memory tracking
**Description**:
- Track invalidating patterns in memory
- Only re-validate when relevant events occur
- Minimal database overhead for unchanged state
- Real-time invalidation on state changes

**Benefits**:
- Minimal database queries
- Real-time invalidation
- Scalable with transaction volume
- Aligns with algebraic structure story

**Limitations**:
- Complex event handling
- Memory overhead for tracking
- Requires reliable event sources

## Experiment Matrix

### Transaction Types
- **ADVERTISE**: Asset advertisement with ownership, uniqueness, expiry, and price validation
- **BUY**: Purchase transaction with advertisement validation, payment matching, and availability checks

### Validation Phases
1. **Pre-commit**: Individual transaction validation
2. **Block Proposal**: Cross-transaction validation within block
3. **Commit**: Final validation against committed state

### Rule Complexity Levels
- **Simple**: Basic ownership and price validation
- **Complex**: Full validation including uniqueness, expiry, and cross-transaction constraints

### Batch Sizes
- **Single**: 1 transaction
- **Small**: 5 transactions
- **Medium**: 10 transactions
- **Large**: 25 transactions

### Experiment Configurations

| Configuration | Validation | Optimization | Rule Complexity | Batch Size | Phase |
|---------------|------------|--------------|-----------------|------------|-------|
| B1 | Imperative | None | Simple | Single | Pre-commit |
| B2 | Imperative | None | Complex | Single | Pre-commit |
| B3 | Imperative + SHACL | None | Simple | Single | Pre-commit |
| B4 | Imperative + SHACL | None | Complex | Single | Pre-commit |
| B5 | Imperative + SHACL | None | Simple | Batch(5) | Pre-commit |
| B6 | Imperative + SHACL | None | Complex | Batch(10) | Pre-commit |
| O1-1 | Imperative + SHACL | Support-Set Hash | Simple | Single | All Phases |
| O1-2 | Imperative + SHACL | Support-Set Hash | Complex | Single | All Phases |
| O1-3 | Imperative + SHACL | Support-Set Hash | Simple | Batch(5) | All Phases |
| O2-1 | Imperative + SHACL | Delta/Invalidation | Simple | Single | All Phases |
| O2-2 | Imperative + SHACL | Delta/Invalidation | Complex | Single | All Phases |
| O2-3 | Imperative + SHACL | Delta/Invalidation | Simple | Batch(10) | All Phases |
| O2-4 | Imperative + SHACL | Delta/Invalidation | Complex | Batch(25) | All Phases |

## Evaluation Metrics

### Primary Metrics

#### 1. Latency (p95)
**Definition**: 95th percentile validation time per transaction
**Measurement**: Time from transaction submission to validation completion
**Target**: < 100ms for single transaction, < 50ms per transaction for batches

#### 2. Throughput
**Definition**: Transactions validated per second
**Measurement**: Total transactions processed / total time
**Target**: > 100 TPS for single transactions, > 500 TPS for batches

#### 3. Database Hits Avoided
**Definition**: Number of database queries saved through optimization
**Measurement**: (Baseline DB queries - Optimized DB queries) / Baseline DB queries
**Target**: > 70% reduction for Opt-2, > 30% reduction for Opt-1

#### 4. SHACL Calls Avoided
**Definition**: Number of SHACL validations skipped through optimization
**Measurement**: (Baseline SHACL calls - Optimized SHACL calls) / Baseline SHACL calls
**Target**: > 80% reduction for Opt-2, > 50% reduction for Opt-1

### Secondary Metrics

#### 5. Memory Usage
**Definition**: Peak memory consumption during validation
**Measurement**: Memory usage in MB
**Target**: < 100MB for single transactions, < 500MB for batches

#### 6. Cache Hit Rate
**Definition**: Percentage of cache hits for support sets
**Measurement**: Cache hits / (Cache hits + Cache misses)
**Target**: > 80% for Opt-1, > 90% for Opt-2

#### 7. Event Processing Latency
**Definition**: Time to process invalidation events
**Measurement**: Time from event occurrence to invalidation completion
**Target**: < 10ms for Opt-2

#### 8. False Positive Rate
**Definition**: Percentage of unnecessary re-validations
**Measurement**: Unnecessary re-validations / Total re-validations
**Target**: < 5% for Opt-2

## Success Criteria

### Minimum Viable Results
1. **Latency**: Opt-2 achieves < 50ms p95 latency for single transactions
2. **Throughput**: Opt-2 achieves > 200 TPS for single transactions
3. **DB Reduction**: Opt-2 achieves > 60% reduction in database queries
4. **SHACL Reduction**: Opt-2 achieves > 70% reduction in SHACL calls

### Target Results
1. **Latency**: Opt-2 achieves < 25ms p95 latency for single transactions
2. **Throughput**: Opt-2 achieves > 500 TPS for single transactions
3. **DB Reduction**: Opt-2 achieves > 80% reduction in database queries
4. **SHACL Reduction**: Opt-2 achieves > 85% reduction in SHACL calls
5. **Batch Performance**: Opt-2 achieves > 1000 TPS for batch validation

### Stretch Goals
1. **Latency**: Opt-2 achieves < 10ms p95 latency for single transactions
2. **Throughput**: Opt-2 achieves > 1000 TPS for single transactions
3. **DB Reduction**: Opt-2 achieves > 90% reduction in database queries
4. **SHACL Reduction**: Opt-2 achieves > 95% reduction in SHACL calls
5. **Batch Performance**: Opt-2 achieves > 2000 TPS for batch validation

## Experimental Setup

### Test Environment
- **Hardware**: 8-core CPU, 32GB RAM, SSD storage
- **Database**: MongoDB 4.4+ with appropriate indexes
- **Python**: 3.8+ with pyshacl and rdflib packages
- **BigchainDB**: Latest version with custom transaction types

### Test Data
- **Transaction Volume**: 10,000 transactions per test run
- **Asset Diversity**: 1,000 unique assets
- **User Diversity**: 100 unique users (public keys)
- **Time Range**: 7-day simulation with realistic timing

### Test Scenarios

#### Scenario 1: Single Transaction Validation
- Validate individual ADVERTISE and BUY transactions
- Measure latency and throughput
- Compare imperative vs SHACL vs optimized approaches

#### Scenario 2: Batch Validation
- Validate batches of 5, 10, and 25 transactions
- Measure batch processing efficiency
- Compare single vs batch validation performance

#### Scenario 3: Multi-Phase Validation
- Simulate complete three-phase validation lifecycle
- Measure performance across all phases
- Compare optimization effectiveness per phase

#### Scenario 4: Event-Driven Invalidation
- Simulate realistic event patterns
- Measure invalidation accuracy and latency
- Compare event-driven vs full re-validation

#### Scenario 5: Stress Testing
- High-volume transaction processing
- Memory usage under load
- Performance degradation analysis

## Data Collection

### Performance Metrics
- **Timing**: Use Python `time.perf_counter()` for high-precision timing
- **Memory**: Use `psutil` for memory monitoring
- **Database**: MongoDB profiler for query analysis
- **SHACL**: Custom instrumentation in SHACL validator

### Logging
- **Transaction IDs**: Track individual transaction validation
- **Phase Information**: Record validation phase and timing
- **Error Details**: Log validation errors and warnings
- **Performance Data**: Record all metrics for analysis

### Analysis Tools
- **Statistical Analysis**: Python pandas and scipy
- **Visualization**: Matplotlib and seaborn for charts
- **Database Analysis**: MongoDB Compass for query analysis
- **Memory Profiling**: Python memory_profiler

## Expected Outcomes

### Baseline Results
- Imperative validation: ~50ms per transaction
- SHACL validation: ~100ms per transaction (2x overhead)
- Database queries: 3-5 queries per transaction per phase
- Memory usage: ~10MB per 1000 transactions

### Opt-1 Results (Support-Set Hashing)
- Latency: ~60ms per transaction (20% improvement)
- Database queries: 3-5 queries per transaction per phase (no reduction)
- SHACL calls: ~50% reduction when data unchanged
- Memory usage: ~15MB per 1000 transactions

### Opt-2 Results (Delta/Invalidation)
- Latency: ~25ms per transaction (75% improvement)
- Database queries: ~1 query per transaction per phase (80% reduction)
- SHACL calls: ~85% reduction through event-driven invalidation
- Memory usage: ~20MB per 1000 transactions

### Batch Validation Results
- Single validation: ~25ms per transaction
- Batch validation: ~10ms per transaction (60% improvement)
- Database queries: ~0.5 queries per transaction (90% reduction)
- SHACL calls: ~95% reduction through batch processing

## Risk Mitigation

### Performance Risks
- **SHACL Overhead**: If SHACL validation is too slow, focus on Opt-2
- **Memory Usage**: If memory usage is too high, implement streaming validation
- **Database Bottlenecks**: If DB queries dominate, prioritize Opt-2

### Correctness Risks
- **Event Gaps**: If events are missed, add periodic reconciliation
- **False Positives**: If too many unnecessary re-validations, tune invalidation patterns
- **Race Conditions**: If concurrent validation fails, add proper locking

### Implementation Risks
- **SHACL Complexity**: If SHACL rules are too complex, simplify or use hybrid approach
- **Event Reliability**: If event sources are unreliable, implement fallback mechanisms
- **Integration Issues**: If integration is problematic, use middleware approach

## Conclusion

This experiment matrix provides a comprehensive framework for evaluating SHACL-based transaction validation in SmartChainDB. The focus on Opt-2 (delta/invalidation) approach aligns with the project goals of demonstrating compositionality, middleware drop-in capability, and batch validation potential while achieving significant performance improvements.

The success criteria are designed to show clear benefits over imperative validation while maintaining correctness and reliability. The experimental setup ensures realistic testing conditions that will provide meaningful results for the research paper.
