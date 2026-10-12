#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
docker compose --env-file .env --env-file docker/4node/peers.env -f docker-compose.4node.yml down
echo "4-node cluster stopped (validator keys kept under docker/4node/n*)"
