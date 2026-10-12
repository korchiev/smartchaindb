#!/bin/bash
# Start the single validator on this host. Run from the repo root.
set -euo pipefail
cd "$(dirname "$0")/../.."
test -f .env
test -f docker/4node/node.env
test -f docker/4node/node/config/genesis.json
docker compose --env-file .env --env-file docker/4node/node.env -f docker-compose.onenode.yml up -d --build mongo shacl
bash docker/4node/start_tm.sh
docker compose --env-file .env --env-file docker/4node/node.env -f docker-compose.onenode.yml up -d --build bdb
