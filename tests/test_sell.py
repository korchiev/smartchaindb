# Copyright © 2020 Interplanetary Database Association e.V.,
# BigchainDB and IPDB software contributors.
# SPDX-License-Identifier: (Apache-2.0 AND CC-BY-4.0)
# Code is Apache-2.0 and docs are CC-BY-4.0

"""Test SELL transaction type"""

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


class TestSell:
    """Test the SELL transaction type"""

    def test_sell_creation(self):
        """Test creating a SELL transaction"""
        # Create test inputs
        inputs = [Mock()]
        inputs[0].fulfills = Mock()
        inputs[0].fulfills.txid = "test_tx_id"
        inputs[0].fulfills.output = 0
        
        # Create test metadata
        metadata = {
            'seller_public_key': 'seller_pub_key_123',
            'sale_amount': 100.0,
            'sale_currency': 'USD',
            'escrow_details': {
                'escrow_id': 'escrow_123',
                'escrow_amount': 100.0,
                'escrow_currency': 'USD'
            },
            'sale_timestamp': '2023-01-01T10:00:00Z'
        }
        
        # Create transaction
        tx = Transaction.sell(
            inputs=inputs,
            asset_id="asset_123",
            buy_offer_id="buy_offer_456",
            metadata=metadata
        )
        
        assert tx.operation == Transaction.SELL
        assert tx.asset['id'] == "asset_123"
        assert tx.asset['buy_offer_id'] == "buy_offer_456"
        assert tx.metadata == metadata
        assert len(tx.inputs) == 1
        assert len(tx.outputs) == 0

    def test_sell_validation_success(self):
        """Test successful SELL validation"""
        # Create test inputs
        inputs = [Mock()]
        inputs[0].fulfills = Mock()
        inputs[0].fulfills.txid = "test_tx_id"
        inputs[0].fulfills.output = 0
        
        # Create test metadata
        metadata = {
            'seller_public_key': 'seller_pub_key_123',
            'sale_amount': 100.0,
            'sale_currency': 'USD',
            'escrow_details': {
                'escrow_id': 'escrow_123',
                'escrow_amount': 100.0,
                'escrow_currency': 'USD'
            },
            'sale_timestamp': '2023-01-01T10:00:00Z'
        }
        
        # Test validation
        validated_inputs, validated_outputs = Transaction.validate_sell(
            inputs, "asset_123", "buy_offer_456", metadata
        )
        
        assert validated_inputs == inputs
        assert validated_outputs == []

    def test_sell_validation_invalid_inputs(self):
        """Test SELL validation with invalid inputs"""
        # Test with non-list inputs
        with pytest.raises(TypeError, match="`inputs` must be a list instance"):
            Transaction.validate_sell("not_a_list", "asset_123", "buy_offer_456", {})
        
        # Test with wrong number of inputs
        inputs = [Mock(), Mock()]  # Two inputs instead of one
        with pytest.raises(ValueError, match="`inputs` must contain exactly one item"):
            Transaction.validate_sell(inputs, "asset_123", "buy_offer_456", {})

    def test_sell_validation_invalid_metadata(self):
        """Test SELL validation with invalid metadata"""
        inputs = [Mock()]
        
        # Test with non-dict metadata
        with pytest.raises(TypeError, match="`metadata` must be a dict"):
            Transaction.validate_sell(inputs, "asset_123", "buy_offer_456", "not_a_dict")
        
        # Test with missing required fields
        incomplete_metadata = {
            'seller_public_key': 'seller_pub_key_123',
            'sale_amount': 100.0
            # Missing other required fields
        }
        
        with pytest.raises(ValueError, match="`metadata` must contain 'sale_currency' field"):
            Transaction.validate_sell(inputs, "asset_123", "buy_offer_456", incomplete_metadata)

    def test_sell_validation_invalid_amount(self):
        """Test SELL validation with invalid amount"""
        inputs = [Mock()]
        metadata = {
            'seller_public_key': 'seller_pub_key_123',
            'sale_amount': -100.0,  # Negative amount
            'sale_currency': 'USD',
            'escrow_details': {},
            'sale_timestamp': '2023-01-01T10:00:00Z'
        }
        
        with pytest.raises(ValueError, match="`sale_amount` must be a positive number"):
            Transaction.validate_sell(inputs, "asset_123", "buy_offer_456", metadata)

    def test_sell_validation_invalid_escrow_details(self):
        """Test SELL validation with invalid escrow details"""
        inputs = [Mock()]
        metadata = {
            'seller_public_key': 'seller_pub_key_123',
            'sale_amount': 100.0,
            'sale_currency': 'USD',
            'escrow_details': 'not_a_dict',  # Not a dict
            'sale_timestamp': '2023-01-01T10:00:00Z'
        }
        
        with pytest.raises(ValueError, match="`escrow_details` must be a dict"):
            Transaction.validate_sell(inputs, "asset_123", "buy_offer_456", metadata)

    def test_sell_inputs_validation_success(self, monkeypatch):
        """Test successful SELL inputs validation"""
        # Create mock bigchain
        mock_bigchain = Mock()
        
        # Create test transaction
        tx = Transaction(
            operation=Transaction.SELL,
            asset={"id": "asset_123", "buy_offer_id": "buy_offer_456"},
            inputs=[Mock()],
            metadata={
                'seller_public_key': 'seller_pub_key_123',
                'sale_amount': 100.0,
                'sale_currency': 'USD',
                'escrow_details': {
                    'escrow_id': 'escrow_123',
                    'escrow_amount': 100.0,
                    'escrow_currency': 'USD'
                },
                'sale_timestamp': '2023-01-01T10:00:00Z'
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
        mock_input_tx.outputs[0].public_keys = ["seller_pub_key_123"]
        mock_input_tx.outputs[0].amount = "1"
        
        # Mock buy offer transaction
        mock_buy_offer_tx = Mock()
        mock_buy_offer_tx.operation = "BUY_OFFER"
        mock_buy_offer_tx.asset = {"id": "asset_123", "advertisement_id": "ad_789"}
        
        # Mock advertisement transaction
        mock_ad_tx = Mock()
        mock_ad_tx.operation = "ADVERTISEMENT"
        mock_ad_tx.metadata = {'status': 'OPEN', 'advertiser_public_key': 'seller_pub_key_123'}
        
        # Mock bigchain methods
        mock_bigchain.get_transaction.side_effect = lambda txid: {
            "input_tx_id": mock_input_tx,
            "buy_offer_456": mock_buy_offer_tx,
            "ad_789": mock_ad_tx
        }.get(txid)
        
        mock_bigchain.get_spent.return_value = None
        
        # Mock signature validation
        monkeypatch.setattr(tx, 'inputs_valid', lambda conditions: True)
        monkeypatch.setattr(tx, 'get_asset_id', lambda txs: "asset_123")
        
        # Test validation
        result = tx.validate_sell_inputs(mock_bigchain)
        assert result is True

    def test_sell_inputs_validation_wrong_input_count(self):
        """Test SELL inputs validation with wrong input count"""
        mock_bigchain = Mock()
        tx = Transaction(
            operation=Transaction.SELL,
            asset={"id": "asset_123", "buy_offer_id": "buy_offer_456"},
            inputs=[Mock(), Mock()],  # Two inputs instead of one
            metadata={}
        )
        
        with pytest.raises(ValueError, match="Sell transaction must have exactly one input"):
            tx.validate_sell_inputs(mock_bigchain)

    def test_sell_inputs_validation_buy_offer_not_found(self, monkeypatch):
        """Test SELL inputs validation when buy offer doesn't exist"""
        mock_bigchain = Mock()
        mock_bigchain.get_transaction.return_value = None
        
        tx = Transaction(
            operation=Transaction.SELL,
            asset={"id": "asset_123", "buy_offer_id": "buy_offer_456"},
            inputs=[Mock()],
            metadata={}
        )
        
        tx.inputs[0].fulfills = Mock()
        tx.inputs[0].fulfills.txid = "input_tx_id"
        tx.inputs[0].fulfills.output = 0
        
        with pytest.raises(ValueError, match="Referenced buy offer buy_offer_456 does not exist"):
            tx.validate_sell_inputs(mock_bigchain)

    def test_sell_inputs_validation_buy_offer_wrong_operation(self, monkeypatch):
        """Test SELL inputs validation when referenced transaction is not a buy offer"""
        mock_bigchain = Mock()
        
        # Mock transaction with wrong operation
        mock_wrong_tx = Mock()
        mock_wrong_tx.operation = "TRANSFER"  # Not BUY_OFFER
        
        mock_bigchain.get_transaction.side_effect = lambda txid: {
            "buy_offer_456": mock_wrong_tx
        }.get(txid)
        
        tx = Transaction(
            operation=Transaction.SELL,
            asset={"id": "asset_123", "buy_offer_id": "buy_offer_456"},
            inputs=[Mock()],
            metadata={}
        )
        
        tx.inputs[0].fulfills = Mock()
        tx.inputs[0].fulfills.txid = "input_tx_id"
        tx.inputs[0].fulfills.output = 0
        
        with pytest.raises(ValueError, match="Referenced transaction buy_offer_456 is not a buy offer"):
            tx.validate_sell_inputs(mock_bigchain)

    def test_sell_inputs_validation_asset_mismatch(self, monkeypatch):
        """Test SELL inputs validation when asset IDs don't match"""
        mock_bigchain = Mock()
        
        # Mock buy offer transaction with different asset ID
        mock_buy_offer_tx = Mock()
        mock_buy_offer_tx.operation = "BUY_OFFER"
        mock_buy_offer_tx.asset = {"id": "different_asset", "advertisement_id": "ad_789"}
        
        mock_bigchain.get_transaction.side_effect = lambda txid: {
            "buy_offer_456": mock_buy_offer_tx
        }.get(txid)
        
        tx = Transaction(
            operation=Transaction.SELL,
            asset={"id": "asset_123", "buy_offer_id": "buy_offer_456"},
            inputs=[Mock()],
            metadata={}
        )
        
        tx.inputs[0].fulfills = Mock()
        tx.inputs[0].fulfills.txid = "input_tx_id"
        tx.inputs[0].fulfills.output = 0
        
        with pytest.raises(ValueError, match="Buy offer targets different asset than sell transaction"):
            tx.validate_sell_inputs(mock_bigchain)

    def test_sell_inputs_validation_seller_not_advertiser(self, monkeypatch):
        """Test SELL inputs validation when seller is not the advertiser"""
        mock_bigchain = Mock()
        
        # Mock buy offer transaction
        mock_buy_offer_tx = Mock()
        mock_buy_offer_tx.operation = "BUY_OFFER"
        mock_buy_offer_tx.asset = {"id": "asset_123", "advertisement_id": "ad_789"}
        
        # Mock advertisement transaction with different advertiser
        mock_ad_tx = Mock()
        mock_ad_tx.operation = "ADVERTISEMENT"
        mock_ad_tx.metadata = {'status': 'OPEN', 'advertiser_public_key': 'different_advertiser'}
        
        mock_bigchain.get_transaction.side_effect = lambda txid: {
            "buy_offer_456": mock_buy_offer_tx,
            "ad_789": mock_ad_tx
        }.get(txid)
        
        tx = Transaction(
            operation=Transaction.SELL,
            asset={"id": "asset_123", "buy_offer_id": "buy_offer_456"},
            inputs=[Mock()],
            metadata={'seller_public_key': 'seller_pub_key_123'}
        )
        
        tx.inputs[0].fulfills = Mock()
        tx.inputs[0].fulfills.txid = "input_tx_id"
        tx.inputs[0].fulfills.output = 0
        
        with pytest.raises(ValueError, match="Seller must be the advertiser"):
            tx.validate_sell_inputs(mock_bigchain)

    def test_sell_inputs_validation_seller_not_owner(self, monkeypatch):
        """Test SELL inputs validation when seller is not the current owner"""
        mock_bigchain = Mock()
        
        # Mock buy offer transaction
        mock_buy_offer_tx = Mock()
        mock_buy_offer_tx.operation = "BUY_OFFER"
        mock_buy_offer_tx.asset = {"id": "asset_123", "advertisement_id": "ad_789"}
        
        # Mock advertisement transaction
        mock_ad_tx = Mock()
        mock_ad_tx.operation = "ADVERTISEMENT"
        mock_ad_tx.metadata = {'status': 'OPEN', 'advertiser_public_key': 'seller_pub_key_123'}
        
        # Mock input transaction with different owner
        mock_input_tx = Mock()
        mock_input_tx.id = "input_tx_id"
        mock_input_tx.outputs = [Mock()]
        mock_input_tx.outputs[0].public_keys = ["different_owner"]  # Different owner
        
        mock_bigchain.get_transaction.side_effect = lambda txid: {
            "input_tx_id": mock_input_tx,
            "buy_offer_456": mock_buy_offer_tx,
            "ad_789": mock_ad_tx
        }.get(txid)
        
        mock_bigchain.get_spent.return_value = None
        
        tx = Transaction(
            operation=Transaction.SELL,
            asset={"id": "asset_123", "buy_offer_id": "buy_offer_456"},
            inputs=[Mock()],
            metadata={'seller_public_key': 'seller_pub_key_123'}
        )
        
        tx.inputs[0].fulfills = Mock()
        tx.inputs[0].fulfills.txid = "input_tx_id"
        tx.inputs[0].fulfills.output = 0
        
        with pytest.raises(ValueError, match="Seller must be the current owner of the asset"):
            tx.validate_sell_inputs(mock_bigchain)

    def test_sell_inputs_validation_advertisement_locked(self, monkeypatch):
        """Test SELL inputs validation when advertisement is LOCKED"""
        mock_bigchain = Mock()
        
        # Mock buy offer transaction
        mock_buy_offer_tx = Mock()
        mock_buy_offer_tx.operation = "BUY_OFFER"
        mock_buy_offer_tx.asset = {"id": "asset_123", "advertisement_id": "ad_789"}
        
        # Mock advertisement transaction with LOCKED status
        mock_ad_tx = Mock()
        mock_ad_tx.operation = "ADVERTISEMENT"
        mock_ad_tx.metadata = {'status': 'LOCKED', 'advertiser_public_key': 'seller_pub_key_123'}
        
        mock_bigchain.get_transaction.side_effect = lambda txid: {
            "buy_offer_456": mock_buy_offer_tx,
            "ad_789": mock_ad_tx
        }.get(txid)
        
        tx = Transaction(
            operation=Transaction.SELL,
            asset={"id": "asset_123", "buy_offer_id": "buy_offer_456"},
            inputs=[Mock()],
            metadata={'seller_public_key': 'seller_pub_key_123'}
        )
        
        tx.inputs[0].fulfills = Mock()
        tx.inputs[0].fulfills.txid = "input_tx_id"
        tx.inputs[0].fulfills.output = 0
        
        with pytest.raises(ValueError, match="Cannot sell asset with advertisement status LOCKED"):
            tx.validate_sell_inputs(mock_bigchain)

    def test_sell_inputs_validation_missing_escrow_details(self, monkeypatch):
        """Test SELL inputs validation when escrow details are missing"""
        mock_bigchain = Mock()
        
        # Mock buy offer transaction
        mock_buy_offer_tx = Mock()
        mock_buy_offer_tx.operation = "BUY_OFFER"
        mock_buy_offer_tx.asset = {"id": "asset_123", "advertisement_id": "ad_789"}
        
        # Mock advertisement transaction
        mock_ad_tx = Mock()
        mock_ad_tx.operation = "ADVERTISEMENT"
        mock_ad_tx.metadata = {'status': 'OPEN', 'advertiser_public_key': 'seller_pub_key_123'}
        
        # Mock input transaction
        mock_input_tx = Mock()
        mock_input_tx.id = "input_tx_id"
        mock_input_tx.outputs = [Mock()]
        mock_input_tx.outputs[0].public_keys = ["seller_pub_key_123"]
        
        mock_bigchain.get_transaction.side_effect = lambda txid: {
            "input_tx_id": mock_input_tx,
            "buy_offer_456": mock_buy_offer_tx,
            "ad_789": mock_ad_tx
        }.get(txid)
        
        mock_bigchain.get_spent.return_value = None
        
        tx = Transaction(
            operation=Transaction.SELL,
            asset={"id": "asset_123", "buy_offer_id": "buy_offer_456"},
            inputs=[Mock()],
            metadata={
                'seller_public_key': 'seller_pub_key_123',
                'sale_amount': 100.0,
                'sale_currency': 'USD',
                'escrow_details': {},  # Empty escrow details
                'sale_timestamp': '2023-01-01T10:00:00Z'
            }
        )
        
        tx.inputs[0].fulfills = Mock()
        tx.inputs[0].fulfills.txid = "input_tx_id"
        tx.inputs[0].fulfills.output = 0
        
        with pytest.raises(ValueError, match="Sell transaction must include escrow details"):
            tx.validate_sell_inputs(mock_bigchain)
