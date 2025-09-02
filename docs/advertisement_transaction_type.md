# Advertisement Transaction Type

## Overview

The Advertisement transaction type allows users to advertise existing assets for sale or trade without transferring ownership. This transaction type is useful for marketplace applications where users want to list their assets but maintain control until a sale is completed.

## Key Features

- **Asset Reference**: References exactly one existing asset via asset ID
- **Status Management**: Supports three states: OPEN, LOCKED, CLOSED
- **Metadata Support**: Rich metadata for advertisement details
- **Input Validation**: Ensures advertiser owns the referenced asset
- **Business Rules**: Prevents duplicate OPEN advertisements for the same asset

## Transaction Structure

### Asset Field
```json
{
  "asset": {
    "id": "64_character_hex_string"
  }
}
```

### Metadata Field
```json
{
  "metadata": {
    "status": "OPEN|LOCKED|CLOSED",
    "advertiser_public_key": "base58_encoded_public_key",
    "price": "100.50",
    "description": "Asset description",
    "expiry_date": "2024-12-31T23:59:59Z",
    "contact_info": "contact@example.com",
    "location": "New York, NY"
  }
}
```

### Inputs
- Must have exactly one input
- Input must reference an existing asset output
- Advertiser must be the current owner of the asset

### Outputs
- Advertisement transactions have no outputs (empty array)
- They don't transfer ownership, only advertise availability

## Validation Rules

### 1. Asset Reference
- Must reference exactly one existing asset
- Asset ID must match the input transaction's asset

### 2. Ownership Validation
- Advertiser must be the current owner of the asset at validation time
- Verified by checking if advertiser's public key is in the input's `owners_before` list

### 3. Status Validation
- Status must be one of: OPEN, LOCKED, CLOSED
- New advertisements must have OPEN status
- Existing advertisements can be updated to any valid status

### 4. Duplicate Prevention
- No other OPEN advertisement can exist for the same asset
- Prevents market confusion and duplicate listings

### 5. Asset Transferability
- Asset must be transferable (not escrowed/locked)
- Ensures advertised assets can actually be sold

## Usage Examples

### Creating an Advertisement

```python
from bigchaindb.common.transaction import Transaction
from bigchaindb.common.crypto import generate_keypair

# Generate keypair
alice = generate_keypair()

# Create advertisement input (must reference existing asset)
advertisement_input = {
    'fulfillment': 'fulfillment_string',
    'fulfills': {
        'output_index': 0,
        'transaction_id': 'existing_asset_id'
    },
    'owners_before': [alice.public_key]
}

# Create advertisement metadata
metadata = {
    'status': 'OPEN',
    'advertiser_public_key': alice.public_key,
    'price': '150.00',
    'description': 'Beautiful vintage bicycle',
    'expiry_date': '2024-12-31T23:59:59Z'
}

# Create advertisement transaction
ad_tx = Transaction.advertisement(
    inputs=[advertisement_input],
    asset_id='existing_asset_id',
    metadata=metadata
)
```

### Updating Advertisement Status

```python
# Update status to LOCKED (when someone shows interest)
updated_metadata = metadata.copy()
updated_metadata['status'] = 'LOCKED'
updated_metadata['is_new_advertisement'] = False

update_tx = Transaction.advertisement(
    inputs=[advertisement_input],
    asset_id='existing_asset_id',
    metadata=updated_metadata
)
```

### Closing Advertisement

```python
# Close advertisement (e.g., after sale or withdrawal)
closed_metadata = metadata.copy()
closed_metadata['status'] = 'CLOSED'
closed_metadata['is_new_advertisement'] = False

close_tx = Transaction.advertisement(
    inputs=[advertisement_input],
    asset_id='existing_asset_id',
    metadata=closed_metadata
)
```

## Database Queries

### Get Advertisements by Status
```python
# Get all OPEN advertisements
open_ads = bigchain.get_advertisements_by_status('OPEN')

# Get all LOCKED advertisements
locked_ads = bigchain.get_advertisements_by_status('LOCKED')
```

### Get Advertisements by Asset
```python
# Get all advertisements for a specific asset
asset_ads = bigchain.get_advertisements_by_asset('asset_id')
```

### Get All Open Advertisements
```python
# Get all currently open advertisements
open_ads = bigchain.get_open_advertisements()
```

## Business Logic

### Advertisement Lifecycle

1. **OPEN**: Asset is available for purchase
2. **LOCKED**: Asset is reserved (e.g., pending payment verification)
3. **CLOSED**: Advertisement is no longer active (sold, withdrawn, or expired)

### Use Cases

- **Marketplace Listings**: Users can list items for sale
- **Asset Discovery**: Buyers can discover available assets
- **Reservation System**: Support for holding items during payment
- **Inventory Management**: Track asset availability status

## Error Handling

### Common Validation Errors

- `ValueError`: Invalid input count, missing metadata fields, invalid status
- `TypeError`: Invalid data types for fields
- `AssetIdMismatch`: Asset ID doesn't match input
- `InputDoesNotExist`: Referenced input transaction doesn't exist
- `DoubleSpend`: Input already spent
- `InvalidSignature`: Cryptographic signature validation fails

### Error Prevention

- Always validate metadata before creating transactions
- Check asset ownership before advertising
- Ensure proper input structure
- Handle status transitions appropriately

## Integration Notes

### Schema Validation
The advertisement transaction type integrates with BigchainDB's schema validation system:
- Uses `transaction_advertisement_v2.0.yaml` for specific validation
- Inherits common transaction validation from `transaction_v2.0.yaml`

### Transaction Registry
Advertisement transactions are registered in the transaction type registry:
```python
Transaction.register_type(Transaction.ADVERTISEMENT, models.Transaction)
```

### API Support
Advertisement transactions are supported through the standard BigchainDB API endpoints:
- `POST /api/v1/transactions` - Submit advertisement transactions
- `GET /api/v1/transactions` - Query advertisement transactions
- `GET /api/v1/transactions/{tx_id}` - Get specific advertisement details

## Testing

Run the advertisement transaction tests:
```bash
pytest tests/test_advertisement.py -v
```

Run the example script:
```bash
python examples/advertisement_example.py
```

## Future Enhancements

Potential improvements for the Advertisement transaction type:
- **Bidding Support**: Integration with bid/accept transaction types
- **Escrow Integration**: Support for escrow-based sales
- **Multi-Asset Support**: Advertise multiple assets in one transaction
- **Conditional Advertising**: Time-based or condition-based advertisements
- **Reputation System**: Advertiser rating and review integration
