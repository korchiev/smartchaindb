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

docker start orderer.example.com peer0.org1.example.com peer0.org2.example.com >/dev/null
echo "started peers"

for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15; do
  if timeout 1 bash -c 'echo >/dev/tcp/127.0.0.1/7051' 2>/dev/null \
    && timeout 1 bash -c 'echo >/dev/tcp/127.0.0.1/9051' 2>/dev/null \
    && timeout 1 bash -c 'echo >/dev/tcp/127.0.0.1/7050' 2>/dev/null; then
    echo "grpc ports open"
    break
  fi
  sleep 1
done

# Give the peer gRPC stack a few seconds after TCP accept.
sleep 5

if ! curl -sf http://127.0.0.1:3001/ >/dev/null; then
  echo "Fabric SHACL :3001 is down"
  exit 1
fi

cd "${ROOT}/fabric/client"
node enroll.js
echo "=== fabric smoke USE_SHACL=true ==="
USE_SHACL=true npm run smoke
echo "=== containers after smoke ==="
docker ps --format '{{.Names}} {{.Status}}' | grep -E 'peer0|orderer' || true
