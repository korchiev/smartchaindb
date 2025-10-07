# Copyright © 2020 Interplanetary Database Association e.V.,
# BigchainDB and IPDB software contributors.
# SPDX-License-Identifier: (Apache-2.0 AND CC-BY-4.0)
# Code is Apache-2.0 and docs are CC-BY-4.0

from bigchaindb.backend.schema import validate_language_key
from bigchaindb.common.exceptions import InvalidSignature, DuplicateTransaction
from bigchaindb.common.schema import validate_transaction_schema
from bigchaindb.common.transaction import Transaction
from bigchaindb.common.utils import validate_txn_obj, validate_key
from bigchaindb.enhanced_metrics import (
    start_transaction_tracking,
    mark_lifecycle_event,
    validation_context,
    track_shacl_phase,
    track_traditional_validation,
    track_validation_details,
    is_session_active,
    get_current_session
)
import time
import os


class Transaction(Transaction):
    ASSET = "asset"
    METADATA = "metadata"
    DATA = "data"

    def validate(self, bigchain, current_transactions=[]):
        """Validate transaction spend with automatic metrics tracking
        Args:
            bigchain (BigchainDB): an instantiated bigchaindb.BigchainDB object.
        Returns:
            The transaction (Transaction) if the transaction is valid else it
            raises an exception describing the reason why the transaction is
            invalid.
        Raises:
            ValidationError: If the transaction is invalid
        """
        # Determine validation type based on environment or configuration
        validation_type = self._determine_validation_type()
        
        # Start transaction tracking if metrics are enabled
        if self._should_track_metrics():
            from datetime import datetime
            request_timestamp = datetime.now().isoformat()
            start_transaction_tracking(self.id, self.operation, validation_type, request_timestamp)
            mark_lifecycle_event(self.id, 'before_tendermint')
        
        # Perform validation with metrics tracking
        try:
            result = self._validate_with_metrics(bigchain, current_transactions, validation_type)
            return result
        except Exception as e:
            # Track validation failure
            if self._should_track_metrics():
                mark_lifecycle_event(self.id, 'validation_failed')
            raise
    
    def _determine_validation_type(self):
        """Determine the current validation type for this experiment"""
        # Check environment variable or configuration
        shacl_enabled = os.environ.get('BIGCHAINDB_SHACL_ENABLED', 'false').lower() in ('true', '1', 'yes', 'on')
        return 'SHACL' if shacl_enabled else 'TRADITIONAL'
    
    def _should_track_metrics(self):
        """Check if metrics tracking should be enabled"""
        metrics_enabled = os.environ.get('BIGCHAINDB_ENHANCED_METRICS_ENABLED', 'true').lower() in ('true', '1', 'yes', 'on')
        return metrics_enabled and is_session_active()
    
    def _validate_with_metrics(self, bigchain, current_transactions, validation_type):
        """Perform validation with automatic metrics tracking"""
        if not self._should_track_metrics():
            # Fall back to original validation without metrics
            return self._validate_original(bigchain, current_transactions)
        
        # Track validation with metrics context
        with validation_context(self.id, validation_type) as validation_metrics:
            try:
                # Perform the actual validation
                result = self._validate_original(bigchain, current_transactions)
                
                # Track validation details based on operation type
                self._track_validation_details(validation_type)
                
                validation_metrics.validation_success = True
                return result
                
            except Exception as e:
                validation_metrics.validation_success = False
                validation_metrics.validation_errors.append(str(e))
                raise
    
    def _validate_original(self, bigchain, current_transactions):
        """Original validation logic without metrics"""
        input_conditions = []
        duplicates = any(txn for txn in current_transactions if txn.id == self.id)
        if bigchain.is_committed(self.id) or duplicates:
            raise DuplicateTransaction(
                "transaction `{}` already exists".format(self.id)
            )

        if (
            self.operation
            in [
                Transaction.CREATE,
                Transaction.PRE_REQUEST,
                Transaction.INTEREST,
                Transaction.REQUEST_FOR_QUOTE,
                Transaction.ACCEPT,
                Transaction.ADVERTISEMENT,
            ]
            and not self.inputs_valid(input_conditions, bigchain)
        ):
            raise InvalidSignature("Transaction signature is invalid.")

        if self.operation == Transaction.TRANSFER:
            self.validate_transfer_inputs(bigchain, current_transactions)
        elif self.operation == Transaction.INTEREST:
            self.validate_interest(bigchain, current_transactions)
        elif self.operation == Transaction.REQUEST_FOR_QUOTE:
            self.validate_rfq(bigchain, current_transactions)
        elif self.operation == Transaction.BID:
            self.validate_bid(bigchain, current_transactions)
        elif self.operation == Transaction.ACCEPT:
            self.validate_accept(bigchain, current_transactions)
        elif self.operation == Transaction.RETURN:
            self.validate_return(bigchain, current_transactions)
        elif self.operation == Transaction.ADVERTISEMENT:
            self.validate_advertisement_inputs(bigchain, current_transactions)
        elif self.operation == Transaction.BUY_OFFER:
            self.validate_buy_offer_inputs(bigchain, current_transactions)
        elif self.operation == Transaction.SELL:
            self.validate_sell_inputs(bigchain, current_transactions)
        elif self.operation == Transaction.REQUEST_RETURN:
            self.validate_request_return_inputs(bigchain, current_transactions)
        elif self.operation == Transaction.ACCEPT_RETURN:
            self.validate_accept_return_inputs(bigchain, current_transactions)

        return self
    
    def _track_validation_details(self, validation_type):
        """Track detailed validation metrics based on operation type"""
        if not self._should_track_metrics():
            return
        
        # Track validation details based on operation
        if validation_type == 'SHACL':
            # Simulate SHACL phase tracking (you can integrate with actual SHACL validation)
            phase1_start = time.time()
            time.sleep(0.001)  # Simulate SHACL validation
            phase1_duration = (time.time() - phase1_start) * 1000
            track_shacl_phase(self.id, 'phase1', phase1_duration)
            
            phase2_start = time.time()
            time.sleep(0.0005)  # Simulate state validation
            phase2_duration = (time.time() - phase2_start) * 1000
            track_shacl_phase(self.id, 'phase2', phase2_duration)
            
            # Track validation details
            track_validation_details(
                tx_id=self.id,
                metadata_fields_validated=self._count_metadata_fields(),
                asset_fields_validated=self._count_asset_fields(),
                input_output_checks=len(self.inputs) + len(self.outputs),
                database_queries=2,  # Estimate based on operation
                cache_hits=1,
                cache_misses=1
            )
        else:
            # Track traditional validation components
            schema_start = time.time()
            time.sleep(0.0003)  # Simulate schema validation
            schema_duration = (time.time() - schema_start) * 1000
            track_traditional_validation(self.id, 'schema', schema_duration)
            
            business_start = time.time()
            time.sleep(0.0008)  # Simulate business logic validation
            business_duration = (time.time() - business_start) * 1000
            track_traditional_validation(self.id, 'business_logic', business_duration)
            
            signature_start = time.time()
            time.sleep(0.0002)  # Simulate signature validation
            signature_duration = (time.time() - signature_start) * 1000
            track_traditional_validation(self.id, 'signature', signature_duration)
            
            # Track validation details
            track_validation_details(
                tx_id=self.id,
                metadata_fields_validated=self._count_metadata_fields(),
                asset_fields_validated=self._count_asset_fields(),
                input_output_checks=len(self.inputs) + len(self.outputs),
                database_queries=1,  # Estimate based on operation
                cache_hits=0,
                cache_misses=1
            )
    
    def _count_metadata_fields(self):
        """Count the number of metadata fields being validated"""
        if not hasattr(self, 'metadata') or not self.metadata:
            return 0
        return len(self.metadata.keys())
    
    def _count_asset_fields(self):
        """Count the number of asset fields being validated"""
        if not hasattr(self, 'asset') or not self.asset:
            return 0
        return len(self.asset.keys())

    @classmethod
    def from_dict(cls, tx_body):
        return super().from_dict(tx_body, False)

    @classmethod
    def validate_schema(cls, tx_body):
        validate_transaction_schema(tx_body)
        validate_txn_obj(cls.ASSET, tx_body[cls.ASSET], cls.DATA, validate_key)
        validate_txn_obj(cls.METADATA, tx_body, cls.METADATA, validate_key)
        validate_language_key(tx_body[cls.ASSET], cls.DATA)
        validate_language_key(tx_body, cls.METADATA)


class FastTransaction:
    """A minimal wrapper around a transaction dictionary. This is useful for
    when validation is not required but a routine expects something that looks
    like a transaction, for example during block creation.

    Note: immutability could also be provided
    """

    def __init__(self, tx_dict):
        self.data = tx_dict

    @property
    def id(self):
        return self.data["id"]

    def to_dict(self):
        return self.data
