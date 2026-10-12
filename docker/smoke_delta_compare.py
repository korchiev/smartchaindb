#!/usr/bin/env python3
"""Within-platform validation-layer: Direct vs SHACL vs SHACL+Δ.

Creates a real CREATE + ADVERTISEMENT on the live node, then times BUY_OFFER
validation against that advertisement. Does not submit the offer itself.

- Direct: RDF conversion only, no HTTP
- SHACL: HTTP every call (cache cleared)
- SHACL+Δ: second call with the same dependency-value hash
- value-change: same offer, advertisement values mutated, must miss
"""
import time
from datetime import datetime, timedelta, timezone

import requests
from bigchaindb_driver.crypto import generate_keypair
from bigchaindb.common.transaction import Input, Transaction

from bigchaindb.common.shacl_delta import (
    SHACLDeltaCache,
    collect_dep_state,
    hash_dep_state,
)
from bigchaindb.common.shacl_validator import get_shacl_validator

API = "http://127.0.0.1:9984/api/v1/transactions"
N = 7
NOW = datetime.now(timezone.utc)


def iso(dt):
    return dt.replace(microsecond=dt.microsecond or 123456).isoformat()


def post(tx, label):
    resp = requests.post(API + "?mode=commit", json=tx.to_dict(), timeout=45)
    print("SETUP", label, resp.status_code)
    if resp.status_code >= 400:
        print(resp.text[:800])
        raise SystemExit(1)
    return resp.json().get("id") or tx.id


def _median(samples):
    ordered = sorted(samples)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2.0


def _mean(samples):
    return sum(samples) / float(len(samples))


def _fmt(samples):
    return "median {:.2f} ms  mean {:.2f} ms  min {:.2f}  max {:.2f}  n={}".format(
        _median(samples), _mean(samples), min(samples), max(samples), len(samples)
    )


def time_direct(client, tx):
    t0 = time.perf_counter()
    client._convert_to_turtle(tx)
    return (time.perf_counter() - t0) * 1000


def time_shacl(client, tx, dep_hash):
    t0 = time.perf_counter()
    conforms, results = client.validate_transaction(tx, dep_state_hash=dep_hash)
    return (time.perf_counter() - t0) * 1000, conforms, results


class _HttpStore(object):
    def get_transaction(self, txid):
        resp = requests.get(API + "/" + txid, timeout=10)
        if resp.status_code != 200:
            return None
        return resp.json()


def main():
    seller = generate_keypair()
    buyer = generate_keypair()
    escrow = generate_keypair()

    create_tx = Transaction.create(
        [seller.public_key],
        [([seller.public_key], 1)],
        metadata={"requestCreationTimestamp": iso(NOW)},
        asset={
            "machineIdentifier": "wsl-delta-compare-1",
            "capability": ["sell"],
            "capabilityParameters": {"p": "1"},
        },
    ).sign([seller.private_key])
    create_id = post(create_tx, "CREATE")

    adv_tx = Transaction.advertisement(
        inputs=[Input.generate([seller.public_key])],
        asset_id=create_id,
        metadata={
            "status": "OPEN",
            "advertiser_public_key": seller.public_key,
            "price": "100.00",
            "description": "delta compare item",
            "category": "test",
            "expiry_date": iso(NOW + timedelta(days=30)),
            "requestCreationTimestamp": iso(NOW),
        },
    ).sign([seller.private_key])
    adv_id = post(adv_tx, "ADVERTISEMENT")

    offer_tx = Transaction.buy_offer(
        inputs=[Input.generate([buyer.public_key])],
        asset_id=create_id,
        advertisement_id=adv_id,
        metadata={
            "buyer_public_key": buyer.public_key,
            "escrow_public_key": escrow.public_key,
            "offer_amount": "100",
            "offer_currency": "USD",
            "offer_timestamp": iso(NOW),
            "offer_expiry": iso(NOW + timedelta(days=7)),
            "requestCreationTimestamp": iso(NOW),
        },
    ).sign([buyer.private_key])
    tx = offer_tx.to_dict()

    store = _HttpStore()
    parts = collect_dep_state(store, tx)
    if not parts or parts[0].get("missing"):
        raise SystemExit("could not load advertisement {}".format(adv_id))
    h_open = hash_dep_state(parts)
    closed = dict(parts[0])
    closed_meta = dict(closed.get("metadata") or {})
    closed_meta["status"] = "CLOSED"
    closed["metadata"] = closed_meta
    h_closed = hash_dep_state([closed])

    client = get_shacl_validator()
    client.cache_enabled = True
    client.delta_cache = SHACLDeltaCache()

    time_direct(client, tx)
    warm_ms, conforms, results = time_shacl(client, tx, h_open)
    if not conforms:
        raise SystemExit("warmup SHACL rejected: {}".format(results))

    direct = [time_direct(client, tx) for _ in range(N)]

    shacl = []
    for _ in range(N):
        client.delta_cache.clear()
        miss_ms, conforms, results = time_shacl(client, tx, h_open)
        if not conforms:
            raise SystemExit("SHACL rejected: {}".format(results))
        shacl.append(miss_ms)

    delta_hits = []
    for _ in range(N):
        client.delta_cache.clear()
        miss_ms, conforms, _ = time_shacl(client, tx, h_open)
        if not conforms:
            raise SystemExit("SHACL+Δ populate rejected")
        hit_ms, conforms, _ = time_shacl(client, tx, h_open)
        if not conforms:
            raise SystemExit("SHACL+Δ hit rejected")
        delta_hits.append(hit_ms)

    changed_ms, _, _ = time_shacl(client, tx, h_closed)
    stats = client.delta_cache.stats()

    print("platform  BigchainDB validation layer (BUY_OFFER vs live advertisement)")
    print("advertisement", adv_id)
    print("warmup SHACL HTTP     {:.2f} ms".format(warm_ms))
    print("Direct (RDF only)     {}".format(_fmt(direct)))
    print("SHACL (HTTP miss)     {}".format(_fmt(shacl)))
    print("SHACL+Δ (cache hit)   {}".format(_fmt(delta_hits)))
    print("value-change miss     {:.2f} ms  (must not reuse OPEN verdict)".format(changed_ms))
    print("stats", stats)
    if stats["hits"] < N:
        raise SystemExit("expected at least {} cache hits, got {}".format(N, stats["hits"]))
    print("DELTA COMPARE OK")


if __name__ == "__main__":
    main()
