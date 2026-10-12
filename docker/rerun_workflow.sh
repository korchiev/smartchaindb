#!/bin/bash
set -euo pipefail
docker restart smartchaindb-bigchaindb-1 smartchaindb-tendermint-1 >/dev/null
ok=0
for i in $(seq 1 20); do
  if curl -sf http://127.0.0.1:9984 >/dev/null && curl -sf http://127.0.0.1:26657/status >/dev/null; then
    ok=1
    break
  fi
  sleep 2
done
echo "stack-ok=$ok"
if [ "$ok" != 1 ]; then
  docker logs smartchaindb-bigchaindb-1 --tail 30
  exit 1
fi
docker exec smartchaindb-bigchaindb-1 python /tmp/smoke_workflow.py
