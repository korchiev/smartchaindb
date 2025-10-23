# Comprehensive Invalidating Patterns Documentation

## Overview

This document provides a comprehensive overview of all invalidating patterns implemented in the SmartChainDB state-aware cache invalidation system.

## Pattern Categories

### 1. Advertisement Patterns

#### Pattern 1.1: Advertisement Status Change
**Trigger**: When advertisement status changes (OPEN → CLOSED, CLOSED → OPEN)
**Invalidation**: All cache entries for the specific advertisement
**Code**:
```python
def invalidate_by_advertisement(advertisement_id):
    affected_keys = self._entries_by_advertisement.get(advertisement_id, set())
    for cache_key in affected_keys:
        if cache_key in self._cache:
            del self._cache[cache_key]
```

#### Pattern 1.2: Advertisement Creation
**Trigger**: When new advertisements are created for the same asset
**Invalidation**: Cache entries for the asset and related entities
**Code**:
```python
def _handle_advertisement_created(self, event):
    asset_id = event.data.get('asset_id')
    if asset_id:
        self.cache.invalidate_by_asset(asset_id)
```

#### Pattern 1.3: Advertisement Modification
**Trigger**: When advertisement details are updated (price, description, etc.)
**Invalidation**: Cache entries for the specific advertisement
**Code**:
```python
def _handle_advertisement_modified(self, event):
    self.cache.invalidate_by_advertisement(event.entity_id)
```

### 2. Buy Offer Patterns

#### Pattern 2.1: Buy Offer Status Change
**Trigger**: When buy offer status changes (PENDING → ACCEPTED, ACCEPTED → REJECTED)
**Invalidation**: All cache entries for the specific buy offer
**Code**:
```python
def invalidate_by_buy_offer(buy_offer_id):
    affected_keys = self._entries_by_buy_offer.get(buy_offer_id, set())
    for cache_key in affected_keys:
        if cache_key in self._cache:
            del self._cache[cache_key]
```

#### Pattern 2.2: Buy Offer Creation
**Trigger**: When new buy offers are created for the same asset
**Invalidation**: Cache entries for the asset and related advertisements
**Code**:
```python
def _handle_buy_offer_created(self, event):
    asset_id = event.data.get('asset_id')
    if asset_id:
        self.cache.invalidate_by_asset(asset_id)
```

#### Pattern 2.3: Buy Offer Modification
**Trigger**: When buy offer terms are updated (price, conditions, etc.)
**Invalidation**: Cache entries for the specific buy offer
**Code**:
```python
def _handle_buy_offer_modified(self, event):
    self.cache.invalidate_by_buy_offer(event.entity_id)
```

### 3. Asset Patterns

#### Pattern 3.1: Asset Ownership Change
**Trigger**: When asset ownership transfers between parties
**Invalidation**: Cache entries for the asset and all related transactions
**Code**:
```python
def invalidate_by_asset(asset_id):
    affected_keys = self._entries_by_asset.get(asset_id, set())
    for cache_key in affected_keys:
        if cache_key in self._cache:
            del self._cache[cache_key]
```

#### Pattern 3.2: Asset Modification
**Trigger**: When asset properties are updated (metadata, capabilities, etc.)
**Invalidation**: Cache entries for the specific asset
**Code**:
```python
def _handle_asset_modified(self, event):
    self.cache.invalidate_by_asset(event.entity_id)
```

#### Pattern 3.3: Asset Creation
**Trigger**: When new assets are created
**Invalidation**: Cache entries for related entities (if any)
**Code**:
```python
def _handle_asset_created(self, event):
    # Usually no invalidation needed for new assets
    pass
```

### 4. Sell Transaction Patterns

#### Pattern 4.1: Sell Status Change
**Trigger**: When sell transaction status changes (PENDING → COMPLETED, COMPLETED → CANCELLED)
**Invalidation**: Cache entries for the specific sell transaction
**Code**:
```python
def invalidate_by_sell(sell_id):
    affected_keys = self._entries_by_sell.get(sell_id, set())
    for cache_key in affected_keys:
        if cache_key in self._cache:
            del self._cache[cache_key]
```

#### Pattern 4.2: Sell Creation
**Trigger**: When new sell transactions are created
**Invalidation**: Cache entries for the asset and related entities
**Code**:
```python
def _handle_sell_created(self, event):
    asset_id = event.data.get('asset_id')
    if asset_id:
        self.cache.invalidate_by_asset(asset_id)
```

### 5. Return Request Patterns

#### Pattern 5.1: Return Request Status Change
**Trigger**: When return request status changes (PENDING → ACCEPTED, ACCEPTED → REJECTED)
**Invalidation**: Cache entries for the specific return request
**Code**:
```python
def invalidate_by_return_request(request_id):
    affected_keys = self._entries_by_return_request.get(request_id, set())
    for cache_key in affected_keys:
        if cache_key in self._cache:
            del self._cache[cache_key]
```

