"""
SHACL Validator Client with State-Aware Caching and Cache Invalidation

This enhanced version includes:
- State-dependent cache keys that include relevant blockchain state
- Event-driven cache invalidation when blockchain state changes
- Composite cache keys for different validation phases
- Automatic cache invalidation on state changes
"""

import requests
import logging
import time
import hashlib
import json
from threading import Lock
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, Any, Tuple, List, Optional, Set

try:
    from bigchaindb import config
except ImportError:
    # Fallback for when config is not available (e.g., during Docker build)
    config = None

logger = logging.getLogger(__name__)
metrics_logger = logging.getLogger(__name__ + '.metrics')
cache_logger = logging.getLogger(__name__ + '.cache')


class StateAwareCacheKey:
    """
    Generates composite cache keys that include relevant blockchain state.
    This ensures cache invalidation when dependent state changes.
    """
    
    @staticmethod
    def generate_key(tx_dict: Dict[str, Any], state_snapshot: Dict[str, Any]) -> str:
        """
        Generate a composite cache key that includes transaction data and relevant state.
        
        Args:
            tx_dict: Transaction dictionary
            state_snapshot: Current state snapshot for dependencies
            
        Returns:
            Composite cache key as string
        """
        tx_id = tx_dict.get('id', 'unknown')
        operation = tx_dict.get('operation', 'unknown')
        
        # Create state-dependent key components
        key_components = {
            'tx_id': tx_id,
            'operation': operation,
            'state_hash': StateAwareCacheKey._get_state_hash(tx_dict, state_snapshot)
        }
        
        # Convert to deterministic string
        key_string = json.dumps(key_components, sort_keys=True)
        return hashlib.sha256(key_string.encode()).hexdigest()[:16]
    
    @staticmethod
    def _get_state_hash(tx_dict: Dict[str, Any], state_snapshot: Dict[str, Any]) -> str:
        """
        Generate hash of relevant state dependencies for this transaction.
        """
        operation = tx_dict.get('operation', 'unknown')
        state_data = {}
        
        if operation == 'BUY_OFFER':
            # Dependencies: advertisement status, expiry
            advertisement_id = tx_dict.get('asset', {}).get('advertisement_id')
            if advertisement_id and advertisement_id in state_snapshot.get('advertisements', {}):
                ad_state = state_snapshot['advertisements'][advertisement_id]
                state_data['ad_status'] = ad_state.get('status')
                state_data['ad_expiry'] = ad_state.get('expiry')
        
        elif operation == 'SELL':
            # Dependencies: buy offer status, expiry, amount, double-spend check
            buy_offer_id = tx_dict.get('asset', {}).get('buy_offer_id')
            if buy_offer_id and buy_offer_id in state_snapshot.get('buy_offers', {}):
                offer_state = state_snapshot['buy_offers'][buy_offer_id]
                state_data['offer_status'] = offer_state.get('status')
                state_data['offer_expiry'] = offer_state.get('expiry')
                state_data['offer_amount'] = offer_state.get('amount')
                state_data['offer_accepted'] = offer_state.get('accepted')
        
        elif operation == 'TRANSFER':
            # Dependencies: asset existence
            asset_id = tx_dict.get('asset', {}).get('id')
            if asset_id and asset_id in state_snapshot.get('assets', {}):
                state_data['asset_exists'] = state_snapshot['assets'][asset_id].get('exists')
        
        # Create deterministic hash of state dependencies
        if state_data:
            state_string = json.dumps(state_data, sort_keys=True)
            return hashlib.sha256(state_string.encode()).hexdigest()[:8]
        else:
            return 'no_deps'  # No state dependencies


