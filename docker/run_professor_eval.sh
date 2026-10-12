#!/bin/bash
set -euo pipefail
ROOT=/mnt/c/Users/korchien/Research/smartchaindb
cd "$ROOT"
OUT="$ROOT/eval/results"
mkdir -p "$OUT"
export BIGCHAINDB_SERVER_WORKERS=1
N_VAL="${N_VAL:-20}"
N_E2E="${N_E2E:-5}"
N_OFFER="${N_OFFER:-20}"
N_LOAD="${N_LOAD:-16}"
LOAD_CONC="${LOAD_CONC:-1,2,4,8}"
export N_VAL N_E2E N_OFFER N_LOAD LOAD_CONC

bring_up() {
  local enabled="$1"
  local cache="$2"
  export BIGCHAINDB_SHACL_ENABLED="$enabled"
  export BIGCHAINDB_SHACL_CACHE="$cache"
  export BIGCHAINDB_SERVER_WORKERS=1
  echo "=== BDB SHACL_ENABLED=${enabled} CACHE=${cache} WORKERS=1 ==="
  if docker compose version >/dev/null 2>&1; then
    docker compose up -d --no-deps --force-recreate bigchaindb
  else
    echo "docker compose plugin missing"
    exit 1
  fi
  docker restart smartchaindb-tendermint-1 >/dev/null
  ok=0
  for i in $(seq 1 30); do
    if curl -sf http://127.0.0.1:9984 >/dev/null && curl -sf http://127.0.0.1:26657/status >/dev/null; then
      ok=1
      break
    fi
    sleep 2
  done
    if [ "$ok" != 1 ]; then
    echo "stack unhealthy"
    docker logs smartchaindb-bigchaindb-1 --tail 40
    exit 1
  fi
  sleep 8
}

copy_eval() {
  docker cp "$ROOT/eval/bdb_professor_eval.py" smartchaindb-bigchaindb-1:/tmp/bdb_professor_eval.py
}

run_mode() {
  local mode="$1"
  shift
  copy_eval
  docker exec \
    -e N_VAL="$N_VAL" -e N_E2E="$N_E2E" -e N_OFFER="$N_OFFER" -e N_LOAD="$N_LOAD" -e LOAD_CONC="$LOAD_CONC" \
    smartchaindb-bigchaindb-1 \
    python /tmp/bdb_professor_eval.py --live-mode "$mode" --out "/tmp/bdb_${mode}.json" "$@"
  docker cp "smartchaindb-bigchaindb-1:/tmp/bdb_${mode}.json" "$OUT/bdb_${mode}.json"
}

sample_cpu() {
  local log="$1"
  : > "$log"
  while true; do
    docker stats --no-stream --format '{{.Name}},{{.CPUPerc}},{{.MemPerc}}' \
      smartchaindb-shacleng-1 smartchaindb-bigchaindb-1 smartchaindb-tendermint-1 \
      >> "$log" 2>/dev/null || true
    sleep 1
  done
}

clear_netem() {
  for c in smartchaindb-bigchaindb-1 smartchaindb-tendermint-1 smartchaindb-shacleng-1; do
    docker exec -u root "$c" sh -c 'tc qdisc del dev eth0 root 2>/dev/null || true' 2>/dev/null || true
  done
}

apply_netem() {
  local delay="${1:-40}"
  local jitter="${2:-5}"
  echo "=== WAN netem ${delay}ms ±${jitter}ms ==="
  for c in smartchaindb-bigchaindb-1 smartchaindb-tendermint-1; do
    docker exec -u root "$c" sh -c "
      (command -v tc >/dev/null || (apt-get update -qq && apt-get install -y -qq iproute2) || (apk add --no-cache iproute2) || true)
      tc qdisc del dev eth0 root 2>/dev/null || true
      tc qdisc add dev eth0 root netem delay ${delay}ms ${jitter}ms
      tc qdisc show dev eth0
    " || echo "netem failed on $c"
  done
}

echo "=== professor BDB remainder (direct + WAN) $(date -Is) ==="
sample_cpu "$OUT/cpu_bdb.csv" &
CPUPID=$!
trap 'kill $CPUPID 2>/dev/null || true; clear_netem' EXIT

if [ ! -f "$OUT/bdb_direct.json" ]; then
  bring_up false false
  docker restart smartchaindb-tendermint-1 >/dev/null
  sleep 8
  run_mode direct --skip-validation --skip-conflict
fi

bring_up true true
docker restart smartchaindb-tendermint-1 >/dev/null
sleep 8
apply_netem 40 5
copy_eval
docker exec \
  -e N_VAL="$N_VAL" -e N_E2E="$N_E2E" -e N_OFFER="$N_OFFER" -e N_LOAD="$N_LOAD" \
  smartchaindb-bigchaindb-1 \
  python /tmp/bdb_professor_eval.py --live-mode delta --out /tmp/bdb_wan.json --wan --skip-validation --skip-e2e --skip-load --skip-conflict
docker cp smartchaindb-bigchaindb-1:/tmp/bdb_wan.json "$OUT/bdb_wan.json"
clear_netem

kill "$CPUPID" 2>/dev/null || true
echo "=== professor BDB eval done $(date -Is) ==="
ls -l "$OUT"

