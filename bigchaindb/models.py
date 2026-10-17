# Copyright © 2020 Interplanetary Database Association e.V.,
# BigchainDB and IPDB software contributors.
# SPDX-License-Identifier: (Apache-2.0 AND CC-BY-4.0)
# Code is Apache-2.0 and docs are CC-BY-4.0

from bigchaindb.backend.schema import validate_language_key
from bigchaindb.common.exceptions import InvalidSignature, DuplicateTransaction, ValidationError
from bigchaindb.common.schema import validate_transaction_schema
from bigchaindb.common.transaction import Transaction
from bigchaindb.common.utils import validate_txn_obj, validate_key
from bigchaindb.common.shacl_delta import compute_dep_state, ProjectionUnavailable
from bigchaindb.common.shacl_validator import get_shacl_validator
from bigchaindb.common.transaction_security import validate_ledger_authentication
from bigchaindb.common.ledger_state import LedgerStateView
import logging
import time

logger = logging.getLogger(__name__)


class Transaction(Transaction):
    ASSET = "asset"
    METADATA = "metadata"
    DATA = "data"

    def validate(self, bigchain, current_transactions=[]):
        """Validate a transaction.

        Direct (SHACL off): JSON envelope already checked at parse time, then
        native signature + marketplace state rules in this process.

        SHACL / SHACL+Δ (SHACL on): the microservice is authoritative for
        domain rules. Δ reuses a verdict when dependency *values* match.
        """
        duplicates = any(txn for txn in current_transactions if txn.id == self.id)
        if bigchain.is_committed(self.id) or duplicates:
            raise DuplicateTransaction(
                "transaction `{}` already exists".format(self.id)
            )

        bigchain = LedgerStateView(bigchain, current_transactions)
        # Always authenticate, including on a declarative-cache hit.
        try:
            validate_ledger_authentication(self, bigchain, current_transactions)
        except (TypeError, ValueError, AttributeError, IndexError) as exc:
            raise ValidationError("Invalid authentication or input structure: {}".format(exc))

        shacl_validator = get_shacl_validator()
        if not shacl_validator.enabled:
            t0 = time.perf_counter()
            try:
                return self._validate_direct(bigchain, current_transactions)
            finally:
                shacl_validator.record_timing("direct", (time.perf_counter() - t0) * 1000.0)
        
        logger.debug(f"Validating {self.operation} transaction {self.id} via SHACL")
        
        tx_dict = self.to_dict()
        t0 = time.perf_counter()
        # Until projections materialize the block overlay themselves, a
        # nonempty prefix is a conservative non-cacheable context. Full
        # validation still receives that prefix and enforces its effects.
        if current_transactions or not shacl_validator.cache_enabled:
            dep_hash, dep_ids, covered = None, [], None
        else:
            try:
                dep_hash, dep_ids, covered = compute_dep_state(bigchain, tx_dict)
            except ProjectionUnavailable:
                dep_hash, dep_ids, covered = None, [], None
        shacl_validator.record_timing("dep_fetch", (time.perf_counter() - t0) * 1000.0)
        conforms, results = shacl_validator.validate_transaction(
            tx_dict, dep_state_hash=dep_hash, dep_ids=dep_ids, covered_ids=covered,
            pending_transactions=[tx.to_dict() for tx in current_transactions],
            validation_time=getattr(bigchain, "_validation_time", None),
        )
        
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
                f"SHACL validation failed for {self.operation} transaction {self.id}: "
                f"{error_summary}"
            )
            
            # Log all errors in debug mode
            for i, result in enumerate(results, 1):
                logger.debug(f"  Error {i}: {result.get('message', 'Unknown')}")
                logger.debug(f"    Path: {result.get('path')}")
                logger.debug(f"    Severity: {result.get('severity')}")
            
            raise ValidationError(f"SHACL validation failed: {error_summary}")
        
        logger.info(f"✓ SHACL validation passed for {self.operation} transaction {self.id}")
        return self

    def _validate_direct(self, bigchain, current_transactions=[]):
        """Imperative baseline: signatures + existing marketplace state checks."""
        op = self.operation
        try:
            if op == self.TRANSFER:
                self.validate_transfer_inputs(bigchain, current_transactions)
            elif op == self.ADVERTISEMENT:
                self.validate_advertisement_inputs(bigchain, current_transactions)
            elif op == self.BUY_OFFER:
                self.validate_buy_offer_inputs(bigchain, current_transactions)
            elif op == self.SELL:
                self.validate_sell_inputs(bigchain, current_transactions)
                input_conditions = []
                for input_ in self.inputs:
                    if getattr(input_, "fulfills", None) is None:
                        continue
                    src = bigchain.get_transaction(input_.fulfills.txid)
                    if src is not None:
                        input_conditions.append(src.outputs[input_.fulfills.output])
                if input_conditions and not self.inputs_valid(input_conditions):
                    raise InvalidSignature("Transaction signature is invalid.")
            elif op == self.UPDATE_ADV:
                self._validate_update_adv_direct(bigchain)
            elif op == self.REQUEST_RETURN:
                self._validate_request_return_direct(bigchain)
            elif op == self.SELLER_ACCEPT_RETURN:
                self._validate_seller_accept_return_direct(bigchain)
            elif op == self.INTEREST:
                self.validate_interest(bigchain, current_transactions)
            elif op == self.REQUEST_FOR_QUOTE:
                self.validate_rfq(bigchain, current_transactions)
            elif op == self.BID:
                self.validate_bid(bigchain, current_transactions)
            elif op == self.ACCEPT:
                self.validate_accept(bigchain, current_transactions)
            elif op == self.RETURN:
                self.validate_return(bigchain, current_transactions)
            else:
                if not self.inputs_valid([], bigchain):
                    raise InvalidSignature("Transaction signature is invalid.")
        except (ValueError, TypeError) as exc:
            raise ValidationError(str(exc))
        logger.info("Direct validation passed for %s transaction %s", op, self.id)
        return self

    def _asset_parts(self):
        asset = self.asset or {}
        data = asset.get("data") if isinstance(asset.get("data"), dict) else {}
        return asset, data

    def _validate_update_adv_direct(self, bigchain):
        asset, data = self._asset_parts()
        adv_id = data.get("id") or asset.get("id")
        adv = bigchain.get_transaction(adv_id) if adv_id else None
        if adv is None:
            raise ValidationError("UPDATE_ADV advertisement does not exist")
        meta = self.metadata or {}
        updater = meta.get("updater_public_key")
        advertiser = (adv.metadata or {}).get("advertiser_public_key")
        if updater and advertiser and updater != advertiser:
            raise ValidationError("updater must be the advertiser")
        status = meta.get("status")
        if status and status not in ("OPEN", "LOCKED", "CLOSED"):
            raise ValidationError("advertisement status must be OPEN, LOCKED, or CLOSED")
        current = bigchain.get_effective_advertisement_status(adv_id)
        allowed = {"OPEN": ("OPEN", "LOCKED", "CLOSED"), "LOCKED": ("LOCKED", "CLOSED"), "CLOSED": ("CLOSED",)}
        if current not in allowed or status not in allowed[current]:
            raise ValidationError("Invalid advertisement status transition")

    def _validate_request_return_direct(self, bigchain):
        asset, data = self._asset_parts()
        sell_id = data.get("sell_transaction_id") or asset.get("sell_transaction_id")
        sell_tx = bigchain.get_transaction(sell_id) if sell_id else None
        if sell_tx is None:
            raise ValidationError("REQUEST_RETURN sell transaction does not exist")
        if getattr(sell_tx, "operation", None) != self.SELL:
            raise ValidationError("referenced transaction is not a SELL")
        requester = (self.metadata or {}).get("requester_public_key")
        buyer = (sell_tx.metadata or {}).get("buyer_public_key")
        if requester and buyer and requester != buyer:
            raise ValidationError("requester must be the buyer from the sell")
        if bigchain.referencing_transactions("REQUEST_RETURN", "asset.data.sell_transaction_id", sell_id):
            raise ValidationError("A return request already exists for the sale")

    def _validate_seller_accept_return_direct(self, bigchain):
        asset, data = self._asset_parts()
        req_id = data.get("request_return_id") or asset.get("request_return_id")
        req_tx = bigchain.get_transaction(req_id) if req_id else None
        if req_tx is None:
            raise ValidationError("SELLER_ACCEPT_RETURN request does not exist")
        if getattr(req_tx, "operation", None) != self.REQUEST_RETURN:
            raise ValidationError("referenced transaction is not a REQUEST_RETURN")
        req_asset = req_tx.asset or {}
        req_data = req_asset.get("data") if isinstance(req_asset.get("data"), dict) else {}
        sell_id = req_data.get("sell_transaction_id") or req_asset.get("sell_transaction_id")
        sell_tx = bigchain.get_transaction(sell_id) if sell_id else None
        acceptor = (self.metadata or {}).get("seller_public_key")
        seller = (getattr(sell_tx, "metadata", None) or {}).get("seller_public_key")
        if acceptor and seller and acceptor != seller:
            raise ValidationError("only the seller of the sale can accept the return")
        if bigchain.referencing_transactions("SELLER_ACCEPT_RETURN", "asset.data.request_return_id", req_id):
            raise ValidationError("A return acceptance already exists for the request")

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
