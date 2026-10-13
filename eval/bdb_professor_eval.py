#!/usr/bin/env python3
"""Professor-letter metrics on live BigchainDB (one node, not 4-node).

Runs inside the bigchaindb container. Live mode follows the serve
(Direct / SHACL / SHACL+Δ). Validation-layer Direct vs SHACL vs Δ is always
measured in-process when the SHACL engine is reachable.
"""
from __future__ import print_function

import argparse
import base64
import hashlib
import json
import os
import threading
import time
from datetime import datetime, timedelta, timezone

import requests
from bigchaindb_driver.crypto import generate_keypair
from bigchaindb.common.transaction import Input, Transaction

from bigchaindb.common.shacl_delta import SHACLDeltaCache
from bigchaindb.common.shacl_validator import get_shacl_validator

API = os.environ.get("BDB_API", "http://127.0.0.1:9984/api/v1")
TX_API = API + "/transactions"
STATS_API = API + "/shacl-stats"
# Tendermint RPC of the node the API fronts (open-loop submission).
TM_RPC = os.environ.get("TM_RPC", API.rsplit("/api/", 1)[0].rsplit(":", 1)[0] + ":26657")
NOW = datetime.now(timezone.utc)

N_VAL = int(os.environ.get("N_VAL", "20"))
N_E2E = int(os.environ.get("N_E2E", "5"))
N_OFFER = int(os.environ.get("N_OFFER", "20"))
N_DISJOINT = int(os.environ.get("N_DISJOINT", str(N_OFFER)))
N_LOAD = int(os.environ.get("N_LOAD", "16"))
LOAD_CONC = [int(x) for x in os.environ.get("LOAD_CONC", "1,2,4,8").split(",") if x.strip()]
MATRIX_REPS = int(os.environ.get("MATRIX_REPS", "2"))
SEQ_REPS = int(os.environ.get("SEQ_REPS", "2"))
N_RATIO = int(os.environ.get("N_RATIO", "60"))
RATIOS = [float(x) for x in os.environ.get("RATIOS", "0,0.1,0.25,0.5,1.0").split(",") if x.strip()]
OPEN_RATES = [float(x) for x in os.environ.get("OPEN_RATES", "5,10,20,40,80,160").split(",") if x.strip()]
OPEN_DURATION = float(os.environ.get("OPEN_DURATION", "20"))
ENGINE_DOWN_FLAG = os.environ.get("ENGINE_DOWN_FLAG", "/out/engine_down.flag")


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
            resp = requests.get(API.rsplit("/api/", 1)[0] + "/", timeout=3)
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

    sell_tx = make_sell(seller, buyer, create_tx, create_id, offer_id)
    st, ms, resp = post_tx(sell_tx)
    require_ok(st, resp, "SELL")
    sell_id = resp.json().get("id")
    ops.append(("SELL", ms, st))

    ret_tx = make_return(buyer, create_id, sell_id)
    st, ms, resp = post_tx(ret_tx)
    require_ok(st, resp, "REQUEST_RETURN")
    ret_id = resp.json().get("id")
    ops.append(("REQUEST_RETURN", ms, st))

    acc_tx = make_accept(seller, create_id, ret_id)
    st, ms, resp = post_tx(acc_tx)
    require_ok(st, resp, "SELLER_ACCEPT_RETURN")
    ops.append(("SELLER_ACCEPT_RETURN", ms, st))
    return {
        "total_ms": sum(item[1] for item in ops),
        "ops": [{"op": item[0], "ms": item[1], "status": item[2]} for item in ops],
    }


def make_sell(seller, buyer, create_tx, create_id, offer_id, signer=None):
    """SELL spending the CREATE outputs. ``signer`` lets the matrix produce a
    SELL signed by someone who is not the owner (inputs then come from the
    signer's own key, since it cannot fulfil the owner's outputs)."""
    signer = signer or seller
    inputs = create_tx.to_inputs() if signer is seller else gen_input(signer.public_key)
    return Transaction.sell(
        inputs=inputs,
        asset_id=create_id,
        buy_offer_id=offer_id,
        metadata={
            "seller_public_key": signer.public_key,
            "buyer_public_key": buyer.public_key,
            "sale_amount": "100",
            "sale_currency": "USD",
            "sale_timestamp": iso(NOW),
            "sale_notes": "eval sale",
            "requestCreationTimestamp": iso(NOW),
        },
    ).sign([signer.private_key])


def make_return(requester, create_id, sell_id, nonce=""):
    return Transaction.request_return(
        inputs=gen_input(requester.public_key),
        asset_id=create_id,
        sell_transaction_id=sell_id,
        metadata={
            "requester_public_key": requester.public_key,
            "return_reason": "eval return" + (" " + nonce if nonce else ""),
            "return_request_timestamp": iso(NOW),
            "return_policy_details": {
                "return_window_days": 30,
                "return_conditions": "unopened",
                "return_status": "PENDING",
            },
            "requestCreationTimestamp": iso(NOW),
        },
    ).sign([requester.private_key])


