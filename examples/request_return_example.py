# Copyright © 2020 Interplanetary Database Association e.V.,
# BigchainDB and IPDB software contributors.
# SPDX-License-Identifier: (Apache-2.0 AND CC-BY-4.0)
# Code is Apache-2.0 and docs are CC-BY-4.0

"""Example usage of REQUEST_RETURN transaction type"""

import json
from datetime import datetime, timedelta
from bigchaindb.common.transaction import Transaction
from bigchaindb.common.crypto import generate_keypair


def create_request_return_example():
    """Example of creating a REQUEST_RETURN transaction"""
    
    # Generate keypairs for different parties
    requester_keypair = generate_keypair()
    seller_keypair = generate_keypair()
    
    print("=== REQUEST_RETURN Transaction Example ===")
    print(f"Requester public key: {requester_keypair.public_key}")
    print(f"Seller public key: {seller_keypair.public_key}")
    print()
    
    # Create mock input (in real scenario, this would reference an actual asset output)
    from unittest.mock import Mock
    mock_input = Mock()
    mock_input.fulfills = Mock()
    mock_input.fulfills.txid = "asset_creation_tx_id_123"
    mock_input.fulfills.output = 0
    
    # Create metadata for the return request
    current_time = datetime.utcnow()
    
    metadata = {
        'requester_public_key': requester_keypair.public_key,
        'return_reason': 'Item arrived damaged and does not match description',
        'return_request_timestamp': current_time.isoformat() + 'Z',
        'return_policy_details': {
            'return_window_days': 30,
            'return_conditions': 'Item must be in original condition with all packaging',
            'return_status': 'PENDING',
            'return_method': 'Free return shipping',
            'refund_method': 'Original payment method',
            'return_notes': 'Customer service will review photos and approve return'
        }
    }
    
    # Create the REQUEST_RETURN transaction
    return_request_tx = Transaction.request_return(
        inputs=[mock_input],
        asset_id="asset_123",
        sell_transaction_id="sell_tx_456",
        metadata=metadata
    )
    
    print("REQUEST_RETURN Transaction Created:")
    print(f"Operation: {return_request_tx.operation}")
    print(f"Asset ID: {return_request_tx.asset['id']}")
    print(f"Sell Transaction ID: {return_request_tx.asset['sell_transaction_id']}")
    print(f"Requester: {metadata['requester_public_key']}")
    print(f"Return Reason: {metadata['return_reason']}")
    print(f"Request Timestamp: {metadata['return_request_timestamp']}")
    print(f"Return Window: {metadata['return_policy_details']['return_window_days']} days")
    print(f"Return Status: {metadata['return_policy_details']['return_status']}")
    print(f"Return Conditions: {metadata['return_policy_details']['return_conditions']}")
    print()
    
    return return_request_tx


def validate_request_return_example():
    """Example of validating a REQUEST_RETURN transaction"""
    
    print("=== REQUEST_RETURN Validation Example ===")
    
    # Create test inputs
    from unittest.mock import Mock
    inputs = [Mock()]
    inputs[0].fulfills = Mock()
    inputs[0].fulfills.txid = "test_tx_id"
    inputs[0].fulfills.output = 0
    
    # Test metadata
    metadata = {
        'requester_public_key': 'requester_pub_key_123',
        'return_reason': 'Item damaged during shipping',
        'return_request_timestamp': '2023-01-01T10:00:00Z',
        'return_policy_details': {
            'return_window_days': 30,
            'return_conditions': 'Item must be in original condition',
            'return_status': 'PENDING'
        }
    }
    
    try:
        # Validate the transaction
        validated_inputs, validated_outputs = Transaction.validate_request_return(
            inputs, "asset_123", "sell_tx_456", metadata
        )
        print("✅ REQUEST_RETURN validation successful")
        print(f"Validated inputs: {len(validated_inputs)}")
        print(f"Validated outputs: {len(validated_outputs)}")
    except Exception as e:
        print(f"❌ REQUEST_RETURN validation failed: {e}")
    
    print()
    
    # Test validation with invalid data
    print("Testing validation with invalid data...")
    
    # Test with missing required field
    incomplete_metadata = {
        'requester_public_key': 'requester_pub_key_123',
        'return_reason': 'Item damaged during shipping'
        # Missing other required fields
    }
    
    try:
        Transaction.validate_request_return(inputs, "asset_123", "sell_tx_456", incomplete_metadata)
        print("❌ Validation should have failed for incomplete metadata")
    except ValueError as e:
        print(f"✅ Correctly caught validation error: {e}")
    
    # Test with empty return reason
    invalid_reason_metadata = metadata.copy()
    invalid_reason_metadata['return_reason'] = ''
    
    try:
        Transaction.validate_request_return(inputs, "asset_123", "sell_tx_456", invalid_reason_metadata)
        print("❌ Validation should have failed for empty return reason")
    except ValueError as e:
        print(f"✅ Correctly caught validation error: {e}")
    
    # Test with invalid policy details
    invalid_policy_metadata = metadata.copy()
    invalid_policy_metadata['return_policy_details'] = "not_a_dict"
    
    try:
        Transaction.validate_request_return(inputs, "asset_123", "sell_tx_456", invalid_policy_metadata)
        print("❌ Validation should have failed for invalid policy details")
    except ValueError as e:
        print(f"✅ Correctly caught validation error: {e}")
    
    print()


