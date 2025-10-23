# SmartChainDB State-Aware Cache Invalidation System

## Overview

This document explains the implementation of a state-aware caching system for SmartChainDB's SHACL validation service, addressing the critical flaw of caching validation results without accounting for blockchain state changes.

## The Problem

The original caching implementation cached validation results based only on transaction ID, ignoring that blockchain state changes could invalidate previously valid results. For example:

1. **Advertisement Status Change**: An advertisement is validated as `OPEN` and cached
2. **State Change**: Another transaction changes the advertisement status to `CLOSED`
3. **Cache Problem**: The cached validation result is now stale and incorrect

## The Solution: State-Aware Caching

### Core Components

1. **State-Aware Cache Keys**: Composite keys combining transaction ID, operation type, and blockchain state hash
2. **Dependency Tracking**: Maps cache entries to blockchain entities they depend on
3. **Event-Driven Invalidation**: Automatically invalidates cache when relevant state changes
4. **Targeted Invalidation Patterns**: Specific rules for different transaction types

### Data Structures

```python
# Main cache storage
_cache = {}  # Dict[str, CacheEntry]

# Dependency tracking
_entries_by_advertisement = defaultdict(set)  # advertisement_id -> {cache_keys}
_entries_by_buy_offer = defaultdict(set)        # buy_offer_id -> {cache_keys}
_entries_by_asset = defaultdict(set)            # asset_id -> {cache_keys}
_entries_by_sell = defaultdict(set)             # sell_id -> {cache_keys}
_entries_by_return_request = defaultdict(set)   # request_id -> {cache_keys}
_entries_by_creator = defaultdict(set)         # creator_key -> {cache_keys}
_entries_by_advertiser = defaultdict(set)      # advertiser_key -> {cache_keys}
```

### Cache Key Generation

Cache keys are generated using:
- Transaction ID
- Operation type (CREATE, TRANSFER, etc.)
- Hash of relevant blockchain state

```python
def generate_key(tx_dict, state_snapshot):
    tx_id = tx_dict.get('id', '')
    operation = tx_dict.get('operation', '')
    state_hash = state_snapshot.get_hash()
    return f"{tx_id}:{operation}:{state_hash}"
```

## Invalidating Patterns

Invalidating patterns define when and how cache entries should be invalidated based on blockchain state changes.

### Pattern Categories

#### 1. Advertisement Patterns
- **Advertisement Status Change**: When advertisement status changes (OPEN → CLOSED)
- **Advertisement Creation**: When new advertisements are created for the same asset
- **Advertisement Modification**: When advertisement details are updated

#### 2. Buy Offer Patterns
- **Buy Offer Status Change**: When buy offer status changes (PENDING → ACCEPTED)
- **Buy Offer Creation**: When new buy offers are created for the same asset
- **Buy Offer Modification**: When buy offer terms are updated

#### 3. Asset Patterns
- **Asset Ownership Change**: When asset ownership transfers
- **Asset Modification**: When asset properties are updated
- **Asset Creation**: When new assets are created

#### 4. Transaction Patterns
- **Transaction Commit**: When transactions are committed to blocks
- **Transaction Update**: When transaction status changes

### Example: Advertisement Status Change Pattern

```python
def invalidate_by_advertisement(advertisement_id):
    """Invalidate cache entries for a specific advertisement"""
    affected_keys = self._entries_by_advertisement.get(advertisement_id, set())
    
    for cache_key in affected_keys:
        if cache_key in self._cache:
            del self._cache[cache_key]
            self._log_invalidation(cache_key, f"advertisement:{advertisement_id}")
    
    # Clear the dependency tracking
    self._entries_by_advertisement[advertisement_id].clear()
```

## Event-Driven Invalidation

### Event System

The system uses an event bus to coordinate cache invalidation:

```python
class StateChangeEvent:
    def __init__(self, event_type, entity_id, data=None):
        self.event_type = event_type
        self.entity_id = entity_id
        self.data = data
        self.timestamp = time.time()
```

### Event Handlers

```python
def _handle_advertisement_change(self, event):
    """Handle advertisement state changes"""
    if event.event_type == 'advertisement_status_changed':
        self.cache.invalidate_by_advertisement(event.entity_id)
    elif event.event_type == 'advertisement_created':
        # Invalidate related asset caches
        asset_id = event.data.get('asset_id')
        if asset_id:
            self.cache.invalidate_by_asset(asset_id)
```

## Performance Impact

### Cache Hit Rates
- **First validation**: Cache miss, full SHACL validation
- **Subsequent validations**: Cache hit, instant response
- **After state change**: Cache miss, re-validation with updated state

### Memory Usage
- **Cache capacity**: 1000 entries (configurable)
- **Entry size**: ~1KB per entry
- **Total memory**: ~1MB for full cache
- **Eviction**: LRU-based when capacity exceeded

### Validation Speed
- **Cache hit**: ~1ms (instant)
- **Cache miss**: ~30-50ms (full SHACL validation)
- **Improvement**: 30-50x faster for cached validations

## Configuration

### Environment Variables
```bash
BIGCHAINDB_SHACL_ENABLED=true
BIGCHAINDB_SHACL_CACHE_TTL=60
BIGCHAINDB_SHACL_CACHE_MAX_SIZE=1000
```

### Cache Settings
```python
config = {
    "shacl": {
        "cache_enabled": True,
        "cache_ttl": 60,  # seconds
        "cache_max_size": 1000
    }
}
```

## API Endpoints

### Cache Statistics
```http
GET /api/v1/metrics/validation/cache/stats
```

Response:
```json
{
    "cache_size": 150,
    "cache_hits": 1250,
    "cache_misses": 200,
    "hit_rate": 0.86,
    "memory_usage": "156KB"
}
```

### Manual Cache Invalidation
```http
POST /api/v1/metrics/validation/cache/invalidate
Content-Type: application/json

{
    "pattern": "advertisement",
    "entity_id": "ad123"
}
```

## Testing

### Test Coverage
- Cache hit/miss scenarios
- State change invalidation
- Dependency tracking
- Event handling
- Performance benchmarks

### Test Files
- `test_state_aware_cache_invalidation.py`
- `test_comprehensive_invalidating_patterns.py`

## Monitoring

### Logs
```
[STATE-AWARE VALIDATION] tx=abc123..., operation=CREATE, phase=HTTP_POST, 
time=28.70ms, cache_hit=False, result=PASS

[CACHE INVALIDATION] key=abc123:CREATE:hash456, reason=advertisement:ad789
```

### Metrics
- Cache hit rate
- Average validation time
- Memory usage
- Invalidation frequency

## Future Enhancements

1. **Distributed Caching**: Redis-based cache for multi-node deployments
2. **Predictive Invalidation**: ML-based prediction of cache invalidation needs
3. **Cache Warming**: Pre-populate cache with frequently accessed data
4. **Advanced Patterns**: More sophisticated invalidation patterns

## Conclusion

The state-aware cache invalidation system addresses the critical flaw in the original caching implementation by:

1. **Tracking Dependencies**: Knowing which cache entries depend on which blockchain entities
2. **Event-Driven Updates**: Automatically invalidating cache when state changes
3. **Targeted Invalidation**: Only invalidating relevant cache entries, not the entire cache
4. **Performance Optimization**: Maintaining high cache hit rates while ensuring correctness

This system ensures that cached validation results remain accurate even as the blockchain state evolves, providing both performance benefits and correctness guarantees.
