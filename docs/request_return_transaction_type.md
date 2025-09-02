# REQUEST_RETURN Transaction Type

## Overview

The `REQUEST_RETURN` transaction type is a specialized transaction type in SmartChainDB that enables buyers to request returns of purchased assets. It provides a mechanism for dispute resolution and customer satisfaction by allowing buyers to initiate return requests for assets that don't meet expectations or have issues.

## Key Features

- **Return Initiation**: Enables buyers to request returns of purchased assets
- **Dispute Resolution**: Provides framework for resolving purchase disputes
- **Policy Compliance**: Ensures returns comply with established return policies
- **Status Tracking**: Manages return request lifecycle and status updates
- **Asset Verification**: Validates asset condition and eligibility for return
- **Policy Enforcement**: Implements return policy rules and time windows

## Transaction Structure

### Asset Payload
```json
{
  "id": "return_request_id",
  "sell_transaction_id": "sell_transaction_identifier"
}
```

**Required Fields:**
- `id`: Unique identifier for the return request
- `sell_transaction_id`: Reference to the sale being disputed

### Metadata
```json
{
  "requester_public_key": "requester_public_key_hash",
  "return_reason": "Asset not as described",
  "return_request_timestamp": "2024-01-01T00:00:00Z",
  "return_policy_details": {
    "return_status": "PENDING",
    "return_window": 30,
    "return_conditions": ["unused", "original_packaging"]
  }
}
```

**Required Fields:**
- `requester_public_key`: Public key of the buyer requesting return
- `return_reason`: Reason for requesting the return
- `return_request_timestamp`: When the return was requested
- `return_policy_details`: Details of return policy and status

### Inputs
```json
{
  "inputs": [
    {
      "fulfills": {
        "transaction_id": "previous_tx_id",
        "output_index": 0
      },
      "owners_before": ["requester_public_key"],
      "fulfillment": "fulfillment_condition"
    }
  ]
}
```

**Requirements:**
- Exactly one input must be provided
- Input must reference a valid previous transaction output
- Input must be signed by the requester

### Outputs
```json
{
  "outputs": [
    {
      "condition": "output_condition",
      "public_keys": ["return_request_public_key"],
      "amount": "1"
    }
  ]
}
```

**Generated Automatically:**
- Outputs are created for the return request transaction
- Each output represents the return request's existence and state
- Amount is typically "1" for indivisible requests

## Validation Rules

### 1. Sale Transaction Reference
- **Rule**: Must reference exactly one SellTx (the sale being disputed)
- **Validation**: `sell_transaction_id` must exist and be valid
- **Implementation**: Checked in `validate_request_return_inputs` method

### 2. Buyer Authorization
- **Rule**: Buyer must be the current owner of the asset right now
- **Validation**: `requester_public_key` must match current asset owner
- **Implementation**: Checked in `validate_request_return_inputs` method

### 3. Return Eligibility
- **Rule**: Sale is eligible for return (within window, policy allows)
- **Validation**: Return must be within policy time window and conditions
- **Implementation**: Checked in `validate_request_return_inputs` method

### 4. Asset Integrity
- **Rule**: Asset not re-transferred since that sale; still the same item
- **Validation**: Asset must not have been transferred since the sale
- **Implementation**: Checked in `validate_request_return_inputs` method

### 5. Return Request Uniqueness
- **Rule**: Single active OPEN return request per sale at a time
- **Validation**: No other active return requests for the same sale
- **Implementation**: Checked in `validate_request_return_inputs` method

### 6. Return Policy Compliance
- **Rule**: Return must comply with established return policies
- **Validation**: Return reason and conditions must meet policy requirements
- **Implementation**: Checked in `validate_request_return_inputs` method

### 7. Input Requirements
- **Rule**: Must have exactly one input
- **Validation**: Inputs array must contain exactly one item
- **Implementation**: Enforced in `validate_request_return` method

## Usage Examples

### Basic Return Request
```python
from bigchaindb.common.transaction import Transaction
from bigchaindb.common.crypto import generate_key_pair

# Generate key pair for requester
requester_keys = generate_key_pair()

# Create a return request transaction
return_request = Transaction.request_return(
    inputs=[input_tx],
    asset_id="return_request_001",
    metadata={
        "requester_public_key": requester_keys.public_key,
        "return_reason": "Asset not as described",
        "return_request_timestamp": "2024-01-01T00:00:00Z",
        "return_policy_details": {
            "return_status": "PENDING",
            "return_window": 30,
            "return_conditions": ["unused", "original_packaging"]
        }
    }
)
```

### Return Request with Custom Policy
```python
# Create return request with specific policy details
return_metadata = {
    "requester_public_key": requester_keys.public_key,
    "return_reason": "Defective product",
    "return_request_timestamp": "2024-01-01T00:00:00Z",
    "return_policy_details": {
        "return_status": "PENDING",
        "return_window": 60,
        "return_conditions": ["defective", "within_warranty"],
        "warranty_claim": True
    }
}
```

