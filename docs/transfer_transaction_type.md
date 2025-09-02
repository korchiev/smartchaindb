# TRANSFER Transaction Type

## Overview

The `TRANSFER` transaction type is one of the core transaction types in SmartChainDB, enabling the transfer of asset ownership from one party to another. It represents the fundamental mechanism for asset circulation within the blockchain network.

## Key Features

- **Asset Transfer**: Moves ownership of existing assets between parties
- **Input Consumption**: Consumes previous transaction outputs as inputs
- **Output Generation**: Creates new outputs for recipients
- **Signature Validation**: Ensures transaction authenticity and authorization
- **Double-Spend Prevention**: Prevents the same input from being used multiple times
- **Asset Consistency**: Maintains asset ID consistency across the transfer chain

## Transaction Structure

### Asset Payload
```json
{
  "id": "asset_identifier_hash"
}
```

**Required Fields:**
- `id`: SHA3 hexdigest of the asset identifier (must reference an existing asset)

### Metadata
The `TRANSFER` transaction type does not require specific metadata fields, but custom metadata can be included for business logic purposes.

### Inputs
```json
{
  "inputs": [
    {
      "fulfills": {
        "transaction_id": "previous_tx_id",
        "output_index": 0
      },
      "owners_before": ["owner_public_key"],
      "fulfillment": "fulfillment_condition"
    }
  ]
}
```

**Requirements:**
- At least one input must be provided
- Each input must reference a valid previous transaction output
- Inputs must be signed by the current owner(s)

### Outputs
```json
{
  "outputs": [
    {
      "condition": "output_condition",
      "public_keys": ["recipient_public_key"],
      "amount": "1"
    }
  ]
}
```

**Generated Automatically:**
- Outputs are created based on the `recipients` parameter
- Each output represents a transfer of ownership to a specific recipient
- Amount must match the sum of input amounts

## Validation Rules

### 1. Asset Reference Validation
- **Rule**: Must reference exactly one existing asset via `asset.id`
- **Validation**: Asset ID must be a valid SHA3 hexdigest
- **Implementation**: Checked in `validate_transfer` method

### 2. Input Requirements
- **Rule**: Must have at least one input
- **Validation**: Inputs array cannot be empty
- **Implementation**: Enforced in `validate_transfer` method

### 3. Input Existence
- **Rule**: All referenced inputs must exist in the blockchain
- **Validation**: Check that `fulfills.transaction_id` and `fulfills.output_index` reference valid outputs
- **Implementation**: Checked in `validate_transfer_inputs` method

### 4. Double-Spend Prevention
- **Rule**: Inputs cannot have been previously consumed
- **Validation**: Ensure inputs are not already spent in current or previous transactions
- **Implementation**: Checked in `validate_transfer_inputs` method

### 5. Asset ID Consistency
- **Rule**: All inputs must reference the same asset
- **Validation**: Verify that all input transactions have the same `asset.id`
- **Implementation**: Checked in `validate_transfer_inputs` method

### 6. Amount Matching
- **Rule**: Sum of input amounts must equal sum of output amounts
- **Validation**: Ensure no value is created or destroyed during transfer
- **Implementation**: Checked in `validate_transfer_inputs` method

### 7. Signature Validation
- **Rule**: All inputs must be properly signed by current owners
- **Validation**: Verify cryptographic signatures match the `owners_before` public keys
- **Implementation**: Checked in `validate_transfer_inputs` method

## Usage Examples

### Basic Asset Transfer
```python
from bigchaindb.common.transaction import Transaction
from bigchaindb.common.crypto import generate_key_pair

# Generate key pairs for sender and recipient
sender_keys = generate_key_pair()
recipient_keys = generate_key_pair()

# Create a transfer transaction
transfer_tx = Transaction.transfer(
    inputs=[input_tx],
    recipients=[recipient_keys.public_key],
    asset_id="asset_identifier_hash",
    metadata={"transfer_reason": "purchase"}
)
```

### Multi-Input Transfer
```python
# Transfer using multiple inputs
transfer_tx = Transaction.transfer(
    inputs=[input_tx1, input_tx2],
    recipients=[recipient_keys.public_key],
    asset_id="asset_identifier_hash"
)
```

### Multi-Recipient Transfer
```python
# Split asset among multiple recipients
transfer_tx = Transaction.transfer(
    inputs=[input_tx],
    recipients=[recipient1.public_key, recipient2.public_key],
    asset_id="asset_identifier_hash"
)
```

## Database Queries

### Get Transfer Transactions by Asset
```python
from bigchaindb.backend.localmongodb.query import get_txids_filtered

# Retrieve all transfer transactions for a specific asset
transfer_txs = get_txids_filtered(
    conn, 
    Transaction.TRANSFER, 
    asset_id="asset_identifier_hash"
)
```

### Filter by Operation Type
```python
# The get_txids_filtered function automatically handles TRANSFER operations
# with the following MongoDB query structure:
{
    "operation": "TRANSFER",
    "asset.id": asset_id
}
```

## Business Logic

### Transfer Workflow
1. **Input Validation**: Verify all inputs exist and are spendable
2. **Ownership Verification**: Confirm current owner has authority to transfer
3. **Asset Consistency**: Ensure all inputs reference the same asset
4. **Amount Calculation**: Calculate total input and output amounts
5. **Output Generation**: Create new outputs for recipients
6. **Signature Verification**: Validate all cryptographic signatures
7. **Transaction Recording**: Store the transfer transaction in the blockchain

### Error Handling
- **InputDoesNotExist**: Raised when referenced inputs don't exist
- **DoubleSpend**: Raised when inputs have already been consumed
- **AssetIdMismatch**: Raised when inputs reference different assets
- **InvalidSignature**: Raised when signatures don't match owners
- **ValueError**: Raised when input/output amounts don't match

## Integration Notes

### Schema Registration
The `TRANSFER` transaction type is automatically registered in the system:
```python
# In bigchaindb/__init__.py
Transaction.register_type(Transaction.TRANSFER, models.Transaction)
```

### Schema Validation
Transfer transactions use the `transaction_transfer_v2.0.yaml` schema:
```python
# In bigchaindb/common/schema/__init__.py
_, TX_SCHEMA_TRANSFER = _load_schema("transaction_transfer_" + TX_SCHEMA_VERSION)
```

### Core Validation
Transfer validation is integrated into the main transaction validation flow:
```python
# In bigchaindb/models.py
if self.operation == Transaction.TRANSFER:
    self.validate_transfer_inputs(bigchain, current_transactions)
```

## Performance Considerations

- **Input Lookup**: Transfer validation requires database queries to verify input existence
- **Signature Verification**: Cryptographic operations can be computationally expensive
- **Chain Traversal**: Deep asset chains may require multiple database lookups
- **Concurrent Transfers**: Multiple transfers of the same asset must be processed sequentially

## Security Features

- **Cryptographic Signatures**: Ensures only authorized owners can transfer assets
- **Double-Spend Prevention**: Prevents asset duplication through input consumption
- **Asset Integrity**: Maintains asset identity throughout the transfer chain
- **Input Validation**: Comprehensive validation of all input references and conditions
