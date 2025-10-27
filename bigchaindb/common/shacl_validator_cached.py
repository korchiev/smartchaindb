"""
SHACL Validator Client with Performance Caching and Comprehensive Metrics

This enhanced version includes:
- In-memory validation result caching with configurable TTL
- Detailed performance metrics and profiling
- Comprehensive logging for debugging and analysis
- Thread-safe cache operations
- Cache effectiveness analytics
"""

import requests
import logging
import time
from threading import Lock
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, Any, Tuple, List, Optional
try:
    from bigchaindb import config
except ImportError:
    # Fallback for when config is not available (e.g., during Docker build)
    config = None

logger = logging.getLogger(__name__)
metrics_logger = logging.getLogger(__name__ + '.metrics')
cache_logger = logging.getLogger(__name__ + '.cache')


class ValidationMetrics:
    """
    Comprehensive metrics tracker for SHACL validation performance.
    """
    
    def __init__(self):
        self.lock = Lock()
        self.reset_metrics()
    
    def reset_metrics(self):
        """Reset all metrics to initial state."""
        with self.lock:
            self._data = {
                'total_validations': 0,
                'cache_hits': 0,
                'cache_misses': 0,
                'cache_expirations': 0,
                'cache_evictions': 0,
                'validation_errors': 0,
                'total_time_ms': 0.0,
                'min_time_ms': float('inf'),
                'max_time_ms': 0.0,
                
                # Detailed timing records
                'validation_records': [],  # (timestamp, tx_id, operation, phase, duration_ms, cache_hit, result)
                
                # Per-operation stats
                'by_operation': defaultdict(lambda: {
                    'total': 0,
                    'cache_hits': 0,
                    'cache_misses': 0,
                    'total_time_ms': 0.0,
                    'min_time_ms': float('inf'),
                    'max_time_ms': 0.0
                }),
                
                # Per-phase stats (HTTP_POST, CHECK_TX, DELIVER_TX)
                'by_phase': defaultdict(lambda: {
                    'total': 0,
                    'cache_hits': 0,
                    'cache_misses': 0,
                    'total_time_ms': 0.0
                }),
                
                'start_time': time.time()
            }
    
    def record_validation(self, tx_id: str, operation: str, phase: str, 
                         duration_ms: float, cache_hit: bool, success: bool):
        """Record a validation event."""
        with self.lock:
            self._data['total_validations'] += 1
            
            if cache_hit:
                self._data['cache_hits'] += 1
            else:
                self._data['cache_misses'] += 1
            
            if not success:
                self._data['validation_errors'] += 1
            
            self._data['total_time_ms'] += duration_ms
            self._data['min_time_ms'] = min(self._data['min_time_ms'], duration_ms)
            self._data['max_time_ms'] = max(self._data['max_time_ms'], duration_ms)
            
            # Record detailed event
            self._data['validation_records'].append({
                'timestamp': datetime.now().isoformat(),
                'tx_id': tx_id[:16] + '...',  # Truncate for privacy
                'operation': operation,
                'phase': phase,
                'duration_ms': round(duration_ms, 2),
                'cache_hit': cache_hit,
                'success': success
            })
            
            # Keep only last 1000 records to prevent memory bloat
            if len(self._data['validation_records']) > 1000:
                self._data['validation_records'] = self._data['validation_records'][-1000:]
            
            # Update per-operation stats
            op_stats = self._data['by_operation'][operation]
            op_stats['total'] += 1
            if cache_hit:
                op_stats['cache_hits'] += 1
            else:
                op_stats['cache_misses'] += 1
            op_stats['total_time_ms'] += duration_ms
            op_stats['min_time_ms'] = min(op_stats['min_time_ms'], duration_ms)
            op_stats['max_time_ms'] = max(op_stats['max_time_ms'], duration_ms)
            
            # Update per-phase stats
            phase_stats = self._data['by_phase'][phase]
            phase_stats['total'] += 1
            if cache_hit:
                phase_stats['cache_hits'] += 1
            else:
                phase_stats['cache_misses'] += 1
            phase_stats['total_time_ms'] += duration_ms
    
    def record_cache_event(self, event_type: str):
        """Record cache-specific events (expiration, eviction)."""
        with self.lock:
            if event_type == 'expiration':
                self._data['cache_expirations'] += 1
            elif event_type == 'eviction':
                self._data['cache_evictions'] += 1
    
    def get_summary(self) -> Dict[str, Any]:
        """Get comprehensive metrics summary."""
        with self.lock:
            total = self._data['total_validations']
            if total == 0:
                return {'message': 'No validations recorded yet'}
            
            cache_hits = self._data['cache_hits']
            cache_misses = self._data['cache_misses']
            cache_hit_rate = (cache_hits / total * 100) if total > 0 else 0
            
            total_time = self._data['total_time_ms']
            avg_time = total_time / total if total > 0 else 0
            
            # Calculate average times for cache hits vs misses
            hit_records = [r for r in self._data['validation_records'] if r['cache_hit']]
            miss_records = [r for r in self._data['validation_records'] if not r['cache_hit']]
            
            avg_hit_time = sum(r['duration_ms'] for r in hit_records) / len(hit_records) if hit_records else 0
            avg_miss_time = sum(r['duration_ms'] for r in miss_records) / len(miss_records) if miss_records else 0
            
            uptime = time.time() - self._data['start_time']
            
            summary = {
                'uptime_seconds': round(uptime, 2),
                'total_validations': total,
                'cache_hit_rate_percent': round(cache_hit_rate, 2),
                'cache_hits': cache_hits,
                'cache_misses': cache_misses,
                'cache_expirations': self._data['cache_expirations'],
                'cache_evictions': self._data['cache_evictions'],
                'validation_errors': self._data['validation_errors'],
                'performance': {
                    'total_time_ms': round(total_time, 2),
                    'avg_time_ms': round(avg_time, 2),
                    'min_time_ms': round(self._data['min_time_ms'], 2),
                    'max_time_ms': round(self._data['max_time_ms'], 2),
                    'avg_cache_hit_time_ms': round(avg_hit_time, 2),
                    'avg_cache_miss_time_ms': round(avg_miss_time, 2),
                    'time_saved_by_cache_ms': round((avg_miss_time - avg_hit_time) * cache_hits, 2) if cache_hits > 0 else 0
                },
                'by_operation': {},
                'by_phase': {},
                'recent_validations': self._data['validation_records'][-10:]  # Last 10
            }
            
            # Add per-operation stats
            for op, stats in self._data['by_operation'].items():
                op_total = stats['total']
                summary['by_operation'][op] = {
                    'total': op_total,
                    'cache_hit_rate_percent': round(stats['cache_hits'] / op_total * 100, 2) if op_total > 0 else 0,
                    'avg_time_ms': round(stats['total_time_ms'] / op_total, 2) if op_total > 0 else 0,
                    'min_time_ms': round(stats['min_time_ms'], 2),
                    'max_time_ms': round(stats['max_time_ms'], 2)
                }
            
            # Add per-phase stats
            for phase, stats in self._data['by_phase'].items():
                phase_total = stats['total']
                summary['by_phase'][phase] = {
                    'total': phase_total,
                    'cache_hit_rate_percent': round(stats['cache_hits'] / phase_total * 100, 2) if phase_total > 0 else 0,
                    'avg_time_ms': round(stats['total_time_ms'] / phase_total, 2) if phase_total > 0 else 0
                }
            
            return summary


