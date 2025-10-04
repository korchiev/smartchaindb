"""
Test SHACL validation integration

This module tests the SHACL validation system for BigchainDB transactions.
"""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from bigchaindb.common.shacl_validator import SHACLValidatorClient, get_shacl_validator


class TestSHACLValidatorClient:
    """Test SHACL validator client"""
    
    def test_validator_disabled_by_default(self):
        """Test that SHACL validation is disabled by default"""
        with patch('bigchaindb.common.shacl_validator.config_utils') as mock_config:
            mock_config.get.return_value = False
            validator = SHACLValidatorClient()
            assert validator.enabled is False
    
    def test_validator_can_be_enabled(self):
        """Test that SHACL validation can be enabled via config"""
        with patch('bigchaindb.common.shacl_validator.config') as mock_config:
            mock_config.get.return_value = {
                'enabled': True,
                'endpoint': 'http://localhost:3000',
                'timeout': 5
            }
            validator = SHACLValidatorClient()
            assert validator.enabled is True
            assert validator.endpoint == 'http://localhost:3000'
            assert validator.timeout == 5
    
    def test_json_to_turtle_conversion_create(self):
        """Test JSON to Turtle conversion for CREATE transaction"""
        validator = SHACLValidatorClient()
        
        tx = {
            'id': 'test123',
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
        
        turtle = validator._convert_to_turtle(tx)
        
        assert '@prefix bdb:' in turtle
        assert 'bdb:CREATETransaction' in turtle
        assert 'bdb:operation "CREATE"' in turtle
        assert 'bdb:machineIdentifier "machine1"' in turtle
        assert 'bdb:requestCreationTimestamp' in turtle
    
    def test_json_to_turtle_conversion_buy_offer(self):
        """Test JSON to Turtle conversion for BUY_OFFER transaction"""
        validator = SHACLValidatorClient()
        
        tx = {
            'id': 'buyoffer123',
            'operation': 'BUY_OFFER',
            'version': '2.0',
            'asset': {
                'id': 'asset123',
                'data': {
                    'advertisement_id': 'ad123'
                }
            },
            'metadata': {
                'buyer_public_key': '4zEhw3jXEW22ybMkdVyrs6T4TiUPW1rKt6FUQ84UyMqW',
                'offer_amount': '900',
                'offer_currency': 'USD',
                'escrow_public_key': 'B7nbJxzpkgjAXqEjNspzvM1JJsR9dMM371fLR5JiSD5j',
                'offer_expiry': '2025-10-05T00:00:00Z'
            },
            'inputs': [{}],
            'outputs': [{}]
        }
        
        turtle = validator._convert_to_turtle(tx)
        
        assert 'bdb:BUY_OFFERTransaction' in turtle
        assert 'bdb:operation "BUY_OFFER"' in turtle
        assert 'bdb:advertisement_id "ad123"' in turtle
        assert 'bdb:buyer_public_key' in turtle
        assert 'bdb:offer_amount "900"' in turtle
    
    @patch('bigchaindb.common.shacl_validator.requests.post')
    def test_validate_transaction_success(self, mock_post):
        """Test successful SHACL validation"""
        # Mock successful validation response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'conforms': True,
            'results': []
        }
        mock_post.return_value = mock_response
        
        with patch('bigchaindb.common.shacl_validator.config') as mock_config:
            mock_config.get.return_value = {'enabled': True}
            
            validator = SHACLValidatorClient()
            tx = {
                'id': 'test123',
                'operation': 'CREATE',
                'version': '2.0',
                'asset': {'data': {}},
                'metadata': {},
                'inputs': [],
                'outputs': []
            }
            
            conforms, results = validator.validate_transaction(tx)
            
            assert conforms is True
            assert len(results) == 0
            mock_post.assert_called_once()
    
    @patch('bigchaindb.common.shacl_validator.requests.post')
    def test_validate_transaction_failure(self, mock_post):
        """Test failed SHACL validation"""
        # Mock failed validation response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'conforms': False,
            'results': [
                {
                    'message': ['offer_amount is required'],
                    'path': 'bdb:offer_amount',
                    'severity': 'Violation'
                }
            ]
        }
        mock_post.return_value = mock_response
        
        with patch('bigchaindb.common.shacl_validator.config') as mock_config:
            mock_config.get.return_value = {'enabled': True}
            
            validator = SHACLValidatorClient()
            tx = {
                'id': 'buyoffer123',
                'operation': 'BUY_OFFER',
                'version': '2.0',
                'asset': {},
                'metadata': {},  # Missing required fields
                'inputs': [],
                'outputs': []
            }
            
            conforms, results = validator.validate_transaction(tx)
            
            assert conforms is False
            assert len(results) > 0
            assert 'offer_amount' in str(results[0])
    
    @patch('bigchaindb.common.shacl_validator.requests.post')
    def test_validate_transaction_shape_not_found(self, mock_post):
        """Test validation when shape is not found"""
        # Mock 404 response
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.json.return_value = {
            'error': 'Shape type "UNKNOWN_OP" not found',
            'available_shapes': ['CREATE', 'BUY_OFFER', 'SELL']
        }
        mock_post.return_value = mock_response
        
        with patch('bigchaindb.common.shacl_validator.config') as mock_config:
            mock_config.get.return_value = {'enabled': True}
            
            validator = SHACLValidatorClient()
            tx = {
                'id': 'test123',
                'operation': 'UNKNOWN_OP',
                'version': '2.0',
                'asset': {},
                'metadata': {},
                'inputs': [],
                'outputs': []
            }
            
            # Should return True to not block transactions when shape is missing
            conforms, results = validator.validate_transaction(tx)
            
            assert conforms is True
    
    @patch('bigchaindb.common.shacl_validator.requests.post')
    def test_validate_transaction_timeout(self, mock_post):
        """Test validation timeout handling"""
        import requests
        mock_post.side_effect = requests.exceptions.Timeout()
        
        with patch('bigchaindb.common.shacl_validator.config') as mock_config:
            mock_config.get.return_value = {'enabled': True}
            
            validator = SHACLValidatorClient()
            tx = {
                'id': 'test123',
                'operation': 'CREATE',
                'version': '2.0',
                'asset': {},
                'metadata': {},
                'inputs': [],
                'outputs': []
            }
            
            conforms, results = validator.validate_transaction(tx)
            
            assert conforms is False
            assert 'timeout' in str(results[0]).lower()
    
    @patch('bigchaindb.common.shacl_validator.requests.get')
    def test_health_check_success(self, mock_get):
        """Test SHACL service health check"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response
        
        with patch('bigchaindb.common.shacl_validator.config') as mock_config:
            mock_config.get.return_value = {'enabled': True}
            
            validator = SHACLValidatorClient()
            assert validator.health_check() is True
    
    @patch('bigchaindb.common.shacl_validator.requests.get')
    def test_health_check_failure(self, mock_get):
        """Test SHACL service health check failure"""
        import requests
        mock_get.side_effect = requests.exceptions.ConnectionError()
        
        with patch('bigchaindb.common.shacl_validator.config') as mock_config:
            mock_config.get.return_value = {'enabled': True}
            
            validator = SHACLValidatorClient()
            assert validator.health_check() is False


def test_get_shacl_validator_singleton():
    """Test that get_shacl_validator returns singleton instance"""
    validator1 = get_shacl_validator()
    validator2 = get_shacl_validator()
    
    assert validator1 is validator2

