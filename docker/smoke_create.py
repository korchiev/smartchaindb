#!/usr/bin/env python3
"""Smoke CREATE through live BigchainDB + SHACL (run inside the bigchaindb container)."""
from datetime import datetime

import requests
from bigchaindb_driver.crypto import generate_keypair
from bigchaindb.common.transaction import Transaction

alice = generate_keypair()
tx = Transaction.create(
    [alice.public_key],
    [([alice.public_key], 1)],
    metadata={"requestCreationTimestamp": datetime.utcnow().isoformat()},
    asset={
        "machineIdentifier": "wsl-smoke-1",
        "capability": ["read"],
        "capabilityParameters": {"p": "1"},
    },
).sign([alice.private_key])

url = "http://127.0.0.1:9984/api/v1/transactions?mode=commit"
resp = requests.post(url, json=tx.to_dict(), timeout=30)
print("POST", resp.status_code)
print(resp.text[:800])
if resp.status_code >= 400:
    raise SystemExit(1)

txid = resp.json().get("id") or tx.id
got = requests.get("http://127.0.0.1:9984/api/v1/transactions/" + txid, timeout=10)
print("GET", got.status_code, got.json().get("operation"), got.json().get("id"))
