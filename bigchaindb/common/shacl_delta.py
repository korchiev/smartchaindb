"""SHACL+Δ cache: reuse a SHACL verdict only when dependency *values* match.

Cache key is (tx_id, dependency-state-hash). The hash covers the referenced
prior transactions' operation/asset/metadata, not just their IDs. A committed
transaction invalidates entries indexed by the entities it writes or whose
derived-query answers it changes. Reading an entity does not itself change it.
"""
import hashlib
import json
import logging
import re
import threading
import time
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

CacheEntry = Tuple[float, bool, List[Dict[str, Any]], Optional[float]]


class ProjectionUnavailable(ValueError):
    """A required query could not be observed; do not reuse a verdict."""


def _nested(d: Any, *path: str) -> Any:
    cur = d
    for key in path:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    return cur


def dependency_ids(tx_dict: Dict[str, Any]) -> List[str]:
    """IDs of prior txs whose *values* this operation's SHACL state depends on."""
    op = tx_dict.get("operation")
    asset = tx_dict.get("asset") or {}
    data = asset.get("data") if isinstance(asset.get("data"), dict) else {}
    found: List[str] = []

    def add(value: Any) -> None:
        if isinstance(value, str) and value and value not in found:
            found.append(value)

    if op == "BUY_OFFER":
        add(data.get("advertisement_id"))
    elif op == "SELL":
        add(data.get("buy_offer_id"))
    elif op == "REQUEST_RETURN":
        add(data.get("sell_transaction_id"))
    elif op == "SELLER_ACCEPT_RETURN":
        add(data.get("request_return_id"))
    elif op == "UPDATE_ADV":
        add(data.get("id") or asset.get("id"))
    elif op in ("ADVERTISEMENT", "TRANSFER"):
        add(asset.get("id"))
    return found


def affected_ids(tx_dict: Dict[str, Any]) -> List[str]:
    """Entity ids whose cached verdicts a committed tx can change.

    Include writes and derived-query effects, not everything a tx reads.
    In particular, an offer reads an advertisement but does not change it.
    """
    found: List[str] = []

    def add(value: Any) -> None:
        if isinstance(value, str) and value and value not in found:
            found.append(value)

    add(tx_dict.get("id"))

    op = tx_dict.get("operation")
    asset = tx_dict.get("asset") or {}
    data = asset.get("data") if isinstance(asset.get("data"), dict) else {}
    if op in ("ADVERTISEMENT", "TRANSFER", "SELL", "CREATE"):
        add(asset.get("id") or data.get("id"))
    elif op == "UPDATE_ADV":
        add(data.get("id") or asset.get("id"))
    if op == "SELL":
        add(data.get("buy_offer_id"))
    if op == "REQUEST_RETURN":
        add(data.get("sell_transaction_id"))
    if op == "SELLER_ACCEPT_RETURN":
        add(data.get("request_return_id"))
    return found


def _tx_as_dict(tx: Any) -> Optional[Dict[str, Any]]:
    if tx is None:
        return None
    if hasattr(tx, "to_dict"):
        return tx.to_dict()
    if isinstance(tx, dict):
        return tx
    return None


# Facts the state checker reads that are *not* stored on the dependency tx
# itself: the exclusivity queries (one SELL per offer, one return request per
# sale, one acceptance per request) and the open-advertisement uniqueness for
# an asset. (operation of the dependency) -> (committed operation that would
# change the fact, field that points back at the dependency).
DERIVED_FACTS: Dict[str, Tuple[str, str]] = {
    "BUY_OFFER": ("SELL", "asset.data.buy_offer_id"),
    "SELL": ("REQUEST_RETURN", "asset.data.sell_transaction_id"),
    "REQUEST_RETURN": ("SELLER_ACCEPT_RETURN", "asset.data.request_return_id"),
}


def _referencing_ids(bigchain: Any, operation: str, field: Any, value: str) -> Optional[List[str]]:
    """Ids of committed ``operation`` txs whose ``field`` (or any of several
    fields) equals ``value``; None when no database connection is available."""
    conn = getattr(bigchain, "connection", None)
    if conn is None:
        return None
    if isinstance(field, (list, tuple)):
        flt = {"operation": operation, "$or": [{f: value} for f in field]}
    else:
        flt = {"operation": operation, field: value}
    try:
        cursor = conn.run(conn.collection("transactions").find(flt, {"id": 1, "_id": 0}))
        return sorted(doc["id"] for doc in cursor if doc.get("id"))
    except Exception as exc:  # pragma: no cover - backend specific
        logger.debug("derived fact lookup failed: %s", exc)
        return None


