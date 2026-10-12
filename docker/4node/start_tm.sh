#!/bin/bash
# Tendermint is started outside Compose. Compose rejects this image's entrypoint
# override and reports it as an invalid mount.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
HOME_DIR="$ROOT/docker/4node/node"
test -x "$HOME_DIR/run.sh"
test -f "$HOME_DIR/node.env"
docker rm -f scdb-node-tm-1 >/dev/null 2>&1 || true
docker run -d \
  --name scdb-node-tm-1 \
  --network scdb-node_default \
  --network-alias tm \
  --hostname tm \
  --user 0:0 \
  -v "$HOME_DIR:/tendermint" \
  -p 26656:26656 \
  -p 26657:26657 \
  --restart unless-stopped \
  --entrypoint /bin/sh \
  tendermint/tendermint:v0.31.5 \
  /tendermint/run.sh
