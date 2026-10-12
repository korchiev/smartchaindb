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
export N="${N:-2}"

cd "${ROOT}/fabric/client"
node enroll.js
N="$N" MODES=direct,shacl,delta npm run eval