class SHACLValidatorClient:
    """
    Enhanced SHACL validator client with caching and comprehensive metrics.
    
    Features:
    - In-memory result caching with configurable TTL
    - Detailed performance metrics and profiling
    - Thread-safe operations
    - Cache effectiveness analytics
    """
    
    def __init__(self, endpoint: Optional[str] = None, timeout: Optional[int] = None, phase: str = 'UNKNOWN'):
        """
        Initialize the SHACL validator client.
        
        Args:
            endpoint: URL of the SHACL microservice (default from config)
            timeout: HTTP request timeout in seconds (default from config)
            phase: Validation phase identifier (HTTP_POST, CHECK_TX, DELIVER_TX)
        """
        shacl_config = config.get('shacl', {}) if config else {}
        
        # Check environment variable for SHACL enablement
        import os
        env_enabled = os.getenv('BIGCHAINDB_SHACL_ENABLED', '').lower() in ('true', '1', 'yes')
        
        self.enabled = shacl_config.get('enabled', False) or env_enabled
        self.endpoint = endpoint or shacl_config.get('endpoint', 'http://shacleng:3000')
        self.timeout = timeout or shacl_config.get('timeout', 10)
        self.phase = phase
        
        # ═══════════════════════════════════════════════════════════════════
        # Cache Configuration
        # ═══════════════════════════════════════════════════════════════════
        self.cache_enabled = shacl_config.get('cache_enabled', True)
        self.cache_ttl = shacl_config.get('cache_ttl', 60)  # seconds
        self.cache_max_size = shacl_config.get('cache_max_size', 1000)
        
        # Cache storage: {tx_id: (timestamp, result)}
        self._cache = {}
        self._cache_lock = Lock()
        
        # Metrics
        self.metrics = ValidationMetrics()
        
        logger.info(
            f"SHACL validator initialized: "
            f"enabled={self.enabled}, "
            f"endpoint={self.endpoint}, "
            f"cache_enabled={self.cache_enabled} "
            f"(TTL={self.cache_ttl}s, max_size={self.cache_max_size}), "
            f"phase={self.phase}"
        )
    
    def validate_transaction(self, tx_dict: Dict[str, Any]) -> Tuple[bool, List[Dict[str, Any]]]:
        """
        Validate a transaction with caching and performance tracking.
        
        Args:
            tx_dict: Transaction dictionary
            
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
            # ═══════════════════════════════════════════════════════════════
            # Phase 1: Check cache
            # ═══════════════════════════════════════════════════════════════
            if self.cache_enabled:
                cached_result = self._get_from_cache(tx_id)
                if cached_result is not None:
                    cache_hit = True
                    conforms, results = cached_result
                    duration_ms = (time.time() - start_time) * 1000
                    
                    cache_logger.debug(
                        f"[CACHE HIT] tx={tx_id[:16]}..., "
                        f"operation={operation}, "
                        f"phase={self.phase}, "
                        f"time={duration_ms:.2f}ms"
                    )
                    
                    self.metrics.record_validation(
                        tx_id, operation, self.phase, 
                        duration_ms, cache_hit=True, success=conforms
                    )
                    
                    return conforms, results
            
            # ═══════════════════════════════════════════════════════════════
            # Phase 2: Cache miss - perform validation
            # ═══════════════════════════════════════════════════════════════
            cache_logger.debug(
                f"[CACHE MISS] tx={tx_id[:16]}..., "
                f"operation={operation}, "
                f"phase={self.phase}"
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
                
                # Cache the result
                if self.cache_enabled:
                    self._put_in_cache(tx_id, (conforms, results))
                
                duration_ms = (time.time() - start_time) * 1000
                
                metrics_logger.info(
                    f"[VALIDATION] tx={tx_id[:16]}..., "
                    f"operation={operation}, "
                    f"phase={self.phase}, "
                    f"time={duration_ms:.2f}ms, "
                    f"cache_hit={cache_hit}, "
                    f"result={'PASS' if conforms else 'FAIL'}"
                )
                
                self.metrics.record_validation(
                    tx_id, operation, self.phase,
                    duration_ms, cache_hit=False, success=conforms
                )
                
                return conforms, results
            else:
                logger.error(f"SHACL service returned status {response.status_code}")
                duration_ms = (time.time() - start_time) * 1000
                self.metrics.record_validation(
                    tx_id, operation, self.phase,
                    duration_ms, cache_hit=False, success=False
                )
                return False, [{"message": f"SHACL service error: {response.status_code}"}]
        
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(f"SHACL validation exception: {e}", exc_info=True)
            self.metrics.record_validation(
                tx_id, operation, self.phase,
                duration_ms, cache_hit=False, success=False
            )
            return False, [{"message": f"Validation error: {str(e)}"}]
    
    def _get_from_cache(self, tx_id: str) -> Optional[Tuple[bool, List[Dict[str, Any]]]]:
        """Retrieve validation result from cache if not expired."""
        with self._cache_lock:
            if tx_id in self._cache:
                timestamp, result = self._cache[tx_id]
                age = time.time() - timestamp
                
                if age < self.cache_ttl:
                    return result
                else:
                    # Expired
                    del self._cache[tx_id]
                    self.metrics.record_cache_event('expiration')
                    cache_logger.debug(
                        f"[CACHE EXPIRED] tx={tx_id[:16]}..., age={age:.2f}s"
                    )
        
        return None
    
    def _put_in_cache(self, tx_id: str, result: Tuple[bool, List[Dict[str, Any]]]):
        """Store validation result in cache with LRU eviction."""
        with self._cache_lock:
            # Clean up if cache is too large
            if len(self._cache) >= self.cache_max_size:
                # Remove oldest 10% of entries (LRU-like)
                sorted_items = sorted(self._cache.items(), key=lambda x: x[1][0])
                to_remove = max(1, int(self.cache_max_size * 0.1))
                
                for old_tx_id, _ in sorted_items[:to_remove]:
                    del self._cache[old_tx_id]
                    self.metrics.record_cache_event('eviction')
                
                cache_logger.info(
                    f"[CACHE EVICTION] Removed {to_remove} old entries, "
                    f"cache_size={len(self._cache)}"
                )
            
            self._cache[tx_id] = (time.time(), result)
            cache_logger.debug(
                f"[CACHE STORE] tx={tx_id[:16]}..., cache_size={len(self._cache)}"
            )
    
    def _convert_to_turtle(self, tx_dict: Dict[str, Any]) -> str:
        """
        Convert a BigchainDB transaction to RDF Turtle format.
        
        Args:
            tx_dict: Transaction dictionary
            
        Returns:
            Transaction serialized as Turtle RDF string
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
        
        # Add inputs count
        inputs = tx_dict.get('inputs', [])
        if inputs:
            turtle += f'    bdb:inputs "{len(inputs)}"^^xsd:integer ;\n'
        
        # Add outputs count
        outputs = tx_dict.get('outputs', [])
        if outputs:
            turtle += f'    bdb:outputs "{len(outputs)}"^^xsd:integer ;\n'
        
        # Remove trailing semicolon and newline, add period
        turtle = turtle.rstrip(';\n') + ' .\n'
        
        return turtle
    
    def _serialize_asset(self, asset: Dict[str, Any], operation: str) -> str:
        """Serialize asset field to Turtle."""
        turtle = ""
        
        # For CREATE, asset has 'data' with nested fields
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
                elif isinstance(value, list):
                    # Handle lists (e.g., capability lists)
                    list_str = ', '.join(str(v) for v in value)
                    turtle += f'            bdb:{key} "{list_str}" ;\n'
            
            turtle = turtle.rstrip(';\n') + '\n'
            turtle += "        ]\n"
            turtle += "    ] ;\n"
        
        # For ADVERTISEMENT, BUY_OFFER, SELL: asset has 'id' and optional 'data'
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
                # Check if it looks like a datetime string
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
                # Skip complex nested structures for now
                logger.debug(f"Skipping complex metadata field: {key}")
            elif value is None:
                # Skip null values
                pass
        
        turtle = turtle.rstrip(';\n') + '\n'
        turtle += "    ] ;\n"
        
        return turtle
    
    def clear_cache(self):
        """Clear all cached validation results."""
        with self._cache_lock:
            cache_size = len(self._cache)
            self._cache.clear()
            logger.info(f"Cache cleared: {cache_size} entries removed")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get current cache statistics."""
        with self._cache_lock:
            return {
                'cache_size': len(self._cache),
                'cache_max_size': self.cache_max_size,
                'cache_utilization_percent': round(len(self._cache) / self.cache_max_size * 100, 2),
                'cache_enabled': self.cache_enabled,
                'cache_ttl_seconds': self.cache_ttl
            }
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get comprehensive performance metrics."""
        return self.metrics.get_summary()
    
    def health_check(self) -> bool:
        """Check if SHACL service is available."""
        if not self.enabled:
            return True
        
        try:
            response = requests.get(f'{self.endpoint}/', timeout=2)
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"SHACL health check failed: {e}")
            return False


# Global singleton instance
_shacl_validator = None


def get_shacl_validator(phase: str = 'UNKNOWN') -> SHACLValidatorClient:
    """
    Get or create the global SHACL validator instance.
    
    Args:
        phase: Validation phase identifier
    
    Returns:
        SHACLValidatorClient instance
    """
    global _shacl_validator
    if _shacl_validator is None:
        _shacl_validator = SHACLValidatorClient(phase=phase)
    return _shacl_validator

