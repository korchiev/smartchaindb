#!/bin/bash
set -euo pipefail
export PATH="${HOME}/fabric-samples/bin:${PATH}"
ROOT="/mnt/c/Users/korchien/Research/smartchaindb"

echo "=== start existing Fabric nodes ==="
docker start orderer.example.com peer0.org1.example.com peer0.org2.example.com

echo "=== wait for peer and orderer ports ==="
for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20; do
  if timeout 1 bash -c 'echo >/dev/tcp/127.0.0.1/7051' 2>/dev/null \
    && timeout 1 bash -c 'echo >/dev/tcp/127.0.0.1/9051' 2>/dev/null \
    && timeout 1 bash -c 'echo >/dev/tcp/127.0.0.1/7050' 2>/dev/null; then
    echo "ports open after ${i} tries"
    break
  fi
  sleep 2
done

docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}' | head -20

cd "${ROOT}/fabric/shacl"
if [ ! -d node_modules ]; then
  npm install
fi
if ! curl -sf http://127.0.0.1:3001/ >/dev/null; then
  echo "=== starting Fabric SHACL on :3001 ==="
  nohup node server.js > /tmp/fabric-shacl.log 2>&1 &
  echo $! > /tmp/fabric-shacl.pid
  for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15; do
    if curl -sf http://127.0.0.1:3001/ >/dev/null; then
      break
    fi
    sleep 1
  done
fi
echo "=== SHACL ==="
curl -sS http://127.0.0.1:3001/
echo

cd "${ROOT}/fabric/client"
if [ ! -d node_modules ]; then
  npm install
fi
export FABRIC_CONNECTION_PROFILE="${HOME}/fabric-samples/test-network/organizations/peerOrganizations/org1.example.com/connection-org1.json"
export FABRIC_WALLET_DIR="${HOME}/fabric-wallet"
export FABRIC_IDENTITY=appUser
export FABRIC_CHANNEL=mychannel
export FABRIC_CONTRACT=marketplace
export SHACL_ENDPOINT=http://127.0.0.1:3001

node enroll.js
echo "=== fabric smoke USE_SHACL=true ==="
USE_SHACL=true npm run smoke
