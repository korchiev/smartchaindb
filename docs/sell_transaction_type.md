# SELL Transaction Type

## Overview

The `SELL` transaction type completes the sale process by accepting a buy offer and executing two atomic transfer transactions: one transferring the asset ownership to the buyer, and another transferring the payment from escrow to the seller. This ensures secure, simultaneous completion of both the asset and payment transfers, with the escrow system providing security for both parties.

## Key Features

- **Two Atomic Transfers**: Asset ownership and payment transfer happen simultaneously
- **Escrow Integration**: Payment automatically comes from escrow created by BUY_OFFER
- **Asset Transfer**: Securely transfers asset ownership to buyer
- **Buy Offer Validation**: Must reference a valid, existing buy offer
- **Advertisement Status Control**: Prevents multiple sales and ensures proper flow
- **Secure Payment**: Payment transfer is automatic and secure through escrow

## Transaction Structure

### Asset
```json
{
  "id": "asset_1234567890abcdef",
  "buy_offer_id": "buy_offer_abcdef123456"
}
```

- **`id`**: The asset ID being sold (SHA3 hexdigest)
- **`buy_offer_id`**: The buy offer ID being accepted (SHA3 hexdigest)

### Metadata
```json
{
  "seller_public_key": "seller_public_key_here",
  "buyer_public_key": "buyer_public_key_here",
  "sale_amount": 1000.00,
  "sale_currency": "USD",
  "sale_timestamp": "2024-01-15T14:00:00Z",
  "sale_notes": "Asset sold to buyer via buy offer acceptance"
}
```

- **`seller_public_key`**: Public key of the seller (base58)
- **`buyer_public_key`**: Public key of the buyer (base58)
- **`sale_amount`**: Amount of the sale (number)
- **`sale_currency`**: Currency of the sale (string)
- **`sale_timestamp`**: When the sale was executed (ISO 8601)
- **`sale_notes`**: Optional notes about the sale (string)

### Inputs
- **Asset Input**: References the asset being sold (owned by seller)

### Outputs
- **Asset Output**: Transfers asset ownership to buyer
- **Payment Output**: Transfers payment from escrow to seller

## Validation Rules

### 1. **Buy Offer Reference**
- Must reference exactly one existing BuyOffer transaction
- Buy offer must target the same asset as the sell transaction
- Buy offer must have sufficient escrow funds

### 2. **Asset Consistency**
- Asset ID must match between sell transaction and buy offer
- Ensures consistency in the transaction chain
- Prevents asset mismatches

### 3. **Seller Authorization**
- Seller must be the current owner of the asset
- Seller must be the advertiser from the original advertisement
- Valid cryptographic signatures required

### 4. **Advertisement Status Control**
- Cannot sell if advertisement is already LOCKED or CLOSED
- Prevents multiple sales of the same asset
- Ensures proper transaction flow

### 5. **Escrow Integration**
- Payment automatically comes from escrow created by BUY_OFFER
- No need for separate payment handling
- Secure, automatic payment transfer

### 6. **Two Atomic Transfers**
- Asset ownership transfer to buyer
- Payment transfer from escrow to seller
- Both transfers happen simultaneously for security

### 7. **Input Requirements**
- Must have exactly one input for the asset being sold
- Input must be unspent and owned by the seller
- Valid cryptographic signatures required

## Usage Examples

### Creating a Sell Transaction
```python
from bigchaindb.common.transaction import Transaction
from bigchaindb.common.crypto import generate_keypair

# Generate keypairs
seller_keypair = generate_keypair()
buyer_keypair = generate_keypair()

# Create input for the asset being sold
asset_input = Transaction.Input.generate([seller_keypair.public_key])

# Create metadata
metadata = {
    'seller_public_key': seller_keypair.public_key,
    'buyer_public_key': buyer_keypair.public_key,
    'sale_amount': 1000.00,
    'sale_currency': 'USD',
    'sale_timestamp': '2024-01-15T14:00:00Z',
    'sale_notes': 'Asset sold to buyer via buy offer acceptance'
}

# Create SELL transaction
sell_tx = Transaction.sell(
    inputs=[asset_input],
    asset_id='asset_1234567890abcdef',
    buy_offer_id='buy_offer_abcdef123456',
    metadata=metadata
 )
```

