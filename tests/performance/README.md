# SHACL Validation Cache Performance Tests

Real-world performance testing for SHACL validation caching in BigchainDB.

**No mocks. No sleeps. Real transactions only.**

---

## 📋 Test Files

| File | Description | Usage |
|------|-------------|-------|
| `test_cache_real_transactions.py` | Comprehensive pytest test suite | `pytest` |
| `run_cache_benchmark.py` | Standalone benchmark script | Direct execution |

---

## 🚀 Quick Start

### Option 1: Run Pytest Suite (Recommended)

```bash
# Navigate to smartchaindb directory
cd smartchaindb

# Run all tests with verbose output
pytest tests/performance/test_cache_real_transactions.py -v -s

# Run specific test
pytest tests/performance/test_cache_real_transactions.py::TestRealTransactionCaching::test_001_validate_single_create_transaction -v -s
```

### Option 2: Run Standalone Benchmark

```bash
# Navigate to smartchaindb directory
cd smartchaindb

# Run directly
python tests/performance/run_cache_benchmark.py
```

---

## 🧪 Test Scenarios

### Test 1: Single CREATE Transaction
**What it does:** Validates a single CREATE transaction through the full SHACL pipeline.

**Measures:**
- Actual validation time
- SHACL microservice response
- Cache initialization

**Expected:**
- Validation time: 40-60ms
- Cache miss (first validation)
- Successful validation

---

### Test 2: CREATE → ADVERTISEMENT Flow
**What it does:** Tests two related transactions in sequence.

**Measures:**
- Individual transaction validation times
- Cache behavior across operations
- Transaction chaining

**Expected:**
- CREATE: 40-60ms
- ADVERTISEMENT: 40-60ms
- Each transaction cached independently

---

### Test 3: Full Marketplace Flow
**What it does:** Runs CREATE → ADVERTISEMENT → (BUY_OFFER) → (SELL) flow.

**Measures:**
- End-to-end marketplace transaction performance
- Cache effectiveness across transaction types
- Total flow time

**Expected:**
- Each operation validates successfully
- Cumulative caching benefits
- Total flow time < 200ms

**Note:** BUY_OFFER and SELL require committed transactions in MongoDB, so unit tests stop at ADVERTISEMENT.

---

### Test 4: Batch CREATE Transactions
**What it does:** Creates and validates 10-20 unique transactions in sequence.

**Measures:**
- Average validation time per transaction
- Cache growth
- System stability under load

**Expected:**
- Avg time: 40-60ms per transaction
- Cache size equals number of transactions
- No cache hits (all unique transactions)

---

### Test 5: Metrics Endpoint Integration
**What it does:** Tests HTTP API access to validation metrics.

**Checks:**
- Endpoint availability
- Metrics format
- Data accuracy

**Expected:**
- HTTP 200 response
- Valid JSON with metrics
- Accurate cache statistics

**Note:** Requires BigchainDB services running (`docker-compose up`).

---

### Test 6: Cache Effectiveness
**What it does:** Validates the **same** transaction 5 times to measure cache hit rate.

**Measures:**
- First validation time (cache miss)
- Subsequent validation times (cache hits)
- Speedup factor

**Expected:**
- First: 40-60ms (cache miss)
- Subsequent: < 5ms (cache hits)
- Speedup: > 10x
- Cache hit rate: 80% (4/5 validations)

**This is the KEY test for cache effectiveness!**

---

### Test 7: Final Summary
**What it does:** Aggregates all test results and provides performance rating.

**Reports:**
- Total validations
- Overall cache hit rate
- Total time saved
- Performance rating (EXCELLENT/GOOD/NEEDS TUNING)

---

## 📊 Expected Results

### Healthy System

```
Overall Statistics:
  Total validations: 50-100
  Cache hit rate: 40-60%
  Time saved: 500-2000ms

Performance:
  Avg validation time: 20-40ms
  Avg cache hit: < 5ms
  Avg cache miss: 40-60ms

Cache Status:
  Size: 30-50 entries
  Utilization: 3-5%

Performance Rating: EXCELLENT ✅
```

### Cache Working Correctly

**Single transaction 5x validation:**
- Validation 1: 52.34ms - MISS ✓
- Validation 2: 0.67ms - HIT ✓
- Validation 3: 0.54ms - HIT ✓
- Validation 4: 0.62ms - HIT ✓
- Validation 5: 0.59ms - HIT ✓
- **Speedup: 88x** 🚀

---

## 🛠️ Prerequisites

### Required Services
- MongoDB running
- SHACL microservice running (`shacleng`)
- BigchainDB server components

### Start Services

```bash
cd smartchaindb
docker-compose up -d

# Wait for services to be ready (~10s)
sleep 10

# Check service health
docker-compose ps
```

### Configuration
Ensure caching is enabled in `bigchaindb/__init__.py`:

```python
"shacl": {
    "enabled": True,
    "cache_enabled": True,
    "cache_ttl": 60,
    "cache_max_size": 1000
}
```

---

## 🐛 Troubleshooting

### Test Fails with "Cannot connect to SHACL service"

