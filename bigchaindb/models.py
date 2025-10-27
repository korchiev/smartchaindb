# Copyright © 2020 Interplanetary Database Association e.V.,
# BigchainDB and IPDB software contributors.
# SPDX-License-Identifier: (Apache-2.0 AND CC-BY-4.0)
# Code is Apache-2.0 and docs are CC-BY-4.0

from bigchaindb.backend.schema import validate_language_key
from bigchaindb.common.exceptions import InvalidSignature, DuplicateTransaction, ValidationError
from bigchaindb.common.schema import validate_transaction_schema
from bigchaindb.common.transaction import Transaction
from bigchaindb.common.utils import validate_txn_obj, validate_key
from bigchaindb.common.shacl_validator_cached import get_shacl_validator
import logging
import traceback

logger = logging.getLogger(__name__)


class Transaction(Transaction):
    ASSET = "asset"
    METADATA = "metadata"
    DATA = "data"

    def validate(self, bigchain, current_transactions=[]):
        """
        Validate transaction using SHACL validation service with caching.
        
        All validation logic (syntactic, semantic, and state consistency)
        is now handled by the SHACL microservice using declarative constraints.
        Caching improves performance for the triple-validation pattern.
        
        Args:
            bigchain (BigchainDB): an instantiated bigchaindb.BigchainDB object.
            current_transactions: list of transactions in current block
            
        Returns:
            The transaction (Transaction) if valid
            
        Raises:
            ValidationError: If SHACL validation fails
            DuplicateTransaction: If transaction already exists
        """
        
        # ═══════════════════════════════════════════════════════════════
        # Detect which validation phase we're in by examining call stack
        # ═══════════════════════════════════════════════════════════════
        phase = 'UNKNOWN'
        stack = traceback.extract_stack()
        
        for frame in stack:
            if 'check_tx' in frame.filename or 'check_tx' in frame.name:
                phase = 'CHECK_TX'
                break
            elif 'deliver_tx' in frame.filename or 'deliver_tx' in frame.name:
                phase = 'DELIVER_TX'
                break
            elif 'transactions.py' in frame.filename:  # HTTP API
                phase = 'HTTP_POST'
                break
        
        # ═══════════════════════════════════════════════════════════════
        # Check for duplicates in current block or database
        # ═══════════════════════════════════════════════════════════════
        duplicates = any(txn for txn in current_transactions if txn.id == self.id)
        if bigchain.is_committed(self.id) or duplicates:
            raise DuplicateTransaction(
                "transaction `{}` already exists".format(self.id)
            )
        
        # ═══════════════════════════════════════════════════════════════
        # ENHANCED STATE-AWARE SHACL VALIDATION WITH ROBUST CACHING
        # Handles: syntactic, semantic, and state consistency across all phases
        # ═══════════════════════════════════════════════════════════════
        try:
            from bigchaindb.common.shacl_validator_state_aware_enhanced import shacl_validator
        except ImportError:
            # Fallback to original validator
            shacl_validator = get_shacl_validator(phase=phase)
        
        if not shacl_validator.enabled:
            raise ValidationError(
                "SHACL validation is disabled. "
                "Set BIGCHAINDB_SHACL_ENABLED=true to enable validation."
            )
        
        logger.debug(f"Validating {self.operation} transaction {self.id} via Enhanced SHACL (phase={phase})")
        
        # Use enhanced state-aware validation with phase support
        conforms, results = shacl_validator.validate_transaction(self.to_dict(), phase=phase)
        
        if not conforms:
            # Extract error messages from SHACL results
            error_messages = []
            for result in results:
                if isinstance(result.get('message'), list):
                    error_messages.extend(result['message'])
                else:
                    error_messages.append(str(result.get('message', 'Unknown error')))
            
            error_summary = '; '.join(error_messages[:5])  # Show first 5 errors
            
            logger.error(
                f"SHACL validation failed for {self.operation} transaction {self.id} "
                f"(phase={phase}): {error_summary}"
            )
            
            # Log all errors in debug mode
            for i, result in enumerate(results, 1):
                logger.debug(f"  Error {i}: {result.get('message', 'Unknown')}")
                logger.debug(f"    Path: {result.get('path')}")
                logger.debug(f"    Severity: {result.get('severity')}")
            
            raise ValidationError(f"SHACL validation failed: {error_summary}")
        
        logger.debug(f"✓ SHACL validation passed for {self.operation} transaction {self.id} (phase={phase})")
        
        return self

    @classmethod
    def from_dict(cls, tx_body):
        """Create transaction from dictionary (no validation during deserialization)"""
        return super().from_dict(tx_body, False)

    @classmethod
    def validate_schema(cls, tx_body):
        """
        Validate transaction schema.
        
        Note: This is called during transaction creation/parsing.
        The comprehensive validation happens in validate() method via SHACL.
        """
        validate_transaction_schema(tx_body)

    @classmethod
    def from_db(cls, bigchain, tx_dict):
        """Reconstruct transaction from database"""
        return cls.from_dict(tx_dict)
