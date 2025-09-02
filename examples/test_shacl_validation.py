#!/usr/bin/env python3
"""
Comprehensive test script for SHACL-based transaction validation.
Demonstrates the declarative approach vs traditional imperative validation.
"""

import sys
import os
import json
import time
from datetime import datetime, timedelta
from datetime import timezone

try:
    from bigchaindb.common.transaction import Transaction
    from bigchaindb.common.crypto import generate_key_pair
    from bigchaindb.common.shacl_schemas import SHACLValidator
    from bigchaindb.common.transaction_interceptor import TransactionInterceptor
    print("✅ Successfully imported BigchainDB modules including SHACL validation")
except ImportError as e:
    print(f"❌ Import error: {e}")
    sys.exit(1)

def create_test_transactions():
    """Create test transaction data for all types"""
    
    # Generate test keypairs
    advertiser_keypair = generate_key_pair()
    buyer_keypair = generate_key_pair()
    seller_keypair = generate_key_pair()
    escrow_keypair = generate_key_pair()
    
    # Test asset ID
    test_asset_id = "test_asset_123"
    
    # Test advertisement transaction
    advertisement_tx = {
        "operation": "ADVERTISEMENT",
        "asset": {
            "id": test_asset_id
        },
        "metadata": {
            "status": "OPEN",
            "advertiser_public_key": advertiser_keypair.public_key,
            "price": "1000.00",
            "description": "Test asset for sale"
        },
        "inputs": [{"owners_before": [advertiser_keypair.public_key], "fulfillment": "test"}],
        "outputs": []
    }
    
    # Test buy offer transaction
    buy_offer_tx = {
        "operation": "BUY_OFFER",
        "asset": {
            "id": test_asset_id,
            "advertisement_id": "ad_123"
        },
        "metadata": {
            "buyer_public_key": buyer_keypair.public_key,
            "offer_amount": 1000.00,
            "offer_currency": "USD",
            "offer_expiry": (datetime.utcnow() + timedelta(days=7)).strftime('%Y-%m-%dT%H:%M:%S'),
            "escrow_public_key": escrow_keypair.public_key
        },
        "inputs": [{"owners_before": [buyer_keypair.public_key], "fulfillment": "test"}],
        "outputs": [{"amount": 1000, "public_keys": [escrow_keypair.public_key], "fulfillment": "test"}]
    }
    
    # Test sell transaction
    sell_tx = {
        "operation": "SELL",
        "asset": {
            "id": test_asset_id,
            "buy_offer_id": "buy_offer_123"
        },
        "metadata": {
            "seller_public_key": seller_keypair.public_key,
            "buyer_public_key": buyer_keypair.public_key,
            "sale_amount": 1000.00,
            "sale_currency": "USD"
        },
        "inputs": [{"owners_before": [seller_keypair.public_key], "fulfillment": "test"}],
        "outputs": [
            {"amount": 1, "public_keys": [buyer_keypair.public_key], "fulfillment": "test"},
            {"amount": 1000, "public_keys": [seller_keypair.public_key], "fulfillment": "test"}
        ]
    }
    
    # Test request return transaction
    request_return_tx = {
        "operation": "REQUEST_RETURN",
        "asset": {
            "id": test_asset_id,
            "sell_transaction_id": "sell_123"
        },
        "metadata": {
            "requester_public_key": buyer_keypair.public_key,
            "return_reason": "Item not as described",
            "return_policy_details": {
                "return_window_days": 30,
                "return_status": "PENDING"
            }
        },
        "inputs": [{"owners_before": [buyer_keypair.public_key], "fulfillment": "test"}],
        "outputs": []
    }
    
    # Test accept return transaction
    accept_return_tx = {
        "operation": "ACCEPT_RETURN",
        "asset": {
            "id": test_asset_id,
            "request_return_id": "return_request_123"
        },
        "metadata": {
            "accepter_public_key": seller_keypair.public_key,
            "return_acceptance_timestamp": datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S'),
            "refund_details": {
                "refund_amount": 1000.00,
                "refund_currency": "USD",
                "refund_method": "Escrow return"
            },
            "return_processing_notes": "Return accepted, processing refund"
        },
        "inputs": [{"owners_before": [seller_keypair.public_key], "fulfillment": "test"}],
        "outputs": []
    }
    
    return {
        'ADVERTISEMENT': advertisement_tx,
        'BUY_OFFER': buy_offer_tx,
        'SELL': sell_tx,
        'REQUEST_RETURN': request_return_tx,
        'ACCEPT_RETURN': accept_return_tx
    }