### Complex Return Request Structure
```json
{
  "asset": {
    "id": "return_request_001",
    "sell_transaction_id": "sell_transaction_001"
  },
  "metadata": {
    "requester_public_key": "requester_public_key_hash",
    "return_reason": "Product quality issues",
    "return_request_timestamp": "2024-01-01T00:00:00Z",
    "return_policy_details": {
      "return_status": "PENDING",
      "return_window": 45,
      "return_conditions": [
        "unused",
        "original_packaging",
        "within_return_window"
      ],
      "return_type": "full_refund",
      "return_method": "shipping_return"
    },
    "asset_condition": {
      "current_state": "unopened",
      "packaging_condition": "original",
      "accessories_included": true,
      "damage_assessment": "none"
    },
    "return_justification": {
      "primary_reason": "Product quality issues",
      "detailed_description": "Item received with manufacturing defects",
      "evidence_provided": "photo_evidence_hash",
      "customer_service_contact": "support_ticket_123"
    },
    "refund_preferences": {
      "refund_method": "original_payment",
      "refund_timing": "upon_return_receipt",
      "shipping_refund": "buyer_pays_return_shipping"
    }
  }
}
```

## Database Queries

### Get Return Requests by Sale
```python
from bigchaindb.backend.localmongodb.query import get_return_requests_by_sale

# Retrieve return requests for a specific sale
return_requests = get_return_requests_by_sale(
    conn, 
    "sell_transaction_identifier"
)
```

### Get Return Requests by Status
```python
from bigchaindb.backend.localmongodb.query import get_return_requests_by_status

# Retrieve return requests by status
pending_returns = get_return_requests_by_status(
    conn, 
    "PENDING"
)
```

### Get Returns by Requester
```python
# Query for return requests by a specific requester
def get_returns_by_requester(conn, requester_public_key):
    query = {
        "operation": "REQUEST_RETURN",
        "metadata.requester_public_key": requester_public_key
    }
    return conn.run(query)
```

### Get Returns by Date Range
```python
# Query for return requests within a specific date range
def get_returns_by_date_range(conn, start_date, end_date):
    query = {
        "operation": "REQUEST_RETURN",
        "metadata.return_request_timestamp": {
            "$gte": start_date,
            "$lte": end_date
        }
    }
    return conn.run(query)
```

### Get Returns by Reason
```python
# Query for return requests by specific reason
def get_returns_by_reason(conn, return_reason):
    query = {
        "operation": "REQUEST_RETURN",
        "metadata.return_reason": return_reason
    }
    return conn.run(query)
```

## Business Logic

### Return Request Workflow
1. **Request Creation**: Buyer creates return request with reason and details
2. **Sale Validation**: System validates referenced sale transaction
3. **Asset Verification**: Confirm requester is current asset owner
4. **Policy Check**: Verify return complies with return policy
5. **Eligibility Validation**: Check return window and conditions
6. **Request Recording**: Store return request transaction on blockchain
7. **Status Management**: Update return request status and notify parties

### Return Request States
- **PENDING**: Return request is under review
- **APPROVED**: Return request has been approved
- **REJECTED**: Return request has been rejected
- **PROCESSING**: Return is being processed
- **COMPLETED**: Return has been fully processed
- **CANCELLED**: Return request has been cancelled

### Return Policy Validation
- **Time Window**: Return must be within policy time limit
- **Condition Requirements**: Asset must meet return condition criteria
- **Reason Validation**: Return reason must be acceptable
- **Documentation**: Required documentation must be provided
- **Asset State**: Asset must be in returnable condition

### Return Request Validation
- **Sale Existence**: Referenced sale must exist and be valid
- **Asset Ownership**: Requester must be current asset owner
- **Policy Compliance**: Return must meet policy requirements
- **Request Uniqueness**: No duplicate active requests for same sale
- **Asset Integrity**: Asset must not have been transferred since sale

### Error Handling
- **InvalidSaleTransaction**: Raised when referenced sale doesn't exist
- **UnauthorizedRequester**: Raised when requester lacks authorization
- **ReturnPolicyViolation**: Raised when return violates policy
- **ReturnWindowExpired**: Raised when return window has passed
- **DuplicateRequest**: Raised when duplicate return request exists
- **AssetTransferred**: Raised when asset has been transferred since sale

## Integration Notes

### Schema Registration
The `REQUEST_RETURN` transaction type is registered in the system:
```python
# In bigchaindb/__init__.py
Transaction.register_type(Transaction.REQUEST_RETURN, models.Transaction)
```

### Schema Validation
Return request transactions use the `transaction_request_return_v2.0.yaml` schema:
```python
# In bigchaindb/common/schema/__init__.py
_, TX_SCHEMA_REQUEST_RETURN = _load_schema("transaction_request_return_" + TX_SCHEMA_VERSION)
```

### Core Validation
Return request validation is integrated into the main transaction validation flow:
```python
# In bigchaindb/models.py
elif self.operation == Transaction.REQUEST_RETURN:
    self.validate_request_return_inputs(bigchain, current_transactions)
```

## Performance Considerations

- **Request Processing**: Efficient handling of return requests
- **Policy Validation**: Quick validation of return policy compliance
- **Asset Verification**: Optimized asset ownership validation
- **Database Queries**: Efficient querying of return data and status

## Security Features

- **Requester Authentication**: Cryptographic signatures ensure only authorized buyers can request returns
- **Policy Enforcement**: Strict compliance with return policies
- **Asset Verification**: Comprehensive validation of asset ownership
- **Request Integrity**: Immutable return request records on the blockchain

## Use Cases

### Customer Service
- Product quality issues
- Wrong item received
- Damaged during shipping
- Customer satisfaction returns

### Business Operations
- Inventory management
- Quality control processes
- Customer relationship management
- Dispute resolution

### E-commerce
- Online marketplace returns
- Digital asset refunds
- Service cancellation requests
- Subscription modifications