#### Pattern 5.2: Return Request Creation
**Trigger**: When new return requests are created
**Invalidation**: Cache entries for the asset and related transactions
**Code**:
```python
def _handle_return_request_created(self, event):
    asset_id = event.data.get('asset_id')
    if asset_id:
        self.cache.invalidate_by_asset(asset_id)
```

### 6. Creator Patterns

#### Pattern 6.1: Creator Key Change
**Trigger**: When creator public key changes or is updated
**Invalidation**: Cache entries for all transactions created by the creator
**Code**:
```python
def invalidate_by_creator(creator_key):
    affected_keys = self._entries_by_creator.get(creator_key, set())
    for cache_key in affected_keys:
        if cache_key in self._cache:
            del self._cache[cache_key]
```

### 7. Advertiser Patterns

#### Pattern 7.1: Advertiser Key Change
**Trigger**: When advertiser public key changes or is updated
**Invalidation**: Cache entries for all advertisements by the advertiser
**Code**:
```python
def invalidate_by_advertiser(advertiser_key):
    affected_keys = self._entries_by_advertiser.get(advertiser_key, set())
    for cache_key in affected_keys:
        if cache_key in self._cache:
            del self._cache[cache_key]
```

## Event-Driven Invalidation Flow

### Event Types

```python
class EventType:
    # Advertisement events
    ADVERTISEMENT_STATUS_CHANGED = 'advertisement_status_changed'
    ADVERTISEMENT_CREATED = 'advertisement_created'
    ADVERTISEMENT_MODIFIED = 'advertisement_modified'
    
    # Buy offer events
    BUY_OFFER_STATUS_CHANGED = 'buy_offer_status_changed'
    BUY_OFFER_CREATED = 'buy_offer_created'
    BUY_OFFER_MODIFIED = 'buy_offer_modified'
    
    # Asset events
    ASSET_OWNERSHIP_CHANGED = 'asset_ownership_changed'
    ASSET_MODIFIED = 'asset_modified'
    ASSET_CREATED = 'asset_created'
    
    # Sell events
    SELL_STATUS_CHANGED = 'sell_status_changed'
    SELL_CREATED = 'sell_created'
    
    # Return request events
    RETURN_REQUEST_STATUS_CHANGED = 'return_request_status_changed'
    RETURN_REQUEST_CREATED = 'return_request_created'
    
    # Creator events
    CREATOR_KEY_CHANGED = 'creator_key_changed'
    
    # Advertiser events
    ADVERTISER_KEY_CHANGED = 'advertiser_key_changed'
```

### Event Handler Mapping

```python
EVENT_HANDLERS = {
    EventType.ADVERTISEMENT_STATUS_CHANGED: '_handle_advertisement_change',
    EventType.ADVERTISEMENT_CREATED: '_handle_advertisement_change',
    EventType.ADVERTISEMENT_MODIFIED: '_handle_advertisement_change',
    
    EventType.BUY_OFFER_STATUS_CHANGED: '_handle_buy_offer_change',
    EventType.BUY_OFFER_CREATED: '_handle_buy_offer_change',
    EventType.BUY_OFFER_MODIFIED: '_handle_buy_offer_change',
    
    EventType.ASSET_OWNERSHIP_CHANGED: '_handle_asset_change',
    EventType.ASSET_MODIFIED: '_handle_asset_change',
    EventType.ASSET_CREATED: '_handle_asset_change',
    
    EventType.SELL_STATUS_CHANGED: '_handle_sell_change',
    EventType.SELL_CREATED: '_handle_sell_change',
    
    EventType.RETURN_REQUEST_STATUS_CHANGED: '_handle_return_request_change',
    EventType.RETURN_REQUEST_CREATED: '_handle_return_request_change',
    
    EventType.CREATOR_KEY_CHANGED: '_handle_creator_change',
    EventType.ADVERTISER_KEY_CHANGED: '_handle_advertiser_change',
}
```

## Dependency Tracking

### Dependency Mapping

