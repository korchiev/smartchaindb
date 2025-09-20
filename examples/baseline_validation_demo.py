#!/usr/bin/env python3
"""
Baseline validation demo for SmartChainDB SHACL integration.

This script demonstrates the baseline validation approach using both
imperative validation and SHACL validation for ADVERTISE and BUY transactions.
"""

import json
import time
import sys
import os
from datetime import datetime, timedelta

# Add the project root to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from bigchaindb import BigchainDB
from bigchaindb.shacl_validator import SHACLValidationMiddleware
from bigchaindb.common.transaction import Transaction
from bigchaindb.common.crypto import generate_key_pair


def create_sample_transactions():
    """Create sample ADVERTISE and BUY transactions for testing."""
    
    # Generate key pairs
    alice_priv, alice_pub = generate_key_pair()
    bob_priv, bob_pub = generate_key_pair()
    
    # Create a sample asset (CREATE transaction)
    asset_data = {
        "data": {
            "name": "Sample Asset",
            "description": "A sample asset for testing"
        }
    }
    
    create_tx = Transaction.create(
        owners=[alice_pub],
        asset=asset_data,
        metadata={"created_by": "alice"}
    ).sign([alice_priv])
    
    # Create ADVERTISE transaction
    expiry_time = (datetime.now() + timedelta(days=7)).isoformat()
    
    advertise_tx = Transaction(
        operation="ADVERTISE",
        asset={
            "id": create_tx.id,
            "data": {
                "asset_id": create_tx.id,
                "price": "100.50",
                "currency": "USD",
                "conditions": "Cash only"
            }
        },
        metadata={
            "expiry_time": expiry_time,
            "advertisement_type": "SALE",
            "description": "Selling my sample asset",
            "status": "OPEN"
        },
        inputs=[{
            "fulfills": {
                "transaction_id": create_tx.id,
                "output_index": 0
            },
            "owners_before": [alice_pub],
            "fulfillment": create_tx.outputs[0].fulfillment.serialize_uri()
        }],
        outputs=[{
            "amount": "1",
            "condition": {
                "details": {
                    "type": "ed25519-sha-256",
                    "public_key": alice_pub
                },
                "uri": create_tx.outputs[0].condition.uri
            },
            "public_keys": [alice_pub]
        }]
    ).sign([alice_priv])
    
    # Create BUY transaction
    buy_tx = Transaction(
        operation="BUY",
        asset={
            "id": advertise_tx.id,
            "data": {
                "advertisement_id": advertise_tx.id,
                "buyer_public_key": bob_pub,
                "payment_amount": "100.50",
                "payment_currency": "USD"
            }
        },
        metadata={
            "purchase_timestamp": datetime.now().isoformat(),
            "buyer_contact": "bob@example.com"
        },
        inputs=[{
            "fulfills": {
                "transaction_id": create_tx.id,
                "output_index": 0
            },
            "owners_before": [bob_pub],
            "fulfillment": create_tx.outputs[0].fulfillment.serialize_uri()
        }],
        outputs=[{
            "amount": "100.50",
            "condition": {
                "details": {
                    "type": "ed25519-sha-256",
                    "public_key": alice_pub
                },
                "uri": create_tx.outputs[0].condition.uri
            },
            "public_keys": [alice_pub]
        }]
    ).sign([bob_priv])
    
    return {
        "create": create_tx.to_dict(),
        "advertise": advertise_tx.to_dict(),
        "buy": buy_tx.to_dict()
    }


