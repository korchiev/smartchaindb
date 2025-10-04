# SELL Transaction Type

## Overview

The `SELL` transaction type completes the sale process by accepting a buy offer and executing an atomic transfer. It transfers the asset ownership to the buyer while creating a payment output for the seller. The transaction validates that a valid BUY_OFFER with escrowed funds exists, ensuring both parties' interests are protected.

## Key Features

- **Atomic Asset Transfer**: Asset ownership transfer happens on-chain with UTXO spending
- **Escrow Validation**: Validates that escrowed payment exists from BUY_OFFER
- **Dual Outputs**: Creates two outputs - asset to buyer, payment value to seller
- **Buy Offer Validation**: Must reference a valid, existing buy offer
- **Advertisement Status Control**: Prevents multiple sales and ensures proper flow
- **Simplified Payment**: Payment output represents value transfer (validated against escrow)

## Transaction Structure

### Asset
```json
{
  "id": "asset_1234567890abcdef",
  "data": {
    "buy_offer_id": "buy_offer_abcdef123456"
  }
}
```

- **`id`**: The asset ID being sold (SHA3 hexdigest)
- **`data.buy_offer_id`**: The buy offer ID being accepted (SHA3 hexdigest)

### Metadata
```json
{
  "seller_public_key": "seller_public_key_here",
  "buyer_public_key": "buyer_public_key_here",
  "sale_amount": "900",
  "sale_currency": "USD",
  "sale_timestamp": "2024-01-15T14:00:00Z",
  "requestCreationTimestamp": "2024-01-15T14:00:00Z",
  "sale_notes": "Asset sold to buyer via buy offer acceptance"
}
```

- **`seller_public_key`**: Public key of the seller (base58, required)
- **`buyer_public_key`**: Public key of the buyer (base58, required)
- **`sale_amount`**: Amount of the sale as integer string (required)
- **`sale_currency`**: Currency of the sale (string, required)
- **`sale_timestamp`**: When the sale was executed (ISO 8601, required)
- **`requestCreationTimestamp`**: Transaction creation timestamp (ISO 8601, required)
- **`sale_notes`**: Optional notes about the sale (string, optional)

### Inputs
- **Single Input**: References the seller's asset being sold (UTXO from CREATE transaction)
- The input must be owned by the seller and properly signed

### Outputs
- **Output 1 (Asset Transfer)**: Amount "1", transfers asset ownership to buyer's public key
- **Output 2 (Payment Value)**: Amount equals sale_amount, assigned to seller's public key
  - Represents the payment value (validated against BUY_OFFER escrow)
  - Not a UTXO spend of the escrow, but a new output creation

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

### 5. **Escrow Validation**
- Validates that BUY_OFFER exists with escrowed funds
- Ensures escrow amount matches sale_amount
- BUY_OFFER must have created escrow output

### 6. **Asset Transfer (On-Chain)**
- Asset ownership transfers via UTXO spending
- Input: Seller's asset (from CREATE transaction)
- Output 1: Asset to buyer with amount "1"

### 7. **Payment Representation**
- Output 2 represents payment value to seller
- value creation validated against escrow
- Both transfers happen simultaneously for security

### 8. **Input Requirements**
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

### Escrow Validation
1. **Escrow Source**: Validates BUY_OFFER created escrow output
2. **Amount Matching**: Verifies escrow amount matches sale amount
3. **Security**: Both parties are protected through escrow validation
4. **Simplified Model**: Payment value represented, not spent as UTXO

### Validation Flow
1. **Input validation**: Verify asset ownership and signatures
2. **Buy offer check**: Ensure buy offer exists and is valid
3. **Asset consistency**: Verify asset IDs match
4. **Seller authorization**: Confirm seller is authorized
5. **Advertisement status**: Check advertisement allows sales
6. **Output validation**: Verify two atomic transfers are properly configured

## Integration Notes

### With BUY_OFFER Transaction
- SELL transaction validates the escrow output created by BUY_OFFER
- Payment value is represented in SELL outputs (not spent as UTXO)
- Escrow validation ensures payment security

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
- One input (asset) and two outputs (asset transfer + payment value)
- Efficient transaction structure with simplified atomic swap
- Minimal blockchain bloat

## Security Features

### Atomic Asset Transfer
- Asset ownership transfer is on-chain via UTXO spending
- Single transaction ensures atomicity
- No risk of partial asset transfer

### Escrow Validation
- Payment value validated against BUY_OFFER escrow
- Ensures escrow was properly created before SELL
- Protects both buyer and seller interests

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