## Database Queries

### Get Sell Transactions by Asset
```python
def get_sell_transactions_by_asset(conn, asset_id):
    """Get all sell transactions for a specific asset"""
    query = {
        'operation': 'SELL',
        'asset.id': asset_id
    }
    return conn.transactions.find(query)
```

### Get Sell Transactions by Buy Offer
```python
def get_sell_transaction_by_buy_offer(conn, buy_offer_id):
    """Get sell transaction for a specific buy offer"""
    query = {
        'operation': 'SELL',
        'asset.buy_offer_id': buy_offer_id
    }
    return conn.transactions.find_one(query)
```

### Get Sell Transactions by Seller
```python
def get_sell_transactions_by_seller(conn, seller_public_key):
    """Get all sell transactions from a specific seller"""
    query = {
        'operation': 'SELL',
        'metadata.seller_public_key': seller_public_key
    }
    return conn.transactions.find(query)
```

## Business Logic

### Sale Execution Process
1. **Buy Offer Validation**: Verify buy offer exists and is valid
2. **Asset Ownership Check**: Confirm seller owns the asset
3. **Advertisement Status**: Ensure advertisement allows sales
4. **Two Atomic Transfers**: Execute asset and payment transfers simultaneously
5. **Status Updates**: Update advertisement status to reflect sale

### Escrow Integration
1. **Escrow Source**: Payment comes from escrow created by BUY_OFFER
2. **Automatic Transfer**: No manual payment handling required
3. **Security**: Both parties are protected through escrow system
4. **Refund Capability**: Escrow can handle returns if needed

### Validation Flow
1. **Input validation**: Verify asset ownership and signatures
2. **Buy offer check**: Ensure buy offer exists and is valid
3. **Asset consistency**: Verify asset IDs match
4. **Seller authorization**: Confirm seller is authorized
5. **Advertisement status**: Check advertisement allows sales
6. **Output validation**: Verify two atomic transfers are properly configured

## Integration Notes

### With BUY_OFFER Transaction
- SELL transaction consumes the escrow output created by BUY_OFFER
- Payment transfer is automatic and secure
- No need for separate payment handling

### With Advertisement System
- SELL transaction references advertisement through buy offer
- Can trigger advertisement status changes (OPEN → LOCKED → CLOSED)
- Prevents multiple sales of the same asset

### With Return System
- If buyer wants to return asset, escrow can handle refund
- REQUEST_RETURN and ACCEPT_RETURN handle return process
- Escrow ensures secure refund handling

## Performance Considerations

### Database Indexing
- Index on `asset.buy_offer_id` for fast buy offer lookups
- Index on `metadata.seller_public_key` for seller queries
- Index on `asset.id` for asset-based queries

### Transaction Size
- Two outputs required for atomic transfers
- Efficient transaction structure
- Minimal blockchain bloat

## Security Features

### Atomic Transfers
- Both asset and payment transfers happen simultaneously
- No risk of partial completion
- Ensures transaction integrity

### Escrow Protection
- Payment comes from secure escrow account
- No direct payment handling required
- Automatic security through escrow system

### Signature Validation
- All inputs must be properly signed
- Prevents unauthorized asset transfers
- Ensures seller actually owns the assets

### Status Control
- Advertisement status prevents multiple sales
- Ensures proper transaction flow
- Prevents transaction conflicts

## Use Cases

### E-commerce Platforms
- Secure online marketplace sales
- Automatic payment processing
- Buyer and seller protection

### Real Estate
- Property sales with escrow
- Secure deposit handling
- Contract fulfillment guarantees

### Supply Chain
- Supplier payment processing
- Contract fulfillment guarantees
- Quality assurance payments

### Digital Asset Trading
- NFT marketplace sales
- Cryptocurrency transactions
- Secure peer-to-peer trading