def run_baseline_validation_demo():
    """Run the baseline validation demo."""
    
    print("=== SmartChainDB SHACL Baseline Validation Demo ===\n")
    
    # Check if SHACL is available
    try:
        from bigchaindb.shacl_validator import SHACL_AVAILABLE
        if not SHACL_AVAILABLE:
            print("⚠️  SHACL validation not available. Install pyshacl and rdflib packages.")
            print("   Running with imperative validation only.\n")
    except ImportError:
        print("⚠️  SHACL validator module not found.")
        print("   Running with imperative validation only.\n")
    
    # Create sample transactions
    print("1. Creating sample transactions...")
    transactions = create_sample_transactions()
    
    print(f"   ✓ Created CREATE transaction: {transactions['create']['id'][:8]}...")
    print(f"   ✓ Created ADVERTISE transaction: {transactions['advertise']['id'][:8]}...")
    print(f"   ✓ Created BUY transaction: {transactions['buy']['id'][:8]}...")
    print()
    
    # Initialize BigchainDB (mock for demo)
    print("2. Initializing BigchainDB...")
    try:
        bdb = BigchainDB()
        print("   ✓ BigchainDB initialized")
    except Exception as e:
        print(f"   ⚠️  BigchainDB initialization failed: {e}")
        print("   Using mock BigchainDB for demo")
        bdb = None
    
    # Initialize SHACL validation middleware
    print("3. Initializing SHACL validation middleware...")
    try:
        middleware = SHACLValidationMiddleware(bdb, enable_shacl=True)
        print("   ✓ SHACL validation middleware initialized")
    except Exception as e:
        print(f"   ⚠️  SHACL middleware initialization failed: {e}")
        print("   Using imperative validation only")
        middleware = SHACLValidationMiddleware(bdb, enable_shacl=False)
    print()
    
    # Test individual transaction validation
    print("4. Testing individual transaction validation...")
    
    # Test ADVERTISE transaction
    print("   Testing ADVERTISE transaction:")
    is_valid, errors = middleware.validate_transaction(transactions['advertise'], "pre_commit")
    if is_valid:
        print("   ✓ ADVERTISE transaction is valid")
    else:
        print("   ✗ ADVERTISE transaction is invalid:")
        for error in errors:
            print(f"     - {error}")
    
    # Test BUY transaction
    print("   Testing BUY transaction:")
    is_valid, errors = middleware.validate_transaction(transactions['buy'], "pre_commit")
    if is_valid:
        print("   ✓ BUY transaction is valid")
    else:
        print("   ✗ BUY transaction is invalid:")
        for error in errors:
            print(f"     - {error}")
    print()
    
    # Test batch validation
    print("5. Testing batch validation...")
    batch_transactions = [transactions['advertise'], transactions['buy']]
    batch_results = middleware.validate_batch(batch_transactions, "pre_commit")
    
    for i, (is_valid, errors) in enumerate(batch_results):
        tx_type = "ADVERTISE" if i == 0 else "BUY"
        if is_valid:
            print(f"   ✓ {tx_type} transaction in batch is valid")
        else:
            print(f"   ✗ {tx_type} transaction in batch is invalid:")
            for error in errors:
                print(f"     - {error}")
    print()
    
    # Performance statistics
    if middleware.shacl_validator:
        print("6. Performance statistics:")
        stats = middleware.shacl_validator.get_stats()
        print(f"   Total validations: {stats['total_validations']}")
        print(f"   Total RDF build time: {stats['total_rdf_build_time']:.4f}s")
        print(f"   Total SHACL time: {stats['total_shacl_time']:.4f}s")
        print(f"   Average validation time: {stats['total_rdf_build_time'] + stats['total_shacl_time']:.4f}s")
        print()
    
    # Test invalid transactions
    print("7. Testing invalid transactions...")
    
    # Create invalid ADVERTISE transaction (expired)
    invalid_advertise = transactions['advertise'].copy()
    invalid_advertise['metadata']['expiry_time'] = (datetime.now() - timedelta(days=1)).isoformat()
    
    print("   Testing expired ADVERTISE transaction:")
    is_valid, errors = middleware.validate_transaction(invalid_advertise, "pre_commit")
    if is_valid:
        print("   ✓ Expired ADVERTISE transaction is valid (unexpected)")
    else:
        print("   ✓ Expired ADVERTISE transaction is invalid (expected):")
        for error in errors:
            print(f"     - {error}")
    
    # Create invalid BUY transaction (wrong price)
    invalid_buy = transactions['buy'].copy()
    invalid_buy['asset']['data']['payment_amount'] = "50.00"  # Wrong price
    
    print("   Testing BUY transaction with wrong price:")
    is_valid, errors = middleware.validate_transaction(invalid_buy, "pre_commit")
    if is_valid:
        print("   ✓ BUY transaction with wrong price is valid (unexpected)")
    else:
        print("   ✓ BUY transaction with wrong price is invalid (expected):")
        for error in errors:
            print(f"     - {error}")
    
    print("\n=== Demo completed ===")


if __name__ == "__main__":
    run_baseline_validation_demo()