def make_accept(acceptor, create_id, ret_id, nonce=""):
    return Transaction.seller_accept_return(
        inputs=gen_input(acceptor.public_key),
        asset_id=create_id,
        request_return_id=ret_id,
        metadata={
            "seller_public_key": acceptor.public_key,
            "acceptance_timestamp": iso(NOW),
            "processing_notes": "accepted" + (" " + nonce if nonce else ""),
            "requestCreationTimestamp": iso(NOW),
            "refund_details": {
                "refund_amount": 100.0,
                "refund_currency": "USD",
                "refund_method": "original_payment",
            },
        },
    ).sign([acceptor.private_key])


def run_validation_layer(n):
    """In-process validator microbenchmark on the validator's own database.

    Every condition runs the real ``Transaction.validate`` path, i.e. the same
    code CheckTx and DeliverTx execute: Direct runs the imperative checks;
    SHACL runs dependency fetch + RDF + engine round-trip; a SHACL+Δ hit runs
    dependency fetch + hash + cache lookup. Phase timers are reported per
    condition. Runs inside the bigchaindb container.
    """
    from bigchaindb.lib import BigchainDB
    from bigchaindb.models import Transaction as ModelTx
    from bigchaindb.common.exceptions import ValidationError

    bigchain = BigchainDB()
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

    client = get_shacl_validator()
    orig = (client.enabled, client.cache_enabled, client.delta_cache)

    def validate_once():
        t0 = time.perf_counter()
        try:
            ModelTx.from_dict(tx).validate(bigchain)
            ok, err = True, None
        except ValidationError as exc:
            ok, err = False, str(exc)[:200]
        return (time.perf_counter() - t0) * 1000.0, ok, err

    def condition(label, enabled, cache, repeat, before_each=None, expect_ok=True):
        client.enabled = enabled
        client.cache_enabled = cache
        client.timing.clear()
        samples = []
        for _ in range(repeat):
            if before_each:
                before_each()
            ms, ok, err = validate_once()
            if ok != expect_ok:
                raise SystemExit("{}: unexpected verdict ok={} err={}".format(label, ok, err))
            samples.append(ms)
        row = summarize(samples)
        row["phases"] = client.timing.snapshot()
        return row

    out = {}
    # Direct: imperative checks against the same database.
    out["direct"] = condition("direct", False, False, n)

    # SHACL miss: fresh cache every call.
    client.delta_cache = SHACLDeltaCache()
    out["shacl_miss"] = condition("shacl_miss", True, False, n)

    # SHACL+Δ hit: populate once, then re-validate the same pending offer.
    client.delta_cache = SHACLDeltaCache()
    client.enabled, client.cache_enabled = True, True
    _, ok, err = validate_once()
    if not ok:
        raise SystemExit("delta populate rejected: {}".format(err))
    out["delta_hit"] = condition("delta_hit", True, True, n)
    hit_stats = client.delta_cache.stats()

    # Value change: close the advertisement on the ledger, re-validate the
    # same pending offer. The dependency hash changes, the cache misses, and
    # the verdict flips to reject.
    st, _, resp = post_tx(make_update(seller, adv_id, status="CLOSED", price="100.00"))
    require_ok(st, resp, "UPDATE_ADV CLOSED")
    client.timing.clear()
    ms, ok, err = validate_once()
    out["value_change"] = {
        "n": 1, "median": ms, "samples": [ms], "rejected": not ok, "reason": err,
        "phases": client.timing.snapshot(),
    }
    out["delta_stats_after"] = client.delta_cache.stats()
    out["delta_stats_hits"] = hit_stats

    client.enabled, client.cache_enabled, client.delta_cache = orig
    return out


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
            st1, ms1, r1 = validate_http(offer)
            require_ok(st1, r1, "VALIDATE first")
            st2, ms2, r2 = validate_http(offer)
            require_ok(st2, r2, "VALIDATE second")
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


# Dependency classes for the Δ sequence: pending tx T, an unrelated commit U,
# and a relevant commit R that changes T's dependency (and should flip T).
def _seq_buy_offer(c):
    T = make_offer(c["buyer"], c["escrow"], c["create_id"], c["adv_id"])
    R = make_update(c["seller"], c["adv_id"], status="CLOSED", price="100.00")
    return T, R


def _seq_sell(c):
    T = make_sell(c["seller"], c["buyer"], c["create_tx"], c["create_id"], c["offer_id"])
    # Competing sale of the same offer (different notes so the id differs).
    R = Transaction.sell(
        inputs=c["create_tx"].to_inputs(),
        asset_id=c["create_id"],
        buy_offer_id=c["offer_id"],
        metadata=dict(T.to_dict()["metadata"], sale_notes="competing sale"),
    ).sign([c["seller"].private_key])
    return T, R


def _seq_request_return(c):
    T = make_return(c["buyer"], c["create_id"], c["sell_id"])
    R = make_return(c["buyer"], c["create_id"], c["sell_id"], nonce="first")
    return T, R


def _seq_accept_return(c):
    T = make_accept(c["seller"], c["create_id"], c["ret_id"])
    R = make_accept(c["seller"], c["create_id"], c["ret_id"], nonce="first")
    return T, R


