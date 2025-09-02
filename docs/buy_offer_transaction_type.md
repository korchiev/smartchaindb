# BUY_OFFER Transaction Type

## Overview

The `BUY_OFFER` transaction type enables buyers to submit offers for assets listed in advertisements. This implementation uses **direct escrow transfer** where buyers transfer their payment asset directly to an escrow account as part of the same transaction, ensuring that all offers are backed by real, locked funds in a single atomic operation.

## Key Features

- **Direct Escrow Transfer**: Buyer's payment asset is transferred to escrow within the same transaction
- **Atomic Operation**: Offer submission and escrow transfer happen simultaneously
- **Real Funds Validation**: Only offers with actual locked funds are accepted
- **Advertisement Reference**: Must reference an existing OPEN advertisement
- **Asset Validation**: Ensures buyer owns the asset being offered for
- **Time-based Expiration**: Offers have configurable expiry dates
- **Anti-self-bidding**: Prevents advertisers from bidding on their own assets
- **Escrow Security**: Funds are locked until sale completion or refund

## Transaction Structure

### Asset
```json
{
  "id": "asset_1234567890abcdef",
  "advertisement_id": "advertisement_abcdef123456"
}
```

- **`id`**: The asset ID being offered for (SHA3 hexdigest)
- **`advertisement_id`**: The advertisement ID being responded to (SHA3 hexdigest)

### Metadata
```json
{
  "buyer_public_key": "buyer_public_key_here",
  "offer_amount": 1000.00,
  "offer_currency": "USD",
  "offer_timestamp": "2024-01-15T10:30:00Z",
  "offer_expiry": "2024-01-22T10:30:00Z",
  "escrow_public_key": "escrow_public_key_here",
  "offer_notes": "Interested in purchasing this asset"
}
```

- **`buyer_public_key`**: Public key of the buyer (base58)
- **`offer_amount`**: Amount being offered (number)
- **`offer_currency`**: Currency of the offer (string)
- **`offer_timestamp`**: When the offer was created (ISO 8601)
- **`offer_expiry`**: When the offer expires (ISO 8601)
- **`escrow_public_key`**: Public key of the escrow account (base58)
- **`offer_notes`**: Optional notes about the offer (string)

### Inputs
- **Asset Input**: References the asset being offered for (owned by buyer)
- **Payment Input**: References the buyer's payment asset to be transferred to escrow

### Outputs
- **Escrow Output**: Transfers the buyer's payment asset to the escrow account
- **Asset Output**: Maintains the asset being offered for (no ownership change)

## Validation Rules

### 1. **Direct Escrow Transfer**
- Buyer's payment asset is directly transferred to escrow account
- No separate escrow transaction required
- Escrow amount must match offer amount exactly

### 2. **Asset Ownership Validation**
- Buyer must own the asset being offered for
- Asset ownership is verified through input validation
- No double-spending allowed

### 3. **Advertisement Reference**
- Must reference an existing OPEN advertisement
- Ensures the asset is actually for sale
- Prevents offers on non-existent or closed advertisements

### 4. **Anti-Self-Bidding**
- Buyer cannot be the same as advertiser
- Prevents circular transactions and market manipulation

### 5. **Time-Based Expiration**
- Offers have configurable expiry dates
- Expired offers are automatically invalid
- Prevents stale offers from being accepted

### 6. **Escrow Security**
- Funds are locked in escrow until sale completion
- Automatic refund capability if sales fail
- Both buyer and seller are protected

### 7. **Input Requirements**
- Must have at least one input for the asset being offered for
- Input must be unspent and owned by the buyer
- Valid cryptographic signatures required

## Usage Examples

