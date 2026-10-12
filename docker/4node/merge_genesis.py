#!/usr/bin/env python3
"""Merge four tendermint inits into one 4-validator genesis + peers.env."""
from __future__ import print_function

import json
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))


def main():
    validators = []
    ids = []
    genesis = None
    for i in range(1, 5):
        cfg = os.path.join(ROOT, "n%d" % i, "config")
        with open(os.path.join(cfg, "priv_validator_key.json")) as f:
            key = json.load(f)
        validators.append({
            "address": key["address"],
            "pub_key": key["pub_key"],
            "power": "10",
            "name": "tm%d" % i,
        })
        if genesis is None:
            with open(os.path.join(cfg, "genesis.json")) as f:
                genesis = json.load(f)
        with open(os.path.join(ROOT, "n%d" % i, "node_id")) as f:
            ids.append(f.read().strip())

    genesis["chain_id"] = "smartchaindb-4node"
    genesis["validators"] = validators
    body = json.dumps(genesis, indent=2) + "\n"
    for i in range(1, 5):
        path = os.path.join(ROOT, "n%d" % i, "config", "genesis.json")
        with open(path, "w") as f:
            f.write(body)
        state = os.path.join(ROOT, "n%d" % i, "data", "priv_validator_state.json")
        os.makedirs(os.path.dirname(state), exist_ok=True)
        with open(state, "w") as f:
            f.write('{"height": "0", "round": "0", "step": 0}\n')
        cfg_toml = os.path.join(ROOT, "n%d" % i, "config", "config.toml")
        with open(cfg_toml) as f:
            toml = f.read()
        toml = toml.replace("allow_duplicate_ip = false", "allow_duplicate_ip = true")
        toml = toml.replace("addr_book_strict = true", "addr_book_strict = false")
        with open(cfg_toml, "w") as f:
            f.write(toml)

    lines = []
    for i in range(1, 5):
        peers = []
        for j in range(1, 5):
            if i == j:
                continue
            peers.append("%s@tm%d:26656" % (ids[j - 1], j))
        lines.append("TM%d_PEERS=%s" % (i, ",".join(peers)))
    with open(os.path.join(ROOT, "peers.env"), "w") as f:
        f.write("\n".join(lines) + "\n")

    print("chain_id=smartchaindb-4node")
    for i, nid in enumerate(ids, 1):
        print("tm%d node_id=%s" % (i, nid))
    print("wrote", os.path.join(ROOT, "peers.env"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
