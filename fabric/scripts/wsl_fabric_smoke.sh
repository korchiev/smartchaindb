#!/bin/bash
set -euo pipefail
export PATH="${HOME}/fabric-samples/bin:${PATH}"
SAMPLES="${HOME}/fabric-samples"
ROOT="/mnt/c/Users/korchien/Research/smartchaindb"
CC_PATH="${ROOT}/fabric/chaincode/marketplace"

if ! docker info >/dev/null 2>&1; then
  sudo service docker start
  sleep 2
fi

if [ ! -x "${SAMPLES}/test-network/network.sh" ]; then
  echo "fabric-samples test-network missing at ${SAMPLES}"
  exit 1
fi

cd "${SAMPLES}/test-network"
if ! docker ps --format '{{.Names}}' | grep -q 'peer0.org1'; then
  echo "=== bringing up Fabric test-network ==="
  ./network.sh up createChannel -c mychannel
  echo "=== deploying marketplace chaincode ==="
  ./network.sh deployCC -c mychannel -ccn marketplace -ccp "${CC_PATH}" -ccl go
else
  echo "=== Fabric peers already running ==="
fi

cd "${ROOT}/fabric/shacl"
if [ ! -d node_modules ]; then
  npm install
fi
if ! curl -sf http://127.0.0.1:3001/ >/dev/null; then
  echo "=== starting Fabric SHACL on :3001 ==="
  nohup node server.js > /tmp/fabric-shacl.log 2>&1 &
  echo $! > /tmp/fabric-shacl.pid
  for i in 1 2 3 4 5 6 7 8 9 10; do
    if curl -sf http://127.0.0.1:3001/ >/dev/null; then
      break
    fi
    sleep 1
  done
fi
curl -sS http://127.0.0.1:3001/ || { echo "SHACL :3001 not up"; cat /tmp/fabric-shacl.log || true; exit 1; }
echo

cd "${ROOT}/fabric/client"
if [ ! -d node_modules ]; then
  npm install
fi
# env.sh is sourced by the caller after CRLF strip if needed
export FABRIC_CONNECTION_PROFILE="${HOME}/fabric-samples/test-network/organizations/peerOrganizations/org1.example.com/connection-org1.json"
export FABRIC_WALLET_DIR="${HOME}/fabric-wallet"
export FABRIC_IDENTITY=appUser
export FABRIC_CHANNEL=mychannel
export FABRIC_CONTRACT=marketplace
export SHACL_ENDPOINT=http://127.0.0.1:3001

node enroll.js
echo "=== fabric smoke USE_SHACL=true ==="
USE_SHACL=true npm run smoke
