#!/bin/bash
# Create four Tendermint validator homes and a shared 4-validator genesis.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
IMAGE=tendermint/tendermint:v0.31.5

for i in 1 2 3 4; do
  rm -rf "$HERE/n$i"
  mkdir -p "$HERE/n$i"
  docker run --rm \
    -v "$HERE/n$i:/tendermint" \
    --entrypoint tendermint \
    "$IMAGE" init
  docker run --rm \
    -v "$HERE/n$i:/tendermint" \
    --entrypoint tendermint \
    "$IMAGE" show_node_id > "$HERE/n$i/node_id"
done

if command -v python3 >/dev/null 2>&1; then
  python3 "$HERE/merge_genesis.py"
else
  python "$HERE/merge_genesis.py"
fi
echo "4-node genesis ready under $HERE"
