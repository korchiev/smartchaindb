#!/bin/bash
set -euo pipefail
echo "=== docker ==="
docker ps -a --format '{{.Names}} {{.Status}}' | grep -E 'peer0|orderer|marketplace' || true
echo "=== org1 log ==="
docker logs peer0.org1.example.com --tail 30 || true
echo "=== orderer log ==="
docker logs orderer.example.com --tail 15 || true
