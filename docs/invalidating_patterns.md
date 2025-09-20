# Invalidating Patterns for Delta/Invalidation Approach

## Overview

The delta/invalidation approach monitors specific events that can invalidate previously validated transactions. Instead of re-querying the database and re-validating every phase, we track invalidating patterns in memory and only re-validate when relevant events occur.

## ADVERTISE Transaction Invalidating Patterns

### 1. Ownership Change Pattern
**Event**: Asset ownership transferred
**Pattern**: `AssetTransfer(asset_id, old_owner, new_owner)`
**Invalidates**: All ADVERTISE transactions for the transferred asset
**Reason**: New owner may not want to continue the advertisement

```python
class OwnershipChangePattern:
    def __init__(self):
        self.pattern_type = "AssetTransfer"
        self.required_fields = ["asset_id", "old_owner", "new_owner"]
    
    def matches(self, event):
        return (event.type == "AssetTransfer" and 
                event.asset_id in self.tracked_assets)
    
    def get_invalidated_transactions(self, event):
        return self.get_advertise_txs_for_asset(event.asset_id)
```

### 2. Duplicate Advertisement Pattern
**Event**: New ADVERTISE transaction for same asset
**Pattern**: `AdvertiseTransaction(asset_id, advertiser, status=OPEN)`
**Invalidates**: Existing open ADVERTISE transactions for the same asset
**Reason**: Only one open advertisement per asset allowed

```python
class DuplicateAdvertisementPattern:
    def __init__(self):
        self.pattern_type = "AdvertiseTransaction"
        self.required_fields = ["asset_id", "status"]
    
    def matches(self, event):
        return (event.type == "AdvertiseTransaction" and 
                event.status == "OPEN" and
                event.asset_id in self.tracked_assets)
    
    def get_invalidated_transactions(self, event):
        return self.get_open_advertise_txs_for_asset(event.asset_id)
```

### 3. Time Expiry Pattern
**Event**: Advertisement expiry time reached
**Pattern**: `TimeExpiry(advertisement_id, expiry_time)`
**Invalidates**: The specific expired ADVERTISE transaction
**Reason**: Expired advertisements are no longer valid

```python
class TimeExpiryPattern:
    def __init__(self):
        self.pattern_type = "TimeExpiry"
        self.required_fields = ["advertisement_id", "expiry_time"]
    
    def matches(self, event):
        return (event.type == "TimeExpiry" and 
                event.advertisement_id in self.tracked_advertisements)
    
    def get_invalidated_transactions(self, event):
        return [self.get_advertise_tx(event.advertisement_id)]
```

### 4. Manual Closure Pattern
**Event**: Advertisement manually closed or locked
**Pattern**: `AdvertisementClosure(advertisement_id, reason)`
**Invalidates**: The specific closed ADVERTISE transaction
**Reason**: Manually closed advertisements are no longer valid

```python
class ManualClosurePattern:
    def __init__(self):
        self.pattern_type = "AdvertisementClosure"
        self.required_fields = ["advertisement_id", "reason"]
    
    def matches(self, event):
        return (event.type == "AdvertisementClosure" and 
                event.advertisement_id in self.tracked_advertisements)
    
    def get_invalidated_transactions(self, event):
        return [self.get_advertise_tx(event.advertisement_id)]
```

## BUY Transaction Invalidating Patterns

### 1. Advertisement Closure Pattern
**Event**: Advertisement closed, locked, or cancelled
**Pattern**: `AdvertisementClosure(advertisement_id, status)`
**Invalidates**: All pending BUY transactions for the closed advertisement
**Reason**: Cannot buy from closed advertisements

```python
class AdvertisementClosurePattern:
    def __init__(self):
        self.pattern_type = "AdvertisementClosure"
        self.required_fields = ["advertisement_id", "status"]
    
    def matches(self, event):
        return (event.type == "AdvertisementClosure" and 
                event.status in ["CLOSED", "LOCKED", "CANCELLED"] and
                event.advertisement_id in self.tracked_advertisements)
    
    def get_invalidated_transactions(self, event):
        return self.get_buy_txs_for_advertisement(event.advertisement_id)
```

### 2. Advertisement Expiry Pattern
**Event**: Advertisement expired
**Pattern**: `TimeExpiry(advertisement_id, expiry_time)`
**Invalidates**: All pending BUY transactions for the expired advertisement
**Reason**: Cannot buy from expired advertisements

```python
class AdvertisementExpiryPattern:
    def __init__(self):
        self.pattern_type = "TimeExpiry"
        self.required_fields = ["advertisement_id", "expiry_time"]
    
    def matches(self, event):
        return (event.type == "TimeExpiry" and 
                event.advertisement_id in self.tracked_advertisements)
    
    def get_invalidated_transactions(self, event):
        return self.get_buy_txs_for_advertisement(event.advertisement_id)
```

### 3. Price Change Pattern
**Event**: Advertisement price modified
**Pattern**: `PriceChange(advertisement_id, old_price, new_price)`
**Invalidates**: All pending BUY transactions with old price
**Reason**: Price mismatch invalidates existing purchase attempts

```python
class PriceChangePattern:
    def __init__(self):
        self.pattern_type = "PriceChange"
        self.required_fields = ["advertisement_id", "old_price", "new_price"]
    
    def matches(self, event):
        return (event.type == "PriceChange" and 
                event.advertisement_id in self.tracked_advertisements)
    
    def get_invalidated_transactions(self, event):
        return self.get_buy_txs_with_price(event.advertisement_id, event.old_price)
```

