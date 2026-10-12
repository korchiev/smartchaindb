#!/bin/bash
set -euo pipefail
export PATH="${HOME}/fabric-samples/bin:${PATH}"
ROOT="/mnt/c/Users/korchien/Research/smartchaindb"
OUT="${ROOT}/eval/results"
mkdir -p "$OUT"
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

echo "=== start Fabric peers ==="
bash "${ROOT}/fabric/scripts/wsl_start_existing_fabric.sh"

cd "${ROOT}/fabric/client"
if [ ! -d node_modules ]; then
  npm install
fi
node enroll.js

sample_cpu() {
  local log="$1"
  : > "$log"
  while true; do
    if [ -f /tmp/fabric-shacl.pid ]; then
      ps -p "$(cat /tmp/fabric-shacl.pid)" -o pid=,%cpu=,rss= >> "$log" 2>/dev/null || true
    fi
    docker stats --no-stream --format '{{.Name}},{{.CPUPerc}}' \
      peer0.org1.example.com peer0.org2.example.com orderer.example.com \
      >> "$log" 2>/dev/null || true
    sleep 1
  done
}

sample_cpu "$OUT/cpu_fabric.csv" &
CPUPID=$!
trap 'kill $CPUPID 2>/dev/null || true; bash "${ROOT}/fabric/scripts/wan_profile.sh" 0 0 >/dev/null 2>&1 || true' EXIT

echo "=== Fabric LAN three-way ==="
OUT="${OUT}/fabric.json" MODES=direct,shacl,delta npm run professor

echo "=== Fabric WAN 40ms ==="
bash "${ROOT}/fabric/scripts/wan_profile.sh" 40 5
OUT="${ROOT}/eval/results/fabric_wan.json" WAN=true MODES=direct,shacl,delta SKIP_LOAD=true \
  N_E2E=3 N_OFFER=12 npm run professor

# remove netem
for c in peer0.org1.example.com peer0.org2.example.com orderer.example.com; do
  docker exec -u root "$c" sh -c 'tc qdisc del dev eth0 root 2>/dev/null || true' || true
done
kill "$CPUPID" 2>/dev/null || true
echo "=== Fabric professor eval done ==="
ls -l "${ROOT}/eval/results"