SEQ_CLASSES = [
    ("BUY_OFFER->ADVERTISEMENT", "adv", _seq_buy_offer),
    ("SELL->BUY_OFFER", "offer", _seq_sell),
    ("REQUEST_RETURN->SELL", "sell", _seq_request_return),
    ("SELLER_ACCEPT_RETURN->REQUEST_RETURN", "return", _seq_accept_return),
]


def run_delta_sequence(reps, policies=("delta", "entity", "flush")):
    """Centerpiece: cold miss -> hit -> unrelated commit (still hit?) ->
    relevant commit (invalidated?) -> revalidate (verdict flips?), for every
    dependency class, under each invalidation policy, both with the commit
    signal delivered to the cache (ABCI process) and without it (the web
    admission process never sees commits). Stale reuse = cached verdict that
    disagrees with a fresh engine verdict. Runs in-process on a validator."""
    from bigchaindb.lib import BigchainDB
    from bigchaindb.models import Transaction as ModelTx
    from bigchaindb.common.exceptions import ValidationError

    bigchain = BigchainDB()
    client = get_shacl_validator()
    orig = (client.enabled, client.cache_enabled, client.delta_cache)
    client.enabled = True

    def verdict(tx_dict):
        try:
            ModelTx.from_dict(tx_dict).validate(bigchain)
            return True
        except ValidationError:
            return False

    def fresh(tx_dict):
        saved = client.cache_enabled
        client.cache_enabled = False
        try:
            return verdict(tx_dict)
        finally:
            client.cache_enabled = saved

    def step(name, tx_dict, expect):
        before = client.delta_cache.stats()
        t0 = time.perf_counter()
        v = verdict(tx_dict)
        ms = (time.perf_counter() - t0) * 1000.0
        after = client.delta_cache.stats()
        delta = {k: after[k] - before[k] for k in ("hits", "misses", "cold_misses", "dep_change_misses",
                                                    "entity_hash_mismatch_hits") if k in after}
        kind = "hit" if delta["hits"] else ("miss" if delta["misses"] else "none")
        f = fresh(tx_dict)
        return {"step": name, "kind": kind, "expected": expect, "verdict": v, "fresh_verdict": f,
                "stale": v != f, "ms": ms, "counters": delta}

    rows = []
    for rep in range(reps):
        for cls, stage, builder in SEQ_CLASSES:
            for policy in policies:
                for signal in (True, False):
                    ctx = build_stage(stage, "seq{}-{}".format(rep, cls[:5]))
                    T, R = builder(ctx)
                    T_dict = T.to_dict()
                    client.cache_enabled = True
                    client.delta_cache = SHACLDeltaCache(policy=policy)
                    steps = [step("cold", T_dict, "miss"), step("repeat", T_dict, "hit")]
                    # Unrelated commit: a CREATE by a stranger.
                    U = make_create(generate_keypair(), "unrel-{}-{}".format(rep, cls[:4]))
                    st, _, resp = post_tx(U)
                    require_ok(st, resp, "sequence unrelated CREATE")
                    if signal:
                        client.on_tx_committed(U.to_dict())
                    s_before = client.delta_cache.stats()
                    steps.append(step("after_unrelated", T_dict, "hit"))
                    # Relevant commit.
                    st, _, resp = post_tx(R)
                    require_ok(st, resp, "sequence relevant commit")
                    inv_before = client.delta_cache.stats()
                    if signal:
                        client.on_tx_committed(R.to_dict())
                    inv_after = client.delta_cache.stats()
                    steps.append(step("after_relevant", T_dict, "miss"))
                    rows.append({
                        "rep": rep, "class": cls, "policy": policy, "commit_signal": signal,
                        "steps": steps,
                        "unrelated_preserved": steps[2]["kind"] == "hit",
                        "relevant_invalidated": inv_after["dep_invalidations"] - inv_before["dep_invalidations"],
                        "verdict_flipped": steps[0]["verdict"] != steps[3]["fresh_verdict"],
                        "stale_reuse": sum(1 for s in steps if s["stale"]),
                        "unused": s_before,
                    })
                    print("seq", cls, policy, "signal" if signal else "nosignal",
                          [s["kind"] for s in steps], "stale", rows[-1]["stale_reuse"],
                          "flip", rows[-1]["verdict_flipped"], flush=True)
    client.enabled, client.cache_enabled, client.delta_cache = orig
    summary = {}
    for policy in policies:
        for signal in (True, False):
            sel = [r for r in rows if r["policy"] == policy and r["commit_signal"] == signal]
            if not sel:
                continue
            summary["{}/{}".format(policy, "signal" if signal else "nosignal")] = {
                "sequences": len(sel),
                "unrelated_preserved": sum(1 for r in sel if r["unrelated_preserved"]),
                "relevant_invalidated": sum(1 for r in sel if r["relevant_invalidated"] > 0),
                "verdict_flipped": sum(1 for r in sel if r["verdict_flipped"]),
                "stale_reuse": sum(r["stale_reuse"] for r in sel),
            }
    for r in rows:
        r.pop("unused", None)
    return {"reps": reps, "summary": summary, "rows": rows}


