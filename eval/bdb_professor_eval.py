#!/usr/bin/env python3
"""Professor-letter metrics on live BigchainDB (one node, not 4-node).

Runs inside the bigchaindb container. Live mode follows the serve
(Direct / SHACL / SHACL+Δ). Validation-layer Direct vs SHACL vs Δ is always
measured in-process when the SHACL engine is reachable.
"""
from __future__ import print_function

import argparse
import json
import os
import threading
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

API = os.environ.get("BDB_API", "http://127.0.0.1:9984/api/v1")
TX_API = API + "/transactions"
STATS_API = API + "/shacl-stats"
NOW = datetime.now(timezone.utc)

N_VAL = int(os.environ.get("N_VAL", "20"))
N_E2E = int(os.environ.get("N_E2E", "5"))
N_OFFER = int(os.environ.get("N_OFFER", "20"))
N_LOAD = int(os.environ.get("N_LOAD", "16"))
LOAD_CONC = [int(x) for x in os.environ.get("LOAD_CONC", "1,2,4,8").split(",") if x.strip()]


def iso(dt):
    return dt.replace(microsecond=dt.microsecond or 123456).isoformat()


def summarize(samples):
    if not samples:
        return {"n": 0, "samples": []}
    ordered = sorted(samples)
    n = len(ordered)

    def pct(p):
        if n == 1:
            return ordered[0]
        idx = int(round((p / 100.0) * (n - 1)))
        idx = max(0, min(n - 1, idx))
        return ordered[idx]

    return {
        "n": n,
        "mean": sum(samples) / float(n),
        "median": pct(50),
        "p95": pct(95),
        "min": ordered[0],
        "max": ordered[-1],
        "samples": samples,
    }


def wait_api():
    last = None
    for _ in range(40):
        try:
            resp = requests.get("http://127.0.0.1:9984/", timeout=3)
            if resp.status_code < 500:
                return
            last = resp.status_code
        except requests.RequestException as exc:
            last = exc
        time.sleep(2)
    raise SystemExit("API never became reachable: {}".format(last))


def post_tx(tx, timeout=60, retries=4):
    body = tx.to_dict()
    txid = body.get("id") or getattr(tx, "id", None)
    last_resp = None
    last_exc = None
    for attempt in range(retries):
        t0 = time.perf_counter()
        try:
            resp = requests.post(TX_API + "?mode=commit", json=body, timeout=timeout)
            ms = (time.perf_counter() - t0) * 1000.0
            text = ""
            try:
                text = resp.text or ""
            except Exception:
                text = ""
            if txid and (
                resp.status_code == 500
                or (resp.status_code == 400 and "already exists" in text)
            ):
                got = requests.get(TX_API + "/" + txid, timeout=10)
                if got.status_code == 200:
                    return 202, ms, got
            if resp.status_code == 500 and attempt < retries - 1:
                time.sleep(2.0 * (attempt + 1))
                last_resp = resp
                continue
            return resp.status_code, ms, resp
        except requests.RequestException as exc:
            last_exc = exc
            if txid:
                try:
                    got = requests.get(TX_API + "/" + txid, timeout=10)
                    if got.status_code == 200:
                        return 202, (time.perf_counter() - t0) * 1000.0, got
                except requests.RequestException:
                    pass
            time.sleep(2.0 * (attempt + 1))
    if last_resp is not None:
        return last_resp.status_code, 0.0, last_resp
    raise last_exc


def validate_http(tx, timeout=45):
    t0 = time.perf_counter()
    resp = requests.post(TX_API + "/validate", json=tx.to_dict(), timeout=timeout)
    ms = (time.perf_counter() - t0) * 1000.0
    return resp.status_code, ms, resp


def require_ok(status, resp, label):
    if status >= 400:
        text = ""
        try:
            text = resp.text[:500]
        except Exception:
            text = str(resp)
        raise SystemExit("{} failed {}: {}".format(label, status, text))


