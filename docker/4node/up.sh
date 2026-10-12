#!/bin/bash
# Bring up the LAN 4-validator cluster. Stop the 1-node stack first.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
COMPOSE=(docker compose --env-file .env --env-file docker/4node/peers.env -f docker-compose.4node.yml)

if [[ ! -f docker/4node/peers.env || ! -f docker/4node/n1/config/genesis.json ]]; then
  echo "=== generating 4-validator genesis ==="
  bash docker/4node/gen_genesis.sh
fi

if curl -sf http://127.0.0.1:9984 >/dev/null 2>&1; then
  echo "Port 9984 in use — stopping 1-node stack"
  docker compose -f docker-compose.yml down
fi

echo "=== starting 4-node cluster ==="
"${COMPOSE[@]}" up -d

echo "=== waiting for HTTP on 9984/9184/9284/9384 ==="
ok=0
for i in $(seq 1 60); do
  if curl -sf http://127.0.0.1:9984 >/dev/null \
     && curl -sf http://127.0.0.1:9184 >/dev/null \
     && curl -sf http://127.0.0.1:9284 >/dev/null \
     && curl -sf http://127.0.0.1:9384 >/dev/null; then
    ok=1
    break
  fi
  sleep 3
done
if [[ "$ok" != 1 ]]; then
  echo "cluster HTTP not ready"
  "${COMPOSE[@]}" ps
  "${COMPOSE[@]}" logs --tail 40 bdb1 tm1
  exit 1
fi

echo "=== tendermint net_info (want n_peers=3 on each) ==="
for port in 26657 26667 26677 26687; do
  peers=$(curl -sf "http://127.0.0.1:${port}/net_info" | grep -o '"n_peers": "[0-9]*"' | head -1 | grep -o '[0-9]*' || echo "?")
  echo "  :${port} n_peers=${peers}"
done

echo "cluster up. clients: http://127.0.0.1:9984 (and 9184, 9284, 9384)"