### 4. Insufficient Funds Pattern
**Event**: Buyer's balance insufficient
**Pattern**: `InsufficientFunds(buyer_public_key, required_amount, current_balance)`
**Invalidates**: All pending BUY transactions from the buyer
**Reason**: Insufficient funds prevent purchase

```python
class InsufficientFundsPattern:
    def __init__(self):
        self.pattern_type = "InsufficientFunds"
        self.required_fields = ["buyer_public_key", "required_amount", "current_balance"]
    
    def matches(self, event):
        return (event.type == "InsufficientFunds" and 
                event.buyer_public_key in self.tracked_buyers)
    
    def get_invalidated_transactions(self, event):
        return self.get_buy_txs_for_buyer(event.buyer_public_key)
```

### 5. Asset Ownership Change Pattern
**Event**: Asset ownership transferred
**Pattern**: `AssetTransfer(asset_id, old_owner, new_owner)`
**Invalidates**: All BUY transactions for advertisements of the transferred asset
**Reason**: New owner may not honor existing advertisements

```python
class AssetOwnershipChangePattern:
    def __init__(self):
        self.pattern_type = "AssetTransfer"
        self.required_fields = ["asset_id", "old_owner", "new_owner"]
    
    def matches(self, event):
        return (event.type == "AssetTransfer" and 
                event.asset_id in self.tracked_assets)
    
    def get_invalidated_transactions(self, event):
        return self.get_buy_txs_for_asset(event.asset_id)
```

## Cross-Transaction Invalidating Patterns

### 1. Double-Selling Pattern
**Event**: Multiple BUY transactions for same asset in same block
**Pattern**: `DoubleSelling(asset_id, buy_tx_ids)`
**Invalidates**: All but the first BUY transaction for the asset
**Reason**: Same asset cannot be sold twice

```python
class DoubleSellingPattern:
    def __init__(self):
        self.pattern_type = "DoubleSelling"
        self.required_fields = ["asset_id", "buy_tx_ids"]
    
    def matches(self, event):
        return (event.type == "DoubleSelling" and 
                len(event.buy_tx_ids) > 1)
    
    def get_invalidated_transactions(self, event):
        # Keep first transaction, invalidate rest
        return event.buy_tx_ids[1:]
```

### 2. Advertisement Consistency Pattern
**Event**: BUY transaction references non-existent advertisement
**Pattern**: `InvalidAdvertisementReference(buy_tx_id, advertisement_id)`
**Invalidates**: The BUY transaction with invalid reference
**Reason**: Cannot buy from non-existent advertisement

```python
class InvalidAdvertisementPattern:
    def __init__(self):
        self.pattern_type = "InvalidAdvertisementReference"
        self.required_fields = ["buy_tx_id", "advertisement_id"]
    
    def matches(self, event):
        return (event.type == "InvalidAdvertisementReference" and 
                event.buy_tx_id in self.tracked_buy_transactions)
    
    def get_invalidated_transactions(self, event):
        return [event.buy_tx_id]
```

## Event Processing Architecture

### Event Watcher
```python
class InvalidationWatcher:
    def __init__(self):
        self.patterns = [
            OwnershipChangePattern(),
            DuplicateAdvertisementPattern(),
            TimeExpiryPattern(),
            ManualClosurePattern(),
            AdvertisementClosurePattern(),
            AdvertisementExpiryPattern(),
            PriceChangePattern(),
            InsufficientFundsPattern(),
            AssetOwnershipChangePattern(),
            DoubleSellingPattern(),
            InvalidAdvertisementPattern()
        ]
        self.tracked_transactions = {}
        self.tracked_assets = set()
        self.tracked_advertisements = set()
        self.tracked_buyers = set()
    
    def add_transaction(self, tx):
        """Add transaction to tracking"""
        self.tracked_transactions[tx.id] = tx
        if tx.operation == "ADVERTISE":
            self.tracked_assets.add(tx.asset["data"]["asset_id"])
            self.tracked_advertisements.add(tx.id)
        elif tx.operation == "BUY":
            self.tracked_buyers.add(tx.asset["data"]["buyer_public_key"])
    
    def process_event(self, event):
        """Process incoming event and return invalidated transactions"""
        invalidated = []
        for pattern in self.patterns:
            if pattern.matches(event):
                invalidated.extend(pattern.get_invalidated_transactions(event))
        return invalidated
    
    def remove_transaction(self, tx_id):
        """Remove transaction from tracking"""
        if tx_id in self.tracked_transactions:
            del self.tracked_transactions[tx_id]
```

### Event Sources
1. **Block Commit Events**: New transactions committed to blockchain
2. **Time Events**: Periodic checks for expired advertisements
3. **Balance Events**: Account balance changes
4. **Ownership Events**: Asset transfer events
5. **Status Events**: Advertisement status changes

### Performance Benefits
- **No Database Queries**: Events processed in memory
- **Selective Re-validation**: Only invalidated transactions re-validated
- **Real-time Updates**: Immediate invalidation on relevant events
- **Scalable**: Pattern matching scales with number of patterns, not transactions

## Implementation Considerations

### Event Ordering
- Events must be processed in chronological order
- Block events have higher priority than time events
- Conflicting events require conflict resolution

### Memory Management
- Track only active transactions (not committed ones)
- Implement LRU cache for frequently accessed data
- Periodic cleanup of expired tracking data

### Error Handling
- Graceful degradation if event processing fails
- Fallback to full re-validation if needed
- Logging and monitoring for event processing

### Testing
- Unit tests for each pattern
- Integration tests with real events
- Performance tests with high event volumes
