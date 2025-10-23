"""
Event-Driven Cache Invalidation System for Blockchain State Changes

This module provides event listeners and handlers that automatically invalidate
cache entries when blockchain state changes that affect validation results.
"""

import logging
import time
from typing import Dict, Any, List, Callable, Optional
from threading import Lock, Thread
from collections import defaultdict
from bigchaindb.common.shacl_validator_state_aware import get_state_aware_shacl_validator

logger = logging.getLogger(__name__)


class StateChangeEvent:
    """
    Represents a blockchain state change event.
    """
    
    def __init__(self, event_type: str, entity_id: str, entity_type: str, 
                 old_state: Dict[str, Any] = None, new_state: Dict[str, Any] = None):
        self.event_type = event_type  # 'CREATE', 'UPDATE', 'DELETE'
        self.entity_id = entity_id
        self.entity_type = entity_type  # 'advertisement', 'buy_offer', 'asset', 'transaction'
        self.old_state = old_state or {}
        self.new_state = new_state or {}
        self.timestamp = time.time()
    
    def __repr__(self):
        return f"StateChangeEvent({self.event_type}, {self.entity_type}:{self.entity_id})"


class CacheInvalidationHandler:
    """
    Handles cache invalidation based on state change events.
    """
    
    def __init__(self):
        self.validator = get_state_aware_shacl_validator()
        self.logger = logging.getLogger(__name__ + '.invalidation')
    
    def handle_event(self, event: StateChangeEvent):
        """
        Handle a state change event and invalidate relevant cache entries.
        """
        self.logger.info(f"Processing state change event: {event}")
        
        try:
            if event.entity_type == 'advertisement':
                self._handle_advertisement_change(event)
            elif event.entity_type == 'buy_offer':
                self._handle_buy_offer_change(event)
            elif event.entity_type == 'asset':
                self._handle_asset_change(event)
            elif event.entity_type == 'transaction':
                self._handle_transaction_change(event)
            elif event.entity_type == 'return_request':
                self._handle_return_request_change(event)
            elif event.entity_type == 'accept_return':
                self._handle_accept_return_change(event)
            else:
                self.logger.warning(f"Unknown entity type: {event.entity_type}")
        
        except Exception as e:
            self.logger.error(f"Error handling state change event: {e}", exc_info=True)
    
    def _handle_advertisement_change(self, event: StateChangeEvent):
        """
        Handle advertisement state changes.
        """
        ad_id = event.entity_id
        
        if event.event_type == 'UPDATE':
            old_status = event.old_state.get('status')
            new_status = event.new_state.get('status')
            
            # If status changed from OPEN to CLOSED, invalidate dependent cache entries
            if old_status == 'OPEN' and new_status == 'CLOSED':
                self.logger.info(f"Advertisement {ad_id} closed - invalidating dependent cache entries")
                self.validator.invalidate_advertisement_cache(ad_id)
            
            # If expiry changed, invalidate cache entries
            old_expiry = event.old_state.get('expiry')
            new_expiry = event.new_state.get('expiry')
            if old_expiry != new_expiry:
                self.logger.info(f"Advertisement {ad_id} expiry changed - invalidating cache")
                self.validator.invalidate_advertisement_cache(ad_id)
        
        elif event.event_type == 'DELETE':
            self.logger.info(f"Advertisement {ad_id} deleted - invalidating dependent cache entries")
            self.validator.invalidate_advertisement_cache(ad_id)
    
    def _handle_buy_offer_change(self, event: StateChangeEvent):
        """
        Handle buy offer state changes.
        """
        offer_id = event.entity_id
        
        if event.event_type == 'UPDATE':
            old_status = event.old_state.get('status')
            new_status = event.new_state.get('status')
            
            # If offer was accepted, invalidate cache entries
            if old_status != 'ACCEPTED' and new_status == 'ACCEPTED':
                self.logger.info(f"Buy offer {offer_id} accepted - invalidating dependent cache entries")
                self.validator.invalidate_buy_offer_cache(offer_id)
            
            # If expiry changed, invalidate cache entries
            old_expiry = event.old_state.get('expiry')
            new_expiry = event.new_state.get('expiry')
            if old_expiry != new_expiry:
                self.logger.info(f"Buy offer {offer_id} expiry changed - invalidating cache")
                self.validator.invalidate_buy_offer_cache(offer_id)
            
            # If amount changed, invalidate cache entries
            old_amount = event.old_state.get('amount')
            new_amount = event.new_state.get('amount')
            if old_amount != new_amount:
                self.logger.info(f"Buy offer {offer_id} amount changed - invalidating cache")
                self.validator.invalidate_buy_offer_cache(offer_id)
        
        elif event.event_type == 'DELETE':
            self.logger.info(f"Buy offer {offer_id} deleted - invalidating dependent cache entries")
            self.validator.invalidate_buy_offer_cache(offer_id)
    
    def _handle_asset_change(self, event: StateChangeEvent):
        """
        Handle asset state changes.
        """
        asset_id = event.entity_id
        
        if event.event_type == 'DELETE':
            self.logger.info(f"Asset {asset_id} deleted - invalidating dependent cache entries")
            self.validator.invalidate_asset_cache(asset_id)
        
        elif event.event_type == 'UPDATE':
            # Check if asset ownership or existence changed
            old_exists = event.old_state.get('exists', True)
            new_exists = event.new_state.get('exists', True)
            
            if old_exists != new_exists:
                self.logger.info(f"Asset {asset_id} existence changed - invalidating cache")
                self.validator.invalidate_asset_cache(asset_id)
    
    def _handle_transaction_change(self, event: StateChangeEvent):
        """
        Handle transaction state changes (like commits, rollbacks).
        """
        tx_id = event.entity_id
        
        if event.event_type == 'COMMIT':
            # When a transaction is committed, it might affect dependent validations
            tx_data = event.new_state.get('transaction_data', {})
            operation = tx_data.get('operation')
            
            if operation == 'SELL':
                # A SELL transaction being committed means the buy offer is now accepted
                buy_offer_id = tx_data.get('asset', {}).get('buy_offer_id')
                if buy_offer_id:
                    self.logger.info(f"SELL transaction {tx_id} committed - invalidating buy offer {buy_offer_id} cache")
                    self.validator.invalidate_buy_offer_cache(buy_offer_id)
                
                # Also invalidate asset cache for double-selling prevention
                asset_id = tx_data.get('asset', {}).get('id')
                if asset_id:
                    self.logger.info(f"SELL transaction {tx_id} committed - invalidating asset {asset_id} cache")
                    self.validator.invalidate_asset_cache(asset_id)
            
            elif operation == 'ADVERTISEMENT':
                # An advertisement being committed might change its status
                ad_id = tx_id
                status = tx_data.get('metadata', {}).get('status')
                if status == 'CLOSED':
                    self.logger.info(f"Advertisement {ad_id} committed as CLOSED - invalidating cache")
                    self.validator.invalidate_advertisement_cache(ad_id)
                
                # Invalidate asset cache for uniqueness (one OPEN ad per asset)
                asset_id = tx_data.get('asset', {}).get('id')
                if asset_id:
                    self.logger.info(f"Advertisement {ad_id} committed - invalidating asset {asset_id} cache")
                    self.validator.invalidate_asset_cache(asset_id)
            
            elif operation == 'TRANSFER':
                # A TRANSFER transaction changes asset ownership
                asset_id = tx_data.get('asset', {}).get('id')
                if asset_id:
                    self.logger.info(f"TRANSFER transaction {tx_id} committed - invalidating asset {asset_id} cache")
                    self.validator.invalidate_asset_cache(asset_id)
            
            elif operation == 'ACCEPT_RETURN':
                # An ACCEPT_RETURN transaction fulfills a return request
                request_id = tx_data.get('asset', {}).get('request_id')
                if request_id:
                    self.logger.info(f"ACCEPT_RETURN transaction {tx_id} committed - invalidating return request {request_id} cache")
                    self.validator.invalidate_return_request_cache(request_id)
    
    def _handle_return_request_change(self, event: StateChangeEvent):
        """
        Handle return request state changes.
        """
        request_id = event.entity_id
        
        if event.event_type == 'UPDATE':
            old_status = event.old_state.get('status')
            new_status = event.new_state.get('status')
            
            # If return request is fulfilled, invalidate dependent cache entries
            if old_status != 'FULFILLED' and new_status == 'FULFILLED':
                self.logger.info(f"Return request {request_id} fulfilled - invalidating dependent cache entries")
                self.validator.invalidate_return_request_cache(request_id)
        
        elif event.event_type == 'DELETE':
            self.logger.info(f"Return request {request_id} deleted - invalidating dependent cache entries")
            self.validator.invalidate_return_request_cache(request_id)
    
    def _handle_accept_return_change(self, event: StateChangeEvent):
        """
        Handle accept return state changes.
        """
        accept_id = event.entity_id
        
        if event.event_type == 'UPDATE':
            old_status = event.old_state.get('status')
            new_status = event.new_state.get('status')
            
            # If accept return is processed, invalidate dependent cache entries
            if old_status != 'PROCESSED' and new_status == 'PROCESSED':
                self.logger.info(f"Accept return {accept_id} processed - invalidating dependent cache entries")
                # This would invalidate any cache entries dependent on this accept return
        
        elif event.event_type == 'DELETE':
            self.logger.info(f"Accept return {accept_id} deleted - invalidating dependent cache entries")
            # This would invalidate any cache entries dependent on this accept return