def test_shacl_validator():
    """Test the SHACL validator directly"""
    print("\n=== Testing SHACL Validator ===")
    
    validator = SHACLValidator()
    
    # Test supported operations
    supported_ops = validator.list_supported_operations()
    print(f"✅ Supported operations: {supported_ops}")
    
    # Test schema export
    for operation in supported_ops:
        try:
            schema_json = validator.export_schema(operation, 'json')
            print(f"✅ {operation} schema exported successfully")
        except Exception as e:
            print(f"❌ Failed to export {operation} schema: {e}")

def test_transaction_interceptor():
    """Test the transaction interceptor"""
    print("\n=== Testing Transaction Interceptor ===")
    
    interceptor = TransactionInterceptor()
    
    # Test schema info
    for operation in ['BUY_OFFER', 'SELL', 'REQUEST_RETURN']:
        info = interceptor.get_schema_info(operation)
        print(f"📋 {operation}: {info.get('constraint_count', 0)} constraints, "
              f"Business rules: {info.get('has_business_rules', False)}, "
              f"State validation: {info.get('has_state_validation', False)}")

def test_validation_comparison():
    """Compare SHACL vs traditional validation"""
    print("\n=== Validation Method Comparison ===")
    
    interceptor = TransactionInterceptor()
    test_txs = create_test_transactions()
    
    results = {}
    
    for operation, tx_data in test_txs.items():
        print(f"\n🔍 Testing {operation} transaction:")
        
        # Test SHACL validation
        shacl_valid, shacl_errors, shacl_time = interceptor.intercept_and_validate(
            tx_data, use_shacl=True
        )
        
        # Test traditional validation
        trad_valid, trad_errors, trad_time = interceptor.intercept_and_validate(
            tx_data, use_shacl=False
        )
        
        results[operation] = {
            'shacl': {'valid': shacl_valid, 'errors': shacl_errors, 'time': shacl_time},
            'traditional': {'valid': trad_valid, 'errors': trad_errors, 'time': trad_time}
        }
        
        print(f"   SHACL: {'✅' if shacl_valid else '❌'} in {shacl_time:.2f}ms")
        if shacl_errors:
            print(f"      Errors: {shacl_errors}")
        
        print(f"   Traditional: {'✅' if trad_valid else '❌'} in {trad_time:.2f}ms")
        if trad_errors:
            print(f"      Errors: {trad_errors}")
    
    return results

def test_invalid_transactions():
    """Test validation with invalid transaction data"""
    print("\n=== Testing Invalid Transactions ===")
    
    validator = SHACLValidator()
    
    # Test invalid BUY_OFFER (missing required fields)
    invalid_buy_offer = {
        "operation": "BUY_OFFER",
        "asset": {
            "id": "test_asset"
            # Missing advertisement_id
        },
        "metadata": {
            # Missing required fields
            "buyer_public_key": "invalid_key"
        }
    }
    
    result = validator.validate_transaction(invalid_buy_offer)
    print(f"❌ Invalid BUY_OFFER validation: {result['valid']}")
    if not result['valid']:
        for error in result['errors']:
            print(f"   Error: {error}")
    
    # Test invalid ADVERTISEMENT (wrong status)
    invalid_advertisement = {
        "operation": "ADVERTISEMENT",
        "asset": {
            "id": "test_asset"
        },
        "metadata": {
            "status": "INVALID_STATUS",  # Invalid status
            "advertiser_public_key": "valid_key_12345678901234567890123456789012345678901234",
            "price": "1000.00"
        },
        "inputs": [{"owners_before": ["key"], "fulfillment": "test"}],
        "outputs": []
    }
    
    result = validator.validate_transaction(invalid_advertisement)
    print(f"❌ Invalid ADVERTISEMENT validation: {result['valid']}")
    if not result['valid']:
        for error in result['errors']:
            print(f"   Error: {error}")