```python
class DependencyTracker:
    def __init__(self):
        self._entries_by_advertisement = defaultdict(set)
        self._entries_by_buy_offer = defaultdict(set)
        self._entries_by_asset = defaultdict(set)
        self._entries_by_sell = defaultdict(set)
        self._entries_by_return_request = defaultdict(set)
        self._entries_by_creator = defaultdict(set)
        self._entries_by_advertiser = defaultdict(set)
    
    def track_dependencies(self, tx_dict, cache_key):
        """Track dependencies for a transaction"""
        # Track advertisement dependencies
        if 'advertisementId' in tx_dict.get('asset', {}).get('data', {}):
            ad_id = tx_dict['asset']['data']['advertisementId']
            self._entries_by_advertisement[ad_id].add(cache_key)
        
        # Track buy offer dependencies
        if 'buyOfferId' in tx_dict.get('asset', {}).get('data', {}):
            bo_id = tx_dict['asset']['data']['buyOfferId']
            self._entries_by_buy_offer[bo_id].add(cache_key)
        
        # Track asset dependencies
        if 'assetId' in tx_dict.get('asset', {}).get('data', {}):
            asset_id = tx_dict['asset']['data']['assetId']
            self._entries_by_asset[asset_id].add(cache_key)
        
        # Track sell dependencies
        if 'sellId' in tx_dict.get('asset', {}).get('data', {}):
            sell_id = tx_dict['asset']['data']['sellId']
            self._entries_by_sell[sell_id].add(cache_key)
        
        # Track return request dependencies
        if 'returnRequestId' in tx_dict.get('asset', {}).get('data', {}):
            req_id = tx_dict['asset']['data']['returnRequestId']
            self._entries_by_return_request[req_id].add(cache_key)
        
        # Track creator dependencies
        if 'inputs' in tx_dict and tx_dict['inputs']:
            creator_key = tx_dict['inputs'][0].get('owners_before', [None])[0]
            if creator_key:
                self._entries_by_creator[creator_key].add(cache_key)
        
        # Track advertiser dependencies
        if 'advertiserKey' in tx_dict.get('asset', {}).get('data', {}):
            advertiser_key = tx_dict['asset']['data']['advertiserKey']
            self._entries_by_advertiser[advertiser_key].add(cache_key)
```

## Performance Considerations

### Cache Hit Rate Impact

| Pattern Type | Invalidation Scope | Hit Rate Impact | Performance Impact |
|--------------|-------------------|-----------------|-------------------|
| Advertisement Status | Single advertisement | Low | Minimal |
| Advertisement Creation | Asset + related | Medium | Moderate |
| Asset Ownership | All asset transactions | High | Significant |
| Creator Key Change | All creator transactions | Very High | Major |
| Buy Offer Status | Single buy offer | Low | Minimal |

### Optimization Strategies

1. **Lazy Invalidation**: Only invalidate when cache is accessed
2. **Batch Invalidation**: Group multiple invalidations together
3. **Selective Invalidation**: Only invalidate entries that are likely to be accessed
4. **Cache Warming**: Pre-populate frequently accessed entries

## Testing Patterns

### Unit Tests

```python
def test_advertisement_status_change_invalidation():
    """Test that advertisement status changes invalidate cache"""
    # Setup
    cache = StateAwareCache()
    tx = create_advertisement_transaction()
    cache_key = cache.generate_key(tx, state_snapshot)
    cache._cache[cache_key] = CacheEntry(conforms=True, timestamp=time.time())
    
    # Action
    cache.invalidate_by_advertisement('ad_123')
    
    # Assert
    assert cache_key not in cache._cache
    assert len(cache._entries_by_advertisement['ad_123']) == 0

def test_asset_ownership_change_cascade():
    """Test that asset ownership changes cascade to related entities"""
    # Setup
    cache = StateAwareCache()
    # ... setup multiple transactions for the same asset
    
    # Action
    cache.invalidate_by_asset('asset_123')
    
    # Assert
    # All cache entries for the asset should be invalidated
    # Related advertisement and buy offer entries should be invalidated
```

### Integration Tests

```python
def test_end_to_end_invalidation_flow():
    """Test complete invalidation flow from event to cache cleanup"""
    # Setup
    event_bus = EventBus()
    cache = StateAwareCache()
    handler = CacheInvalidationHandler(cache)
    
    # Action
    event = StateChangeEvent('advertisement_status_changed', 'ad_123')
    event_bus.emit(event)
    
    # Assert
    # Cache should be invalidated
    # Dependencies should be cleaned up
    # Performance metrics should be updated
```

## Monitoring and Metrics

### Key Metrics

1. **Invalidation Frequency**: How often each pattern is triggered
2. **Cache Hit Rate**: Before and after invalidation
3. **Invalidation Overhead**: Time spent on invalidation operations
4. **Memory Usage**: Cache size before and after invalidation

### Logging

```python
def log_invalidation(cache_key, reason, pattern_type):
    logger.info(f"[CACHE INVALIDATION] key={cache_key}, reason={reason}, "
                f"pattern={pattern_type}, timestamp={time.time()}")
```

## Conclusion

The comprehensive invalidating patterns system provides:

1. **Complete Coverage**: All transaction types and state changes are handled
2. **Efficient Invalidation**: Only relevant cache entries are invalidated
3. **Event-Driven Architecture**: Automatic invalidation based on state changes
4. **Performance Optimization**: Maintains high cache hit rates while ensuring correctness
5. **Scalability**: System can handle high transaction volumes with minimal performance impact

This system ensures that the SmartChainDB cache remains accurate and performant even as the blockchain state evolves continuously.
