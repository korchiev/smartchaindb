#!/usr/bin/env python3
"""Seed synthetic marketplace state directly into MongoDB (state-size sweep).

Runs inside the bigchaindb container on *every* validator with the same
arguments, so the four databases stay identical. Documents are deterministic
(ids derive from the lifecycle index), carry ``seed: true`` and never collide
with live transactions; nothing the live workload submits references them.
This emulates ledger size for the validator microbenchmark; it does not go
through consensus and the paper says so.

Usage:
  python eval/seed_state.py --target 10000        # ensure 10,000 lifecycles exist
  python eval/seed_state.py --reset               # remove seeded documents
  python eval/seed_state.py --indexes off|on      # drop / recreate marketplace indexes
"""
import argparse
import hashlib
import json
import time

from bigchaindb import config_utils
from bigchaindb.lib import BigchainDB
from bigchaindb.backend.localmongodb.schema import INDEXES

MARKER = {"seed": True}
PK = "H" * 43  # syntactically plausible base58 key; never signs anything


def hid(kind, i):
    return hashlib.sha3_256("seed:{}:{}".format(kind, i).encode()).hexdigest()


def lifecycle(i):
    ts = "2026-01-01T00:00:00.000000+00:00"
    create_id, adv_id, offer_id, upd_id = hid("create", i), hid("adv", i), hid("offer", i), hid("upd", i)
    txs = [
        {"id": create_id, "operation": "CREATE", "version": "2.0", "inputs": [],
         "outputs": [{"public_keys": [PK], "amount": "1", "condition": {}}], "seed": True},
        {"id": adv_id, "operation": "ADVERTISEMENT", "version": "2.0", "inputs": [], "outputs": [],
         "asset": {"id": create_id}, "seed": True},
        {"id": offer_id, "operation": "BUY_OFFER", "version": "2.0", "inputs": [], "outputs": [],
         "asset": {"id": create_id, "data": {"advertisement_id": adv_id}}, "seed": True},
    ]
    metas = [
        {"id": create_id, "metadata": {"requestCreationTimestamp": ts}, "seed": True},
        {"id": adv_id, "metadata": {"status": "OPEN", "advertiser_public_key": PK, "price": "100.00",
                                    "requestCreationTimestamp": ts}, "seed": True},
        {"id": offer_id, "metadata": {"buyer_public_key": PK, "offer_amount": "100",
                                      "requestCreationTimestamp": ts}, "seed": True},
    ]
    assets = [{"id": create_id, "data": {"machineIdentifier": "seed-{}".format(i)}, "seed": True}]
    if i % 10 == 0:  # one in ten advertisements has been updated (closed)
        txs.append({"id": upd_id, "operation": "UPDATE_ADV", "version": "2.0", "inputs": [], "outputs": [],
                    "asset": {"id": adv_id, "data": {"id": adv_id}}, "seed": True})
        metas.append({"id": upd_id, "metadata": {"status": "CLOSED", "updater_public_key": PK,
                                                 "requestCreationTimestamp": ts}, "seed": True})
    return txs, metas, assets


def insert(coll, docs):
    if not docs:
        return
    try:
        coll.insert_many(docs, ordered=False)
    except Exception as exc:  # duplicates on re-run are fine
        if "duplicate" not in str(exc).lower() and "E11000" not in str(exc):
            raise


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", type=int, help="total seeded lifecycles to ensure")
    parser.add_argument("--reset", action="store_true")
    parser.add_argument("--indexes", choices=["on", "off"])
    parser.add_argument("--chunk", type=int, default=2000)
    args = parser.parse_args()

    config_utils.autoconfigure()
    b = BigchainDB()
    db = b.connection.conn[b.connection.dbname]
    txc, metac, assetc = db["transactions"], db["metadata"], db["assets"]
    marker = db["eval_seed"]

    if args.reset:
        t0 = time.time()
        r1 = txc.delete_many(MARKER).deleted_count
        r2 = metac.delete_many(MARKER).deleted_count
        r3 = assetc.delete_many(MARKER).deleted_count
        marker.delete_many({})
        print(json.dumps({"reset": True, "transactions": r1, "metadata": r2, "assets": r3,
                          "seconds": time.time() - t0}))

    if args.indexes:
        names = [kw["name"] for fields, kw in INDEXES["transactions"] if kw["name"].startswith("mk_")]
        existing = set(txc.index_information().keys())
        if args.indexes == "off":
            for name in names:
                if name in existing:
                    txc.drop_index(name)
            print(json.dumps({"indexes": "off", "dropped": [n for n in names if n in existing]}))
        else:
            t0 = time.time()
            for fields, kw in INDEXES["transactions"]:
                if kw["name"].startswith("mk_"):
                    txc.create_index(fields, **kw)
            print(json.dumps({"indexes": "on", "created": names, "seconds": time.time() - t0}))

    if args.target is not None:
        have = (marker.find_one({"_id": "lifecycles"}) or {}).get("n", 0)
        t0 = time.time()
        i = have
        while i < args.target:
            hi = min(args.target, i + args.chunk)
            txs, metas, assets = [], [], []
            for k in range(i, hi):
                a, m, s = lifecycle(k)
                txs += a
                metas += m
                assets += s
            insert(txc, txs)
            insert(metac, metas)
            insert(assetc, assets)
            i = hi
            marker.replace_one({"_id": "lifecycles"}, {"_id": "lifecycles", "n": i}, upsert=True)
        print(json.dumps({
            "seeded_lifecycles": args.target, "added": args.target - have,
            "seconds": time.time() - t0,
            "transactions_total": txc.estimated_document_count(),
            "seeded_transactions": txc.count_documents(MARKER),
            "indexes": sorted(txc.index_information().keys()),
        }))


if __name__ == "__main__":
    main()
