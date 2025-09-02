#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Example script demonstrating the Advertisement transaction type.

This script shows how to:
1. Create an advertisement for an existing asset
2. Update advertisement status
3. Query advertisements
"""

import os
import sys
from datetime import datetime, timedelta

# Add the parent directory to the path so we can import bigchaindb
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bigchaindb.common.transaction import Transaction
from bigchaindb.common.crypto import generate_keypair


def create_advertisement_example():
    """Example of creating an advertisement transaction."""
    print("=== Advertisement Transaction Example ===\n")
    
    # Generate keypairs for demonstration
    alice = generate_keypair()
    bob = generate_keypair()
    
    print(f"Alice's public key: {alice.public_key}")
    print(f"Bob's public key: {bob.public_key}\n")
    
    # Simulate an existing asset (in real scenario, this would be a CREATE transaction)
    asset_id = "a" * 64  # Mock asset ID
    
    # Create advertisement input (simulating spending an existing asset output)
    advertisement_input = {
        'fulfillment': 'pGSAINxaGvuL8mR9nDiV7lLdb0X7JNT3mG5VhwKJqHmMqg',  # Mock fulfillment
        'fulfills': {
            'output_index': 0,
            'transaction_id': asset_id
        },
        'owners_before': [alice.public_key]
    }
    
    # Create advertisement metadata
    metadata = {
        'status': 'OPEN',
        'advertiser_public_key': alice.public_key,
        'price': '150.00',
        'description': 'Beautiful vintage bicycle in excellent condition',
        'expiry_date': (datetime.now() + timedelta(days=30)).isoformat(),
        'contact_info': 'alice@example.com',
        'location': 'New York, NY'
    }
    
    print("Creating advertisement with metadata:")
    for key, value in metadata.items():
        print(f"  {key}: {value}")
    print()
    
    # Create the advertisement transaction
    try:
        ad_tx = Transaction.advertisement(
            inputs=[advertisement_input],
            asset_id=asset_id,
            metadata=metadata
        )
        
        print("Advertisement transaction created successfully!")
        print(f"Transaction ID: {ad_tx.id}")
        print(f"Operation: {ad_tx.operation}")
        print(f"Asset ID: {ad_tx.asset['id']}")
        print(f"Inputs: {len(ad_tx.inputs)}")
        print(f"Outputs: {len(ad_tx.outputs)}")
        print(f"Metadata keys: {list(ad_tx.metadata.keys())}")
        
    except Exception as e:
        print(f"Error creating advertisement: {e}")
        return None
    
    return ad_tx


def update_advertisement_status_example(ad_tx):
    """Example of updating advertisement status."""
    print("\n=== Updating Advertisement Status ===\n")
    
    if not ad_tx:
        print("No advertisement transaction to update.")
        return
    
    # Create a new transaction to update the status
    # In a real scenario, this would reference the previous advertisement
    
    # Simulate updating status to LOCKED (e.g., when someone shows interest)
    updated_metadata = ad_tx.metadata.copy()
    updated_metadata['status'] = 'LOCKED'
    updated_metadata['locked_at'] = datetime.now().isoformat()
    updated_metadata['is_new_advertisement'] = False  # This is an update, not new
    
    print("Updating advertisement status to LOCKED...")
    
    try:
        # Create update transaction (in real scenario, this would reference the ad)
        update_tx = Transaction.advertisement(
            inputs=[ad_tx.inputs[0]],  # Reuse the same input
            asset_id=ad_tx.asset['id'],
            metadata=updated_metadata
        )
        
        print("Status update transaction created successfully!")
        print(f"New status: {update_tx.metadata['status']}")
        print(f"Locked at: {update_tx.metadata['locked_at']}")
        
    except Exception as e:
        print(f"Error updating advertisement: {e}")


def advertisement_validation_example():
    """Example of advertisement validation rules."""
    print("\n=== Advertisement Validation Rules ===\n")
    
    alice = generate_keypair()
    
    print("Testing validation rules:")
    
    # Test 1: Must have exactly one input
    print("1. Testing input count validation...")
    try:
        Transaction.advertisement(
            inputs=[],  # No inputs - should fail
            asset_id='a' * 64,
            metadata={'status': 'OPEN', 'advertiser_public_key': alice.public_key}
        )
        print("   ❌ Should have failed - no inputs")
    except ValueError as e:
        print(f"   ✅ Correctly failed: {e}")
    
    # Test 2: Must have required metadata fields
    print("2. Testing required metadata fields...")
    try:
        Transaction.advertisement(
            inputs=[{'fulfillment': 'test', 'fulfills': {'output_index': 0, 'transaction_id': 'a' * 64}}],
            asset_id='a' * 64,
            metadata={'advertiser_public_key': alice.public_key}  # Missing status
        )
        print("   ❌ Should have failed - missing status")
    except ValueError as e:
        print(f"   ✅ Correctly failed: {e}")
    
    # Test 3: Status must be valid
    print("3. Testing status validation...")
    try:
        Transaction.advertisement(
            inputs=[{'fulfillment': 'test', 'fulfills': {'output_index': 0, 'transaction_id': 'a' * 64}}],
            asset_id='a' * 64,
            metadata={'status': 'INVALID_STATUS', 'advertiser_public_key': alice.public_key}
        )
        print("   ❌ Should have failed - invalid status")
    except ValueError as e:
        print(f"   ✅ Correctly failed: {e}")
    
    # Test 4: New advertisement must have OPEN status
    print("4. Testing new advertisement status requirement...")
    try:
        Transaction.advertisement(
            inputs=[{'fulfillment': 'test', 'fulfills': {'output_index': 0, 'transaction_id': 'a' * 64}}],
            asset_id='a' * 64,
            metadata={'status': 'CLOSED', 'advertiser_public_key': alice.public_key}
        )
        print("   ❌ Should have failed - new ad must be OPEN")
    except ValueError as e:
        print(f"   ✅ Correctly failed: {e}")


def main():
    """Main function to run all examples."""
    print("BigchainDB Advertisement Transaction Type Examples")
    print("=" * 50)
    
    # Create advertisement example
    ad_tx = create_advertisement_example()
    
    # Update status example
    update_advertisement_status_example(ad_tx)
    
    # Validation rules example
    advertisement_validation_example()
    
    print("\n=== Summary ===")
    print("The Advertisement transaction type provides:")
    print("- Asset reference via asset ID")
    print("- Status management (OPEN, LOCKED, CLOSED)")
    print("- Metadata for advertisement details")
    print("- Input validation (exactly one input)")
    print("- Business rule validation")
    print("- No outputs (advertisements don't transfer ownership)")


if __name__ == "__main__":
    main()
