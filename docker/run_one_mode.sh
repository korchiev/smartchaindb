#!/bin/bash
set -euo pipefail
ROOT=/mnt/c/Users/korchien/Research/smartchaindb
cd "$ROOT"
MODE="${1:-direct}"
case "$MODE" in
  direct) export BIGCHAINDB_SHACL_ENABLED=false; export BIGCHAINDB_SHACL_CACHE=false ;;
  shacl) export BIGCHAINDB_SHACL_ENABLED=true; export BIGCHAINDB_SHACL_CACHE=false ;;
  delta) export BIGCHAINDB_SHACL_ENABLED=true; export BIGCHAINDB_SHACL_CACHE=true ;;
  *) echo "mode: direct|shacl|delta"; exit 1 ;;
esac

echo "=== mode $MODE enabled=$BIGCHAINDB_SHACL_ENABLED cache=$BIGCHAINDB_SHACL_CACHE ==="
if docker compose version >/dev/null 2>&1; then
  docker compose up -d --no-deps --force-recreate bigchaindb
else
  echo "docker compose missing"
  exit 1
fi
docker restart smartchaindb-tendermint-1 >/dev/null
ok=0
for i in $(seq 1 25); do
  if curl -sf http://127.0.0.1:9984 >/dev/null && curl -sf http://127.0.0.1:26657/status >/dev/null; then
    ok=1
    break
  fi
  sleep 2
done
if [ "$ok" != 1 ]; then
  echo "unhealthy"
  docker logs smartchaindb-bigchaindb-1 --tail 40
  exit 1
fi
docker cp "$ROOT/docker/smoke_workflow.py" smartchaindb-bigchaindb-1:/tmp/smoke_workflow.py
docker exec smartchaindb-bigchaindb-1 python /tmp/smoke_workflow.py
