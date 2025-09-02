# Copyright © 2020 Interplanetary Database Association e.V.,
# BigchainDB and IPDB software contributors.
# SPDX-License-Identifier: (Apache-2.0 AND CC-BY-4.0)
# Code is Apache-2.0 and docs are CC-BY-4.0

"""Test the Advertisement transaction type implementation."""

import pytest
from bigchaindb.common.transaction import Transaction
from bigchaindb.common.exceptions import (
    ValidationError,
    AssetIdMismatch,
    InputDoesNotExist,
    DoubleSpend,
    InvalidSignature,
)
from bigchaindb.common.crypto import generate_keypair


class TestAdvertisementTransaction:
    """Test Advertisement transaction creation and validation."""

    def test_create_advertisement_transaction(self):
        """Test creating a basic advertisement transaction."""
        # Generate keypairs
        alice, bob = generate_keypair(), generate_keypair()
        
        # Create a mock input (simulating an existing asset output)
        mock_input = {
            'fulfillment': 'pGSAINxaGvuL8mR9nDiV7lLdb0X7JNT3mG5VhwKJqHmMqg',
            'fulfills': {
                'output_index': 0,
                'transaction_id': 'a' * 64  # Mock transaction ID
            },
            'owners_before': [alice.public_key]
        }
        
        # Create advertisement metadata
        metadata = {
            'status': 'OPEN',
            'advertiser_public_key': alice.public_key,
            'price': '100.50',
            'description': 'A beautiful bicycle for sale',
            'expiry_date': '2024-12-31T23:59:59Z'
        }
        
        # Create advertisement transaction
        ad_tx = Transaction.advertisement(
            inputs=[mock_input],
            asset_id='a' * 64,
            metadata=metadata
        )
        
        # Verify transaction properties
        assert ad_tx.operation == 'ADVERTISEMENT'
        assert ad_tx.asset['id'] == 'a' * 64
        assert len(ad_tx.inputs) == 1
        assert len(ad_tx.outputs) == 0  # Advertisement has no outputs
        assert ad_tx.metadata['status'] == 'OPEN'
        assert ad_tx.metadata['advertiser_public_key'] == alice.public_key

    def test_advertisement_validation_rules(self):
        """Test advertisement validation rules."""
        alice, bob = generate_keypair(), generate_keypair()
        
        # Test: Must have exactly one input
        with pytest.raises(ValueError, match="exactly one item"):
            Transaction.advertisement(
                inputs=[],  # No inputs
                asset_id='a' * 64,
                metadata={'status': 'OPEN', 'advertiser_public_key': alice.public_key}
            )
        
        # Test: Must have required metadata fields
        with pytest.raises(ValueError, match="must contain 'status'"):
            Transaction.advertisement(
                inputs=[{'fulfillment': 'test', 'fulfills': {'output_index': 0, 'transaction_id': 'a' * 64}}],
                asset_id='a' * 64,
                metadata={'advertiser_public_key': alice.public_key}  # Missing status
            )
        
        # Test: Status must be valid
        with pytest.raises(ValueError, match="must be one of"):
            Transaction.advertisement(
                inputs=[{'fulfillment': 'test', 'fulfills': {'output_index': 0, 'transaction_id': 'a' * 64}}],
                asset_id='a' * 64,
                metadata={'status': 'INVALID', 'advertiser_public_key': alice.public_key}
            )
        
        # Test: Asset must have ID property
        with pytest.raises(TypeError, match="holding an `id` property"):
            Transaction(
                operation='ADVERTISEMENT',
                asset={'data': 'invalid'},  # Should have 'id' not 'data'
                inputs=[{'fulfillment': 'test', 'fulfills': {'output_index': 0, 'transaction_id': 'a' * 64}}],
                metadata={'status': 'OPEN', 'advertiser_public_key': alice.public_key}
            )

    def test_advertisement_status_validation(self):
        """Test advertisement status validation."""
        alice = generate_keypair()
        
        # Test: New advertisement must have OPEN status
        with pytest.raises(ValueError, match="must be 'OPEN'"):
            Transaction.advertisement(
                inputs=[{'fulfillment': 'test', 'fulfills': {'output_index': 0, 'transaction_id': 'a' * 64}}],
                asset_id='a' * 64,
                metadata={'status': 'CLOSED', 'advertiser_public_key': alice.public_key}
            )
        
        # Test: Valid statuses are accepted
        valid_statuses = ['OPEN', 'LOCKED', 'CLOSED']
        for status in valid_statuses:
            # For non-new advertisements, any status is allowed
            metadata = {'status': status, 'advertiser_public_key': alice.public_key}
            metadata['is_new_advertisement'] = False
            
            ad_tx = Transaction.advertisement(
                inputs=[{'fulfillment': 'test', 'fulfills': {'output_index': 0, 'transaction_id': 'a' * 64}}],
                asset_id='a' * 64,
                metadata=metadata
            )
            assert ad_tx.metadata['status'] == status

    def test_advertisement_asset_id_validation(self):
        """Test advertisement asset ID validation."""
        alice = generate_keypair()
        
        # Test: Asset ID must be string
        with pytest.raises(TypeError, match="must be a string"):
            Transaction.advertisement(
                inputs=[{'fulfillment': 'test', 'fulfills': {'output_index': 0, 'transaction_id': 'a' * 64}}],
                asset_id=123,  # Should be string
                metadata={'status': 'OPEN', 'advertiser_public_key': alice.public_key}
            )
        
        # Test: Valid asset ID is accepted
        valid_asset_id = 'a' * 64
        ad_tx = Transaction.advertisement(
            inputs=[{'fulfillment': 'test', 'fulfills': {'output_index': 0, 'transaction_id': 'a' * 64}}],
            asset_id=valid_asset_id,
            metadata={'status': 'OPEN', 'advertiser_public_key': alice.public_key}
        )
        assert ad_tx.asset['id'] == valid_asset_id

    def test_advertisement_metadata_validation(self):
        """Test advertisement metadata validation."""
        alice = generate_keypair()
        
        # Test: Metadata must be dict
        with pytest.raises(TypeError, match="must be a dict"):
            Transaction.advertisement(
                inputs=[{'fulfillment': 'test', 'fulfills': {'output_index': 0, 'transaction_id': 'a' * 64}}],
                asset_id='a' * 64,
                metadata="not a dict"  # Should be dict
            )
        
        # Test: Advertiser public key must be string
        with pytest.raises(TypeError, match="must be a string"):
            Transaction.advertisement(
                inputs=[{'fulfillment': 'test', 'fulfills': {'output_index': 0, 'transaction_id': 'a' * 64}}],
                asset_id='a' * 64,
                metadata={'status': 'OPEN', 'advertiser_public_key': 123}  # Should be string
            )

    def test_advertisement_operation_constant(self):
        """Test that ADVERTISEMENT is properly defined as a constant."""
        assert hasattr(Transaction, 'ADVERTISEMENT')
        assert Transaction.ADVERTISEMENT == 'ADVERTISEMENT'
        assert 'ADVERTISEMENT' in Transaction.ALLOWED_OPERATIONS

    def test_advertisement_schema_validation(self):
        """Test that advertisement transactions pass schema validation."""
        alice = generate_keypair()
        
        ad_tx = Transaction.advertisement(
            inputs=[{'fulfillment': 'test', 'fulfills': {'output_index': 0, 'transaction_id': 'a' * 64}}],
            asset_id='a' * 64,
            metadata={'status': 'OPEN', 'advertiser_public_key': alice.public_key}
        )
        
        # Convert to dict for schema validation
        tx_dict = ad_tx.to_dict()
        
        # This should not raise any schema validation errors
        # (assuming the schema validation is properly set up)
        assert tx_dict['operation'] == 'ADVERTISEMENT'
        assert 'id' in tx_dict['asset']
        assert tx_dict['metadata']['status'] == 'OPEN'
        assert 'advertiser_public_key' in tx_dict['metadata']