def demonstrate_business_rules():
    """Demonstrate the business rules for REQUEST_RETURN transactions"""
    
    print("=== REQUEST_RETURN Business Rules ===")
    
    print("1. References exactly one SellTx (the sale being disputed)")
    print("   - Must reference a valid sell transaction")
    print("   - Sell transaction must exist and be valid")
    print()
    
    print("2. Buyer = current owner of the asset right now")
    print("   - Requester must be the current owner of the asset")
    print("   - Prevents unauthorized return requests")
    print("   - Ensures only the buyer can request returns")
    print()
    
    print("3. Sale is eligible for return (within window, policy allows)")
    print("   - Return must be within the allowed time window")
    print("   - Return policy must allow returns")
    print("   - Prevents returns outside of policy terms")
    print()
    
    print("4. Asset not re-transferred since that sale; still the same item")
    print("   - Asset must not have been transferred to another party")
    print("   - Ensures the same physical item is being returned")
    print("   - Maintains integrity of the return process")
    print()
    
    print("5. Single active OPEN return request per sale at a time")
    print("   - Only one pending return request allowed per sale")
    print("   - Prevents duplicate or conflicting return requests")
    print("   - Ensures orderly processing of returns")
    print()


def demonstrate_return_policy_variations():
    """Demonstrate different return policy configurations"""
    
    print("=== Return Policy Variations ===")
    
    print("1. Standard Return Policy (30 days)")
    standard_policy = {
        'return_window_days': 30,
        'return_conditions': 'Item must be in original condition with packaging',
        'return_status': 'PENDING',
        'return_method': 'Free return shipping',
        'refund_method': 'Original payment method'
    }
    print(f"   - Return window: {standard_policy['return_window_days']} days")
    print(f"   - Conditions: {standard_policy['return_conditions']}")
    print()
    
    print("2. Extended Return Policy (60 days)")
    extended_policy = {
        'return_window_days': 60,
        'return_conditions': 'Item must be in good condition',
        'return_status': 'PENDING',
        'return_method': 'Customer pays return shipping',
        'refund_method': 'Store credit or original payment method'
    }
    print(f"   - Return window: {extended_policy['return_window_days']} days")
    print(f"   - Conditions: {extended_policy['return_conditions']}")
    print()
    
    print("3. No Return Policy")
    no_return_policy = {
        'return_window_days': 0,
        'return_conditions': 'No returns accepted',
        'return_status': 'NOT_ALLOWED',
        'return_method': 'N/A',
        'refund_method': 'N/A'
    }
    print(f"   - Return window: {no_return_policy['return_window_days']} days")
    print(f"   - Conditions: {no_return_policy['return_conditions']}")
    print()


def demonstrate_return_workflow():
    """Demonstrate the complete return request workflow"""
    
    print("=== Return Request Workflow ===")
    
    print("1. Customer Receives Item")
    print("   - Item is delivered to buyer")
    print("   - Buyer inspects item")
    print("   - Buyer discovers issue or decides to return")
    print()
    
    print("2. Return Request Creation")
    print("   - Buyer creates REQUEST_RETURN transaction")
    print("   - References the original sell transaction")
    print("   - Includes return reason and policy details")
    print("   - Status set to 'PENDING'")
    print()
    
    print("3. Return Request Review")
    print("   - Seller reviews return request")
    print("   - Validates return reason and conditions")
    print("   - Checks return policy compliance")
    print("   - Approves or rejects return")
    print()
    
    print("4. Return Processing")
    print("   - If approved: Return instructions provided")
    print("   - If rejected: Reason provided to buyer")
    print("   - Return status updated accordingly")
    print()
    
    print("5. Return Completion")
    print("   - Item returned to seller")
    print("   - Refund processed according to policy")
    print("   - Return status updated to 'COMPLETED'")
    print()


if __name__ == "__main__":
    # Run examples
    create_request_return_example()
    validate_request_return_example()
    demonstrate_business_rules()
    demonstrate_return_policy_variations()
    demonstrate_return_workflow()
    
    print("=== Summary ===")
    print("REQUEST_RETURN transactions enable buyers to request returns of purchased items.")
    print("They provide:")
    print("- Structured return request process")
    print("- Policy-based validation and approval")
    print("- Prevention of duplicate return requests")
    print("- Complete audit trail of return process")
    print("- Flexible return policy configurations")
    print("- Secure and verifiable return handling")
