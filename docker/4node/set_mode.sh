#!/bin/bash
# Recreate this host's BigchainDB container in one validation mode.
# Tendermint is restarted by the caller after every host has been recreated.
set -euo pipefail
mode="${1:?mode direct|shacl|delta}"
cd /root/smartchaindb
case "$mode" in
  direct) en=false; ca=false ;;
  shacl) en=true; ca=false ;;
  delta) en=true; ca=true ;;
  *) echo "unknown mode: $mode" >&2; exit 1 ;;
esac
export BIGCHAINDB_SHACL_ENABLED="$en"
export BIGCHAINDB_SHACL_CACHE="$ca"
docker compose --env-file .env --env-file docker/4node/node.env \
  -f docker-compose.onenode.yml up -d --no-build --no-deps --force-recreate bdb
docker exec scdb-node-bdb-1 python -c 'import os; print(os.environ.get("BIGCHAINDB_SHACL_ENABLED"), os.environ.get("BIGCHAINDB_SHACL_CACHE"))'
