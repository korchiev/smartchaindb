"""
Enhanced Metrics Integration Guide

This guide shows how to integrate the enhanced metrics system into your existing
BigchainDB validation code to compare SHACL vs traditional validation performance.
"""

# 1. Import the enhanced metrics system
from bigchaindb.enhanced_metrics import (
    start_transaction_tracking,
    mark_lifecycle_event,
    validation_context,
    track_shacl_phase,
    track_traditional_validation,
    track_validation_details
)

# 2. Integration in models.py (Transaction validation)
"""
In your models.py file, modify the validation method to include metrics tracking:

```python
def validate(self, bigchain, current_transactions=[]):
    # Start transaction tracking
    validation_type = 'SHACL' if self._is_shacl_enabled() else 'TRADITIONAL'
    request_timestamp = datetime.now().isoformat()
    
    start_transaction_tracking(
        tx_id=self.id,
        operation=self.operation,
        validation_type=validation_type,
        request_timestamp=request_timestamp
    )
    
    # Mark lifecycle events
    mark_lifecycle_event(self.id, 'before_tendermint')
    
    # Perform validation with metrics context
    with validation_context(self.id, validation_type) as validation_metrics:
        try:
            if validation_type == 'SHACL':
                # SHACL validation with phase tracking
                self._validate_with_shacl_metrics(bigchain, current_transactions)
            else:
                # Traditional validation with component tracking
                self._validate_with_traditional_metrics(bigchain, current_transactions)
            
            validation_metrics.validation_success = True
            
        except Exception as e:
            validation_metrics.validation_success = False
            validation_metrics.validation_errors.append(str(e))
            raise
    
    # Mark remaining lifecycle events
    mark_lifecycle_event(self.id, 'check_tx')
    mark_lifecycle_event(self.id, 'deliver_tx')
    mark_lifecycle_event(self.id, 'end_block')
    mark_lifecycle_event(self.id, 'commit')
```

# 3. SHACL Validation with Metrics
```python
def _validate_with_shacl_metrics(self, bigchain, current_transactions):
    # Phase 1: Syntactic/Semantic validation
    phase1_start = time.time()
    
    # Your existing SHACL validation code
    shacl_validator = get_shacl_validator()
    conforms, results = shacl_validator.validate_transaction(self.to_dict())
    
    phase1_duration = (time.time() - phase1_start) * 1000
    track_shacl_phase(self.id, 'phase1', phase1_duration)
    
    if not conforms:
        raise ValidationError(f"SHACL validation failed: {results}")
    
    # Phase 2: State consistency validation
    phase2_start = time.time()
    
    # Your existing state validation code
    self.validate_state_consistency(bigchain, current_transactions)
    
    phase2_duration = (time.time() - phase2_start) * 1000
    track_shacl_phase(self.id, 'phase2', phase2_duration)
    
    # Track validation details
    track_validation_details(
        tx_id=self.id,
        metadata_fields_validated=self._count_metadata_fields(),
        asset_fields_validated=self._count_asset_fields(),
        input_output_checks=len(self.inputs) + len(self.outputs),
        database_queries=self._count_database_queries(),
        cache_hits=self._count_cache_hits(),
        cache_misses=self._count_cache_misses()
    )
```

# 4. Traditional Validation with Metrics
```python
def _validate_with_traditional_metrics(self, bigchain, current_transactions):
    # Schema validation
    schema_start = time.time()
    self.validate_schema()
    schema_duration = (time.time() - schema_start) * 1000
    track_traditional_validation(self.id, 'schema', schema_duration)
    
    # Business logic validation
    business_start = time.time()
    self.validate_business_logic(bigchain, current_transactions)
    business_duration = (time.time() - business_start) * 1000
    track_traditional_validation(self.id, 'business_logic', business_duration)
    
    # Signature validation
    signature_start = time.time()
    self.validate_signatures()
    signature_duration = (time.time() - signature_start) * 1000
    track_traditional_validation(self.id, 'signature', signature_duration)
    
    # Track validation details
    track_validation_details(
        tx_id=self.id,
        metadata_fields_validated=self._count_metadata_fields(),
        asset_fields_validated=self._count_asset_fields(),
        input_output_checks=len(self.inputs) + len(self.outputs),
        database_queries=self._count_database_queries(),
        cache_hits=self._count_cache_hits(),
        cache_misses=self._count_cache_misses()
    )
```

# 5. Integration in transaction.py (Enhanced validation functions)
"""
For your enhanced validation functions, add metrics tracking:

