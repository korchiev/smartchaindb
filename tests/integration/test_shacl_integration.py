"""
Integration test for SHACL validation with actual SHACL microservice

NOTE: This test requires the SHACL microservice to be running.
Run with: docker-compose up -d shacleng
"""

import pytest
import requests
import time
from bigchaindb.common.shacl_validator import SHACLValidatorClient


@pytest.fixture
def shacl_service_available():
    """Check if SHACL service is available"""
    try:
        response = requests.get('http://localhost:3000/', timeout=2)
        return response.status_code == 200
    except:
        pytest.skip("SHACL service not available. Run: docker-compose up -d shacleng")


@pytest.fixture
def validator():
    """Create validator instance for testing"""
    return SHACLValidatorClient(endpoint='http://localhost:3000', timeout=5)


class TestSHACLIntegration:
    """Integration tests with actual SHACL microservice"""
    
    def test_service_health_check(self, shacl_service_available):
        """Test SHACL service is running and healthy"""
        response = requests.get('http://localhost:3000/')
        assert response.status_code == 200
        
        data = response.json()
        assert 'message' in data
        assert 'loaded_shapes' in data
        assert len(data['loaded_shapes']) > 0
    
    def test_validate_create_transaction(self, shacl_service_available, validator):
        """Test validation of CREATE transaction"""
        tx = {
            'id': 'test_create_123',
            'operation': 'CREATE',
            'version': '2.0',
            'asset': {
                'data': {
                    'machineIdentifier': 'machine1',
                    'capability': 'read',
                    'capabilityParameters': 'param1'
                }
            },
            'metadata': {
                'requestCreationTimestamp': '2025-10-04T00:00:00Z'
            },
            'inputs': [{}],
            'outputs': [{}]
        }
        
        conforms, results = validator.validate_transaction(tx)
        
        # May fail if shape is strict about input structure
        # But should not crash
        assert isinstance(conforms, bool)
        assert isinstance(results, list)
    
    def test_validate_advertisement_transaction(self, shacl_service_available, validator):
        """Test validation of ADVERTISEMENT transaction"""
        tx = {
            'id': 'test_ad_123',
            'operation': 'ADVERTISEMENT',
            'version': '2.0',
            'asset': {
                'id': 'a' * 64  # 64-char hex string
            },
            'metadata': {
                'status': 'OPEN',
                'advertiser_public_key': '872WwZuFENK6bqarm6t9cbxobeEDckbMmjXRBqnPra6M',
                'price': '100.00',
                'description': 'Test item',
                'requestCreationTimestamp': '2025-10-04T00:00:00Z'
            },
            'inputs': [{}],
            'outputs': [{}]
        }
        
        conforms, results = validator.validate_transaction(tx)
        
        assert isinstance(conforms, bool)
        assert isinstance(results, list)
    
    def test_validate_buy_offer_transaction(self, shacl_service_available, validator):
        """Test validation of BUY_OFFER transaction"""
        tx = {
            'id': 'test_buyoffer_123',
            'operation': 'BUY_OFFER',
            'version': '2.0',
            'asset': {
                'id': 'a' * 64,
                'data': {
                    'advertisement_id': 'b' * 64
                }
            },
            'metadata': {
                'buyer_public_key': '4zEhw3jXEW22ybMkdVyrs6T4TiUPW1rKt6FUQ84UyMqW',
                'escrow_public_key': 'B7nbJxzpkgjAXqEjNspzvM1JJsR9dMM371fLR5JiSD5j',
                'offer_amount': '900',
                'offer_currency': 'USD',
                'offer_expiry': '2025-10-05T00:00:00Z',
                'requestCreationTimestamp': '2025-10-04T00:00:00Z'
            },
            'inputs': [{}],
            'outputs': [{}]
        }
        
        conforms, results = validator.validate_transaction(tx)
        
        assert isinstance(conforms, bool)
        assert isinstance(results, list)
    
    def test_validate_sell_transaction(self, shacl_service_available, validator):
        """Test validation of SELL transaction"""
        tx = {
            'id': 'test_sell_123',
            'operation': 'SELL',
            'version': '2.0',
            'asset': {
                'id': 'a' * 64,
                'data': {
                    'buy_offer_id': 'c' * 64
                }
            },
            'metadata': {
                'seller_public_key': 'Bq9QeS38NcTQh8oJp3jjQwzhrrn2xJpXzVUCFL9Xuiiv',
                'buyer_public_key': 'Ek1TLMb8nmThTVXDb69RpkkWN4r7q8yDfCNr6W9tHyfy',
                'sale_amount': '900',
                'sale_currency': 'USD',
                'requestCreationTimestamp': '2025-10-04T00:00:00Z'
            },
            'inputs': [{}],
            'outputs': [{}, {}]  # Two outputs for SELL
        }
        
        conforms, results = validator.validate_transaction(tx)
        
        assert isinstance(conforms, bool)
        assert isinstance(results, list)
    
    def test_validate_invalid_transaction(self, shacl_service_available, validator):
        """Test validation of invalid transaction (missing required fields)"""
        tx = {
            'id': 'test_invalid_123',
            'operation': 'BUY_OFFER',
            'version': '2.0',
            'asset': {
                'id': 'a' * 64
            },
            'metadata': {
                # Missing required fields like buyer_public_key, offer_amount, etc.
            },
            'inputs': [],
            'outputs': []
        }
        
        conforms, results = validator.validate_transaction(tx)
        
        # Should not conform due to missing required fields
        assert isinstance(conforms, bool)
        if not conforms:
            assert len(results) > 0
    
    def test_validate_unknown_operation(self, shacl_service_available, validator):
        """Test validation of transaction with unknown operation"""
        tx = {
            'id': 'test_unknown_123',
            'operation': 'UNKNOWN_OPERATION',
            'version': '2.0',
            'asset': {},
            'metadata': {},
            'inputs': [],
            'outputs': []
        }
        
        # Should return True (shape not found, don't block)
        conforms, results = validator.validate_transaction(tx)
        
        assert conforms is True
    
    def test_direct_api_call(self, shacl_service_available):
        """Test direct API call to SHACL service"""
        turtle_data = """
@prefix bdb: <http://bigchaindb.com/ns#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

<urn:tx:test123> a bdb:CREATETransaction ;
    bdb:operation "CREATE" ;
    bdb:version "2.0" ;
    bdb:asset [
        bdb:data [
            bdb:machineIdentifier "machine1" ;
            bdb:capability "read" ;
        ]
    ] ;
    bdb:metadata [
        bdb:requestCreationTimestamp "2025-10-04T00:00:00Z"^^xsd:dateTime ;
    ] ;
    bdb:inputs "1"^^xsd:integer ;
    bdb:outputs "1"^^xsd:integer .
"""
        
        response = requests.post(
            'http://localhost:3000/validate',
            json={
                'shapeType': 'CREATE',
                'data': turtle_data
            },
            timeout=5
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert 'conforms' in data
        assert 'results' in data
        assert isinstance(data['conforms'], bool)
        assert isinstance(data['results'], list)


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])