class StateSnapshotManager:
    """
    Manages blockchain state snapshots for cache key generation.
    """
    
    def __init__(self):
        self._state_snapshot = {}
        self._snapshot_lock = Lock()
        self._last_update = 0
        self._update_interval = 5  # Update every 5 seconds
    
    def get_state_snapshot(self) -> Dict[str, Any]:
        """
        Get current state snapshot, updating if needed.
        """
        current_time = time.time()
        
        with self._snapshot_lock:
            if current_time - self._last_update > self._update_interval:
                self._update_snapshot()
                self._last_update = current_time
            
            return self._state_snapshot.copy()
    
    def _update_snapshot(self):
        """
        Update state snapshot by querying current blockchain state.
        This is a simplified version - in production, this would query MongoDB.
        """
        # For now, we'll use a placeholder that gets updated by state change events
        # In a real implementation, this would query MongoDB for current state
        pass
    
    def update_advertisement_state(self, ad_id: str, status: str, expiry: str = None):
        """Update advertisement state in snapshot."""
        with self._snapshot_lock:
            if 'advertisements' not in self._state_snapshot:
                self._state_snapshot['advertisements'] = {}
            
            self._state_snapshot['advertisements'][ad_id] = {
                'status': status,
                'expiry': expiry,
                'updated': time.time()
            }
    
    def update_buy_offer_state(self, offer_id: str, status: str, expiry: str = None, 
                              amount: str = None, accepted: bool = False):
        """Update buy offer state in snapshot."""
        with self._snapshot_lock:
            if 'buy_offers' not in self._state_snapshot:
                self._state_snapshot['buy_offers'] = {}
            
            self._state_snapshot['buy_offers'][offer_id] = {
                'status': status,
                'expiry': expiry,
                'amount': amount,
                'accepted': accepted,
                'updated': time.time()
            }
    
    def update_asset_state(self, asset_id: str, exists: bool):
        """Update asset state in snapshot."""
        with self._snapshot_lock:
            if 'assets' not in self._state_snapshot:
                self._state_snapshot['assets'] = {}
            
            self._state_snapshot['assets'][asset_id] = {
                'exists': exists,
                'updated': time.time()
            }


