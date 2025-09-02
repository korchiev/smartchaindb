# Copyright © 2020 Interplanetary Database Association e.V.,
# BigchainDB and IPDB software contributors.
# SPDX-License-Identifier: (Apache-2.0 AND CC-BY-4.0)
# Code is Apache-2.0 and docs are CC-BY-4.0

"""Test BuyOffer transaction type"""

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


class TestBuyOffer:
    """Test the BuyOffer transaction type"""

    def test_buy_offer_creation(self):
        """Test creating a BuyOffer transaction"""
        # Create test inputs
        inputs = [Mock()]
        inputs[0].fulfills = Mock()
        inputs[0].fulfills.txid = "test_tx_id"
        inputs[0].fulfills.output = 0
        
        # Create test metadata
        metadata = {
            'buyer_public_key': 'buyer_pub_key_123',
            'offer_amount': 100.0,
            'offer_currency': 'USD',
            'funds_evidence': 'bank_statement_123',
            'offer_timestamp': '2023-01-01T10:00:00Z',
            'offer_expiry': '2023-01-31T10:00:00Z'
        }
        
        # Create transaction
        tx = Transaction.buy_offer(
            inputs=inputs,
            asset_id="asset_123",
            advertisement_id="ad_456",
            metadata=metadata
        )
        
        assert tx.operation == Transaction.BUY_OFFER
        assert tx.asset['id'] == "asset_123"
        assert tx.asset['advertisement_id'] == "ad_456"
        assert tx.metadata == metadata
        assert len(tx.inputs) == 1
        assert len(tx.outputs) == 0

    def test_buy_offer_validation_success(self):
        """Test successful BuyOffer validation"""
        # Create test inputs
        inputs = [Mock()]
        inputs[0].fulfills = Mock()
        inputs[0].fulfills.txid = "test_tx_id"
        inputs[0].fulfills.output = 0
        
        # Create test metadata
        metadata = {
            'buyer_public_key': 'buyer_pub_key_123',
            'offer_amount': 100.0,
            'offer_currency': 'USD',
            'funds_evidence': 'bank_statement_123',
            'offer_timestamp': '2023-01-01T10:00:00Z',
            'offer_expiry': '2023-01-31T10:00:00Z'
        }
        
        # Test validation
        validated_inputs, validated_outputs = Transaction.validate_buy_offer(
            inputs, "asset_123", "ad_456", metadata
        )
        
        assert validated_inputs == inputs
        assert validated_outputs == []

    def test_buy_offer_validation_invalid_inputs(self):
        """Test BuyOffer validation with invalid inputs"""
        # Test with non-list inputs
        with pytest.raises(TypeError, match="`inputs` must be a list instance"):
            Transaction.validate_buy_offer("not_a_list", "asset_123", "ad_456", {})
        
        # Test with wrong number of inputs
        inputs = [Mock(), Mock()]  # Two inputs instead of one
        with pytest.raises(ValueError, match="`inputs` must contain exactly one item"):
            Transaction.validate_buy_offer(inputs, "asset_123", "ad_456", {})

    def test_buy_offer_validation_invalid_metadata(self):
        """Test BuyOffer validation with invalid metadata"""
        inputs = [Mock()]
        
        # Test with non-dict metadata
        with pytest.raises(TypeError, match="`metadata` must be a dict"):
            Transaction.validate_buy_offer(inputs, "asset_123", "ad_456", "not_a_dict")
        
        # Test with missing required fields
        incomplete_metadata = {
            'buyer_public_key': 'buyer_pub_key_123',
            'offer_amount': 100.0
            # Missing other required fields
        }
        
        with pytest.raises(ValueError, match="`metadata` must contain 'offer_currency' field"):
            Transaction.validate_buy_offer(inputs, "asset_123", "ad_456", incomplete_metadata)

    def test_buy_offer_validation_invalid_amount(self):
        """Test BuyOffer validation with invalid amount"""
        inputs = [Mock()]
        metadata = {
            'buyer_public_key': 'buyer_pub_key_123',
            'offer_amount': -100.0,  # Negative amount
            'offer_currency': 'USD',
            'funds_evidence': 'bank_statement_123',
            'offer_timestamp': '2023-01-01T10:00:00Z',
            'offer_expiry': '2023-01-31T10:00:00Z'
        }
        
        with pytest.raises(ValueError, match="`offer_amount` must be a positive number"):
            Transaction.validate_buy_offer(inputs, "asset_123", "ad_456", metadata)

    def test_buy_offer_validation_invalid_currency(self):
        """Test BuyOffer validation with invalid currency"""
        inputs = [Mock()]
        metadata = {
            'buyer_public_key': 'buyer_pub_key_123',
            'offer_amount': 100.0,
            'offer_currency': '',  # Empty currency
            'funds_evidence': 'bank_statement_123',
            'offer_timestamp': '2023-01-01T10:00:00Z',
            'offer_expiry': '2023-01-31T10:00:00Z'
        }
        
        with pytest.raises(ValueError, match="`offer_currency` must be a non-empty string"):
            Transaction.validate_buy_offer(inputs, "asset_123", "ad_456", metadata)

    def test_buy_offer_inputs_validation_success(self, monkeypatch):
        """Test successful BuyOffer inputs validation"""
        # Create mock bigchain
        mock_bigchain = Mock()
        
        # Create test transaction
        tx = Transaction(
            operation=Transaction.BUY_OFFER,
            asset={"id": "asset_123", "advertisement_id": "ad_456"},
            inputs=[Mock()],
            metadata={
                'buyer_public_key': 'buyer_pub_key_123',
                'offer_amount': 100.0,
                'offer_currency': 'USD',
                'funds_evidence': 'bank_statement_123',
                'offer_timestamp': '2023-01-01T10:00:00Z',
                'offer_expiry': (datetime.utcnow() + timedelta(days=30)).isoformat() + 'Z'
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
        mock_input_tx.outputs[0].public_keys = ["owner_pub_key"]
        mock_input_tx.outputs[0].amount = "1"
        
        # Mock advertisement transaction
        mock_ad_tx = Mock()
        mock_ad_tx.operation = "ADVERTISEMENT"
        mock_ad_tx.metadata = {'status': 'OPEN', 'advertiser_public_key': 'advertiser_pub_key'}
        
        # Mock bigchain methods
        mock_bigchain.get_transaction.side_effect = lambda txid: {
            "input_tx_id": mock_input_tx,
            "ad_456": mock_ad_tx
        }.get(txid)
        
        mock_bigchain.get_spent.return_value = None
        
        # Mock signature validation
        monkeypatch.setattr(tx, 'inputs_valid', lambda conditions: True)
        monkeypatch.setattr(tx, 'get_asset_id', lambda txs: "asset_123")
        
        # Test validation
        result = tx.validate_buy_offer_inputs(mock_bigchain)
        assert result is True

    def test_buy_offer_inputs_validation_wrong_input_count(self):
        """Test BuyOffer inputs validation with wrong input count"""
        mock_bigchain = Mock()
        tx = Transaction(
            operation=Transaction.BUY_OFFER,
            asset={"id": "asset_123", "advertisement_id": "ad_456"},
            inputs=[Mock(), Mock()],  # Two inputs instead of one
            metadata={}
        )
        
        with pytest.raises(ValueError, match="Buy offer must have exactly one input"):
            tx.validate_buy_offer_inputs(mock_bigchain)

    def test_buy_offer_inputs_validation_advertisement_not_found(self, monkeypatch):
        """Test BuyOffer inputs validation when advertisement doesn't exist"""
        mock_bigchain = Mock()
        mock_bigchain.get_transaction.return_value = None
        
        tx = Transaction(
            operation=Transaction.BUY_OFFER,
            asset={"id": "asset_123", "advertisement_id": "ad_456"},
            inputs=[Mock()],
            metadata={}
        )
        
        tx.inputs[0].fulfills = Mock()
        tx.inputs[0].fulfills.txid = "input_tx_id"
        tx.inputs[0].fulfills.output = 0
        
        with pytest.raises(ValueError, match="Referenced advertisement ad_456 does not exist"):
            tx.validate_buy_offer_inputs(mock_bigchain)

    def test_buy_offer_inputs_validation_advertisement_not_open(self, monkeypatch):
        """Test BuyOffer inputs validation when advertisement is not OPEN"""
        mock_bigchain = Mock()
        
        # Mock advertisement transaction with CLOSED status
        mock_ad_tx = Mock()
        mock_ad_tx.operation = "ADVERTISEMENT"
        mock_ad_tx.metadata = {'status': 'CLOSED', 'advertiser_public_key': 'advertiser_pub_key'}
        
        mock_bigchain.get_transaction.side_effect = lambda txid: {
            "ad_456": mock_ad_tx
        }.get(txid)
        
        tx = Transaction(
            operation=Transaction.BUY_OFFER,
            asset={"id": "asset_123", "advertisement_id": "ad_456"},
            inputs=[Mock()],
            metadata={}
        )
        
        tx.inputs[0].fulfills = Mock()
        tx.inputs[0].fulfills.txid = "input_tx_id"
        tx.inputs[0].fulfills.output = 0
        
        with pytest.raises(ValueError, match="Referenced advertisement ad_456 is not OPEN"):
            tx.validate_buy_offer_inputs(mock_bigchain)

    def test_buy_offer_inputs_validation_buyer_equals_advertiser(self, monkeypatch):
        """Test BuyOffer inputs validation when buyer equals advertiser"""
        mock_bigchain = Mock()
        
        # Mock advertisement transaction
        mock_ad_tx = Mock()
        mock_ad_tx.operation = "ADVERTISEMENT"
        mock_ad_tx.metadata = {'status': 'OPEN', 'advertiser_public_key': 'same_pub_key'}
        
        mock_bigchain.get_transaction.side_effect = lambda txid: {
            "ad_456": mock_ad_tx
        }.get(txid)
        
        tx = Transaction(
            operation=Transaction.BUY_OFFER,
            asset={"id": "asset_123", "advertisement_id": "ad_456"},
            inputs=[Mock()],
            metadata={'buyer_public_key': 'same_pub_key'}  # Same as advertiser
        )
        
        tx.inputs[0].fulfills = Mock()
        tx.inputs[0].fulfills.txid = "input_tx_id"
        tx.inputs[0].fulfills.output = 0
        
        with pytest.raises(ValueError, match="Buyer cannot be the same as advertiser"):
            tx.validate_buy_offer_inputs(mock_bigchain)

    def test_buy_offer_inputs_validation_expired_offer(self, monkeypatch):
        """Test BuyOffer inputs validation when offer has expired"""
        mock_bigchain = Mock()
        
        # Mock advertisement transaction
        mock_ad_tx = Mock()
        mock_ad_tx.operation = "ADVERTISEMENT"
        mock_ad_tx.metadata = {'status': 'OPEN', 'advertiser_public_key': 'advertiser_pub_key'}
        
        mock_bigchain.get_transaction.side_effect = lambda txid: {
            "ad_456": mock_ad_tx
        }.get(txid)
        
        # Create expired offer
        expired_time = (datetime.utcnow() - timedelta(days=1)).isoformat() + 'Z'
        
        tx = Transaction(
            operation=Transaction.BUY_OFFER,
            asset={"id": "asset_123", "advertisement_id": "ad_456"},
            inputs=[Mock()],
            metadata={
                'buyer_public_key': 'buyer_pub_key',
                'offer_amount': 100.0,
                'offer_currency': 'USD',
                'funds_evidence': 'bank_statement_123',
                'offer_timestamp': '2023-01-01T10:00:00Z',
                'offer_expiry': expired_time
            }
        )
        
        tx.inputs[0].fulfills = Mock()
        tx.inputs[0].fulfills.txid = "input_tx_id"
        tx.inputs[0].fulfills.output = 0
        
        with pytest.raises(ValueError, match="Offer has expired"):
            tx.validate_buy_offer_inputs(mock_bigchain)

    def test_buy_offer_inputs_validation_missing_funds_evidence(self, monkeypatch):
        """Test BuyOffer inputs validation when funds evidence is missing"""
        mock_bigchain = Mock()
        
        # Mock advertisement transaction
        mock_ad_tx = Mock()
        mock_ad_tx.operation = "ADVERTISEMENT"
        mock_ad_tx.metadata = {'status': 'OPEN', 'advertiser_public_key': 'advertiser_pub_key'}
        
        mock_bigchain.get_transaction.side_effect = lambda txid: {
            "ad_456": mock_ad_tx
        }.get(txid)
        
        tx = Transaction(
            operation=Transaction.BUY_OFFER,
            asset={"id": "asset_123", "advertisement_id": "ad_456"},
            inputs=[Mock()],
            metadata={
                'buyer_public_key': 'buyer_pub_key',
                'offer_amount': 100.0,
                'offer_currency': 'USD',
                'funds_evidence': '',  # Empty funds evidence
                'offer_timestamp': '2023-01-01T10:00:00Z',
                'offer_expiry': (datetime.utcnow() + timedelta(days=30)).isoformat() + 'Z'
            }
        )
        
        tx.inputs[0].fulfills = Mock()
        tx.inputs[0].fulfills.txid = "input_tx_id"
        tx.inputs[0].fulfills.output = 0
        
        with pytest.raises(ValueError, match="Buy offer must include evidence of sufficient funds"):
            tx.validate_buy_offer_inputs(mock_bigchain)