### Creating a Buy Offer
```python
from bigchaindb.common.transaction import Transaction
from bigchaindb.common.crypto import generate_keypair

# Generate keypairs
buyer_keypair = generate_keypair()
escrow_keypair = generate_keypair()

# Create input for the asset being offered for
asset_input = Transaction.Input.generate([buyer_keypair.public_key])

# Create metadata
metadata = {
    'buyer_public_key': buyer_keypair.public_key,
    'offer_amount': 1000.00,
    'offer_currency': 'USD',
    'offer_timestamp': '2024-01-15T10:30:00Z',
    'offer_expiry': '2024-01-22T10:30:00Z',
    'escrow_public_key': escrow_keypair.public_key,
    'offer_notes': 'Interested in purchasing this asset'
}

# Create BUY_OFFER transaction
buy_offer_tx = Transaction.buy_offer(
    inputs=[asset_input],
    asset_id='asset_1234567890abcdef',
    advertisement_id='advertisement_abcdef123456',
    metadata=metadata
)
```

## Database Queries

### Get Buy Offers by Advertisement
```python
def get_buy_offers_by_advertisement(conn, advertisement_id):
    """Get all buy offers for a specific advertisement"""
    query = {
        'operation': 'BUY_OFFER',
        'asset.advertisement_id': advertisement_id
    }
    return conn.transactions.find(query)
```

### Get Active Buy Offers
```python
def get_active_buy_offers(conn):
    """Get all active (non-expired) buy offers"""
    current_time = datetime.utcnow().isoformat() + 'Z'
    query = {
        'operation': 'BUY_OFFER',
        'metadata.offer_expiry': {'$gt': current_time}
    }
    return conn.transactions.find(query)
```

### Get Buy Offers by Buyer
```python
def get_buy_offers_by_buyer(conn, buyer_public_key):
    """Get all buy offers from a specific buyer"""
    query = {
        'operation': 'BUY_OFFER',
        'metadata.buyer_public_key': buyer_public_key
    }
    return conn.transactions.find(query)
```

## Business Logic

### Escrow Transfer Process
1. **Buyer submits offer**: Creates BUY_OFFER transaction
2. **Direct escrow transfer**: Buyer's payment asset moves to escrow account
3. **Funds locked**: Payment is locked until sale completion
4. **Sale execution**: When seller accepts, funds move to seller
5. **Refund capability**: If sale fails, funds return to buyer

### Validation Flow
1. **Input validation**: Verify asset ownership and signatures
2. **Advertisement check**: Ensure advertisement exists and is OPEN
3. **Anti-self-bidding**: Verify buyer ≠ advertiser
4. **Time validation**: Check offer hasn't expired
5. **Escrow validation**: Verify escrow output is properly configured
6. **Amount validation**: Ensure escrow amount matches offer amount

## Integration Notes

### With SELL Transaction
- BUY_OFFER creates escrow output that SELL transaction consumes
- SELL transaction transfers asset to buyer and payment to seller
- Both transfers happen atomically

### With Advertisement System
- BUY_OFFER references existing advertisement
- Can trigger advertisement status changes (OPEN → LOCKED)
- Prevents multiple offers on same advertisement

### With Return System
- If buyer wants to return asset, escrow can refund payment
- REQUEST_RETURN and ACCEPT_RETURN handle return process
- Escrow ensures secure refund handling

## Performance Considerations

### Database Indexing
- Index on `asset.advertisement_id` for fast advertisement lookups
- Index on `metadata.buyer_public_key` for buyer queries
- Index on `metadata.offer_expiry` for expiration checks

### Transaction Size
- Single transaction handles both offer and escrow
- Reduces blockchain bloat compared to separate transactions
- More efficient for users and network

## Security Features

### Escrow Protection
- Funds are locked in escrow until sale completion
- No party can access funds without proper authorization
- Automatic refund capability for failed sales

### Signature Validation
- All inputs must be properly signed
- Prevents unauthorized asset transfers
- Ensures buyer actually owns the assets

### Anti-Fraud Measures
- Anti-self-bidding prevents market manipulation
- Time-based expiration prevents stale offers
- Asset ownership validation prevents fake offers

## Use Cases

### E-commerce Platforms
- Secure online marketplaces
- Buyer protection through escrow
- Automatic dispute resolution

### Real Estate
- Property purchase offers
- Secure deposit handling
- Contract fulfillment guarantees

### Supply Chain
- Supplier payment escrow
- Contract fulfillment guarantees
- Quality assurance payments

### Digital Asset Trading
- NFT marketplace offers
- Cryptocurrency escrow
- Secure peer-to-peer trading