class StateChangeEventBus:
    """
    Event bus for managing state change events and their handlers.
    """
    
    def __init__(self):
        self._handlers = defaultdict(list)
        self._lock = Lock()
        self._event_queue = []
        self._queue_lock = Lock()
        self._running = False
        self._worker_thread = None
        
        # Register default cache invalidation handler
        self.register_handler('state_change', CacheInvalidationHandler())
    
    def register_handler(self, event_type: str, handler: Callable[[StateChangeEvent], None]):
        """
        Register a handler for a specific event type.
        """
        with self._lock:
            self._handlers[event_type].append(handler)
            logger.info(f"Registered handler for event type: {event_type}")
    
    def emit_event(self, event: StateChangeEvent):
        """
        Emit a state change event to all registered handlers.
        """
        with self._queue_lock:
            self._event_queue.append(event)
        
        logger.debug(f"Emitted event: {event}")
    
    def start_event_processing(self):
        """
        Start the event processing worker thread.
        """
        if self._running:
            return
        
        self._running = True
        self._worker_thread = Thread(target=self._process_events, daemon=True)
        self._worker_thread.start()
        logger.info("Started state change event processing")
    
    def stop_event_processing(self):
        """
        Stop the event processing worker thread.
        """
        self._running = False
        if self._worker_thread:
            self._worker_thread.join(timeout=5)
        logger.info("Stopped state change event processing")
    
    def _process_events(self):
        """
        Process events from the queue in a separate thread.
        """
        while self._running:
            try:
                # Get next event from queue
                event = None
                with self._queue_lock:
                    if self._event_queue:
                        event = self._event_queue.pop(0)
                
                if event:
                    # Process event with all registered handlers
                    with self._lock:
                        handlers = self._handlers.get('state_change', [])
                    
                    for handler in handlers:
                        try:
                            handler.handle_event(event)
                        except Exception as e:
                            logger.error(f"Error in event handler: {e}", exc_info=True)
                
                else:
                    # No events, sleep briefly
                    time.sleep(0.1)
            
            except Exception as e:
                logger.error(f"Error processing events: {e}", exc_info=True)
                time.sleep(1)


