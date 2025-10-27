"""
Enhanced State-Aware SHACL Validator with Robust Caching

This enhanced version includes:
- Phase-aware validation (HTTP_POST, CHECK_TX, DELIVER_TX)
- State-aware cache keys with blockchain state hash
- Dependency tracking for cache invalidation
- Robust cache invalidation patterns
- Multi-phase transaction lifecycle support
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

class ValidationMetrics:
    """Enhanced metrics tracking for state-aware validation"""
    
    def __init__(self):
        self.validation_count = 0
        self.cache_hits = 0
        self.cache_misses = 0
        self.cache_invalidations = 0
        self.inflight_conflicts = 0
        self.soft_races = 0
        self.deliver_winners = 0
        self.deliver_losers = 0
        self.validation_times = []
        self.phase_stats = defaultdict(lambda: {'hits': 0, 'misses': 0, 'times': []})
        self.state_changes = 0
        
    def record_validation(self, tx_id: str, operation: str, phase: str, 
                         duration_ms: float, cache_hit: bool, success: bool,
                         conversion_ms: float = None, shacl_request_ms: float = None,
                         cache_overhead_ms: float = None):
        """Record validation metrics"""
        self.validation_count += 1
        if cache_hit:
            self.cache_hits += 1
        else:
            self.cache_misses += 1
            
        self.validation_times.append(duration_ms)
        self.phase_stats[phase]['hits' if cache_hit else 'misses'] += 1
        self.phase_stats[phase]['times'].append(duration_ms)
        
        parts = [
            f"[STATE-AWARE VALIDATION] tx={tx_id[:16]}...",
            f"operation={operation}", f"phase={phase}",
            f"time={duration_ms:.2f}ms", f"cache_hit={cache_hit}",
            f"result={'PASS' if success else 'FAIL'}"
        ]
        if conversion_ms is not None:
            parts.append(f"conversion_ms={conversion_ms:.2f}")
        if shacl_request_ms is not None:
            parts.append(f"shacl_request_ms={shacl_request_ms:.2f}")
        if cache_overhead_ms is not None:
            parts.append(f"cache_overhead_ms={cache_overhead_ms:.2f}")
        metrics_logger.info(
            ", ".join(parts)
        )
    
    def record_cache_invalidation(self, reason: str, affected_entries: int):
        """Record cache invalidation events"""
        self.cache_invalidations += 1
        self.state_changes += 1
        cache_logger.info(
            f"[CACHE INVALIDATION] reason={reason}, "
            f"affected_entries={affected_entries}"
        )
    
    def record_inflight_conflict(self, operation: str, conflict_key: str, holder_tx_id: str):
        """Record in-flight locking conflicts (minimal invalidating patterns)"""
        self.inflight_conflicts += 1
        metrics_logger.info(
            f"[INFLIGHT CONFLICT] operation={operation}, key={conflict_key}, holder={holder_tx_id[:16]}..."
        )
    
    def record_soft_race(self, operation: str, race_key: str):
        """Record that a transaction is part of a soft race group (allowed to proceed)."""
        self.soft_races += 1
        metrics_logger.info(
            f"[SOFT RACE] operation={operation}, key={race_key}"
        )
    
    def record_deliver_outcome(self, is_winner: bool, operation: str, race_key: Optional[str] = None):
        if is_winner:
            self.deliver_winners += 1
            metrics_logger.info(
                f"[DELIVER WINNER] operation={operation}{', key='+race_key if race_key else ''}"
            )
        else:
            self.deliver_losers += 1
            metrics_logger.info(
                f"[DELIVER LOSER] operation={operation}{', key='+race_key if race_key else ''}"
            )
    
    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive metrics"""
        total_validations = self.validation_count
        hit_rate = (self.cache_hits / total_validations * 100) if total_validations > 0 else 0
        avg_time = sum(self.validation_times) / len(self.validation_times) if self.validation_times else 0
        
        return {
            'total_validations': total_validations,
            'cache_hit_rate_percent': round(hit_rate, 2),
            'average_validation_time_ms': round(avg_time, 2),
            'cache_hits': self.cache_hits,
            'cache_misses': self.cache_misses,
            'cache_invalidations': self.cache_invalidations,
            'inflight_conflicts': self.inflight_conflicts,
            'state_changes': self.state_changes,
            'phase_stats': dict(self.phase_stats)
        }


