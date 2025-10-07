# Copyright © 2020 Interplanetary Database Association e.V.,
# BigchainDB and IPDB software contributors.
# SPDX-License-Identifier: (Apache-2.0 AND CC-BY-4.0)
# Code is Apache-2.0 and docs are CC-BY-4.0

"""This module provides the blueprint for some basic API endpoints.

For more information please refer to the documentation: http://bigchaindb.com/http-api
"""
import logging

from flask import current_app, request, jsonify
from flask_restful import Resource, reqparse

from bigchaindb.common.transaction_mode_types import (
    BROADCAST_TX_ASYNC,
    BROADCAST_TX_SYNC,
    BROADCAST_TX_COMMIT,
)
from bigchaindb.common.exceptions import SchemaValidationError, ValidationError
from bigchaindb.web.views.base import make_error, validate_schema_definition
from bigchaindb.web.views import parameters
from bigchaindb.models import Transaction
from bigchaindb.utils import log_metric
from bigchaindb.enhanced_metrics import (
    start_experiment_session,
    end_experiment_session,
    mark_lifecycle_event,
    is_session_active,
    get_current_session,
    save_current_results
)
import os
import time


logger = logging.getLogger(__name__)
recovery_logger = logging.getLogger("recovery")


def _ensure_experiment_session():
    """Ensure an experiment session is started for automatic metrics tracking"""
    if not is_session_active():
        # Auto-start session with current validation type only
        experiment_name = os.environ.get('BIGCHAINDB_EXPERIMENT_NAME', 'Auto_Experiment')
        
        # Determine current validation type
        shacl_enabled = os.environ.get('BIGCHAINDB_SHACL_ENABLED', 'false').lower() in ('true', '1', 'yes', 'on')
        current_validation_type = 'SHACL' if shacl_enabled else 'TRADITIONAL'
        
        # Only track the current validation type
        validation_types = [current_validation_type]
        operations_tested = ['CREATE', 'TRANSFER', 'BUY_OFFER', 'SELL', 'REQUEST_RETURN', 'ACCEPT_RETURN']
        
        configuration = {
            'auto_started': True,
            'shacl_enabled': shacl_enabled,
            'metrics_enabled': os.environ.get('BIGCHAINDB_ENHANCED_METRICS_ENABLED', 'true').lower() in ('true', '1', 'yes', 'on'),
            'validation_type': current_validation_type,
            'single_experiment': True
        }
        
        notes = f"Automatically started {current_validation_type} validation experiment session for external driver requests"
        
        session_id = start_experiment_session(
            experiment_name=experiment_name,
            validation_types=validation_types,
            operations_tested=operations_tested,
            configuration=configuration,
            notes=notes
        )
        
        logger.info(f"Auto-started {current_validation_type} experiment session: {session_id}")


def _auto_save_results_if_needed():
    """Auto-save results periodically or when certain conditions are met"""
    if not is_session_active():
        return
    
    session = get_current_session()
    if not session:
        return
    
    # Save checkpoint every 100 transactions
    checkpoint_interval = int(os.environ.get('BIGCHAINDB_METRICS_CHECKPOINT_INTERVAL', '100'))
    if session.total_transactions > 0 and session.total_transactions % checkpoint_interval == 0:
        checkpoint_name = f"auto_checkpoint_{session.total_transactions}"
        save_current_results(checkpoint_name)
        logger.info(f"Auto-saved checkpoint: {checkpoint_name}")


logger = logging.getLogger(__name__)
recovery_logger = logging.getLogger("recovery")


class TransactionApi(Resource):
    def get(self, tx_id):
        """API endpoint to get details about a transaction.

        Args:
            tx_id (str): the id of the transaction.

        Return:
            A JSON string containing the data about the transaction.
        """
        pool = current_app.config["bigchain_pool"]

        with pool() as bigchain:
            tx = bigchain.get_transaction(tx_id)

        if not tx:
            return make_error(404)

        return tx.to_dict()


class TransactionValidateApi(Resource):
    def get(self):
        return dict()

    def post(self):
        """API endpoint to validate transaction.

        Return:
            A ``dict`` containing the data about the transaction.
        """
        pool = current_app.config["bigchain_pool"]

        error, tx, tx_obj = validate_schema_definition(request)

        if error is not None:
            return error

        with pool() as bigchain:
            try:
                bigchain.validate_transaction(tx_obj)
            except ValidationError as e:
                return make_error(
                    400, "Invalid transaction ({}): {}".format(type(e).__name__, e)
                )

        response = jsonify(tx)
        response.status_code = 202
        return response


class TransactionListApi(Resource):
    def get(self):
        parser = reqparse.RequestParser()
        parser.add_argument("operation", type=parameters.valid_operation)
        parser.add_argument("asset_id", type=parameters.valid_txid, required=True)
        parser.add_argument("last_tx", type=parameters.valid_bool, required=False)
        args = parser.parse_args()
        with current_app.config["bigchain_pool"]() as bigchain:
            txs = bigchain.get_transactions_filtered(**args)
        return [tx.to_dict() for tx in txs]

    def post(self):
        """API endpoint to push transactions to the Federation with automatic metrics tracking.

        Return:
            A ``dict`` containing the data about the transaction.
        """
        # Auto-start experiment session if not already started
        _ensure_experiment_session()
        
        parser = reqparse.RequestParser()
        parser.add_argument(
            "mode", type=parameters.valid_mode, default=BROADCAST_TX_ASYNC
        )
        args = parser.parse_args()
        mode = str(args["mode"])
        pool = current_app.config["bigchain_pool"]
        tx = request.get_json(force=True)

        log_metric(
            "received_tx",
            tx["metadata"]["requestCreationTimestamp"],
            tx["operation"],
            tx["id"],
            None
        )

        error, tx, tx_obj = validate_schema_definition(tx)
        if error is not None:
            return error
        if tx_obj.operation == Transaction.RETURN:
            return make_error(
                400, "Invalid transaction type ({})".format(tx_obj.operation)
            )

        with pool() as bigchain:
            try:
                bigchain.validate_transaction(tx_obj)
            except ValidationError as e:
                return make_error(
                    400, "Invalid transaction ({}): {}".format(type(e).__name__, e)
                )
            else:
                log_metric(
                    "before_tendermint",
                    tx_obj.metadata["requestCreationTimestamp"],
                    tx_obj.operation,
                    tx_obj._id,
                    None
                )
                
                # Track lifecycle events for metrics
                if is_session_active():
                    mark_lifecycle_event(tx_obj.id, 'check_tx')
                
                status_code, message = bigchain.write_transaction(tx_obj, mode)
                
                # Track additional lifecycle events
                if is_session_active():
                    if status_code == 202:
                        mark_lifecycle_event(tx_obj.id, 'deliver_tx')
                        mark_lifecycle_event(tx_obj.id, 'end_block')
                        mark_lifecycle_event(tx_obj.id, 'commit')
                    else:
                        mark_lifecycle_event(tx_obj.id, 'transaction_failed')
                    
                    # Auto-save results if needed
                    _auto_save_results_if_needed()

        if status_code == 202:
            response = jsonify(tx)
            response.status_code = 202
            return response
        else:
            return make_error(status_code, message)


class BidsForRFQTransactionApi(Resource):
    def get(self, tx_id):
        """API endpoint to get all bids raised against a RFQ transaction.

        Args:
            tx_id (str): the id of the RFQ transaction.

        Return:
            A JSON string containing the data about the Bid transactions.
        """
        pool = current_app.config["bigchain_pool"]

        with pool() as bigchain:
            txs = bigchain.get_locked_bid_txids_for_rfq(tx_id)

        return txs
