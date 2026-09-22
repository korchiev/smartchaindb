#!/bin/bash
set -euo pipefail
export PATH="${HOME}/fabric-samples/bin:${PATH}"
ROOT="/mnt/c/Users/korchien/Research/smartchaindb"
export FABRIC_CONNECTION_PROFILE="${HOME}/fabric-samples/test-network/organizations/peerOrganizations/org1.example.com/connection-org1.json"
export FABRIC_WALLET_DIR="${HOME}/fabric-wallet"
export FABRIC_IDENTITY=appUser
export FABRIC_CHANNEL=mychannel
export FABRIC_CONTRACT=marketplace
export SHACL_ENDPOINT=http://127.0.0.1:3001

echo "=== health ==="
curl -sS -m 3 http://127.0.0.1:3001/
echo
docker ps --format '{{.Names}} {{.Status}}' | grep -E 'peer0|orderer' || true

cd "${ROOT}/fabric/client"
if [ ! -d node_modules ]; then
  npm install
fi
node enroll.js
echo "=== fabric smoke USE_SHACL=true ==="
USE_SHACL=true npm run smoke