class BlockchainStateMonitor:
    """
    Monitors blockchain state changes and emits events.
    This is a simplified version that would integrate with actual blockchain events.
    """
    
    def __init__(self, event_bus: StateChangeEventBus):
        self.event_bus = event_bus
        self.logger = logging.getLogger(__name__ + '.monitor')
        self._monitoring = False
    
    def start_monitoring(self):
        """
        Start monitoring blockchain state changes.
        """
        self._monitoring = True
        self.logger.info("Started blockchain state monitoring")
    
    def stop_monitoring(self):
        """
        Stop monitoring blockchain state changes.
        """
        self._monitoring = False
        self.logger.info("Stopped blockchain state monitoring")
    
    def on_transaction_committed(self, tx_data: Dict[str, Any]):
        """
        Called when a transaction is committed to the blockchain.
        """
        if not self._monitoring:
            return
        
        tx_id = tx_data.get('id')
        operation = tx_data.get('operation')
        
        # Emit transaction commit event
        event = StateChangeEvent(
            event_type='COMMIT',
            entity_id=tx_id,
            entity_type='transaction',
            new_state={'transaction_data': tx_data}
        )
        self.event_bus.emit_event(event)
        
        # Emit specific entity events based on operation
        if operation == 'ADVERTISEMENT':
            self._emit_advertisement_event(tx_data, 'CREATE')
        elif operation == 'BUY_OFFER':
            self._emit_buy_offer_event(tx_data, 'CREATE')
        elif operation == 'SELL':
            self._emit_sell_event(tx_data)
        elif operation == 'TRANSFER':
            self._emit_asset_event(tx_data, 'UPDATE')
        elif operation == 'REQUEST_RETURN':
            self._emit_return_request_event(tx_data, 'CREATE')
        elif operation == 'ACCEPT_RETURN':
            self._emit_accept_return_event(tx_data, 'CREATE')
    
    def on_transaction_updated(self, tx_id: str, old_data: Dict[str, Any], new_data: Dict[str, Any]):
        """
        Called when a transaction's metadata is updated.
        """
        if not self._monitoring:
            return
        
        operation = new_data.get('operation')
        
        if operation == 'ADVERTISEMENT':
            self._emit_advertisement_event(new_data, 'UPDATE', old_data)
        elif operation == 'BUY_OFFER':
            self._emit_buy_offer_event(new_data, 'UPDATE', old_data)
    
    def on_transaction_deleted(self, tx_data: Dict[str, Any]):
        """
        Called when a transaction is deleted or rolled back.
        """
        if not self._monitoring:
            return
        
        tx_id = tx_data.get('id')
        operation = tx_data.get('operation')
        
        if operation == 'ADVERTISEMENT':
            self._emit_advertisement_event(tx_data, 'DELETE')
        elif operation == 'BUY_OFFER':
            self._emit_buy_offer_event(tx_data, 'DELETE')
        elif operation == 'TRANSFER':
            self._emit_asset_event(tx_data, 'DELETE')
    
    def _emit_advertisement_event(self, tx_data: Dict[str, Any], event_type: str, old_data: Dict[str, Any] = None):
        """Emit advertisement state change event."""
        ad_id = tx_data.get('id')
        metadata = tx_data.get('metadata', {})
        
        event = StateChangeEvent(
            event_type=event_type,
            entity_id=ad_id,
            entity_type='advertisement',
            old_state=old_data.get('metadata', {}) if old_data else {},
            new_state=metadata
        )
        self.event_bus.emit_event(event)
    
    def _emit_buy_offer_event(self, tx_data: Dict[str, Any], event_type: str, old_data: Dict[str, Any] = None):
        """Emit buy offer state change event."""
        offer_id = tx_data.get('id')
        metadata = tx_data.get('metadata', {})
        
        event = StateChangeEvent(
            event_type=event_type,
            entity_id=offer_id,
            entity_type='buy_offer',
            old_state=old_data.get('metadata', {}) if old_data else {},
            new_state=metadata
        )
        self.event_bus.emit_event(event)
    
    def _emit_asset_event(self, tx_data: Dict[str, Any], event_type: str):
        """Emit asset state change event."""
        asset_id = tx_data.get('asset', {}).get('id')
        if asset_id:
            event = StateChangeEvent(
                event_type=event_type,
                entity_id=asset_id,
                entity_type='asset',
                new_state={'exists': event_type != 'DELETE'}
            )
            self.event_bus.emit_event(event)
    
    def _emit_sell_event(self, tx_data: Dict[str, Any]):
        """Emit events related to a SELL transaction."""
        # A SELL transaction affects the buy offer it references
        buy_offer_id = tx_data.get('asset', {}).get('buy_offer_id')
        if buy_offer_id:
            # Emit buy offer update event (status changes to ACCEPTED)
            event = StateChangeEvent(
                event_type='UPDATE',
                entity_id=buy_offer_id,
                entity_type='buy_offer',
                old_state={'status': 'PENDING'},
                new_state={'status': 'ACCEPTED'}
            )
            self.event_bus.emit_event(event)
    
    def _emit_return_request_event(self, tx_data: Dict[str, Any], event_type: str):
        """Emit return request state change event."""
        request_id = tx_data.get('id')
        metadata = tx_data.get('metadata', {})
        
        event = StateChangeEvent(
            event_type=event_type,
            entity_id=request_id,
            entity_type='return_request',
            new_state=metadata
        )
        self.event_bus.emit_event(event)
    
    def _emit_accept_return_event(self, tx_data: Dict[str, Any], event_type: str):
        """Emit accept return state change event."""
        accept_id = tx_data.get('id')
        metadata = tx_data.get('metadata', {})
        
        event = StateChangeEvent(
            event_type=event_type,
            entity_id=accept_id,
            entity_type='accept_return',
            new_state=metadata
        )
        self.event_bus.emit_event(event)