def shacl_stats(reset=False):
    try:
        url = STATS_API + ("?reset=1" if reset else "")
        resp = requests.get(url, timeout=5)
        if resp.status_code != 200:
            return None
        return resp.json()
    except requests.RequestException:
        return None


def gen_input(public_key):
    return [Input.generate([public_key])]


def make_create(seller, tag):
    return Transaction.create(
        [seller.public_key],
        [([seller.public_key], 1)],
        metadata={"requestCreationTimestamp": iso(NOW)},
        asset={
            "machineIdentifier": "prof-{}".format(tag)[:64],
            "capability": ["sell"],
            "capabilityParameters": {"p": "1"},
        },
    ).sign([seller.private_key])


def make_adv(seller, create_id, status="OPEN"):
    return Transaction.advertisement(
        inputs=gen_input(seller.public_key),
        asset_id=create_id,
        metadata={
            "status": status,
            "advertiser_public_key": seller.public_key,
            "price": "100.00",
            "description": "professor eval item",
            "category": "test",
            "expiry_date": iso(NOW + timedelta(days=30)),
            "requestCreationTimestamp": iso(NOW),
        },
    ).sign([seller.private_key])


def make_update(seller, adv_id, status="OPEN", price="99.00"):
    return Transaction.update_adv(
        inputs=gen_input(seller.public_key),
        advertisement_id=adv_id,
        metadata={
            "status": status,
            "updater_public_key": seller.public_key,
            "price": price,
            "expiry_date": iso(NOW + timedelta(days=30)),
            "requestCreationTimestamp": iso(NOW),
        },
    ).sign([seller.private_key])


