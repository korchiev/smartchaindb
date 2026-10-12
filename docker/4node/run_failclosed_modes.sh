#!/bin/bash
# Re-measure mutate + stolen-ad on the 4-validator cluster for Direct / SHACL / Δ.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
COMPOSE=(docker compose --env-file .env --env-file docker/4node/peers.env -f docker-compose.4node.yml)
OUT="$ROOT/eval/results"
mkdir -p "$OUT"

wait_http() {
  local ok=0
  local i
  for i in $(seq 1 40); do
    if curl -sf http://127.0.0.1:9984 >/dev/null; then
      ok=1
      break
    fi
    sleep 3
  done
  if [[ "$ok" != 1 ]]; then
    echo "HTTP 9984 not ready"
    exit 1
  fi
}

run_mode() {
  local mode="$1"
  local enabled="$2"
  local cache="$3"
  echo "======== mode=${mode} SHACL=${enabled} CACHE=${cache} ========"
  export BIGCHAINDB_SHACL_ENABLED="$enabled"
  export BIGCHAINDB_SHACL_CACHE="$cache"
  "${COMPOSE[@]}" up -d --force-recreate --no-deps bdb1 bdb2 bdb3 bdb4
  "${COMPOSE[@]}" restart tm1 tm2 tm3 tm4
  wait_http
  sleep 8
  docker cp "$ROOT/eval/bdb_professor_eval.py" scdb4-bdb1-1:/tmp/bdb_professor_eval.py
  docker exec \
    -e N_OFFER=20 \
    -e BDB_API=http://127.0.0.1:9984/api/v1 \
    scdb4-bdb1-1 \
    python /tmp/bdb_professor_eval.py --live-mode "$mode" --only-fail-closed --out "/tmp/bdb_fc_${mode}.json"
  docker cp "scdb4-bdb1-1:/tmp/bdb_fc_${mode}.json" "$OUT/bdb_fc_${mode}.json"
  echo "wrote $OUT/bdb_fc_${mode}.json"
}

run_mode direct false false
run_mode shacl true false
run_mode delta true true
echo "fail-closed campaign done"