**Cause:** SHACL microservice not running

**Fix:**
```bash
docker-compose up -d shacleng
docker-compose logs -f shacleng  # Check for errors
```

---

### Test Fails with "Cannot connect to MongoDB"

**Cause:** MongoDB not running or not accessible

**Fix:**
```bash
docker-compose up -d mongodb
docker-compose logs -f mongodb  # Check for errors
```

---

### Cache Hit Rate is 0%

**Cause:** Caching disabled or not working

**Check:**
```python
# In Python shell
from bigchaindb.common.shacl_validator_cached import get_shacl_validator
validator = get_shacl_validator()
print(validator.cache_enabled)  # Should be True
```

**Fix:** Set `cache_enabled: True` in config

---

### Validation Times are Very High (>200ms)

**Possible causes:**
1. SHACL microservice slow
2. MongoDB queries slow
3. Network latency

**Debug:**
```bash
# Check SHACL service logs
docker-compose logs shacleng | grep "validation took"

# Check MongoDB performance
docker-compose exec mongodb mongo --eval "db.serverStatus().connections"

# Check network
docker-compose exec bigchaindb ping shacleng
```

---

## 📈 Interpreting Results

### Cache Hit Rate

| Rate | Meaning | Action |
|------|---------|--------|
| 0% | Cache not working | Check config |
| 1-20% | Mostly unique TXs | Expected for unique data |
| 40-60% | Normal operation | ✓ Working well |
| 80-100% | Repeat validations | Test 6 scenario |

### Validation Times

| Time | Status | Notes |
|------|--------|-------|
| < 5ms | Cache hit | Excellent! |
| 40-60ms | Cache miss | Normal |
| 100-200ms | Slow | Check SHACL service |
| > 200ms | Very slow | Check MongoDB |

### Speedup Factor

| Factor | Rating |
|--------|--------|
| > 50x | Excellent |
| 10-50x | Good |
| 2-10x | OK |
| < 2x | Poor |

---

## 🎯 Performance Goals

### Target Metrics

- **Cache hit rate:** 40-60% (normal operations)
- **Cache hit time:** < 5ms
- **Cache miss time:** 40-60ms
- **Speedup (same TX):** > 10x
- **Batch avg time:** < 50ms

### If Not Meeting Goals

1. **Check SHACL service:**
   ```bash
   docker-compose logs shacleng | tail -50
   ```

2. **Check MongoDB indexes:**
   ```javascript
   db.transactions.getIndexes()
   db.metadata.getIndexes()
   ```

3. **Tune cache settings:**
   ```python
   "cache_ttl": 120,  # Increase if many repeats
   "cache_max_size": 5000  # Increase if many TXs
   ```

---

## 🔬 Adding New Tests

### Test Template

```python
def test_00X_my_test(self, bigchain, validator, seller_keys):
    """
    Test X: Description
    
    What it tests and why.
    """
    print("\n" + "="*80)
    print("TEST X: My Test Name")
    print("="*80)
    
    validator.clear_cache()
    validator.metrics.reset_metrics()
    
    # Create transaction
    tx = BDBTransaction.create(
        [seller_keys.public_key],
        [([seller_keys.public_key], 1)],
        asset={'data': {...}},
        metadata={...}
    )
    
    # Validate
    start = time.time()
    tx.validate(bigchain)
    duration = (time.time() - start) * 1000
    
    # Check metrics
    metrics = validator.get_metrics_summary()
    
    # Assertions
    assert metrics['total_validations'] > 0
    
    print("\n✅ TEST PASSED")
```

---

## 📚 Related Documentation

- **Cache Implementation:** `CACHE_IMPLEMENTATION_COMPLETE.md`
- **SHACL Overview:** `SHACL_QUICKSTART.md`
- **Metrics API:** `bigchaindb/web/views/validation_metrics.py`
- **Validator Code:** `bigchaindb/common/shacl_validator_cached.py`

---

## ✅ Success Criteria

Tests are successful if:

1. ✅ All tests pass
2. ✅ Cache hit rate > 40% (for Test 6)
3. ✅ Speedup > 10x (for Test 6)
4. ✅ No validation errors
5. ✅ Average time < 60ms

---

## 🎉 Example Successful Run

```
==================================================================================
TEST 6: Cache Effectiveness (Same Transaction Multiple Times)
==================================================================================

Validating same transaction 5 times...
  Validation 1:   52.34ms - MISS (expected)
  Validation 2:    0.67ms - HIT (expected)
  Validation 3:    0.54ms - HIT (expected)
  Validation 4:    0.62ms - HIT (expected)
  Validation 5:    0.59ms - HIT (expected)

Analysis:
  First (uncached): 52.34ms
  Avg (cached): 0.61ms
  Speedup: 85.80x

  Total validations: 5
  Cache hits: 4
  Cache misses: 1
  Hit rate: 80.0%
  Cache size: 1
  Avg time: 10.95ms
  Time saved: 208.64ms

✅ TEST PASSED
```

---

*Last Updated: October 4, 2025*
*Status: ✅ READY FOR USE*


