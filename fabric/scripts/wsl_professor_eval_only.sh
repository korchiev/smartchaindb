#!/bin/bash
set -euo pipefail
export PATH="${HOME}/fabric-samples/bin:${PATH}"
ROOT="/mnt/c/Users/korchien/Research/smartchaindb"
OUTDIR="${ROOT}/eval/results"
mkdir -p "$OUTDIR"
export N_VAL="${N_VAL:-20}"
export N_E2E="${N_E2E:-5}"
export N_OFFER="${N_OFFER:-20}"
export N_LOAD="${N_LOAD:-16}"
export LOAD_CONC="${LOAD_CONC:-1,2,4,8}"
export FABRIC_CONNECTION_PROFILE="${HOME}/fabric-samples/test-network/organizations/peerOrganizations/org1.example.com/connection-org1.json"
export FABRIC_WALLET_DIR="${HOME}/fabric-wallet"
export FABRIC_IDENTITY=appUser
export FABRIC_CHANNEL=mychannel
export FABRIC_CONTRACT=marketplace
export SHACL_ENDPOINT=http://127.0.0.1:3001

curl -sf http://127.0.0.1:3001/ >/dev/null
cd "${ROOT}/fabric/client"
node enroll.js

echo "=== Fabric LAN three-way ==="
OUT="${OUTDIR}/fabric.json" MODES=direct,shacl,delta npm run professor

echo "=== Fabric WAN 40ms ==="
bash "${ROOT}/fabric/scripts/wan_profile.sh" 40 5
OUT="${OUTDIR}/fabric_wan.json" WAN=true MODES=direct,shacl,delta SKIP_LOAD=true \
  N_E2E=3 N_OFFER=12 npm run professor

for c in peer0.org1.example.com peer0.org2.example.com orderer.example.com; do
  docker exec -u root "$c" sh -c 'tc qdisc del dev eth0 root 2>/dev/null || true' || true
done
echo "=== Fabric professor eval done ==="
ls -l "${OUTDIR}"