def run_update_ratio_sweep(n, ratios):
    """Live: how the HTTP-admission hit rate and commit latency respond as the
    fraction of *relevant* intervening commits rises. For each offer: validate
    (populates the admission cache), commit one intervening tx that is relevant
    (UPDATE_ADV on the offer's ad, still OPEN) with probability p and unrelated
    (stranger CREATE) otherwise, then commit the offer."""
    import random
    rng = random.Random(1234)
    sellers = [setup_open_ad("ratio{}".format(i)) for i in range(4)]
    out = []
    for p in ratios:
        shacl_stats(reset=True)
        lat = []
        committed = rejected = relevant = 0
        for i in range(n):
            seller, create_id, adv_id = sellers[i % len(sellers)]
            offer = make_offer(generate_keypair(), generate_keypair(), create_id, adv_id)
            validate_http(offer)
            if rng.random() < p:
                relevant += 1
                st, _, resp = post_tx(make_update(seller, adv_id, status="OPEN", price="{}.00".format(90 + (i % 9))))
                require_ok(st, resp, "ratio relevant UPDATE_ADV")
            else:
                st, _, resp = post_tx(make_create(generate_keypair(), "ratio-u{}".format(i)))
                require_ok(st, resp, "ratio unrelated CREATE")
            st, ms, resp = post_tx(offer)
            lat.append(ms)
            if st < 400:
                committed += 1
            else:
                rejected += 1
        stats = shacl_stats(reset=False)
        out.append({"relevant_ratio": p, "n": n, "relevant_commits": relevant,
                    "committed": committed, "rejected": rejected,
                    "latency": summarize(lat), "stats": stats})
        print("ratio p={} committed={} rejected={} p50={:.0f}ms".format(
            p, committed, rejected, out[-1]["latency"].get("median", 0)), flush=True)
    return out


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


def post_once(body, timeout=60):
    """Single commit-mode POST without retries; classifies the outcome."""
    t0 = time.perf_counter()
    try:
        resp = requests.post(TX_API + "?mode=commit", json=body, timeout=timeout)
        ms = (time.perf_counter() - t0) * 1000.0
        text = (resp.text or "")[:300]
        status = resp.status_code
    except requests.RequestException as exc:
        ms = (time.perf_counter() - t0) * 1000.0
        text, status = str(exc)[:300], 599
    if status < 400:
        outcome = "accepted"
    elif status < 500:
        outcome = "rejected"
    else:
        outcome = "error"
    return status, ms, text, outcome


def random_id():
    return hashlib.sha3_256(os.urandom(32)).hexdigest()


def build_stage(stage, tag):
    """Fresh asset lifecycle committed up to ``stage`` (create/adv/offer/sell/return)."""
    ctx = {"seller": generate_keypair(), "buyer": generate_keypair(),
           "escrow": generate_keypair(), "thief": generate_keypair()}
    order = ["create", "adv", "offer", "sell", "return"]
    ctx["create_tx"] = make_create(ctx["seller"], tag)
    st, _, resp = post_tx(ctx["create_tx"])
    require_ok(st, resp, "matrix CREATE")
    ctx["create_id"] = resp.json()["id"]
    if order.index(stage) >= 1:
        st, _, resp = post_tx(make_adv(ctx["seller"], ctx["create_id"]))
        require_ok(st, resp, "matrix ADVERTISEMENT")
        ctx["adv_id"] = resp.json()["id"]
    if order.index(stage) >= 2:
        ctx["offer_tx"] = make_offer(ctx["buyer"], ctx["escrow"], ctx["create_id"], ctx["adv_id"])
        st, _, resp = post_tx(ctx["offer_tx"])
        require_ok(st, resp, "matrix BUY_OFFER")
        ctx["offer_id"] = resp.json()["id"]
    if order.index(stage) >= 3:
        st, _, resp = post_tx(make_sell(ctx["seller"], ctx["buyer"], ctx["create_tx"], ctx["create_id"], ctx["offer_id"]))
        require_ok(st, resp, "matrix SELL")
        ctx["sell_id"] = resp.json()["id"]
    if order.index(stage) >= 4:
        st, _, resp = post_tx(make_return(ctx["buyer"], ctx["create_id"], ctx["sell_id"]))
        require_ok(st, resp, "matrix REQUEST_RETURN")
        ctx["ret_id"] = resp.json()["id"]
    return ctx


def _tampered(tx):
    body = tx.to_dict()
    body["metadata"] = dict(body.get("metadata") or {})
    body["metadata"]["requestCreationTimestamp"] = iso(NOW + timedelta(seconds=1))
    return body


def _bad_status_update(c):
    """Properly signed UPDATE_ADV whose status is outside the lifecycle
    vocabulary (the client library refuses to build one, so mutate before
    signing; sign() recomputes the id)."""
    tx = Transaction.update_adv(
        inputs=gen_input(c["seller"].public_key),
        advertisement_id=c["adv_id"],
        metadata={
            "status": "OPEN",
            "updater_public_key": c["seller"].public_key,
            "price": "99.00",
            "expiry_date": iso(NOW + timedelta(days=30)),
            "requestCreationTimestamp": iso(NOW),
        },
    )
    tx.metadata["status"] = "BANANA"
    return tx.sign([c["seller"].private_key])


