#!/bin/bash
set -euo pipefail
ROOT=/mnt/c/Users/korchien/Research/smartchaindb
cd "$ROOT"

echo "=== restart SHACL + BigchainDB to pick up mounted code ==="
docker restart smartchaindb-shacleng-1 smartchaindb-bigchaindb-1 >/dev/null

echo "=== wait for health ==="
ok=0
for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20; do
  if curl -sf http://127.0.0.1:9984 >/dev/null && curl -sf http://127.0.0.1:3000 >/dev/null; then
    ok=1
    break
  fi
  sleep 2
done
if [ "$ok" != 1 ]; then
  echo "stack did not become healthy"
  docker ps --format 'table {{.Names}}\t{{.Status}}'
  docker logs smartchaindb-bigchaindb-1 --tail 40
  docker logs smartchaindb-shacleng-1 --tail 20
  exit 1
fi

echo "=== SHACL health ==="
curl -sS http://127.0.0.1:3000/
echo

echo "=== run lifecycle inside bigchaindb ==="
docker cp "$ROOT/docker/smoke_workflow.py" smartchaindb-bigchaindb-1:/tmp/smoke_workflow.py
docker exec smartchaindb-bigchaindb-1 python /tmp/smoke_workflow.py

echo "=== tendermint sync ==="
curl -sS http://127.0.0.1:26657/status | python3 -c 'import sys,json; print(json.load(sys.stdin)["result"]["sync_info"])'
echo "=== recent bdb log ==="
docker logs smartchaindb-bigchaindb-1 --tail 30