# Global instances
_event_bus = None
_state_monitor = None


def get_event_bus() -> StateChangeEventBus:
    """Get the global event bus instance."""
    global _event_bus
    if _event_bus is None:
        _event_bus = StateChangeEventBus()
        _event_bus.start_event_processing()
    return _event_bus


def get_state_monitor() -> BlockchainStateMonitor:
    """Get the global state monitor instance."""
    global _state_monitor
    if _state_monitor is None:
        _state_monitor = BlockchainStateMonitor(get_event_bus())
        _state_monitor.start_monitoring()
    return _state_monitor


def emit_transaction_committed(tx_data: Dict[str, Any]):
    """
    Convenience function to emit a transaction committed event.
    """
    monitor = get_state_monitor()
    monitor.on_transaction_committed(tx_data)


def emit_transaction_updated(tx_id: str, old_data: Dict[str, Any], new_data: Dict[str, Any]):
    """
    Convenience function to emit a transaction updated event.
    """
    monitor = get_state_monitor()
    monitor.on_transaction_updated(tx_id, old_data, new_data)


def emit_transaction_deleted(tx_data: Dict[str, Any]):
    """
    Convenience function to emit a transaction deleted event.
    """
    monitor = get_state_monitor()
    monitor.on_transaction_deleted(tx_data)