def _wrong_updater(c):
    thief = c["thief"]
    return Transaction.update_adv(
        inputs=gen_input(thief.public_key),
        advertisement_id=c["adv_id"],
        metadata={
            "status": "OPEN",
            "updater_public_key": thief.public_key,
            "price": "1.00",
            "expiry_date": iso(NOW + timedelta(days=30)),
            "requestCreationTimestamp": iso(NOW),
        },
    ).sign([thief.private_key])


def _thief_adv(c):
    thief = c["thief"]
    return Transaction.advertisement(
        inputs=gen_input(thief.public_key),
        asset_id=c["create_id"],
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


def _closed_then_offer(c):
    st, _, resp = post_tx(make_update(c["seller"], c["adv_id"], status="CLOSED"))
    require_ok(st, resp, "matrix UPDATE_ADV CLOSED")
    return make_offer(c["buyer"], c["escrow"], c["create_id"], c["adv_id"])


def _wrong_asset_offer(c):
    other = generate_keypair()
    st, _, resp = post_tx(make_create(other, "other"))
    require_ok(st, resp, "matrix other CREATE")
    return make_offer(c["buyer"], c["escrow"], resp.json()["id"], c["adv_id"])


def _duplicate(first_builder):
    def build(c):
        st, _, resp = post_tx(first_builder(c))
        require_ok(st, resp, "matrix duplicate setup")
        return first_builder(c, nonce="dup")
    return build


# (operation, case, stage needed, expected verdict, builder)
SEMANTIC_CASES = [
    ("CREATE", "valid", "create", "accept", lambda c: make_create(c["buyer"], "m-valid")),
    ("CREATE", "tampered_after_sign", "create", "reject", lambda c: _tampered(make_create(c["buyer"], "m-tamper"))),
    ("ADVERTISEMENT", "valid", "create", "accept", lambda c: make_adv(c["seller"], c["create_id"])),
    ("ADVERTISEMENT", "non_owner", "create", "reject", _thief_adv),
    ("ADVERTISEMENT", "missing_asset", "create", "reject", lambda c: make_adv(c["seller"], random_id())),
    ("UPDATE_ADV", "valid", "adv", "accept", lambda c: make_update(c["seller"], c["adv_id"])),
    ("UPDATE_ADV", "wrong_updater", "adv", "reject", _wrong_updater),
    ("UPDATE_ADV", "bad_status", "adv", "reject", _bad_status_update),
    ("UPDATE_ADV", "missing_adv", "adv", "reject", lambda c: make_update(c["seller"], random_id())),
    ("BUY_OFFER", "valid", "adv", "accept", lambda c: make_offer(c["buyer"], c["escrow"], c["create_id"], c["adv_id"])),
    ("BUY_OFFER", "closed_adv", "adv", "reject", _closed_then_offer),
    ("BUY_OFFER", "missing_adv", "adv", "reject", lambda c: make_offer(c["buyer"], c["escrow"], c["create_id"], random_id())),
    ("BUY_OFFER", "asset_mismatch", "adv", "reject", _wrong_asset_offer),
    ("SELL", "valid", "offer", "accept", lambda c: make_sell(c["seller"], c["buyer"], c["create_tx"], c["create_id"], c["offer_id"])),
    ("SELL", "missing_offer", "offer", "reject", lambda c: make_sell(c["seller"], c["buyer"], c["create_tx"], c["create_id"], random_id())),
    ("SELL", "non_owner", "offer", "reject", lambda c: make_sell(c["seller"], c["buyer"], c["create_tx"], c["create_id"], c["offer_id"], signer=c["thief"])),
    ("REQUEST_RETURN", "valid", "sell", "accept", lambda c: make_return(c["buyer"], c["create_id"], c["sell_id"])),
    ("REQUEST_RETURN", "wrong_requester", "sell", "reject", lambda c: make_return(c["thief"], c["create_id"], c["sell_id"])),
    ("REQUEST_RETURN", "missing_sell", "sell", "reject", lambda c: make_return(c["buyer"], c["create_id"], random_id())),
    ("REQUEST_RETURN", "duplicate", "sell", "reject",
     _duplicate(lambda c, nonce="": make_return(c["buyer"], c["create_id"], c["sell_id"], nonce=nonce))),
    ("SELLER_ACCEPT_RETURN", "valid", "return", "accept", lambda c: make_accept(c["seller"], c["create_id"], c["ret_id"])),
    ("SELLER_ACCEPT_RETURN", "wrong_party", "return", "reject", lambda c: make_accept(c["buyer"], c["create_id"], c["ret_id"])),
    ("SELLER_ACCEPT_RETURN", "missing_request", "return", "reject", lambda c: make_accept(c["seller"], c["create_id"], random_id())),
    ("SELLER_ACCEPT_RETURN", "duplicate", "return", "reject",
     _duplicate(lambda c, nonce="": make_accept(c["seller"], c["create_id"], c["ret_id"], nonce=nonce))),
]


def run_semantic_matrix(reps):
    """Valid and invalid cases for all seven operations. Every case gets a
    fresh lifecycle so cases cannot contaminate one another. Verdicts are
    compared offline across live modes (Direct / SHACL / SHACL+Δ)."""
    rows = []
    for rep in range(reps):
        for op, case, stage, expect, builder in SEMANTIC_CASES:
            ctx = build_stage(stage, "m{}-{}-{}".format(rep, op[:4], case[:6]))
            built = builder(ctx)
            body = built if isinstance(built, dict) else built.to_dict()
            status, ms, text, outcome = post_once(body)
            agrees = (outcome == "accepted") == (expect == "accept")
            rows.append({
                "rep": rep, "op": op, "case": case, "expected": expect,
                "status": status, "outcome": outcome, "ms": ms,
                "as_expected": agrees, "body": text,
            })
            print("matrix", op, case, expect, status, outcome, "OK" if agrees else "MISMATCH", flush=True)
    total = len(rows)
    mismatches = [r for r in rows if not r["as_expected"]]
    errors = [r for r in rows if r["outcome"] == "error"]
    return {
        "reps": reps,
        "cases": total,
        "mismatches": len(mismatches),
        "errors_5xx": len(errors),
        "mismatch_rate": len(mismatches) / float(total) if total else 0.0,
        "rows": rows,
    }


def run_engine_down(flag_path, probes=3, wait_s=600):
    """Fail-closed under engine failure. Sets up an OPEN ad while the engine
    is up, signals the runner, waits for the runner to stop every SHACL
    sidecar (it touches ``flag_path``), then submits valid offers."""
    seller, create_id, adv_id = setup_open_ad("down")
    print("READY_FOR_ENGINE_DOWN", flush=True)
    t0 = time.time()
    while not os.path.exists(flag_path):
        if time.time() - t0 > wait_s:
            raise SystemExit("engine-down flag never appeared: {}".format(flag_path))
        time.sleep(1)
    time.sleep(2)
    rows = []
    for i in range(probes):
        offer = make_offer(generate_keypair(), generate_keypair(), create_id, adv_id)
        status, ms, text, outcome = post_once(offer.to_dict(), timeout=120)
        rows.append({"status": status, "ms": ms, "outcome": outcome, "body": text})
        print("engine_down probe", i, status, outcome, "{:.0f} ms".format(ms), flush=True)
        st_v, ms_v, resp_v = validate_http(make_offer(generate_keypair(), generate_keypair(), create_id, adv_id), timeout=120)
        rows[-1]["validate_status"] = st_v
        rows[-1]["validate_ms"] = ms_v
        rows[-1]["validate_body"] = (resp_v.text or "")[:300]
    return {
        "probes": rows,
        "all_rejected": all(r["outcome"] != "accepted" for r in rows),
        "any_committed": any(r["outcome"] == "accepted" for r in rows),
    }


def tm_rpc(method, params=None, timeout=15):
    resp = requests.post(TM_RPC + "/", json={"jsonrpc": "2.0", "id": "eval", "method": method,
                                             "params": params if params is not None else {}}, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def tm_height():
    return int(tm_rpc("status")["result"]["sync_info"]["latest_block_height"])


def tm_unconfirmed():
    return int(tm_rpc("num_unconfirmed_txs")["result"]["n_txs"])


def _parse_tm_time(value):
    # 2026-10-13T10:11:12.123456789Z -> float seconds
    value = value.rstrip("Z")
    head, _, frac = value.partition(".")
    base = datetime.strptime(head, "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc).timestamp()
    return base + (float("0." + frac[:9]) if frac else 0.0)


def tm_blocks(h_from, h_to):
    """Per-block (height, header time, [tx ids], [deliver codes]) for a height range."""
    blocks = []
    for h in range(h_from, h_to + 1):
        blk = tm_rpc("block", {"height": str(h)})["result"]["block"]
        txs_b64 = (blk.get("data") or {}).get("txs") or []
        ids = []
        for raw in txs_b64:
            try:
                ids.append(json.loads(base64.b64decode(raw).decode("utf8")).get("id"))
            except Exception:
                ids.append(None)
        codes = []
        if ids:
            res = tm_rpc("block_results", {"height": str(h)})["result"]
            deliver = ((res.get("results") or {}).get("DeliverTx") or res.get("deliver_tx") or [])
            codes = [int((d or {}).get("code") or 0) for d in deliver]
        blocks.append({"height": h, "time": _parse_tm_time(blk["header"]["time"]), "ids": ids, "codes": codes})
    return blocks


def run_load_open(rates, duration, senders=8):
    """Open-loop submission through Tendermint broadcast_tx_async at fixed
    offered rates. Throughput is counted from committed blocks (DeliverTx
    code 0) rather than from client round trips; latency is block-derived
    (commit time of the block that includes the tx, approximated by the next
    block's header time) and also client-observed for a small sample."""
    seller, create_id, adv_id = setup_open_ad("open")
    out = []
    for rate in rates:
        n = int(rate * duration)
        print("open-loop rate={} n={} pregenerating".format(rate, n), flush=True)
        bodies = [make_offer(generate_keypair(), generate_keypair(), create_id, adv_id).to_dict() for _ in range(n)]
        encoded = [base64.b64encode(json.dumps(b).encode("utf8")).decode("utf8") for b in bodies]
        ids = [b["id"] for b in bodies]
        # Settle any leftovers from the previous rate.
        t_wait = time.time()
        while tm_unconfirmed() > 0 and time.time() - t_wait < 300:
            time.sleep(1)
        shacl_stats(reset=True)
        h0 = tm_height()

        submit_at = {}
        resp_codes = {"ok": 0, "rpc_error": 0, "exception": 0}
        errors = {}
        lock = threading.Lock()
        import queue
        q = queue.Queue()

        def sender():
            while True:
                item = q.get()
                if item is None:
                    return
                i, b64 = item
                try:
                    submit_at[ids[i]] = time.time()
                    r = tm_rpc("broadcast_tx_async", [b64], timeout=30)
                    with lock:
                        if "error" in r:
                            resp_codes["rpc_error"] += 1
                            msg = str(r["error"])[:80]
                            errors[msg] = errors.get(msg, 0) + 1
                        else:
                            resp_codes["ok"] += 1
                except Exception as exc:
                    with lock:
                        resp_codes["exception"] += 1
                        msg = type(exc).__name__
                        errors[msg] = errors.get(msg, 0) + 1

        threads = [threading.Thread(target=sender, daemon=True) for _ in range(senders)]
        for th in threads:
            th.start()

        sample_ids = ids[:: max(1, n // 16)][:16]
        seen_at = {}
        stop = threading.Event()

        def tracker():
            pending = set(sample_ids)
            while pending and not stop.is_set():
                for sid in list(pending):
                    if sid not in submit_at:
                        continue
                    try:
                        got = requests.get(TX_API + "/" + sid, timeout=5)
                        if got.status_code == 200:
                            seen_at[sid] = time.time()
                            pending.discard(sid)
                    except requests.RequestException:
                        pass
                time.sleep(0.5)

        tr = threading.Thread(target=tracker, daemon=True)
        tr.start()

        t_start = time.time()
        for i, b64 in enumerate(encoded):
            target = t_start + i / rate
            delay = target - time.time()
            if delay > 0:
                time.sleep(delay)
            q.put((i, b64))
        for _ in threads:
            q.put(None)
        for th in threads:
            th.join()
        t_submit_end = time.time()

        t_wait = time.time()
        pending_tm = tm_unconfirmed()
        while pending_tm > 0 and time.time() - t_wait < 300:
            time.sleep(1)
            pending_tm = tm_unconfirmed()
        time.sleep(3)
        t_drain_end = time.time()
        stop.set()
        tr.join(timeout=10)
        h1 = tm_height()

        blocks = tm_blocks(h0 + 1, h1)
        wanted = set(ids)
        committed_ok = committed_rejected = 0
        block_latency = []
        for idx, blk in enumerate(blocks):
            commit_time = blocks[idx + 1]["time"] if idx + 1 < len(blocks) else None
            for tid, code in zip(blk["ids"], blk["codes"] or [0] * len(blk["ids"])):
                if tid not in wanted:
                    continue
                if code == 0:
                    committed_ok += 1
                else:
                    committed_rejected += 1
                if commit_time is not None and tid in submit_at:
                    block_latency.append((commit_time - submit_at[tid]) * 1000.0)
        client_latency = [(seen_at[s] - submit_at[s]) * 1000.0 for s in sample_ids if s in seen_at and s in submit_at]
        span_blocks = (blocks[-1]["time"] - blocks[0]["time"]) if len(blocks) > 1 else 0.0
        wall = t_drain_end - t_start
        row = {
            "offered_rate": rate,
            "duration_s": duration,
            "attempted": n,
            "rpc": resp_codes,
            "rpc_errors": errors,
            "submit_wall_s": t_submit_end - t_start,
            "achieved_offered_rate": n / (t_submit_end - t_start) if t_submit_end > t_start else 0.0,
            "drain_wall_s": wall,
            "still_unconfirmed": pending_tm,
            "blocks": len(blocks),
            "block_span_s": span_blocks,
            "committed_ok": committed_ok,
            "committed_rejected": committed_rejected,
            "lost": n - committed_ok - committed_rejected - pending_tm,
            "committed_tps_wall": committed_ok / wall if wall else 0.0,
            "committed_tps_blockspan": committed_ok / span_blocks if span_blocks else 0.0,
            "latency_block_ms": summarize(block_latency),
            "latency_client_ms": summarize(client_latency),
            "stats": shacl_stats(reset=False),
        }
        print("open-loop rate={} committed_ok={} rejected={} lost={} tps_wall={:.2f} p50={:.0f}ms".format(
            rate, committed_ok, committed_rejected, row["lost"], row["committed_tps_wall"],
            row["latency_block_ms"].get("median", float("nan"))), flush=True)
        out.append(row)
        if rate > 0 and committed_ok < 0.5 * n:
            print("saturated: fewer than half committed; stopping sweep", flush=True)
            break
    return out


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
    parser.add_argument("--skip-matrix", action="store_true")
    parser.add_argument("--skip-open-load", action="store_true")
    parser.add_argument("--skip-sequence", action="store_true")
    parser.add_argument("--skip-ratio", action="store_true")
    parser.add_argument("--only-fail-closed", action="store_true")
    parser.add_argument("--only-engine-down", action="store_true")
    parser.add_argument("--only-open-load", action="store_true")
    parser.add_argument("--only-inprocess", action="store_true",
                        help="validator microbench + Δ sequence only (run inside a validator)")
    parser.add_argument("--state-label", default=None,
                        help="label recorded with --only-inprocess results (e.g. seeded ledger size)")
    parser.add_argument("--wan", action="store_true")
    args = parser.parse_args()

    def write(payload):
        payload["finished_unix"] = time.time()
        outdir = os.path.dirname(args.out)
        if outdir and not os.path.exists(outdir):
            os.makedirs(outdir)
        with open(args.out, "w") as handle:
            json.dump(payload, handle, indent=2)
        print("WROTE", args.out)

    wait_api()
    import logging
    logging.getLogger("bigchaindb").setLevel(logging.CRITICAL)  # rejections are expected; keep stdout readable
    if args.only_inprocess:
        payload = {"platform": "bigchaindb", "live_mode": args.live_mode, "started_unix": time.time(),
                   "n_val": N_VAL, "seq_reps": SEQ_REPS, "state_label": args.state_label}
        print("=== validation layer n={} ===".format(N_VAL))
        payload["validation_layer"] = run_validation_layer(N_VAL)
        print("validation medians", {k: v.get("median") for k, v in payload["validation_layer"].items()
                                     if isinstance(v, dict) and "median" in v})
        if not args.skip_sequence:
            print("=== delta sequence reps={} ===".format(SEQ_REPS))
            payload["delta_sequence"] = run_delta_sequence(SEQ_REPS)
            print("sequence summary", json.dumps(payload["delta_sequence"]["summary"]))
        payload["server_stats"] = shacl_stats(reset=False)
        write(payload)
        return
    if args.only_engine_down:
        payload = {"platform": "bigchaindb", "live_mode": args.live_mode, "started_unix": time.time()}
        print("=== engine down ===")
        payload["engine_down"] = run_engine_down(ENGINE_DOWN_FLAG)
        print("engine_down all_rejected", payload["engine_down"]["all_rejected"])
        write(payload)
        return
    if args.only_open_load:
        payload = {"platform": "bigchaindb", "live_mode": args.live_mode, "started_unix": time.time(),
                   "open_rates": OPEN_RATES, "open_duration": OPEN_DURATION, "tm_rpc": TM_RPC}
        print("=== open-loop load rates={} duration={} ===".format(OPEN_RATES, OPEN_DURATION))
        payload["load_open"] = run_load_open(OPEN_RATES, OPEN_DURATION)
        write(payload)
        return
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
        write(payload)
        return

    payload = {
        "platform": "bigchaindb",
        "live_mode": args.live_mode,
        "wan": bool(args.wan),
        "n_val": N_VAL,
        "n_e2e": N_E2E,
        "n_offer": N_OFFER,
        "n_disjoint": N_DISJOINT,
        "n_load": N_LOAD,
        "matrix_reps": MATRIX_REPS,
        "started_unix": time.time(),
        "server_stats_probe": shacl_stats(reset=False),
    }
    mempool = args.live_mode == "delta"

    if not args.skip_validation and args.live_mode == "delta" and not args.wan:
        print("=== validation layer n={} ===".format(N_VAL))
        payload["validation_layer"] = run_validation_layer(N_VAL)
        print("validation medians", {k: v.get("median") for k, v in payload["validation_layer"].items()
                                     if isinstance(v, dict) and "median" in v})
        if not args.skip_sequence:
            print("=== delta sequence reps={} ===".format(SEQ_REPS))
            payload["delta_sequence"] = run_delta_sequence(SEQ_REPS)

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
            print("=== mix disjoint n={} ===".format(N_DISJOINT))
            payload["mix_disjoint"] = run_mix_disjoint(N_DISJOINT)
        print("=== fail-closed ===")
        payload["fail_closed"] = run_fail_closed()

    if not args.skip_ratio and args.live_mode == "delta" and not args.wan:
        print("=== relevant-update ratio sweep n={} ratios={} ===".format(N_RATIO, RATIOS))
        payload["update_ratio"] = run_update_ratio_sweep(N_RATIO, RATIOS)

    if not args.skip_matrix and not args.wan:
        print("=== semantic matrix reps={} ===".format(MATRIX_REPS))
        payload["semantic_matrix"] = run_semantic_matrix(MATRIX_REPS)
        print("matrix mismatches", payload["semantic_matrix"]["mismatches"], "/", payload["semantic_matrix"]["cases"],
              "5xx", payload["semantic_matrix"]["errors_5xx"])

    if not args.skip_conflict and not args.wan:
        print("=== conflict ===")
        payload["conflict"] = run_conflict()

    if not args.skip_load and not args.wan:
        print("=== closed-loop load {} ===".format(LOAD_CONC))
        payload["load"] = run_load(N_LOAD, LOAD_CONC)

    if not args.skip_open_load and not args.wan:
        print("=== open-loop load rates={} duration={} ===".format(OPEN_RATES, OPEN_DURATION))
        payload["load_open"] = run_load_open(OPEN_RATES, OPEN_DURATION)

    write(payload)


if __name__ == "__main__":
    main()