class StateAwareCache:
    """
    Cache with state-aware invalidation capabilities.
    """
    
    def __init__(self, max_size: int = 1000, ttl: int = 60):
        self.max_size = max_size
        self.ttl = ttl
        self._cache = {}
        self._cache_lock = Lock()
        self._state_manager = StateSnapshotManager()
        
        # Track cache entries by state dependencies for targeted invalidation
        self._entries_by_advertisement = defaultdict(set)
        self._entries_by_buy_offer = defaultdict(set)
        self._entries_by_asset = defaultdict(set)
        self._entries_by_sell = defaultdict(set)
        self._entries_by_return_request = defaultdict(set)
        self._entries_by_creator = defaultdict(set)
        self._entries_by_advertiser = defaultdict(set)
    
    def get(self, tx_dict: Dict[str, Any]) -> Optional[Tuple[bool, List[Dict[str, Any]]]]:
        """
        Get cached validation result using state-aware key.
        """
        state_snapshot = self._state_manager.get_state_snapshot()
        cache_key = StateAwareCacheKey.generate_key(tx_dict, state_snapshot)
        
        with self._cache_lock:
            if cache_key in self._cache:
                timestamp, result = self._cache[cache_key]
                age = time.time() - timestamp
                
                if age < self.ttl:
                    cache_logger.debug(f"[CACHE HIT] key={cache_key[:8]}..., age={age:.2f}s")
                    return result
                else:
                    # Expired
                    del self._cache[cache_key]
                    cache_logger.debug(f"[CACHE EXPIRED] key={cache_key[:8]}..., age={age:.2f}s")
        
        return None
    
    def put(self, tx_dict: Dict[str, Any], result: Tuple[bool, List[Dict[str, Any]]]):
        """
        Store validation result with state-aware key and dependency tracking.
        """
        state_snapshot = self._state_manager.get_state_snapshot()
        cache_key = StateAwareCacheKey.generate_key(tx_dict, state_snapshot)
        
        with self._cache_lock:
            # Clean up if cache is too large
            if len(self._cache) >= self.max_size:
                self._evict_oldest_entries()
            
            self._cache[cache_key] = (time.time(), result)
            
            # Track dependencies for targeted invalidation
            self._track_dependencies(tx_dict, cache_key)
            
            cache_logger.debug(f"[CACHE STORE] key={cache_key[:8]}..., size={len(self._cache)}")
    
    def _track_dependencies(self, tx_dict: Dict[str, Any], cache_key: str):
        """
        Track which cache entries depend on which state elements.
        """
        operation = tx_dict.get('operation', 'unknown')
        
        if operation == 'BUY_OFFER':
            advertisement_id = tx_dict.get('asset', {}).get('advertisement_id')
            if advertisement_id:
                self._entries_by_advertisement[advertisement_id].add(cache_key)
        
        elif operation == 'SELL':
            buy_offer_id = tx_dict.get('asset', {}).get('buy_offer_id')
            if buy_offer_id:
                self._entries_by_buy_offer[buy_offer_id].add(cache_key)
            
            # Track by asset for double-selling prevention
            asset_id = tx_dict.get('asset', {}).get('id')
            if asset_id:
                self._entries_by_asset[asset_id].add(cache_key)
        
        elif operation == 'TRANSFER':
            asset_id = tx_dict.get('asset', {}).get('id')
            if asset_id:
                self._entries_by_asset[asset_id].add(cache_key)
        
        elif operation == 'ADVERTISEMENT':
            # Track by asset for uniqueness (one OPEN ad per asset)
            asset_id = tx_dict.get('asset', {}).get('id')
            if asset_id:
                self._entries_by_asset[asset_id].add(cache_key)
            
            # Track by advertiser for permission changes
            advertiser_key = tx_dict.get('inputs', [{}])[0].get('owners_before', [None])[0]
            if advertiser_key:
                self._entries_by_advertiser[advertiser_key].add(cache_key)
        
        elif operation == 'REQUEST_RETURN':
            sell_id = tx_dict.get('asset', {}).get('sell_id')
            if sell_id:
                self._entries_by_sell[sell_id].add(cache_key)
        
        elif operation == 'ACCEPT_RETURN':
            request_id = tx_dict.get('asset', {}).get('request_id')
            if request_id:
                self._entries_by_return_request[request_id].add(cache_key)
        
        elif operation == 'CREATE':
            # Track by creator for permission changes
            creator_key = tx_dict.get('inputs', [{}])[0].get('owners_before', [None])[0]
            if creator_key:
                self._entries_by_creator[creator_key].add(cache_key)
    
    def invalidate_by_advertisement(self, advertisement_id: str):
        """
        Invalidate all cache entries that depend on this advertisement.
        """
        with self._cache_lock:
            affected_keys = self._entries_by_advertisement.get(advertisement_id, set())
            for cache_key in affected_keys:
                if cache_key in self._cache:
                    del self._cache[cache_key]
                    cache_logger.info(f"[CACHE INVALIDATED] ad={advertisement_id}, key={cache_key[:8]}...")
            
            # Clear tracking
            if advertisement_id in self._entries_by_advertisement:
                del self._entries_by_advertisement[advertisement_id]
    
    def invalidate_by_buy_offer(self, buy_offer_id: str):
        """
        Invalidate all cache entries that depend on this buy offer.
        """
        with self._cache_lock:
            affected_keys = self._entries_by_buy_offer.get(buy_offer_id, set())
            for cache_key in affected_keys:
                if cache_key in self._cache:
                    del self._cache[cache_key]
                    cache_logger.info(f"[CACHE INVALIDATED] offer={buy_offer_id}, key={cache_key[:8]}...")
            
            # Clear tracking
            if buy_offer_id in self._entries_by_buy_offer:
                del self._entries_by_buy_offer[buy_offer_id]
    
    def invalidate_by_asset(self, asset_id: str):
        """
        Invalidate all cache entries that depend on this asset.
        """
        with self._cache_lock:
            affected_keys = self._entries_by_asset.get(asset_id, set())
            for cache_key in affected_keys:
                if cache_key in self._cache:
                    del self._cache[cache_key]
                    cache_logger.info(f"[CACHE INVALIDATED] asset={asset_id}, key={cache_key[:8]}...")
            
            # Clear tracking
            if asset_id in self._entries_by_asset:
                del self._entries_by_asset[asset_id]
    
    def invalidate_by_sell(self, sell_id: str):
        """
        Invalidate all cache entries that depend on this sell transaction.
        """
        with self._cache_lock:
            affected_keys = self._entries_by_sell.get(sell_id, set())
            for cache_key in affected_keys:
                if cache_key in self._cache:
                    del self._cache[cache_key]
                    cache_logger.info(f"[CACHE INVALIDATED] sell={sell_id}, key={cache_key[:8]}...")
            
            # Clear tracking
            if sell_id in self._entries_by_sell:
                del self._entries_by_sell[sell_id]
    
    def invalidate_by_return_request(self, request_id: str):
        """
        Invalidate all cache entries that depend on this return request.
        """
        with self._cache_lock:
            affected_keys = self._entries_by_return_request.get(request_id, set())
            for cache_key in affected_keys:
                if cache_key in self._cache:
                    del self._cache[cache_key]
                    cache_logger.info(f"[CACHE INVALIDATED] return_request={request_id}, key={cache_key[:8]}...")
            
            # Clear tracking
            if request_id in self._entries_by_return_request:
                del self._entries_by_return_request[request_id]
    
    def invalidate_by_creator(self, creator_key: str):
        """
        Invalidate all cache entries that depend on this creator.
        """
        with self._cache_lock:
            affected_keys = self._entries_by_creator.get(creator_key, set())
            for cache_key in affected_keys:
                if cache_key in self._cache:
                    del self._cache[cache_key]
                    cache_logger.info(f"[CACHE INVALIDATED] creator={creator_key[:8]}..., key={cache_key[:8]}...")
            
            # Clear tracking
            if creator_key in self._entries_by_creator:
                del self._entries_by_creator[creator_key]
    
    def invalidate_by_advertiser(self, advertiser_key: str):
        """
        Invalidate all cache entries that depend on this advertiser.
        """
        with self._cache_lock:
            affected_keys = self._entries_by_advertiser.get(advertiser_key, set())
            for cache_key in affected_keys:
                if cache_key in self._cache:
                    del self._cache[cache_key]
                    cache_logger.info(f"[CACHE INVALIDATED] advertiser={advertiser_key[:8]}..., key={cache_key[:8]}...")
            
            # Clear tracking
            if advertiser_key in self._entries_by_advertiser:
                del self._entries_by_advertiser[advertiser_key]
    
    def _evict_oldest_entries(self):
        """
        Evict oldest 10% of entries when cache is full.
        """
        sorted_items = sorted(self._cache.items(), key=lambda x: x[1][0])
        to_remove = max(1, int(self.max_size * 0.1))
        
        for cache_key, _ in sorted_items[:to_remove]:
            del self._cache[cache_key]
        
        cache_logger.info(f"[CACHE EVICTION] Removed {to_remove} entries, size={len(self._cache)}")
    
    def clear(self):
        """Clear all cached entries."""
        with self._cache_lock:
            cache_size = len(self._cache)
            self._cache.clear()
            self._entries_by_advertisement.clear()
            self._entries_by_buy_offer.clear()
            self._entries_by_asset.clear()
            self._entries_by_sell.clear()
            self._entries_by_return_request.clear()
            self._entries_by_creator.clear()
            self._entries_by_advertiser.clear()
            logger.info(f"State-aware cache cleared: {cache_size} entries removed")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self._cache_lock:
            return {
                'cache_size': len(self._cache),
                'max_size': self.max_size,
                'utilization_percent': round(len(self._cache) / self.max_size * 100, 2),
                'tracked_advertisements': len(self._entries_by_advertisement),
                'tracked_buy_offers': len(self._entries_by_buy_offer),
                'tracked_assets': len(self._entries_by_asset),
                'tracked_sells': len(self._entries_by_sell),
                'tracked_return_requests': len(self._entries_by_return_request),
                'tracked_creators': len(self._entries_by_creator),
                'tracked_advertisers': len(self._entries_by_advertiser)
            }


