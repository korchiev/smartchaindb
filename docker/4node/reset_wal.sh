#!/bin/bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
for i in 1 2 3 4; do
  rm -rf "$HERE/n$i/data"
  mkdir -p "$HERE/n$i/data"
  printf '%s\n' '{"height": "0", "round": "0", "step": 0}' > "$HERE/n$i/data/priv_validator_state.json"
done
echo "tendermint WAL reset (keys kept)"
