#!/bin/bash
set -euo pipefail
ROOT=/mnt/c/Users/korchien/Research/smartchaindb
cd "$ROOT"
N="${N:-3}"

recreate_bdb() {
  local enabled="$1"
  local cache="$2"
  echo "=== recreate bigchaindb SHACL_ENABLED=${enabled} SHACL_CACHE=${cache} ==="
  docker stop smartchaindb-bigchaindb-1 >/dev/null 2>&1 || true
  docker rm smartchaindb-bigchaindb-1 >/dev/null 2>&1 || true
  docker compose up -d --no-deps --force-recreate bigchaindb >/dev/null \
    || docker-compose up -d --no-deps --force-recreate bigchaindb >/dev/null
  docker update --env-file /dev/null smartchaindb-bigchaindb-1 >/dev/null 2>&1 || true
}

# docker compose v2 honors env on recreate if we export vars
bring_up() {
  local enabled="$1"
  local cache="$2"
  export BIGCHAINDB_SHACL_ENABLED="$enabled"
  export BIGCHAINDB_SHACL_CACHE="$cache"
  if docker compose version >/dev/null 2>&1; then
    docker compose up -d --no-deps --force-recreate bigchaindb
  else
    echo "docker compose plugin missing; restarting existing container (env may not change)"
    docker restart smartchaindb-bigchaindb-1 >/dev/null
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
    echo "stack unhealthy"
    docker logs smartchaindb-bigchaindb-1 --tail 30
    exit 1
  fi
}

run_trials() {
  local label="$1"
  docker cp "$ROOT/docker/smoke_workflow.py" smartchaindb-bigchaindb-1:/tmp/smoke_workflow.py
  local i
  for i in $(seq 1 "$N"); do
    echo "--- $label trial $i ---"
    docker exec smartchaindb-bigchaindb-1 python /tmp/smoke_workflow.py | tail -n 20
  done
}

echo "=== Direct ==="
bring_up false false
run_trials Direct

echo "=== SHACL ==="
bring_up true false
run_trials SHACL

echo "=== SHACL+Δ ==="
bring_up true true
run_trials 'SHACL+Δ'

echo "THREE-WAY EVAL OK"