def make_offer(buyer, escrow, create_id, adv_id, nonce=""):
    return Transaction.buy_offer(
        inputs=gen_input(buyer.public_key),
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


def setup_open_ad(tag):
    seller = generate_keypair()
    st, ms, resp = post_tx(make_create(seller, tag))
    require_ok(st, resp, "CREATE")
    create_id = resp.json().get("id")
    st, ms, resp = post_tx(make_adv(seller, create_id))
    require_ok(st, resp, "ADVERTISEMENT")
    adv_id = resp.json().get("id")
    return seller, create_id, adv_id


def run_lifecycle(tag):
    seller = generate_keypair()
    buyer = generate_keypair()
    escrow = generate_keypair()
    ops = []

    create_tx = make_create(seller, tag)
    st, ms, resp = post_tx(create_tx)
    require_ok(st, resp, "CREATE")
    create_id = resp.json().get("id")
    ops.append(("CREATE", ms, st))

    st, ms, resp = post_tx(make_adv(seller, create_id))
    require_ok(st, resp, "ADVERTISEMENT")
    adv_id = resp.json().get("id")
    ops.append(("ADVERTISEMENT", ms, st))

    st, ms, resp = post_tx(make_update(seller, adv_id))
    require_ok(st, resp, "UPDATE_ADV")
    ops.append(("UPDATE_ADV", ms, st))

    offer_tx = make_offer(buyer, escrow, create_id, adv_id, tag)
    st, ms, resp = post_tx(offer_tx)
    require_ok(st, resp, "BUY_OFFER")
    offer_id = resp.json().get("id")
    ops.append(("BUY_OFFER", ms, st))

    sell_tx = Transaction.sell(
        inputs=create_tx.to_inputs(),
        asset_id=create_id,
        buy_offer_id=offer_id,
        metadata={
            "seller_public_key": seller.public_key,
            "buyer_public_key": buyer.public_key,
            "sale_amount": "100",
            "sale_currency": "USD",
            "sale_timestamp": iso(NOW),
            "sale_notes": "eval sale",
            "requestCreationTimestamp": iso(NOW),
        },
    ).sign([seller.private_key])
    st, ms, resp = post_tx(sell_tx)
    require_ok(st, resp, "SELL")
    sell_id = resp.json().get("id")
    ops.append(("SELL", ms, st))

    ret_tx = Transaction.request_return(
        inputs=gen_input(buyer.public_key),
        asset_id=create_id,
        sell_transaction_id=sell_id,
        metadata={
            "requester_public_key": buyer.public_key,
            "return_reason": "eval return",
            "return_request_timestamp": iso(NOW),
            "return_policy_details": {
                "return_window_days": 30,
                "return_conditions": "unopened",
                "return_status": "PENDING",
            },
            "requestCreationTimestamp": iso(NOW),
        },
    ).sign([buyer.private_key])
    st, ms, resp = post_tx(ret_tx)
    require_ok(st, resp, "REQUEST_RETURN")
    ret_id = resp.json().get("id")
    ops.append(("REQUEST_RETURN", ms, st))

    acc_tx = Transaction.seller_accept_return(
        inputs=gen_input(seller.public_key),
        asset_id=create_id,
        request_return_id=ret_id,
        metadata={
            "seller_public_key": seller.public_key,
            "acceptance_timestamp": iso(NOW),
            "processing_notes": "accepted",
            "requestCreationTimestamp": iso(NOW),
            "refund_details": {
                "refund_amount": 100.0,
                "refund_currency": "USD",
                "refund_method": "original_payment",
            },
        },
    ).sign([seller.private_key])
    st, ms, resp = post_tx(acc_tx)
    require_ok(st, resp, "SELLER_ACCEPT_RETURN")
    ops.append(("SELLER_ACCEPT_RETURN", ms, st))
    return {
        "total_ms": sum(item[1] for item in ops),
        "ops": [{"op": item[0], "ms": item[1], "status": item[2]} for item in ops],
    }


class _HttpStore(object):
    def get_transaction(self, txid):
        resp = requests.get(TX_API + "/" + txid, timeout=10)
        if resp.status_code != 200:
            return None
        return resp.json()


def run_validation_layer(n):
    seller = generate_keypair()
    buyer = generate_keypair()
    escrow = generate_keypair()
    st, _, resp = post_tx(make_create(seller, "val"))
    require_ok(st, resp, "CREATE")
    create_id = resp.json().get("id")
    st, _, resp = post_tx(make_adv(seller, create_id))
    require_ok(st, resp, "ADVERTISEMENT")
    adv_id = resp.json().get("id")
    offer_tx = make_offer(buyer, escrow, create_id, adv_id, "val")
    tx = offer_tx.to_dict()
    store = _HttpStore()
    parts = collect_dep_state(store, tx)
    h_open = hash_dep_state(parts)
    closed = dict(parts[0])
    closed_meta = dict(closed.get("metadata") or {})
    closed_meta["status"] = "CLOSED"
    closed["metadata"] = closed_meta
    h_closed = hash_dep_state([closed])

    client = get_shacl_validator()
    orig_enabled = client.enabled
    orig_cache = client.cache_enabled
    orig_delta = client.delta_cache

    def time_direct():
        t0 = time.perf_counter()
        client._convert_to_turtle(tx)
        return (time.perf_counter() - t0) * 1000.0

    def time_shacl(dep_hash):
        t0 = time.perf_counter()
        conforms, results = client.validate_transaction(tx, dep_state_hash=dep_hash)
        return (time.perf_counter() - t0) * 1000.0, conforms, results

    client.enabled = False
    client.cache_enabled = False
    direct = [time_direct() for _ in range(n)]

    client.enabled = True
    client.cache_enabled = False
    client.delta_cache = SHACLDeltaCache()
    miss, conforms, results = time_shacl(h_open)
    if not conforms:
        client.enabled = orig_enabled
        client.cache_enabled = orig_cache
        client.delta_cache = orig_delta
        raise SystemExit("validation SHACL rejected: {}".format(results))
    shacl = [miss]
    for _ in range(n - 1):
        client.delta_cache.clear()
        miss_ms, conforms, results = time_shacl(h_open)
        if not conforms:
            raise SystemExit("SHACL rejected")
        shacl.append(miss_ms)

    client.cache_enabled = True
    hits = []
    for _ in range(n):
        client.delta_cache.clear()
        miss_ms, conforms, _ = time_shacl(h_open)
        if not conforms:
            raise SystemExit("Δ populate rejected")
        hit_ms, conforms, _ = time_shacl(h_open)
        if not conforms:
            raise SystemExit("Δ hit rejected")
        hits.append(hit_ms)
    changed_ms, _, _ = time_shacl(h_closed)
    stats = client.delta_cache.stats()

    client.enabled = orig_enabled
    client.cache_enabled = orig_cache
    client.delta_cache = orig_delta
    return {
        "direct_rdf": summarize(direct),
        "shacl_http_miss": summarize(shacl),
        "shacl_delta_hit": summarize(hits),
        "value_change_miss": {"n": 1, "median": changed_ms, "samples": [changed_ms]},
        "stats": stats,
    }


def run_e2e(n, tag):
    trials = []
    for i in range(n):
        trials.append(run_lifecycle("{}-e2e-{}".format(tag, i)))
    totals = [t["total_ms"] for t in trials]
    by_op = {}
    for trial in trials:
        for item in trial["ops"]:
            by_op.setdefault(item["op"], []).append(item["ms"])
    return {
        "trials": trials,
        "total": summarize(totals),
        "by_op": dict((op, summarize(vals)) for op, vals in by_op.items()),
    }


def run_mix_shared(n, mempool_recheck):
    seller, create_id, adv_id = setup_open_ad("shared")
    shacl_stats(reset=True)
    latencies = []
    validate_first = []
    validate_second = []
    committed = 0
    rejected = 0
    for i in range(n):
        buyer = generate_keypair()
        escrow = generate_keypair()
        offer = make_offer(buyer, escrow, create_id, adv_id, "s{}".format(i))
        if mempool_recheck:
            st1, ms1, _ = validate_http(offer)
            st2, ms2, _ = validate_http(offer)
            validate_first.append(ms1)
            validate_second.append(ms2)
        st, ms, resp = post_tx(offer)
        latencies.append(ms)
        if st < 400:
            committed += 1
        else:
            rejected += 1
            print("shared offer reject", st, resp.text[:200])
    return {
        "mix": "shared_ad",
        "attempted": n,
        "committed": committed,
        "rejected": rejected,
        "commit": summarize(latencies),
        "validate_first": summarize(validate_first),
        "validate_second": summarize(validate_second),
        "stats": shacl_stats(reset=False),
    }


def run_mix_mutate(n):
    seller, create_id, adv_id = setup_open_ad("mutate")
    shacl_stats(reset=True)
    half = max(1, n // 2)
    before = []
    after = []
    committed = 0
    rejected = 0
    for i in range(half):
        buyer = generate_keypair()
        escrow = generate_keypair()
        st, ms, resp = post_tx(make_offer(buyer, escrow, create_id, adv_id, "m{}".format(i)))
        before.append(ms)
        if st < 400:
            committed += 1
        else:
            rejected += 1
    st, _, resp = post_tx(make_update(seller, adv_id, status="CLOSED", price="100.00"))
    require_ok(st, resp, "UPDATE_ADV CLOSED")
    for i in range(n - half):
        buyer = generate_keypair()
        escrow = generate_keypair()
        st, ms, resp = post_tx(make_offer(buyer, escrow, create_id, adv_id, "mc{}".format(i)))
        after.append(ms)
        if st < 400:
            committed += 1
        else:
            rejected += 1
    return {
        "mix": "mutating_ad",
        "attempted": n,
        "committed": committed,
        "rejected": rejected,
        "before_close": summarize(before),
        "after_close": summarize(after),
        "abort_rate": rejected / float(n) if n else 0.0,
        "stats": shacl_stats(reset=False),
    }


def run_mix_disjoint(n):
    shacl_stats(reset=True)
    latencies = []
    committed = 0
    rejected = 0
    for i in range(n):
        seller, create_id, adv_id = setup_open_ad("d{}".format(i))
        buyer = generate_keypair()
        escrow = generate_keypair()
        st, ms, resp = post_tx(make_offer(buyer, escrow, create_id, adv_id, "d{}".format(i)))
        latencies.append(ms)
        if st < 400:
            committed += 1
        else:
            rejected += 1
    return {
        "mix": "disjoint",
        "attempted": n,
        "committed": committed,
        "rejected": rejected,
        "commit": summarize(latencies),
        "stats": shacl_stats(reset=False),
    }


def run_conflict(n=12):
    seller, create_id, adv_id = setup_open_ad("conflict")
    shacl_stats(reset=True)
    results = []
    lock = threading.Lock()

    def offer_worker(i):
        buyer = generate_keypair()
        escrow = generate_keypair()
        offer = make_offer(buyer, escrow, create_id, adv_id, "c{}".format(i))
        st, ms, resp = post_tx(offer)
        with lock:
            results.append({"kind": "offer", "status": st, "ms": ms})

    def close_worker():
        time.sleep(0.02)
        st, ms, resp = post_tx(make_update(seller, adv_id, status="CLOSED"))
        with lock:
            results.append({"kind": "close", "status": st, "ms": ms})

    threads = [threading.Thread(target=close_worker)]
    for i in range(n):
        threads.append(threading.Thread(target=offer_worker, args=(i,)))
    for th in threads:
        th.start()
    for th in threads:
        th.join()
    offers = [r for r in results if r["kind"] == "offer"]
    rejected = sum(1 for r in offers if r["status"] >= 400)
    committed = sum(1 for r in offers if r["status"] < 400)
    return {
        "attempted_offers": n,
        "committed": committed,
        "rejected": rejected,
        "abort_rate": rejected / float(n) if n else 0.0,
        "results": results,
        "stats": shacl_stats(reset=False),
    }


def run_fail_closed():
    seller, create_id, adv_id = setup_open_ad("reject")
    thief = generate_keypair()
    bad = Transaction.advertisement(
        inputs=gen_input(thief.public_key),
        asset_id=create_id,
        metadata={
            "status": "OPEN",
            "advertiser_public_key": thief.public_key,
            "price": "1.00",
            "description": "stolen ad",
            "category": "test",
            "expiry_date": iso(NOW + timedelta(days=30)),
            "requestCreationTimestamp": iso(NOW),
        },
    ).sign([thief.private_key])
    st, ms, resp = post_tx(bad)
    return {
        "status": st,
        "ms": ms,
        "rejected": st >= 400,
        "body": resp.text[:300],
    }


def run_load(n, concs):
    seller, create_id, adv_id = setup_open_ad("load")
    out = []
    for c in concs:
        shacl_stats(reset=True)
        per = max(1, n // c)
        attempted = per * c
        box = {"committed": 0, "rejected": 0, "latencies": []}
        lock = threading.Lock()
        start = threading.Event()

        def worker():
            start.wait()
            for i in range(per):
                buyer = generate_keypair()
                escrow = generate_keypair()
                offer = make_offer(buyer, escrow, create_id, adv_id, "L{}-{}".format(c, i) + generate_keypair().public_key[:8])
                try:
                    st, ms, resp = post_tx(offer)
                except requests.RequestException:
                    st, ms = 599, 0.0
                with lock:
                    box["latencies"].append(ms)
                    if st < 400:
                        box["committed"] += 1
                    else:
                        box["rejected"] += 1

        threads = [threading.Thread(target=worker) for _ in range(c)]
        for th in threads:
            th.start()
        t0 = time.perf_counter()
        start.set()
        for th in threads:
            th.join()
        wall = time.perf_counter() - t0
        committed = box["committed"]
        out.append({
            "concurrency": c,
            "attempted": attempted,
            "committed": committed,
            "rejected": box["rejected"],
            "wall_s": wall,
            "offered_tps": attempted / wall if wall else 0.0,
            "committed_tps": committed / wall if wall else 0.0,
            "abort_rate": box["rejected"] / float(attempted) if attempted else 0.0,
            "latency": summarize(box["latencies"]),
            "stats": shacl_stats(reset=False),
        })
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--live-mode", required=True, choices=["direct", "shacl", "delta"])
    parser.add_argument("--out", required=True)
    parser.add_argument("--skip-validation", action="store_true")
    parser.add_argument("--skip-e2e", action="store_true")
    parser.add_argument("--skip-mixes", action="store_true")
    parser.add_argument("--skip-load", action="store_true")
    parser.add_argument("--skip-conflict", action="store_true")
    parser.add_argument("--only-fail-closed", action="store_true")
    parser.add_argument("--wan", action="store_true")
    args = parser.parse_args()

    wait_api()
    if args.only_fail_closed:
        payload = {
            "platform": "bigchaindb",
            "live_mode": args.live_mode,
            "n_offer": N_OFFER,
            "started_unix": time.time(),
        }
        print("=== mix mutate n={} ===".format(N_OFFER))
        payload["mix_mutate"] = run_mix_mutate(N_OFFER)
        print("mutate", payload["mix_mutate"]["committed"], payload["mix_mutate"]["rejected"], payload["mix_mutate"]["abort_rate"])
        print("=== fail-closed ===")
        payload["fail_closed"] = run_fail_closed()
        print("fail_closed", payload["fail_closed"]["status"], payload["fail_closed"]["rejected"])
        payload["finished_unix"] = time.time()
        outdir = os.path.dirname(args.out)
        if outdir and not os.path.exists(outdir):
            os.makedirs(outdir)
        with open(args.out, "w") as handle:
            json.dump(payload, handle, indent=2)
        print("WROTE", args.out)
        return

    payload = {
        "platform": "bigchaindb",
        "live_mode": args.live_mode,
        "wan": bool(args.wan),
        "n_val": N_VAL,
        "n_e2e": N_E2E,
        "n_offer": N_OFFER,
        "n_load": N_LOAD,
        "started_unix": time.time(),
        "server_stats_probe": shacl_stats(reset=False),
    }
    mempool = args.live_mode == "delta"

    if not args.skip_validation and args.live_mode == "delta" and not args.wan:
        print("=== validation layer n={} ===".format(N_VAL))
        payload["validation_layer"] = run_validation_layer(N_VAL)
        print("validation ok", {k: payload["validation_layer"][k].get("median") if isinstance(payload["validation_layer"][k], dict) else payload["validation_layer"][k] for k in payload["validation_layer"]})

    if not args.skip_e2e:
        print("=== e2e n={} mode={} ===".format(N_E2E, args.live_mode))
        payload["e2e"] = run_e2e(N_E2E, args.live_mode)
        print("e2e total", payload["e2e"]["total"])

    if not args.skip_mixes:
        print("=== mix shared n={} ===".format(N_OFFER))
        payload["mix_shared"] = run_mix_shared(N_OFFER, mempool_recheck=mempool)
        print("=== mix mutate n={} ===".format(N_OFFER))
        payload["mix_mutate"] = run_mix_mutate(N_OFFER)
        if not args.wan:
            print("=== mix disjoint n={} ===".format(N_OFFER))
            payload["mix_disjoint"] = run_mix_disjoint(N_OFFER)
        print("=== fail-closed ===")
        payload["fail_closed"] = run_fail_closed()

    if not args.skip_conflict and not args.wan:
        print("=== conflict ===")
        payload["conflict"] = run_conflict()

    if not args.skip_load and not args.wan:
        print("=== load {} ===".format(LOAD_CONC))
        payload["load"] = run_load(N_LOAD, LOAD_CONC)

    payload["finished_unix"] = time.time()
    outdir = os.path.dirname(args.out)
    if outdir and not os.path.exists(outdir):
        os.makedirs(outdir)
    with open(args.out, "w") as handle:
        json.dump(payload, handle, indent=2)
    print("WROTE", args.out)


if __name__ == "__main__":
    main()
