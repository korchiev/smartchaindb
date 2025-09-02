# Copyright © 2020 Interplanetary Database Association e.V.,
# BigchainDB and IPDB software contributors.
# SPDX-License-Identifier: (Apache-2.0 AND CC-BY-4.0)
# Code is Apache-2.0 and docs are CC-BY-4.0

"""Test REQUEST_RETURN transaction type"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, MagicMock

from bigchaindb.common.transaction import Transaction
from bigchaindb.common.exceptions import (
    InputDoesNotExist,
    DoubleSpend,
    AssetIdMismatch,
    InvalidSignature,
    ValueError,
    TypeError
)


class TestRequestReturn:
    """Test the REQUEST_RETURN transaction type"""

    def test_request_return_creation(self):
        """Test creating a REQUEST_RETURN transaction"""
        # Create test inputs
        inputs = [Mock()]
        inputs[0].fulfills = Mock()
        inputs[0].fulfills.txid = "test_tx_id"
        inputs[0].fulfills.output = 0
        
        # Create test metadata
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
        
        # Create transaction
        tx = Transaction.request_return(
            inputs=inputs,
            asset_id="asset_123",
            sell_transaction_id="sell_tx_456",
            metadata=metadata
        )
        
        assert tx.operation == Transaction.REQUEST_RETURN
        assert tx.asset['id'] == "asset_123"
        assert tx.asset['sell_transaction_id'] == "sell_tx_456"
        assert tx.metadata == metadata
        assert len(tx.inputs) == 1
        assert len(tx.outputs) == 0

    def test_request_return_creation_default_status(self):
        """Test creating a REQUEST_RETURN transaction with default status"""
        # Create test inputs
        inputs = [Mock()]
        inputs[0].fulfills = Mock()
        inputs[0].fulfills.txid = "test_tx_id"
        inputs[0].fulfills.output = 0
        
        # Create test metadata without return_policy_details
        metadata = {
            'requester_public_key': 'requester_pub_key_123',
            'return_reason': 'Item damaged during shipping',
            'return_request_timestamp': '2023-01-01T10:00:00Z'
        }
        
        # Create transaction
        tx = Transaction.request_return(
            inputs=inputs,
            asset_id="asset_123",
            sell_transaction_id="sell_tx_456",
            metadata=metadata
        )
        
        # Check that default return status was set
        assert tx.metadata['return_policy_details']['return_status'] == 'PENDING'

    def test_request_return_validation_success(self):
        """Test successful REQUEST_RETURN validation"""
        # Create test inputs
        inputs = [Mock()]
        inputs[0].fulfills = Mock()
        inputs[0].fulfills.txid = "test_tx_id"
        inputs[0].fulfills.output = 0
        
        # Create test metadata
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
        
        # Test validation
        validated_inputs, validated_outputs = Transaction.validate_request_return(
            inputs, "asset_123", "sell_tx_456", metadata
        )
        
        assert validated_inputs == inputs
        assert validated_outputs == []

    def test_request_return_validation_invalid_inputs(self):
        """Test REQUEST_RETURN validation with invalid inputs"""
        # Test with non-list inputs
        with pytest.raises(TypeError, match="`inputs` must be a list instance"):
            Transaction.validate_request_return("not_a_list", "asset_123", "sell_tx_456", {})
        
        # Test with wrong number of inputs
        inputs = [Mock(), Mock()]  # Two inputs instead of one
        with pytest.raises(ValueError, match="`inputs` must contain exactly one item"):
            Transaction.validate_request_return(inputs, "asset_123", "sell_tx_456", {})

    def test_request_return_validation_invalid_metadata(self):
        """Test REQUEST_RETURN validation with invalid metadata"""
        inputs = [Mock()]
        
        # Test with non-dict metadata
        with pytest.raises(TypeError, match="`metadata` must be a dict"):
            Transaction.validate_request_return(inputs, "asset_123", "sell_tx_456", "not_a_dict")
        
        # Test with missing required fields
        incomplete_metadata = {
            'requester_public_key': 'requester_pub_key_123',
            'return_reason': 'Item damaged during shipping'
            # Missing other required fields
        }
        
        with pytest.raises(ValueError, match="`metadata` must contain 'return_request_timestamp' field"):
            Transaction.validate_request_return(inputs, "asset_123", "sell_tx_456", incomplete_metadata)

    def test_request_return_validation_invalid_reason(self):
        """Test REQUEST_RETURN validation with invalid return reason"""
        inputs = [Mock()]
        metadata = {
            'requester_public_key': 'requester_pub_key_123',
            'return_reason': '',  # Empty reason
            'return_request_timestamp': '2023-01-01T10:00:00Z',
            'return_policy_details': {}
        }
        
        with pytest.raises(ValueError, match="`return_reason` must be a non-empty string"):
            Transaction.validate_request_return(inputs, "asset_123", "sell_tx_456", metadata)

    def test_request_return_validation_invalid_policy_details(self):
        """Test REQUEST_RETURN validation with invalid policy details"""
        inputs = [Mock()]
        metadata = {
            'requester_public_key': 'requester_pub_key_123',
            'return_reason': 'Item damaged during shipping',
            'return_request_timestamp': '2023-01-01T10:00:00Z',
            'return_policy_details': 'not_a_dict'  # Not a dict
        }
        
        with pytest.raises(ValueError, match="`return_policy_details` must be a dict"):
            Transaction.validate_request_return(inputs, "asset_123", "sell_tx_456", metadata)

    def test_request_return_inputs_validation_success(self, monkeypatch):
        """Test successful REQUEST_RETURN inputs validation"""
        # Create mock bigchain
        mock_bigchain = Mock()
        
        # Create test transaction
        tx = Transaction(
            operation=Transaction.REQUEST_RETURN,
            asset={"id": "asset_123", "sell_transaction_id": "sell_tx_456"},
            inputs=[Mock()],
            metadata={
                'requester_public_key': 'requester_pub_key_123',
                'return_reason': 'Item damaged during shipping',
                'return_request_timestamp': '2023-01-01T10:00:00Z',
                'return_policy_details': {
                    'return_window_days': 30,
                    'return_conditions': 'Item must be in original condition',
                    'return_status': 'PENDING'
                }
            }
        )
        
        # Mock input
        tx.inputs[0].fulfills = Mock()
        tx.inputs[0].fulfills.txid = "input_tx_id"
        tx.inputs[0].fulfills.output = 0
        
        # Mock input transaction
        mock_input_tx = Mock()
        mock_input_tx.id = "input_tx_id"
        mock_input_tx.outputs = [Mock()]
        mock_input_tx.outputs[0].public_keys = ["requester_pub_key_123"]
        mock_input_tx.outputs[0].amount = "1"
        
        # Mock sell transaction
        mock_sell_tx = Mock()
        mock_sell_tx.operation = "SELL"
        mock_sell_tx.asset = {"id": "asset_123", "buy_offer_id": "buy_offer_789"}
        
        # Mock buy offer transaction
        mock_buy_offer_tx = Mock()
        mock_buy_offer_tx.operation = "BUY_OFFER"
        mock_buy_offer_tx.metadata = {'buyer_public_key': 'requester_pub_key_123'}
        
        # Mock bigchain methods
        mock_bigchain.get_transaction.side_effect = lambda txid: {
            "input_tx_id": mock_input_tx,
            "sell_tx_456": mock_sell_tx,
            "buy_offer_789": mock_buy_offer_tx
        }.get(txid)
        
        mock_bigchain.get_spent.return_value = None
        
        # Mock get_transactions_filtered to return empty list (no existing return requests)
        mock_bigchain.get_transactions_filtered.return_value = []
        
        # Mock signature validation
        monkeypatch.setattr(tx, 'inputs_valid', lambda conditions: True)
        monkeypatch.setattr(tx, 'get_asset_id', lambda txs: "asset_123")
        
        # Test validation
        result = tx.validate_request_return_inputs(mock_bigchain)
        assert result is True

    def test_request_return_inputs_validation_wrong_input_count(self):
        """Test REQUEST_RETURN inputs validation with wrong input count"""
        mock_bigchain = Mock()
        tx = Transaction(
            operation=Transaction.REQUEST_RETURN,
            asset={"id": "asset_123", "sell_transaction_id": "sell_tx_456"},
            inputs=[Mock(), Mock()],  # Two inputs instead of one
            metadata={}
        )
        
        with pytest.raises(ValueError, match="Request return must have exactly one input"):
            tx.validate_request_return_inputs(mock_bigchain)

    def test_request_return_inputs_validation_sell_tx_not_found(self, monkeypatch):
        """Test REQUEST_RETURN inputs validation when sell transaction doesn't exist"""
        mock_bigchain = Mock()
        mock_bigchain.get_transaction.return_value = None
        
        tx = Transaction(
            operation=Transaction.REQUEST_RETURN,
            asset={"id": "asset_123", "sell_transaction_id": "sell_tx_456"},
            inputs=[Mock()],
            metadata={}
        )
        
        tx.inputs[0].fulfills = Mock()
        tx.inputs[0].fulfills.txid = "input_tx_id"
        tx.inputs[0].fulfills.output = 0
        
        with pytest.raises(ValueError, match="Referenced sell transaction sell_tx_456 does not exist"):
            tx.validate_request_return_inputs(mock_bigchain)

    def test_request_return_inputs_validation_sell_tx_wrong_operation(self, monkeypatch):
        """Test REQUEST_RETURN inputs validation when referenced transaction is not a sell transaction"""
        mock_bigchain = Mock()
        
        # Mock transaction with wrong operation
        mock_wrong_tx = Mock()
        mock_wrong_tx.operation = "TRANSFER"  # Not SELL
        
        mock_bigchain.get_transaction.side_effect = lambda txid: {
            "sell_tx_456": mock_wrong_tx
        }.get(txid)
        
        tx = Transaction(
            operation=Transaction.REQUEST_RETURN,
            asset={"id": "asset_123", "sell_transaction_id": "sell_tx_456"},
            inputs=[Mock()],
            metadata={}
        )
        
        tx.inputs[0].fulfills = Mock()
        tx.inputs[0].fulfills.txid = "input_tx_id"
        tx.inputs[0].fulfills.output = 0
        
        with pytest.raises(ValueError, match="Referenced transaction sell_tx_456 is not a sell transaction"):
            tx.validate_request_return_inputs(mock_bigchain)

    def test_request_return_inputs_validation_requester_not_buyer(self, monkeypatch):
        """Test REQUEST_RETURN inputs validation when requester is not the buyer"""
        mock_bigchain = Mock()
        
        # Mock sell transaction
        mock_sell_tx = Mock()
        mock_sell_tx.operation = "SELL"
        mock_sell_tx.asset = {"id": "asset_123", "buy_offer_id": "buy_offer_789"}
        
        # Mock buy offer transaction with different buyer
        mock_buy_offer_tx = Mock()
        mock_buy_offer_tx.operation = "BUY_OFFER"
        mock_buy_offer_tx.metadata = {'buyer_public_key': 'different_buyer'}
        
        mock_bigchain.get_transaction.side_effect = lambda txid: {
            "sell_tx_456": mock_sell_tx,
            "buy_offer_789": mock_buy_offer_tx
        }.get(txid)
        
        tx = Transaction(
            operation=Transaction.REQUEST_RETURN,
            asset={"id": "asset_123", "sell_transaction_id": "sell_tx_456"},
            inputs=[Mock()],
            metadata={'requester_public_key': 'requester_pub_key_123'}  # Different from buyer
        )
        
        tx.inputs[0].fulfills = Mock()
        tx.inputs[0].fulfills.txid = "input_tx_id"
        tx.inputs[0].fulfills.output = 0
        
        with pytest.raises(ValueError, match="Requester must be the buyer from the sell transaction"):
            tx.validate_request_return_inputs(mock_bigchain)

    def test_request_return_inputs_validation_return_policy_not_allowed(self, monkeypatch):
        """Test REQUEST_RETURN inputs validation when return policy doesn't allow returns"""
        mock_bigchain = Mock()
        
        # Mock sell transaction
        mock_sell_tx = Mock()
        mock_sell_tx.operation = "SELL"
        mock_sell_tx.asset = {"id": "asset_123", "buy_offer_id": "buy_offer_789"}
        
        # Mock buy offer transaction
        mock_buy_offer_tx = Mock()
        mock_buy_offer_tx.operation = "BUY_OFFER"
        mock_buy_offer_tx.metadata = {'buyer_public_key': 'requester_pub_key_123'}
        
        mock_bigchain.get_transaction.side_effect = lambda txid: {
            "sell_tx_456": mock_sell_tx,
            "buy_offer_789": mock_buy_offer_tx
        }.get(txid)
        
        # Mock get_transactions_filtered to return empty list
        mock_bigchain.get_transactions_filtered.return_value = []
        
        tx = Transaction(
            operation=Transaction.REQUEST_RETURN,
            asset={"id": "asset_123", "sell_transaction_id": "sell_tx_456"},
            inputs=[Mock()],
            metadata={
                'requester_public_key': 'requester_pub_key_123',
                'return_reason': 'Item damaged during shipping',
                'return_request_timestamp': '2023-01-01T10:00:00Z',
                'return_policy_details': {
                    'return_window_days': 0,  # No return window
                    'return_conditions': 'Item must be in original condition',
                    'return_status': 'PENDING'
                }
            }
        )
        
        tx.inputs[0].fulfills = Mock()
        tx.inputs[0].fulfills.txid = "input_tx_id"
        tx.inputs[0].fulfills.output = 0
        
        with pytest.raises(ValueError, match="Return policy must allow returns"):
            tx.validate_request_return_inputs(mock_bigchain)

    def test_request_return_inputs_validation_existing_active_request(self, monkeypatch):
        """Test REQUEST_RETURN inputs validation when there's already an active return request"""
        mock_bigchain = Mock()
        
        # Mock sell transaction
        mock_sell_tx = Mock()
        mock_sell_tx.operation = "SELL"
        mock_sell_tx.asset = {"id": "asset_123", "buy_offer_id": "buy_offer_789"}
        
        # Mock buy offer transaction
        mock_buy_offer_tx = Mock()
        mock_buy_offer_tx.operation = "BUY_OFFER"
        mock_buy_offer_tx.metadata = {'buyer_public_key': 'requester_pub_key_123'}
        
        # Mock existing return request
        mock_existing_return = Mock()
        mock_existing_return.asset = {"sell_transaction_id": "sell_tx_456"}
        mock_existing_return.metadata = {
            'return_policy_details': {'return_status': 'PENDING'}
        }
        
        mock_bigchain.get_transaction.side_effect = lambda txid: {
            "sell_tx_456": mock_sell_tx,
            "buy_offer_789": mock_buy_offer_tx
        }.get(txid)
        
        # Mock get_transactions_filtered to return existing return request
        mock_bigchain.get_transactions_filtered.return_value = [mock_existing_return]
        
        tx = Transaction(
            operation=Transaction.REQUEST_RETURN,
            asset={"id": "asset_123", "sell_transaction_id": "sell_tx_456"},
            inputs=[Mock()],
            metadata={
                'requester_public_key': 'requester_pub_key_123',
                'return_reason': 'Item damaged during shipping',
                'return_request_timestamp': '2023-01-01T10:00:00Z',
                'return_policy_details': {
                    'return_window_days': 30,
                    'return_conditions': 'Item must be in original condition',
                    'return_status': 'PENDING'
                }
            }
        )
        
        tx.inputs[0].fulfills = Mock()
        tx.inputs[0].fulfills.txid = "input_tx_id"
        tx.inputs[0].fulfills.output = 0
        
        with pytest.raises(ValueError, match="Sale sell_tx_456 already has an active return request"):
            tx.validate_request_return_inputs(mock_bigchain)

    def test_request_return_inputs_validation_no_existing_active_request(self, monkeypatch):
        """Test REQUEST_RETURN inputs validation when there's no existing active return request"""
        mock_bigchain = Mock()
        
        # Mock sell transaction
        mock_sell_tx = Mock()
        mock_sell_tx.operation = "SELL"
        mock_sell_tx.asset = {"id": "asset_123", "buy_offer_id": "buy_offer_789"}
        
        # Mock buy offer transaction
        mock_buy_offer_tx = Mock()
        mock_buy_offer_tx.operation = "BUY_OFFER"
        mock_buy_offer_tx.metadata = {'buyer_public_key': 'requester_pub_key_123'}
        
        # Mock existing return request with different status
        mock_existing_return = Mock()
        mock_existing_return.asset = {"sell_transaction_id": "sell_tx_456"}
        mock_existing_return.metadata = {
            'return_policy_details': {'return_status': 'COMPLETED'}  # Not PENDING
        }
        
        mock_bigchain.get_transaction.side_effect = lambda txid: {
            "sell_tx_456": mock_sell_tx,
            "buy_offer_789": mock_buy_offer_tx
        }.get(txid)
        
        # Mock get_transactions_filtered to return existing return request
        mock_bigchain.get_transactions_filtered.return_value = [mock_existing_return]
        
        # Mock input transaction
        mock_input_tx = Mock()
        mock_input_tx.id = "input_tx_id"
        mock_input_tx.outputs = [Mock()]
        mock_input_tx.outputs[0].public_keys = ["requester_pub_key_123"]
        mock_input_tx.outputs[0].amount = "1"
        
        mock_bigchain.get_transaction.side_effect = lambda txid: {
            "input_tx_id": mock_input_tx,
            "sell_tx_456": mock_sell_tx,
            "buy_offer_789": mock_buy_offer_tx
        }.get(txid)
        
        mock_bigchain.get_spent.return_value = None
        
        # Mock signature validation
        monkeypatch.setattr(tx, 'inputs_valid', lambda conditions: True)
        monkeypatch.setattr(tx, 'get_asset_id', lambda txs: "asset_123")
        
        tx = Transaction(
            operation=Transaction.REQUEST_RETURN,
            asset={"id": "asset_123", "sell_transaction_id": "sell_tx_456"},
            inputs=[Mock()],
            metadata={
                'requester_public_key': 'requester_pub_key_123',
                'return_reason': 'Item damaged during shipping',
                'return_request_timestamp': '2023-01-01T10:00:00Z',
                'return_policy_details': {
                    'return_window_days': 30,
                    'return_conditions': 'Item must be in original condition',
                    'return_status': 'PENDING'
                }
            }
        )
        
        tx.inputs[0].fulfills = Mock()
        tx.inputs[0].fulfills.txid = "input_tx_id"
        tx.inputs[0].fulfills.output = 0
        
        # Test validation - should pass since existing request is not PENDING
        result = tx.validate_request_return_inputs(mock_bigchain)
        assert result is True
