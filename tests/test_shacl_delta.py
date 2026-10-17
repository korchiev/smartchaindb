"""Unit tests for SHACL+Δ value hashing and DeliverTx invalidation."""
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_delta():
    spec = importlib.util.spec_from_file_location(
        "shacl_delta_under_test",
        str(ROOT / "bigchaindb" / "common" / "shacl_delta.py"),
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


delta = _load_delta()


def test_buy_offer_depends_on_advertisement_id():
    tx = {
        "id": "offer1",
        "operation": "BUY_OFFER",
        "asset": {"data": {"advertisement_id": "adv1", "id": "asset1"}},
    }
    assert delta.dependency_ids(tx) == ["adv1"]


def test_update_adv_depends_on_advertisement_id():
    tx = {
        "id": "upd1",
        "operation": "UPDATE_ADV",
        "asset": {"id": "adv1", "data": {"id": "adv1"}},
    }
    assert delta.dependency_ids(tx) == ["adv1"]


def test_create_has_no_dependencies():
    assert delta.dependency_ids({"id": "c1", "operation": "CREATE", "asset": {"data": {}}}) == []


def test_hash_changes_when_dependency_values_change():
    open_adv = {
        "id": "adv1",
        "operation": "ADVERTISEMENT",
        "asset": {"id": "asset1"},
        "metadata": {"status": "OPEN", "price": "100"},
    }
    closed_adv = dict(open_adv)
    closed_adv["metadata"] = {"status": "CLOSED", "price": "100"}

    class Store:
        def __init__(self, row):
            self.row = row

        def get_transaction(self, _id):
            return self.row

    offer = {
        "id": "offer1",
        "operation": "BUY_OFFER",
        "asset": {"data": {"advertisement_id": "adv1"}},
    }
    h_open = delta.compute_dep_state_hash(Store(open_adv), offer)
    h_closed = delta.compute_dep_state_hash(Store(closed_adv), offer)
    assert h_open != h_closed
    assert delta.collect_dep_state(Store(open_adv), offer)[0]["id"] == "adv1"
    assert delta.collect_dep_state(Store(closed_adv), offer)[0]["id"] == "adv1"


def test_hash_stable_for_identical_values():
    parts = [{"id": "adv1", "metadata": {"status": "OPEN"}}]
    assert delta.hash_dep_state(parts) == delta.hash_dep_state(list(parts))


def test_cache_hit_then_invalidate_on_commit():
    cache = delta.SHACLDeltaCache()
    offer = {
        "id": "offer1",
        "operation": "BUY_OFFER",
        "asset": {"data": {"advertisement_id": "adv1"}},
    }
    dep_hash = "abc123"
    cache.put("offer1", dep_hash, True, [], delta.dependency_ids(offer))
    assert cache.get("offer1", dep_hash) == (True, [])
    assert cache.hits == 1

    removed = cache.on_tx_committed(
        {"id": "adv1", "operation": "ADVERTISEMENT", "asset": {"id": "asset1"}}
    )
    assert removed >= 1
    assert cache.get("offer1", dep_hash) is None
    assert cache.misses == 1


def test_update_adv_commit_invalidates_offer_cache():
    cache = delta.SHACLDeltaCache()
    cache.put("offer1", "h1", True, [], ["adv1"])
    cache.on_tx_committed(
        {
            "id": "upd1",
            "operation": "UPDATE_ADV",
            "asset": {"id": "adv1", "data": {"id": "adv1"}},
        }
    )
    assert cache.get("offer1", "h1") is None


def test_affected_ids_include_invalidation_pattern_extras():
    sell = {
        "id": "sell1",
        "operation": "SELL",
        "asset": {"id": "asset1", "data": {"id": "asset1", "buy_offer_id": "offer1"}},
    }
    ids = delta.affected_ids(sell)
    assert "sell1" in ids
    assert "offer1" in ids
    assert "asset1" in ids


def test_conflict_table_aborts_after_shared_dep_commit():
    table = delta.ConflictTable()
    offer = {
        "id": "offer1",
        "operation": "BUY_OFFER",
        "asset": {"data": {"advertisement_id": "adv1"}},
    }
    table.begin("offer1", delta.dependency_ids(offer))
    assert table.changed("offer1") is False
    aborted = table.on_tx_committed(
        {
            "id": "upd1",
            "operation": "UPDATE_ADV",
            "asset": {"id": "adv1", "data": {"id": "adv1"}},
        }
    )
    assert "offer1" in aborted
    assert table.changed("offer1") is True
    assert table.abort_if_changed("offer1") is not None
    table.end("offer1")
    assert table.stats()["aborted"] >= 1


def test_missing_dependency_is_hashed_as_missing():
    class Empty:
        def get_transaction(self, _id):
            return None

    offer = {
        "id": "offer1",
        "operation": "BUY_OFFER",
        "asset": {"data": {"advertisement_id": "nope"}},
    }
    parts = delta.collect_dep_state(Empty(), offer)
    assert parts == [{"id": "nope", "missing": True}]


def test_offer_commit_does_not_invalidate_other_pending_offers():
    cache = delta.SHACLDeltaCache()
    cache.put('offer1', 'h', True, [], ['adv'])
    cache.put('offer2', 'h', True, [], ['adv'])
    cache.on_tx_committed({'id': 'offer1', 'operation': 'BUY_OFFER',
                           'asset': {'data': {'advertisement_id': 'adv'}}})
    assert cache.get('offer2', 'h') == (True, [])
    assert cache.stats()['retirements'] == 1
    assert cache.stats()['dep_invalidations'] == 0


def test_expiry_is_checked_at_the_validation_context_time():
    cache = delta.SHACLDeltaCache()
    cache.put('offer', 'h', True, [], ['adv'], valid_until=100.0)
    assert cache.get('offer', 'h', validation_time=99.999) == (True, [])
    assert cache.get('offer', 'h', validation_time=100.0) is None
    assert cache.stats()['context_expirations'] == 1


def test_return_commit_invalidates_other_returns_for_the_same_sale():
    cache = delta.SHACLDeltaCache()
    cache.put('return2', 'h', True, [], ['sale'])
    cache.on_tx_committed({'id': 'return1', 'operation': 'REQUEST_RETURN',
                           'asset': {'data': {'sell_transaction_id': 'sale'}}})
    assert cache.get('return2', 'h') is None
    assert cache.stats()['dep_invalidations'] == 1


def test_unavailable_projection_query_is_not_a_stable_cache_key():
    class Store:
        def get_transaction(self, _):
            return {'id': 'adv', 'operation': 'ADVERTISEMENT', 'metadata': {'status': 'OPEN'}}
    tx = {'id': 'offer', 'operation': 'BUY_OFFER', 'asset': {'data': {'advertisement_id': 'adv'}}}
    try:
        delta.compute_dep_state(Store(), tx)
    except delta.ProjectionUnavailable:
        pass
    else:
        raise AssertionError('An unobserved required query must disable caching')