def collect_dep_state(bigchain: Any, tx_dict: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Load referenced txs and keep the facts the SHACL state checks read.

    For each dependency: its own operation/asset/metadata, plus the derived
    facts (effective advertisement status, exclusivity counters, open ads on
    the asset) that the sidecar queries. The cache key hashes this list, so a
    verdict is reused only when every fact the checker read is unchanged.
    """
    parts: List[Dict[str, Any]] = []
    getter = getattr(bigchain, "get_transaction", None)
    tx_op = tx_dict.get("operation")
    queue = list(dependency_ids(tx_dict))
    seen: Set[str] = set()
    while queue:
        dep_id = queue.pop(0)
        if dep_id in seen:
            continue
        seen.add(dep_id)
        raw = getter(dep_id) if getter else None
        dep = _tx_as_dict(raw)
        if dep is None:
            parts.append({"id": dep_id, "missing": True})
            continue
        part = {
            "id": dep.get("id"),
            "operation": dep.get("operation"),
            "asset": dep.get("asset"),
            "metadata": dep.get("metadata"),
        }
        dep_op = dep.get("operation")
        if dep_op == "ADVERTISEMENT":
            status_fn = getattr(bigchain, "get_effective_advertisement_status", None)
            if callable(status_fn):
                part["effective_status"] = status_fn(dep.get("id") or dep_id)
            else:
                part["effective_status"] = (dep.get("metadata") or {}).get("status")
            # The checker derives the status from the UPDATE_ADV chain; list it
            # so those reads are part of the projection.
            part["update_ids"] = _referencing_ids(
                bigchain, "UPDATE_ADV", ("asset.id", "asset.data.id"), dep_id)
        if dep_op in DERIVED_FACTS:
            op, field = DERIVED_FACTS[dep_op]
            part["referenced_by"] = _referencing_ids(bigchain, op, field, dep_id)
        if dep_op == "CREATE" and tx_op in ("ADVERTISEMENT", "TRANSFER"):
            part["open_ads"] = _referencing_ids(bigchain, "ADVERTISEMENT", "asset.id", dep_id)
        # Transitive dependency: a SELL's verdict also depends on the status
        # of the advertisement its offer points at.
        if dep_op == "BUY_OFFER" and tx_op == "SELL":
            offer_data = _nested(dep, "asset", "data") or {}
            adv_id = offer_data.get("advertisement_id") or (dep.get("asset") or {}).get("advertisement_id")
            if isinstance(adv_id, str) and adv_id:
                queue.append(adv_id)
        parts.append(part)
    return parts


def dep_ids_from_parts(parts: List[Dict[str, Any]]) -> List[str]:
    """Every entity id the projection covers (direct and transitive deps)."""
    return [p["id"] for p in parts if isinstance(p.get("id"), str) and p["id"]]


_HEX64 = re.compile(r"[0-9a-f]{64}")


def projection_ids(parts: List[Dict[str, Any]]) -> Set[str]:
    """All transaction ids mentioned anywhere in the dependency projection."""
    return set(_HEX64.findall(json.dumps(parts, sort_keys=True, default=str)))


def compute_dep_state(bigchain: Any, tx_dict: Dict[str, Any]) -> Tuple[str, List[str], Set[str]]:
    """(dependency hash, dependency ids to index under, ids covered by the projection)."""
    parts = collect_dep_state(bigchain, tx_dict)
    if any(p.get(key) is None for p in parts
           for key in ("update_ids", "referenced_by", "open_ads") if key in p):
        raise ProjectionUnavailable("A required dependency query is unavailable")
    return hash_dep_state(parts), dep_ids_from_parts(parts), projection_ids(parts)


def hash_dep_state(parts: List[Dict[str, Any]]) -> str:
    canonical = json.dumps(parts, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def compute_dep_state_hash(bigchain: Any, tx_dict: Dict[str, Any]) -> str:
    return hash_dep_state(collect_dep_state(bigchain, tx_dict))


POLICIES = ("delta", "entity", "flush")


class SHACLDeltaCache:
    """In-process memo of SHACL verdicts keyed by tx id × dependency values.

    ``policy`` selects the invalidation baseline the evaluation compares:

    * ``delta``  (default): key is (tx id, hash of dependency *values*); a
      commit drops entries indexed under its affected entity ids.
    * ``entity``: like ``delta`` for invalidation, but the lookup ignores the
      dependency hash, so a verdict is reused whenever *any* verdict for the
      tx id exists. Sound only where every relevant commit reaches
      ``on_tx_committed`` (the ABCI process); the web process never sees
      commits, so this policy can serve stale verdicts there.
    * ``flush``: a commit clears the whole cache.
    """

    def __init__(self, max_size: int = 2048, ttl: Optional[float] = None, policy: str = "delta"):
        self.max_size = max_size
        self.ttl = ttl
        self.policy = policy if policy in POLICIES else "delta"
        self._store: Dict[Tuple[str, str], CacheEntry] = {}
        self._index: Dict[str, Set[Tuple[str, str]]] = {}
        self._lock = threading.Lock()
        self._reset_counters_locked()

    def _reset_counters_locked(self) -> None:
        self.hits = 0
        # misses = cold_misses + dep_change_misses + ttl/context expirations
        self.misses = 0
        self.cold_misses = 0          # no verdict for this tx id at all
        self.dep_change_misses = 0    # verdict exists, but dependency values differ
        self.ttl_expirations = 0
        self.context_expirations = 0  # time-bounded verdict no longer applies
        # invalidations = retirements + dep_invalidations
        self.invalidations = 0
        self.retirements = 0          # committed tx's own verdict removed
        self.dep_invalidations = 0    # another tx's verdict removed: a dependency changed
        self.superseded = 0           # stale verdict replaced after a dep-change miss
        self.evictions = 0            # capacity eviction
        self.flushes = 0              # policy=flush: whole-cache clears on commit
        self.entity_hash_mismatch_hits = 0  # policy=entity: reused despite changed dep values

    def get(self, tx_id: str, dep_hash: str, validation_time: Optional[float] = None) -> Optional[Tuple[bool, List[Dict[str, Any]]]]:
        key = (tx_id, dep_hash)
        with self._lock:
            if self.policy == "entity":
                # Entity-level baseline: any verdict for this tx id counts.
                existing = self._index.get(tx_id)
                if existing and key not in self._store:
                    key = next(iter(existing))
                    self.entity_hash_mismatch_hits += 1
            entry = self._store.get(key)
            if entry is None:
                self.misses += 1
                if self._index.get(tx_id):
                    self.dep_change_misses += 1
                else:
                    self.cold_misses += 1
                return None
            ts, conforms, results, valid_until = entry
            now = time.time() if validation_time is None else validation_time
            if valid_until is not None and now >= valid_until:
                self._drop_locked(key)
                self.misses += 1
                self.context_expirations += 1
                return None
            if self.ttl is not None and (time.time() - ts) > self.ttl:
                self._drop_locked(key)
                self.misses += 1
                self.ttl_expirations += 1
                return None
            self.hits += 1
            return conforms, results

    def put(
        self,
        tx_id: str,
        dep_hash: str,
        conforms: bool,
        results: List[Dict[str, Any]],
        dep_ids: Iterable[str],
        valid_until: Optional[float] = None,
    ) -> None:
        key = (tx_id, dep_hash)
        with self._lock:
            # A tx id carries at most one verdict: drop any entry whose
            # dependency hash no longer matches (it was already a dep-change miss).
            for old in [k for k in self._index.get(tx_id, set()) if k != key]:
                self._drop_locked(old)
                self.superseded += 1
            if len(self._store) >= self.max_size and key not in self._store:
                self._evict_one_locked()
                self.evictions += 1
            self._store[key] = (time.time(), conforms, list(results), valid_until)
            for entity in set(list(dep_ids) + [tx_id]):
                if not entity:
                    continue
                self._index.setdefault(entity, set()).add(key)

    def invalidate_ids(self, entity_ids: Iterable[str], committed_tx_id: Optional[str] = None) -> int:
        removed = 0
        retired = 0
        with self._lock:
            for entity in set(entity_ids):
                if not entity:
                    continue
                keys = list(self._index.pop(entity, set()))
                for key in keys:
                    if key in self._store:
                        del self._store[key]
                        removed += 1
                        if key[0] == committed_tx_id:
                            retired += 1
                    self._forget_key_locked(key)
            self.invalidations += removed
            self.retirements += retired
            self.dep_invalidations += removed - retired
        if removed:
            logger.debug("SHACL+Δ removed %s cache entries (%s retired)", removed, retired)
        return removed

    def on_tx_committed(self, tx_dict: Dict[str, Any]) -> int:
        if self.policy == "flush":
            committed = tx_dict.get("id")
            with self._lock:
                removed = len(self._store)
                retired = sum(1 for key in self._store if key[0] == committed)
                self._store.clear()
                self._index.clear()
                self.flushes += 1
                self.invalidations += removed
                self.retirements += retired
                self.dep_invalidations += removed - retired
            return removed
        return self.invalidate_ids(affected_ids(tx_dict), committed_tx_id=tx_dict.get("id"))

    def memory_estimate(self) -> Dict[str, int]:
        """Approximate resident bytes of the store and reverse index.

        Serialized size of entries plus Python container overhead; an upper
        bound on what the cache itself holds, not the interpreter's RSS.
        """
        import sys
        with self._lock:
            entries = len(self._store)
            payload = 0
            for key, (ts, conforms, results, valid_until) in self._store.items():
                payload += len(key[0]) + len(key[1]) + 8 + 1
                payload += len(json.dumps(results, default=str)) if results else 0
                payload += sys.getsizeof(key) + sys.getsizeof((ts, conforms, results, valid_until))
            index = sum(sys.getsizeof(k) + sys.getsizeof(v) + len(v) * 72 for k, v in self._index.items())
            return {
                "entries": entries,
                "index_entities": len(self._index),
                "store_bytes": payload + sys.getsizeof(self._store),
                "index_bytes": index + sys.getsizeof(self._index),
                "bytes_per_entry": int((payload + index) / entries) if entries else 0,
            }

    def stats(self) -> Dict[str, int]:
        with self._lock:
            return {
                "policy": self.policy,
                "size": len(self._store),
                "index_entities": len(self._index),
                "hits": self.hits,
                "misses": self.misses,
                "cold_misses": self.cold_misses,
                "dep_change_misses": self.dep_change_misses,
                "ttl_expirations": self.ttl_expirations,
                "context_expirations": self.context_expirations,
                "invalidations": self.invalidations,
                "retirements": self.retirements,
                "dep_invalidations": self.dep_invalidations,
                "superseded": self.superseded,
                "evictions": self.evictions,
                "flushes": self.flushes,
                "entity_hash_mismatch_hits": self.entity_hash_mismatch_hits,
            }

    def clear(self) -> None:
        with self._lock:
            self._store.clear()
            self._index.clear()
            self._reset_counters_locked()

    def _drop_locked(self, key: Tuple[str, str]) -> None:
        self._store.pop(key, None)
        self._forget_key_locked(key)

    def _forget_key_locked(self, key: Tuple[str, str]) -> None:
        empty: List[str] = []
        for entity, keys in self._index.items():
            keys.discard(key)
            if not keys:
                empty.append(entity)
        for entity in empty:
            self._index.pop(entity, None)

    def _evict_one_locked(self) -> None:
        if not self._store:
            return
        oldest = min(self._store.items(), key=lambda item: item[1][0])[0]
        self._drop_locked(oldest)


class ConflictTable(object):
    """Track in-flight validations and abort them when a shared dep commits.

    Generation counters per entity: if any dependency's generation changes
    between begin() and the SHACL HTTP return, the verdict is stale.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._generation = {}  # type: Dict[str, int]
        self._inflight = {}  # type: Dict[str, Tuple[List[str], Dict[str, int]]]
        self.detected = 0
        self.aborted = 0

    def begin(self, tx_id: str, dep_ids: Iterable[str]) -> Dict[str, int]:
        deps = [d for d in dep_ids if d]
        with self._lock:
            snapshot = {d: self._generation.get(d, 0) for d in deps}
            self._inflight[tx_id] = (list(deps), snapshot)
            return dict(snapshot)

    def changed(self, tx_id: str) -> bool:
        with self._lock:
            rec = self._inflight.get(tx_id)
            if rec is None:
                return False
            dep_ids, snapshot = rec
            for dep_id in dep_ids:
                if self._generation.get(dep_id, 0) != snapshot.get(dep_id, 0):
                    self.detected += 1
                    return True
            return False

    def abort_if_changed(self, tx_id: str) -> Optional[str]:
        if self.changed(tx_id):
            self.aborted += 1
            return "dependency changed during validation"
        return None

    def end(self, tx_id: str) -> None:
        with self._lock:
            self._inflight.pop(tx_id, None)

    def on_tx_committed(self, tx_dict: Dict[str, Any]) -> List[str]:
        ids = set(affected_ids(tx_dict))
        aborted = []
        with self._lock:
            for entity in ids:
                if not entity:
                    continue
                self._generation[entity] = self._generation.get(entity, 0) + 1
            for inflight_id, (dep_ids, _snapshot) in self._inflight.items():
                for dep_id in dep_ids:
                    if dep_id in ids:
                        aborted.append(inflight_id)
                        break
            if aborted:
                self.detected += len(aborted)
        return aborted

    def stats(self) -> Dict[str, int]:
        with self._lock:
            return {
                "inflight": len(self._inflight),
                "detected": self.detected,
                "aborted": self.aborted,
            }

    def clear(self) -> None:
        with self._lock:
            self._generation.clear()
            self._inflight.clear()
            self.detected = 0
            self.aborted = 0