def test_performance_benchmark():
    """Benchmark SHACL vs traditional validation performance"""
    print("\n=== Performance Benchmark ===")
    
    interceptor = TransactionInterceptor()
    test_txs = create_test_transactions()
    
    # Warm up
    for _ in range(10):
        for tx_data in test_txs.values():
            interceptor.intercept_and_validate(tx_data, use_shacl=True)
            interceptor.intercept_and_validate(tx_data, use_shacl=False)
    
    # Benchmark
    iterations = 100
    shacl_times = []
    trad_times = []
    
    print(f"Running {iterations} iterations for each validation method...")
    
    for _ in range(iterations):
        for tx_data in test_txs.values():
            # SHACL validation
            start = time.time()
            interceptor.intercept_and_validate(tx_data, use_shacl=True)
            shacl_times.append((time.time() - start) * 1000)
            
            # Traditional validation
            start = time.time()
            interceptor.intercept_and_validate(tx_data, use_shacl=False)
            trad_times.append((time.time() - start) * 1000)
    
    # Calculate statistics
    shacl_avg = sum(shacl_times) / len(shacl_times)
    trad_avg = sum(trad_times) / len(trad_times)
    
    print(f"📊 Performance Results:")
    print(f"   SHACL Validation: {shacl_avg:.3f}ms average")
    print(f"   Traditional Validation: {trad_avg:.3f}ms average")
    print(f"   Speedup: {trad_avg/shacl_avg:.2f}x")
    
    if shacl_avg < trad_avg:
        print("   🚀 SHACL validation is faster!")
    else:
        print("   ⚠️  Traditional validation is faster")

def test_shacl_schema_export():
    """Test SHACL schema export functionality"""
    print("\n=== SHACL Schema Export ===")
    
    validator = SHACLValidator()
    
    # Test JSON export
    for operation in ['BUY_OFFER', 'SELL']:
        try:
            schema_json = validator.export_schema(operation, 'json')
            schema_data = json.loads(schema_json)
            
            print(f"✅ {operation} schema exported as JSON:")
            print(f"   Context: {schema_data.get('@context', {}).keys()}")
            print(f"   Type: {schema_data.get('@type')}")
            print(f"   Target Class: {schema_data.get('targetClass')}")
            print(f"   Properties: {len(schema_data.get('property', []))}")
            
        except Exception as e:
            print(f"❌ Failed to export {operation} schema: {e}")

def main():
    """Main test function"""
    print("🚀 SHACL Transaction Validation System Test")
    print("=" * 50)
    
    try:
        # Test 1: Basic SHACL validator
        test_shacl_validator()
        
        # Test 2: Transaction interceptor
        test_transaction_interceptor()
        
        # Test 3: Validation comparison
        results = test_validation_comparison()
        
        # Test 4: Invalid transaction validation
        test_invalid_transactions()
        
        # Test 5: Performance benchmark
        test_performance_benchmark()
        
        # Test 6: Schema export
        test_shacl_schema_export()
        
        # Summary
        print("\n" + "=" * 50)
        print("📋 Test Summary")
        print("=" * 50)
        
        interceptor = TransactionInterceptor() # Re-initialize interceptor for stats
        stats = interceptor.get_validation_stats()
        print(f"Total transactions processed: {stats['total_transactions']}")
        print(f"SHACL validations: {stats['shacl_validations']}")
        print(f"Traditional validations: {stats['traditional_validations']}")
        
        if stats['validation_times']:
            print(f"Average validation time: {stats['avg_validation_time_ms']:.2f}ms")
            print(f"Min validation time: {stats['min_validation_time_ms']:.2f}ms")
            print(f"Max validation time: {stats['max_validation_time_ms']:.2f}ms")
        
        print("\n🎉 All tests completed successfully!")
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