```python
def validate_advertisement_enhanced(self, bigchain, current_transactions=[]):
    # Start validation tracking
    validation_start = time.time()
    
    try:
        # Your existing enhanced validation logic
        # ... validation code ...
        
        # Track validation details
        track_validation_details(
            tx_id=self.id,
            metadata_fields_validated=10,  # Count of fields validated
            asset_fields_validated=1,
            input_output_checks=2,
            database_queries=1,
            cache_hits=0,
            cache_misses=1
        )
        
        return True
        
    except Exception as e:
        # Track validation failure
        track_validation_details(
            tx_id=self.id,
            validation_errors=[str(e)]
        )
        raise
    finally:
        validation_duration = (time.time() - validation_start) * 1000
        track_traditional_validation(self.id, 'enhanced_advertisement', validation_duration)
```

# 6. Configuration
"""
Add to your BigchainDB configuration:

```python
# In your config file or environment variables
BIGCHAINDB_ENHANCED_METRICS_ENABLED = true
BIGCHAINDB_METRICS_LOG_FILE = "enhanced-metrics.jsonl"
BIGCHAINDB_METRICS_CSV_FILE = "enhanced-metrics.csv"
```

# 7. Running Experiments
"""
To run experiments comparing SHACL vs traditional validation:

1. **Enable SHACL validation** and run your workload
2. **Disable SHACL validation** and run the same workload
3. **Analyze the results** using the analysis tool

```bash
# Run transactions with SHACL enabled
export BIGCHAINDB_SHACL_ENABLED=true
python your_workload.py

# Run transactions with SHACL disabled
export BIGCHAINDB_SHACL_ENABLED=false
python your_workload.py

# Analyze the results
python analyze_metrics.py --plots
```

# 8. Key Metrics to Monitor
"""
The enhanced metrics system tracks:

**Performance Metrics:**
- Total transaction latency
- Validation time breakdown
- Tendermint overhead
- Database query time

**SHACL-Specific Metrics:**
- Phase 1 (syntactic/semantic) validation time
- Phase 2 (state consistency) validation time
- SHACL vs traditional validation time comparison

**Traditional-Specific Metrics:**
- Schema validation time
- Business logic validation time
- Signature validation time
- Component breakdown

**Quality Metrics:**
- Validation success rate
- Error rates by validation type
- Error rates by operation type

**System Metrics:**
- Database queries per transaction
- Cache hit/miss ratios
- Fields validated per transaction type

# 9. Analysis and Visualization
"""
The analysis tool provides:

- **Summary Reports**: Performance comparison between SHACL and traditional validation
- **Visualizations**: Charts showing latency distributions, validation time breakdowns, error rates
- **Operation Analysis**: Performance by transaction type (CREATE, TRANSFER, BUY_OFFER, etc.)
- **Phase Analysis**: SHACL phase breakdown and traditional component analysis
- **Error Analysis**: Failure rates and error patterns

# 10. Best Practices
"""
1. **Run balanced experiments**: Equal number of transactions for each validation type
2. **Use realistic workloads**: Test with actual transaction patterns from your use case
3. **Monitor system resources**: Track CPU, memory, and database performance
4. **Test different transaction types**: Each operation may have different performance characteristics
5. **Run multiple iterations**: Get statistical significance with multiple runs
6. **Document your findings**: Keep track of configuration changes and results

This enhanced metrics system will give you comprehensive insights into how SHACL validation affects your BigchainDB performance compared to traditional validation approaches.
"""
