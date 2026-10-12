#!/bin/bash
# Fabric three-way campaign on the cloud droplet, same parameters as SmartChainDB.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
export PATH="${HOME}/fabric-samples/bin:${PATH}"
OUT="${OUT_DIR:-/root/out}"
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

cd "${ROOT}/fabric/shacl"
if ! curl -sf http://127.0.0.1:3001/ >/dev/null; then
  setsid nohup node server.js > /tmp/fabric-shacl.log 2>&1 < /dev/null &
  echo $! > /tmp/fabric-shacl.pid
  for i in $(seq 1 30); do
    curl -sf http://127.0.0.1:3001/ >/dev/null && break
    sleep 1
  done
fi

cd "${ROOT}/fabric/client"
node enroll.js

sample_cpu() {
  local log="$1"
  : > "$log"
  while true; do
    local ts
    ts="$(date +%s.%N)"
    if [ -f /tmp/fabric-shacl.pid ]; then
      ps -p "$(cat /tmp/fabric-shacl.pid)" -o %cpu= 2>/dev/null | sed "s/^ */${ts},fabric-shacl,/;s/$/%/" >> "$log" || true
    fi
    docker stats --no-stream --format "${ts},{{.Name}},{{.CPUPerc}},{{.MemUsage}}" \
      peer0.org1.example.com peer0.org2.example.com orderer.example.com >> "$log" 2>/dev/null || true
    sleep 1
  done
}

sample_cpu "$OUT/cpu_fabric_cloud.csv" &
CPUPID=$!
trap 'kill $CPUPID 2>/dev/null || true' EXIT

OUT="${OUT}/fabric_cloud.json" MODES=direct,shacl,delta npm run professor
echo FABRIC_EVAL_DONE