class StateAwareSHACLValidator:
    """
    Enhanced SHACL validator with state-aware caching and invalidation.
    """
    
    def __init__(self, endpoint: Optional[str] = None, timeout: Optional[int] = None, phase: str = 'UNKNOWN'):
        if config:
            shacl_config = config.get('shacl', {})
        else:
            shacl_config = {}
        
        # Check environment variable first, then config
        import os
        env_enabled = os.getenv('BIGCHAINDB_SHACL_ENABLED', '').lower() in ('true', '1', 'yes')
        
        if env_enabled:
            self.enabled = True
        else:
            self.enabled = shacl_config.get('enabled', False)
        self.endpoint = endpoint or shacl_config.get('endpoint', 'http://shacleng:3000')
        self.timeout = timeout or shacl_config.get('timeout', 10)
        self.phase = phase
        
        # State-aware cache configuration
        self.cache_enabled = shacl_config.get('cache_enabled', True)
        self.cache_ttl = shacl_config.get('cache_ttl', 60)
        self.cache_max_size = shacl_config.get('cache_max_size', 1000)
        
        # Initialize state-aware cache
        self._cache = StateAwareCache(self.cache_max_size, self.cache_ttl)
        self._state_manager = self._cache._state_manager
        
        logger.info(
            f"State-aware SHACL validator initialized: "
            f"enabled={self.enabled}, "
            f"endpoint={self.endpoint}, "
            f"cache_enabled={self.cache_enabled} "
            f"(TTL={self.cache_ttl}s, max_size={self.cache_max_size}), "
            f"phase={self.phase}"
        )
    
    def validate_transaction(self, tx_dict: Dict[str, Any]) -> Tuple[bool, List[Dict[str, Any]]]:
        """
        Validate transaction with state-aware caching.
        """
        tx_id = tx_dict.get('id', 'unknown')
        operation = tx_dict.get('operation', 'unknown')
        
        start_time = time.time()
        cache_hit = False
        conforms = False
        results = []
        
        try:
            # Check state-aware cache first
            if self.cache_enabled:
                cached_result = self._cache.get(tx_dict)
                if cached_result is not None:
                    cache_hit = True
                    conforms, results = cached_result
                    duration_ms = (time.time() - start_time) * 1000
                    
                    cache_logger.debug(
                        f"[STATE-AWARE CACHE HIT] tx={tx_id[:16]}..., "
                        f"operation={operation}, phase={self.phase}, time={duration_ms:.2f}ms"
                    )
                    
                    return conforms, results
            
            # Cache miss - perform validation
            cache_logger.debug(
                f"[STATE-AWARE CACHE MISS] tx={tx_id[:16]}..., "
                f"operation={operation}, phase={self.phase}"
            )
            
            if not self.enabled:
                logger.warning("SHACL validation is disabled")
                return True, []
            
            # Convert to RDF and validate
            turtle_data = self._convert_to_turtle(tx_dict)
            
            response = requests.post(
                f'{self.endpoint}/validate',
                json={
                    'shapeType': operation,
                    'data': turtle_data
                },
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                conforms = result.get('conforms', False)
                results = result.get('results', [])
                
                # Cache the result with state awareness
                if self.cache_enabled:
                    self._cache.put(tx_dict, (conforms, results))
                
                duration_ms = (time.time() - start_time) * 1000
                
                metrics_logger.info(
                    f"[STATE-AWARE VALIDATION] tx={tx_id[:16]}..., "
                    f"operation={operation}, phase={self.phase}, "
                    f"time={duration_ms:.2f}ms, cache_hit={cache_hit}, "
                    f"result={'PASS' if conforms else 'FAIL'}"
                )
                
                return conforms, results
            else:
                logger.error(f"SHACL service returned status {response.status_code}")
                return False, [{"message": f"SHACL service error: {response.status_code}"}]
        
        except Exception as e:
            logger.error(f"SHACL validation exception: {e}", exc_info=True)
            return False, [{"message": f"Validation error: {str(e)}"}]
    
    def _convert_to_turtle(self, tx_dict: Dict[str, Any]) -> str:
        """
        Convert transaction to RDF Turtle format (same as original implementation).
        """
        operation = tx_dict.get('operation', 'UNKNOWN')
        tx_id = tx_dict.get('id', 'unknown')
        version = tx_dict.get('version', '2.0')
        
        # Start Turtle document with prefixes
        turtle = "@prefix bdb: <http://bigchaindb.com/ns#> .\n"
        turtle += "@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .\n\n"
        
        # Create transaction resource
        turtle += f"<urn:tx:{tx_id}> a bdb:{operation}Transaction ;\n"
        turtle += f'    bdb:operation "{operation}" ;\n'
        turtle += f'    bdb:version "{version}" ;\n'
        
        # Add asset information
        asset = tx_dict.get('asset', {})
        if asset:
            turtle += self._serialize_asset(asset, operation)
        
        # Add metadata
        metadata = tx_dict.get('metadata', {})
        if metadata:
            turtle += self._serialize_metadata(metadata)
        
        # Add inputs/outputs count
        inputs = tx_dict.get('inputs', [])
        if inputs:
            turtle += f'    bdb:inputs "{len(inputs)}"^^xsd:integer ;\n'
        
        outputs = tx_dict.get('outputs', [])
        if outputs:
            turtle += f'    bdb:outputs "{len(outputs)}"^^xsd:integer ;\n'
        
        # Remove trailing semicolon and newline, add period
        turtle = turtle.rstrip(';\n') + ' .\n'
        
        return turtle
    
    def _serialize_asset(self, asset: Dict[str, Any], operation: str) -> str:
        """Serialize asset field to Turtle."""
        turtle = ""
        
        if operation == 'CREATE' and 'data' in asset:
            asset_data = asset['data']
            turtle += "    bdb:asset [\n"
            turtle += "        bdb:data [\n"
            
            for key, value in asset_data.items():
                if isinstance(value, str):
                    escaped_value = value.replace('\\', '\\\\').replace('"', '\\"')
                    turtle += f'            bdb:{key} "{escaped_value}" ;\n'
                elif isinstance(value, (int, float)):
                    turtle += f'            bdb:{key} {value} ;\n'
                elif isinstance(value, bool):
                    turtle += f'            bdb:{key} "{str(value).lower()}" ;\n'
                elif isinstance(value, list):
                    list_str = ', '.join(str(v) for v in value)
                    turtle += f'            bdb:{key} "{list_str}" ;\n'
            
            turtle = turtle.rstrip(';\n') + '\n'
            turtle += "        ]\n"
            turtle += "    ] ;\n"
        
        else:
            turtle += "    bdb:asset [\n"
            
            if 'id' in asset:
                turtle += f'        bdb:id "{asset["id"]}" ;\n'
            
            if 'data' in asset:
                turtle += "        bdb:data [\n"
                for key, value in asset['data'].items():
                    if isinstance(value, str):
                        turtle += f'            bdb:{key} "{value}" ;\n'
                    elif isinstance(value, (int, float)):
                        turtle += f'            bdb:{key} {value} ;\n'
                turtle = turtle.rstrip(';\n') + '\n'
                turtle += "        ] ;\n"
            
            turtle = turtle.rstrip(';\n') + '\n'
            turtle += "    ] ;\n"
        
        return turtle
    
    def _serialize_metadata(self, metadata: Dict[str, Any]) -> str:
        """Serialize metadata field to Turtle."""
        turtle = "    bdb:metadata [\n"
        
        for key, value in metadata.items():
            if isinstance(value, str):
                if 'timestamp' in key.lower() or 'expiry' in key.lower() or 'date' in key.lower():
                    turtle += f'        bdb:{key} "{value}"^^xsd:dateTime ;\n'
                else:
                    escaped_value = value.replace('\\', '\\\\').replace('"', '\\"')
                    turtle += f'        bdb:{key} "{escaped_value}" ;\n'
            elif isinstance(value, int):
                turtle += f'        bdb:{key} {value} ;\n'
            elif isinstance(value, float):
                turtle += f'        bdb:{key} {value} ;\n'
            elif isinstance(value, bool):
                turtle += f'        bdb:{key} {"true" if value else "false"} ;\n'
            elif isinstance(value, (list, dict)):
                logger.debug(f"Skipping complex metadata field: {key}")
            elif value is None:
                pass
        
        turtle = turtle.rstrip(';\n') + '\n'
        turtle += "    ] ;\n"
        
        return turtle
    
    # Cache invalidation methods for external use
    def invalidate_advertisement_cache(self, advertisement_id: str):
        """Invalidate cache entries dependent on this advertisement."""
        self._cache.invalidate_by_advertisement(advertisement_id)
        self._state_manager.update_advertisement_state(advertisement_id, 'CLOSED')
    
    def invalidate_buy_offer_cache(self, buy_offer_id: str):
        """Invalidate cache entries dependent on this buy offer."""
        self._cache.invalidate_by_buy_offer(buy_offer_id)
        self._state_manager.update_buy_offer_state(buy_offer_id, 'EXPIRED')
    
    def invalidate_asset_cache(self, asset_id: str):
        """Invalidate cache entries dependent on this asset."""
        self._cache.invalidate_by_asset(asset_id)
        self._state_manager.update_asset_state(asset_id, False)
    
    def invalidate_sell_cache(self, sell_id: str):
        """Invalidate cache entries dependent on this sell transaction."""
        self._cache.invalidate_by_sell(sell_id)
    
    def invalidate_return_request_cache(self, request_id: str):
        """Invalidate cache entries dependent on this return request."""
        self._cache.invalidate_by_return_request(request_id)
    
    def invalidate_creator_cache(self, creator_key: str):
        """Invalidate cache entries dependent on this creator."""
        self._cache.invalidate_by_creator(creator_key)
    
    def invalidate_advertiser_cache(self, advertiser_key: str):
        """Invalidate cache entries dependent on this advertiser."""
        self._cache.invalidate_by_advertiser(advertiser_key)
    
    def clear_cache(self):
        """Clear all cached validation results."""
        self._cache.clear()
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get current cache statistics."""
        return self._cache.get_stats()


# Global singleton instance
_state_aware_validator = None


def get_state_aware_shacl_validator(phase: str = 'UNKNOWN') -> StateAwareSHACLValidator:
    """
    Get or create the global state-aware SHACL validator instance.
    """
    global _state_aware_validator
    if _state_aware_validator is None:
        _state_aware_validator = StateAwareSHACLValidator(phase=phase)
    return _state_aware_validator

