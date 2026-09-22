#!/bin/bash
set -euo pipefail
cd /mnt/c/Users/korchien/Research/smartchaindb
docker compose restart tendermint
sleep 8
echo "=== tendermint sync ==="
curl -sS -m 5 http://127.0.0.1:26657/status
echo
echo "=== tm log ==="
docker logs smartchaindb-tendermint-1 --tail 15