class StateAwareSHACLValidator:
    """Enhanced state-aware SHACL validator with robust caching"""
    
    def __init__(self, endpoint: str = "http://shacleng:3000", timeout: int = 30):
        self.endpoint = endpoint.rstrip('/')
        self.timeout = timeout
        self.metrics = ValidationMetrics()
        
        # Enhanced cache configuration
        self.cache_enabled = True
        self.cache_ttl = 300  # 5 minutes
        self.cache_max_size = 1000
        
        # State-aware cache: phase -> state_hash -> tx_id -> result
        self._cache = defaultdict(lambda: defaultdict(dict))
        self._cache_lock = Lock()
        
        # Dependency tracking: entity_id -> set of cache keys
        self._dependencies = defaultdict(set)
        self._dependency_lock = Lock()
        
        # Blockchain state tracking
        self._current_state_hash = None
        self._state_lock = Lock()
        
        # In-flight minimal invalidating pattern locks
        self.lock_ttl_seconds = 120
        self._locks = {}
        self._tx_to_locks = defaultdict(set)
        self._locks_lock = Lock()
        
        # Soft race markers (do not block at HTTP_POST)
        self.race_ttl_seconds = 120
        self._race_markers = {}
        self._tx_to_races = defaultdict(set)
        self._races_lock = Lock()
        
        # Configuration
        try:
            shacl_config = config.get('shacl', {}) if config else {}
        except:
            shacl_config = {}
        
        import os
        env_enabled = os.getenv('BIGCHAINDB_SHACL_ENABLED', '').lower() in ('true', '1', 'yes')
        self.enabled = shacl_config.get('enabled', False) or env_enabled
        
        logger.info(f"Enhanced State-Aware SHACL Validator initialized: enabled={self.enabled}")
    
    # In-flight minimal invalidating patterns (locks)
    def _lock_keys_for(self, tx_dict: Dict[str, Any]) -> List[str]:
        op = tx_dict.get('operation')
        asset_root = tx_dict.get('asset', {})
        asset_data = asset_root.get('data', {})
        metadata = tx_dict.get('metadata', {})
        keys: List[str] = []
        
        if op == 'ADVERTISEMENT':
            asset_id = asset_root.get('id') or asset_data.get('id')
            if asset_id:
                keys.append(f"adv_lock:asset:{asset_id}")
        elif op == 'BUY_OFFER':
            adv_id = asset_data.get('advertisement_id')
            buyer_pk = metadata.get('buyer_public_key')
            if adv_id and buyer_pk:
                keys.append(f"offer_lock:adv:{adv_id}:buyer:{buyer_pk}")
        elif op == 'SELL':
            buy_offer_id = asset_data.get('buy_offer_id')
            if buy_offer_id:
                keys.append(f"sell_lock:offer:{buy_offer_id}")
        elif op == 'REQUEST_RETURN':
            sell_tx_id = asset_root.get('sell_transaction_id') or asset_data.get('sell_transaction_id')
            if sell_tx_id:
                keys.append(f"retreq_lock:sell:{sell_tx_id}")
        elif op in ('ACCEPT_RETURN', 'SELLER_ACCEPT_RETURN'):
            req_return_id = asset_root.get('request_return_id') or asset_data.get('request_return_id')
            if req_return_id:
                keys.append(f"accept_lock:return:{req_return_id}")
        
        return keys

    def _race_keys_for(self, tx_dict: Dict[str, Any]) -> List[str]:
        """Compute soft race keys for cross-shape exclusivity (deliver-stage winner)."""
        op = tx_dict.get('operation')
        asset_root = tx_dict.get('asset', {})
        asset_data = asset_root.get('data', {})
        keys: List[str] = []
        
        # Exclusive asset group: ADVERTISEMENT vs ownership-changing ops (SELL, TRANSFER)
        asset_id = asset_root.get('id') or asset_data.get('id')
        if asset_id and op in ('ADVERTISEMENT', 'SELL', 'TRANSFER'):
            keys.append(f"exclusive:asset:{asset_id}")
        return keys
    
    def _cleanup_expired_locks(self):
        now = time.time()
        expired = []
        for key, entry in self._locks.items():
            if entry['expires_at'] <= now:
                expired.append((key, entry['tx_id']))
        for key, tx_id in expired:
            del self._locks[key]
            if tx_id in self._tx_to_locks and key in self._tx_to_locks[tx_id]:
                self._tx_to_locks[tx_id].discard(key)
                if not self._tx_to_locks[tx_id]:
                    del self._tx_to_locks[tx_id]
    
    def _acquire_locks(self, tx_id: str, keys: List[str]) -> Tuple[bool, Optional[Dict[str, str]]]:
        with self._locks_lock:
            self._cleanup_expired_locks()
            now = time.time()
            for key in keys:
                entry = self._locks.get(key)
                if entry and entry['tx_id'] != tx_id and entry['expires_at'] > now:
                    return False, {'conflict_key': key, 'holder_tx_id': entry['tx_id']}
            # No conflicts - acquire
            for key in keys:
                self._locks[key] = {'tx_id': tx_id, 'expires_at': now + self.lock_ttl_seconds}
                self._tx_to_locks[tx_id].add(key)
            return True, None
    
    def _refresh_locks(self, tx_id: str):
        with self._locks_lock:
            now = time.time()
            for key in list(self._tx_to_locks.get(tx_id, set())):
                entry = self._locks.get(key)
                if entry and entry['tx_id'] == tx_id:
                    entry['expires_at'] = now + self.lock_ttl_seconds
                else:
                    self._tx_to_locks[tx_id].discard(key)
            if tx_id in self._tx_to_locks and not self._tx_to_locks[tx_id]:
                del self._tx_to_locks[tx_id]

    def _cleanup_expired_races(self):
        now = time.time()
        expired = []
        for key, entry in self._race_markers.items():
            if entry['expires_at'] <= now:
                expired.append((key, entry['tx_ids']))
        for key, tx_ids in expired:
            del self._race_markers[key]
            for tx_id in list(tx_ids):
                if tx_id in self._tx_to_races and key in self._tx_to_races[tx_id]:
                    self._tx_to_races[tx_id].discard(key)
                    if not self._tx_to_races[tx_id]:
                        del self._tx_to_races[tx_id]

    def _mark_races(self, tx_id: str, keys: List[str]):
        with self._races_lock:
            self._cleanup_expired_races()
            now = time.time()
            for key in keys:
                entry = self._race_markers.get(key)
                if entry:
                    entry['tx_ids'].add(tx_id)
                    entry['expires_at'] = now + self.race_ttl_seconds
                else:
                    self._race_markers[key] = {'tx_ids': {tx_id}, 'expires_at': now + self.race_ttl_seconds}
                self._tx_to_races[tx_id].add(key)

    def _refresh_races(self, tx_id: str):
        with self._races_lock:
            now = time.time()
            for key in list(self._tx_to_races.get(tx_id, set())):
                entry = self._race_markers.get(key)
                if entry and tx_id in entry['tx_ids']:
                    entry['expires_at'] = now + self.race_ttl_seconds
                else:
                    self._tx_to_races[tx_id].discard(key)
            if tx_id in self._tx_to_races and not self._tx_to_races[tx_id]:
                del self._tx_to_races[tx_id]

    def _release_races(self, tx_id: str):
        with self._races_lock:
            for key in list(self._tx_to_races.get(tx_id, set())):
                entry = self._race_markers.get(key)
                if entry and tx_id in entry['tx_ids']:
                    entry['tx_ids'].discard(tx_id)
                    if not entry['tx_ids']:
                        del self._race_markers[key]
                self._tx_to_races[tx_id].discard(key)
            if tx_id in self._tx_to_races and not self._tx_to_races[tx_id]:
                del self._tx_to_races[tx_id]

    def _dependency_keys_for(self, tx_dict: Dict[str, Any], phase: str) -> List[str]:
        """Derive dependency keys for cache tracking and invalidation."""
        keys: List[str] = []
        op = tx_dict.get('operation')
        asset_root = tx_dict.get('asset', {})
        asset_data = asset_root.get('data', {})
        asset_id = asset_root.get('id') or asset_data.get('id')
        if asset_id:
            keys.append(f"asset:{asset_id}")
        if op == 'ADVERTISEMENT':
            if asset_id:
                keys.append(f"dep:asset:{asset_id}")
        elif op == 'BUY_OFFER':
            adv_id = asset_data.get('advertisement_id')
            if adv_id:
                keys.append(f"dep:adv:{adv_id}")
        elif op == 'SELL':
            buy_offer_id = asset_data.get('buy_offer_id')
            if buy_offer_id:
                keys.append(f"dep:offer:{buy_offer_id}")
        elif op == 'REQUEST_RETURN':
            sell_tx_id = asset_root.get('sell_transaction_id') or asset_data.get('sell_transaction_id')
            if sell_tx_id:
                keys.append(f"dep:sell:{sell_tx_id}")
        elif op in ('ACCEPT_RETURN', 'SELLER_ACCEPT_RETURN'):
            req_return_id = asset_root.get('request_return_id') or asset_data.get('request_return_id')
            if req_return_id:
                keys.append(f"dep:return:{req_return_id}")
        return keys
    
    def _release_locks(self, tx_id: str):
        with self._locks_lock:
            for key in list(self._tx_to_locks.get(tx_id, set())):
                entry = self._locks.get(key)
                if entry and entry['tx_id'] == tx_id:
                    del self._locks[key]
                self._tx_to_locks[tx_id].discard(key)
            if tx_id in self._tx_to_locks and not self._tx_to_locks[tx_id]:
                del self._tx_to_locks[tx_id]
    
    def _generate_state_hash(self, tx_dict: Dict[str, Any], phase: str) -> str:
        """Generate a hash representing relevant blockchain state for this transaction"""
        state_components = []
        
        # Include transaction operation and phase
        state_components.append(f"op:{tx_dict.get('operation', 'unknown')}")
        state_components.append(f"phase:{phase}")
        
        # Include relevant asset information (support both top-level and data payload)
        asset_root = tx_dict.get('asset', {})
        asset_data = asset_root.get('data', {})
        asset_id = asset_root.get('id') or asset_data.get('id')
        if asset_id:
            state_components.append(f"asset:{asset_id}")
        
        # Include dependency information
        if tx_dict.get('operation') == 'ADVERTISEMENT':
            state_components.append(f"dep:asset:{asset_data.get('id', 'unknown')}")
        elif tx_dict.get('operation') == 'BUY_OFFER':
            state_components.append(f"dep:adv:{asset_data.get('advertisement_id', 'unknown')}")
        elif tx_dict.get('operation') == 'SELL':
            state_components.append(f"dep:offer:{asset_data.get('buy_offer_id', 'unknown')}")
        elif tx_dict.get('operation') == 'REQUEST_RETURN':
            # Schema places sell_transaction_id at the top level of asset
            sell_tx_id = asset_root.get('sell_transaction_id') or asset_data.get('sell_transaction_id')
            state_components.append(f"dep:sell:{sell_tx_id or 'unknown'}")
        elif tx_dict.get('operation') in ('ACCEPT_RETURN', 'SELLER_ACCEPT_RETURN'):
            # Support both op names; schema expects top-level request_return_id
            req_return_id = asset_root.get('request_return_id') or asset_data.get('request_return_id')
            state_components.append(f"dep:return:{req_return_id or 'unknown'}")
        
        # Create hash from state components
        state_string = "|".join(sorted(state_components))
        return hashlib.sha256(state_string.encode()).hexdigest()[:16]
    
    def _get_cache_key(self, tx_id: str, phase: str, state_hash: str) -> str:
        """Generate phase-aware cache key"""
        return f"{phase}:{state_hash}:{tx_id}"
    
    def _get_from_cache(self, tx_id: str, phase: str, state_hash: str) -> Optional[Tuple[bool, List[Dict[str, Any]]]]:
        """Retrieve validation result from state-aware cache"""
        with self._cache_lock:
            cache_key = self._get_cache_key(tx_id, phase, state_hash)
            
            if phase in self._cache and state_hash in self._cache[phase] and tx_id in self._cache[phase][state_hash]:
                timestamp, result = self._cache[phase][state_hash][tx_id]
                age = time.time() - timestamp
                
                if age < self.cache_ttl:
                    cache_logger.debug(
                        f"[CACHE HIT] tx={tx_id[:16]}..., phase={phase}, "
                        f"state={state_hash[:8]}..., age={age:.2f}s"
                    )
                    return result
                else:
                    # Expired
                    del self._cache[phase][state_hash][tx_id]
                    if not self._cache[phase][state_hash]:
                        del self._cache[phase][state_hash]
                    cache_logger.debug(
                        f"[CACHE EXPIRED] tx={tx_id[:16]}..., phase={phase}, "
                        f"state={state_hash[:8]}..., age={age:.2f}s"
                    )
        
        return None
    
    def _put_in_cache(self, tx_id: str, phase: str, state_hash: str, 
                     result: Tuple[bool, List[Dict[str, Any]]], tx_dict: Dict[str, Any] = None):
        """Store validation result in state-aware cache"""
        with self._cache_lock:
            cache_key = self._get_cache_key(tx_id, phase, state_hash)
            
            # Check cache size limit
            total_entries = sum(len(phase_cache) for phase_cache in self._cache.values())
            if total_entries >= self.cache_max_size:
                self._evict_oldest_entries()
            
            # Store result
            self._cache[phase][state_hash][tx_id] = (time.time(), result)
            
            # Track dependencies using explicit keys (not from hashed state)
            if tx_dict is not None:
                dep_keys = self._dependency_keys_for(tx_dict, phase)
                self._track_dependencies(tx_id, phase, state_hash, dep_keys, result)
            
            cache_logger.debug(
                f"[CACHE STORED] tx={tx_id[:16]}..., phase={phase}, "
                f"state={state_hash[:8]}..."
            )
    
    def _track_dependencies(self, tx_id: str, phase: str, state_hash: str, dep_keys: List[str], result: Tuple[bool, List[Dict[str, Any]]]):
        """Track what blockchain entities this cache entry depends on."""
        with self._dependency_lock:
            cache_key = self._get_cache_key(tx_id, phase, state_hash)
            for dep in dep_keys:
                self._dependencies[dep].add(cache_key)
    
    def _evict_oldest_entries(self):
        """Evict oldest cache entries when limit is reached"""
        all_entries = []
        for phase, phase_cache in self._cache.items():
            for state_hash, state_cache in phase_cache.items():
                for tx_id, (timestamp, result) in state_cache.items():
                    all_entries.append((timestamp, phase, state_hash, tx_id))
        
        # Sort by timestamp and remove oldest 10%
        all_entries.sort(key=lambda x: x[0])
        to_remove = all_entries[:max(1, len(all_entries) // 10)]
        
        for timestamp, phase, state_hash, tx_id in to_remove:
            del self._cache[phase][state_hash][tx_id]
            if not self._cache[phase][state_hash]:
                del self._cache[phase][state_hash]
        
        cache_logger.debug(f"[CACHE EVICTED] {len(to_remove)} entries removed")
    
    def invalidate_cache_for_entity(self, entity_type: str, entity_id: str):
        """Invalidate cache entries that depend on a specific blockchain entity"""
        with self._dependency_lock:
            entity_key = f"{entity_type}:{entity_id}"
            affected_keys = self._dependencies.get(entity_key, set()).copy()
            
            if affected_keys:
                # Remove from cache
                with self._cache_lock:
                    for cache_key in affected_keys:
                        parts = cache_key.split(':')
                        if len(parts) >= 3:
                            phase, state_hash, tx_id = parts[0], parts[1], parts[2]
                            if (phase in self._cache and 
                                state_hash in self._cache[phase] and 
                                tx_id in self._cache[phase][state_hash]):
                                del self._cache[phase][state_hash][tx_id]
                                if not self._cache[phase][state_hash]:
                                    del self._cache[phase][state_hash]
                
                # Remove from dependencies
                del self._dependencies[entity_key]
                
                self.metrics.record_cache_invalidation(
                    f"entity_change:{entity_type}:{entity_id}", 
                    len(affected_keys)
                )
                
                cache_logger.info(
                    f"[CACHE INVALIDATED] entity={entity_key}, "
                    f"affected_entries={len(affected_keys)}"
                )
    
    def invalidate_cache_for_phase(self, phase: str):
        """Invalidate all cache entries for a specific phase"""
        with self._cache_lock:
            if phase in self._cache:
                total_entries = sum(len(state_cache) for state_cache in self._cache[phase].values())
                del self._cache[phase]
                
                self.metrics.record_cache_invalidation(f"phase_reset:{phase}", total_entries)
                
                cache_logger.info(
                    f"[CACHE INVALIDATED] phase={phase}, "
                    f"affected_entries={total_entries}"
                )
    
    def validate_transaction(self, tx_dict: Dict[str, Any], phase: str = 'HTTP_POST') -> Tuple[bool, List[Dict[str, Any]]]:
        """
        Enhanced state-aware transaction validation with robust caching
        
        Args:
            tx_dict: Transaction dictionary
            phase: Validation phase (HTTP_POST, CHECK_TX, DELIVER_TX)
            
        Returns:
            Tuple of (conforms: bool, results: List[Dict])
        """
        tx_id = tx_dict.get('id', 'unknown')
        operation = tx_dict.get('operation', 'unknown')
        
        start_time = time.time()
        cache_hit = False
        conforms = False
        results = []
        
        try:
            t_cache_overhead_start = time.time()
            # Minimal invalidating pattern enforcement (fast-fail on conflicts)
            lock_keys = self._lock_keys_for(tx_dict)
            if phase == 'HTTP_POST' and lock_keys:
                acquired, info = self._acquire_locks(tx_id, lock_keys)
                if not acquired:
                    conflict_key = info.get('conflict_key') if info else 'unknown'
                    holder_tx = info.get('holder_tx_id') if info else 'unknown'
                    self.metrics.record_inflight_conflict(operation, conflict_key, holder_tx)
                    return False, [{'message': f'in_flight_conflict: {conflict_key} held by {holder_tx}'}]
            elif phase in ('CHECK_TX', 'DELIVER_TX') and lock_keys:
                # Keep locks alive while the tx progresses through phases
                self._refresh_locks(tx_id)

            # Soft race groups (do not block at HTTP_POST; decide at DELIVER_TX)
            race_keys = self._race_keys_for(tx_dict)
            if phase == 'HTTP_POST' and race_keys:
                self._mark_races(tx_id, race_keys)
                for rk in race_keys:
                    self.metrics.record_soft_race(operation, rk)
            elif phase in ('CHECK_TX', 'DELIVER_TX') and race_keys:
                self._refresh_races(tx_id)

            # Generate state-aware cache key
            state_hash = self._generate_state_hash(tx_dict, phase)
            
            # ═══════════════════════════════════════════════════════════════
            # Phase 1: Check state-aware cache
            # ═══════════════════════════════════════════════════════════════
            if self.cache_enabled:
                cached_result = self._get_from_cache(tx_id, phase, state_hash)
                if cached_result is not None:
                    cache_hit = True
                    conforms, results = cached_result
                    cache_overhead_ms = (time.time() - t_cache_overhead_start) * 1000
                    duration_ms = (time.time() - start_time) * 1000
                    
                    self.metrics.record_validation(
                        tx_id, operation, phase, 
                        duration_ms, cache_hit=True, success=conforms,
                        cache_overhead_ms=cache_overhead_ms
                    )
                    
                    # Release locks at final phase or upon failure
                    if phase == 'DELIVER_TX' or not conforms:
                        self._release_locks(tx_id)
                    return conforms, results
            
            # ═══════════════════════════════════════════════════════════════
            # Phase 2: Cache miss - perform validation
            # ═══════════════════════════════════════════════════════════════
            cache_logger.debug(
                f"[CACHE MISS] tx={tx_id[:16]}..., phase={phase}, "
                f"state={state_hash[:8]}..."
            )
            
            if not self.enabled:
                logger.warning("SHACL validation is disabled")
                return True, []
            
            # Convert to RDF and validate
            t_convert_start = time.time()
            turtle_data = self._convert_to_turtle(tx_dict)
            conversion_ms = (time.time() - t_convert_start) * 1000
            
            t_shacl_start = time.time()
            response = requests.post(
                f'{self.endpoint}/validate',
                json={
                    'shapeType': operation,
                    'data': turtle_data
                },
                timeout=self.timeout
            )
            shacl_request_ms = (time.time() - t_shacl_start) * 1000
            
            if response.status_code == 200:
                result = response.json()
                conforms = result.get('conforms', False)
                results = result.get('results', [])
                
                # Cache the result with state awareness
                if self.cache_enabled:
                    self._put_in_cache(tx_id, phase, state_hash, (conforms, results), tx_dict)
                
                duration_ms = (time.time() - start_time) * 1000
                
                self.metrics.record_validation(
                    tx_id, operation, phase,
                    duration_ms, cache_hit=False, success=conforms,
                    conversion_ms=conversion_ms, shacl_request_ms=shacl_request_ms
                )
                
                # Deliver-stage race outcome metrics and commit-time invalidation
                if phase == 'DELIVER_TX':
                    if race_keys:
                        self.metrics.record_deliver_outcome(conforms, operation, race_keys[0])
                    if conforms:
                        # Commit-time cache invalidation for affected entities
                        for dep in self._dependency_keys_for(tx_dict, phase):
                            # dep format: kind:id1:id2... we only use first two parts as (entity_type, entity_id)
                            parts = dep.split(':', 2)
                            if len(parts) >= 2:
                                entity_type = parts[0] if parts[0] != 'dep' else f"{parts[0]}:{parts[1]}"
                                entity_id = parts[2] if len(parts) == 3 else (parts[1] if parts[0] == 'asset' else '')
                                if entity_id:
                                    self.invalidate_cache_for_entity(entity_type, entity_id)
                    # Release soft race markers
                    self._release_races(tx_id)
                
                # Release locks at final phase or upon failure
                if phase == 'DELIVER_TX' or not conforms:
                    self._release_locks(tx_id)
                return conforms, results
            else:
                logger.error(f"SHACL validation failed: {response.status_code} - {response.text}")
                # On service error, release locks to avoid deadlocks
                self._release_locks(tx_id)
                self._release_races(tx_id)
                return False, [{'message': f'SHACL service error: {response.status_code}'}]
                
        except Exception as e:
            logger.error(f"Validation error: {e}")
            # On error, release locks to avoid deadlocks
            self._release_locks(tx_id)
            self._release_races(tx_id)
            return False, [{'message': str(e)}]
    
    def _convert_to_turtle(self, tx_dict: Dict[str, Any]) -> str:
        """Convert transaction to Turtle RDF format"""
        # Simplified RDF conversion - in production, use proper RDF library
        turtle_lines = []
        
        # Add prefixes
        turtle_lines.extend([
            "@prefix bdb: <http://bigchaindb.org/ns#> .",
            "@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .",
            "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .",
            ""
        ])
        
        # Add transaction data
        tx_id = tx_dict.get('id', 'unknown')
        operation = tx_dict.get('operation', 'unknown')
        
        turtle_lines.append(f"<http://bigchaindb.org/tx/{tx_id}> a bdb:Transaction ;")
        turtle_lines.append(f"    bdb:operation \"{operation}\" ;")
        turtle_lines.append(f"    bdb:version \"2.0\" ;")
        
        # Add metadata
        metadata = tx_dict.get('metadata', {})
        for key, value in metadata.items():
            if isinstance(value, str):
                turtle_lines.append(f"    bdb:{key} \"{value}\" ;")
        
        # Add asset id and top-level fields
        asset_root = tx_dict.get('asset', {})
        asset_id = asset_root.get('id')
        if isinstance(asset_id, str):
            turtle_lines.append(f"    bdb:asset_id \"{asset_id}\" ;")
        sell_tx_id = asset_root.get('sell_transaction_id')
        if isinstance(sell_tx_id, str):
            turtle_lines.append(f"    bdb:sell_transaction_id \"{sell_tx_id}\" ;")
        req_ret_id = asset_root.get('request_return_id')
        if isinstance(req_ret_id, str):
            turtle_lines.append(f"    bdb:request_return_id \"{req_ret_id}\" ;")

        # Add asset data
        asset_data = asset_root.get('data', {})
        for key, value in asset_data.items():
            if isinstance(value, str):
                turtle_lines.append(f"    bdb:{key} \"{value}\" ;")
        
        # Close the statement
        turtle_lines.append("    .")
        
        return "\n".join(turtle_lines)
    
    def clear_cache(self):
        """Clear all cached validation results"""
        with self._cache_lock:
            total_entries = sum(
                len(state_cache) 
                for phase_cache in self._cache.values() 
                for state_cache in phase_cache.values()
            )
            self._cache.clear()
            
        with self._dependency_lock:
            self._dependencies.clear()
            
        logger.info(f"Enhanced cache cleared: {total_entries} entries removed")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get comprehensive cache statistics"""
        with self._cache_lock:
            total_entries = sum(
                len(state_cache) 
                for phase_cache in self._cache.values() 
                for state_cache in phase_cache.values()
            )
            
            phase_stats = {}
            for phase, phase_cache in self._cache.items():
                phase_entries = sum(len(state_cache) for state_cache in phase_cache.values())
                phase_stats[phase] = {
                    'entries': phase_entries,
                    'state_hashes': len(phase_cache)
                }
        
        with self._dependency_lock:
            dependency_count = len(self._dependencies)
        
        return {
            'total_entries': total_entries,
            'cache_max_size': self.cache_max_size,
            'cache_utilization_percent': round(total_entries / self.cache_max_size * 100, 2),
            'cache_enabled': self.cache_enabled,
            'cache_ttl_seconds': self.cache_ttl,
            'phase_stats': phase_stats,
            'dependency_count': dependency_count,
            'metrics': self.metrics.get_stats()
        }


# Global instance
shacl_validator = StateAwareSHACLValidator()
