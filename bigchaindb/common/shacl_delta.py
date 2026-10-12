"""SHACL+Δ cache: reuse a SHACL verdict only when dependency *values* match.

Cache key is (tx_id, dependency-state-hash). The hash covers the referenced
prior transactions' operation/asset/metadata, not just their IDs. A committed
transaction invalidates every entry that listed that tx (or its deps) as a
dependency.
"""
import hashlib
import json
import logging
import threading
import time
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

CacheEntry = Tuple[float, bool, List[Dict[str, Any]]]


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

    Always includes the tx id and its dependency ids, plus marketplace
    invalidation-pattern extras (asset on SELL/ADV/TRANSFER, offer on SELL).
    """
    found: List[str] = []

    def add(value: Any) -> None:
        if isinstance(value, str) and value and value not in found:
            found.append(value)

    add(tx_dict.get("id"))
    for dep_id in dependency_ids(tx_dict):
        add(dep_id)

    op = tx_dict.get("operation")
    asset = tx_dict.get("asset") or {}
    data = asset.get("data") if isinstance(asset.get("data"), dict) else {}
    if op in ("ADVERTISEMENT", "TRANSFER", "SELL", "CREATE"):
        add(asset.get("id") or data.get("id"))
    elif op == "UPDATE_ADV":
        add(data.get("id") or asset.get("id"))
    if op == "SELL":
        add(data.get("buy_offer_id"))
    return found


def _tx_as_dict(tx: Any) -> Optional[Dict[str, Any]]:
    if tx is None:
        return None
    if hasattr(tx, "to_dict"):
        return tx.to_dict()
    if isinstance(tx, dict):
        return tx
    return None


def collect_dep_state(bigchain: Any, tx_dict: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Load referenced txs and keep the fields that affect SHACL state checks."""
    parts: List[Dict[str, Any]] = []
    getter = getattr(bigchain, "get_transaction", None)
    for dep_id in dependency_ids(tx_dict):
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
        if dep.get("operation") == "ADVERTISEMENT":
            status_fn = getattr(bigchain, "get_effective_advertisement_status", None)
            if callable(status_fn):
                part["effective_status"] = status_fn(dep.get("id") or dep_id)
            else:
                part["effective_status"] = (dep.get("metadata") or {}).get("status")
        parts.append(part)
    return parts


def hash_dep_state(parts: List[Dict[str, Any]]) -> str:
    canonical = json.dumps(parts, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def compute_dep_state_hash(bigchain: Any, tx_dict: Dict[str, Any]) -> str:
    return hash_dep_state(collect_dep_state(bigchain, tx_dict))


class SHACLDeltaCache:
    """In-process memo of SHACL verdicts keyed by tx id × dependency values."""

    def __init__(self, max_size: int = 2048, ttl: Optional[float] = None):
        self.max_size = max_size
        self.ttl = ttl
        self._store: Dict[Tuple[str, str], CacheEntry] = {}
        self._index: Dict[str, Set[Tuple[str, str]]] = {}
        self._lock = threading.Lock()
        self.hits = 0
        self.misses = 0
        self.invalidations = 0

    def get(self, tx_id: str, dep_hash: str) -> Optional[Tuple[bool, List[Dict[str, Any]]]]:
        key = (tx_id, dep_hash)
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                self.misses += 1
                return None
            ts, conforms, results = entry
            if self.ttl is not None and (time.time() - ts) > self.ttl:
                self._drop_locked(key)
                self.misses += 1
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
    ) -> None:
        key = (tx_id, dep_hash)
        with self._lock:
            if len(self._store) >= self.max_size and key not in self._store:
                self._evict_one_locked()
            self._store[key] = (time.time(), conforms, list(results))
            for entity in set(list(dep_ids) + [tx_id]):
                if not entity:
                    continue
                self._index.setdefault(entity, set()).add(key)

    def invalidate_ids(self, entity_ids: Iterable[str]) -> int:
        removed = 0
        with self._lock:
            for entity in set(entity_ids):
                if not entity:
                    continue
                keys = list(self._index.pop(entity, set()))
                for key in keys:
                    if key in self._store:
                        del self._store[key]
                        removed += 1
                    self._forget_key_locked(key)
        if removed:
            self.invalidations += removed
            logger.debug("SHACL+Δ invalidated %s cache entries", removed)
        return removed

    def on_tx_committed(self, tx_dict: Dict[str, Any]) -> int:
        return self.invalidate_ids(affected_ids(tx_dict))

    def stats(self) -> Dict[str, int]:
        with self._lock:
            return {
                "size": len(self._store),
                "hits": self.hits,
                "misses": self.misses,
                "invalidations": self.invalidations,
            }

    def clear(self) -> None:
        with self._lock:
            self._store.clear()
            self._index.clear()
            self.hits = 0
            self.misses = 0
            self.invalidations = 0

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
