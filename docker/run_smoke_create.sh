#!/bin/bash
set -euo pipefail
docker cp /mnt/c/Users/korchien/Research/smartchaindb/docker/smoke_create.py smartchaindb-bigchaindb-1:/tmp/smoke_create.py
docker exec smartchaindb-bigchaindb-1 python /tmp/smoke_create.py
echo "=== tendermint sync ==="
curl -sS http://127.0.0.1:26657/status | python3 -c 'import sys,json; print(json.load(sys.stdin)["result"]["sync_info"])'
echo "=== recent bdb log ==="
docker logs smartchaindb-bigchaindb-1 --tail 20
