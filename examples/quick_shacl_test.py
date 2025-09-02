#!/usr/bin/env python3
"""
Quick test script for SHACL validation system.
"""

try:
    from bigchaindb.common.shacl_schemas import SHACLValidator
    from bigchaindb.common.transaction_interceptor import TransactionInterceptor
    print("✅ Successfully imported SHACL validation modules")
except ImportError as e:
    print(f"❌ Import error: {e}")
    exit(1)

def test_basic_shacl():
    """Test basic SHACL functionality"""
    print("\n=== Testing Basic SHACL ===")
    
    validator = SHACLValidator()
    
    # Test supported operations
    operations = validator.list_supported_operations()
    print(f"✅ Supported operations: {operations}")
    
    # Test schema export
    try:
        schema = validator.export_schema('BUY_OFFER', 'json')
        print("✅ BUY_OFFER schema exported successfully")
    except Exception as e:
        print(f"❌ Schema export failed: {e}")

def test_datetime_validation():
    """Test datetime validation"""
    print("\n=== Testing Datetime Validation ===")
    
    validator = SHACLValidator()
    
    # Test valid datetime
    test_datetime = "2025-08-26T01:15:00"
    result = validator._validate_datatype(test_datetime, 'xsd:dateTime')
    print(f"✅ Valid datetime '{test_datetime}': {result}")
    
    # Test invalid datetime
    test_invalid = "invalid_datetime"
    result = validator._validate_datatype(test_invalid, 'xsd:dateTime')
    print(f"❌ Invalid datetime '{test_invalid}': {result}")

def test_transaction_validation():
    """Test transaction validation"""
    print("\n=== Testing Transaction Validation ===")
    
    validator = SHACLValidator()
    
    # Test valid ADVERTISEMENT transaction
    valid_ad = {
        "operation": "ADVERTISEMENT",
        "asset": {"id": "test_asset"},
        "metadata": {
            "status": "OPEN",
            "advertiser_public_key": "12345678901234567890123456789012345678901234",
            "price": "1000.00"
        },
        "inputs": [{"owners_before": ["key"], "fulfillment": "test"}],
        "outputs": []
    }
    
    result = validator.validate_transaction(valid_ad)
    print(f"✅ Valid ADVERTISEMENT: {result['valid']}")
    if not result['valid']:
        for error in result['errors']:
            print(f"   Error: {error}")

if __name__ == "__main__":
    print("🚀 Quick SHACL Validation Test")
    print("=" * 40)
    
    test_basic_shacl()
    test_datetime_validation()
    test_transaction_validation()
    
    print("\n🎉 Quick test completed!")
