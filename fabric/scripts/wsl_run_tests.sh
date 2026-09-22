#!/bin/bash
# Run from Ubuntu-26.04. Starts nothing; assumes SHACL :3000/:3001 and Fabric peers are up.
set -euo pipefail
export FABRIC_CONNECTION_PROFILE="${HOME}/fabric-samples/test-network/organizations/peerOrganizations/org1.example.com/connection-org1.json"
export FABRIC_WALLET_DIR="${HOME}/fabric-wallet"
export FABRIC_IDENTITY=appUser
export FABRIC_CHANNEL=mychannel
export FABRIC_CONTRACT=marketplace
export SHACL_ENDPOINT=http://127.0.0.1:3001
export PATH="${HOME}/fabric-samples/bin:${PATH}"
ROOT="/mnt/c/Users/korchien/Research/smartchaindb"

echo "=== health ==="
curl -sS -m 3 http://127.0.0.1:3000/ | head -c 400; echo
curl -sS -m 3 http://127.0.0.1:3001/ | head -c 400; echo

echo "=== pytest (WSL) ==="
VENV="${HOME}/.venvs/smartchaindb-tests"
if [ ! -x "${VENV}/bin/python" ]; then
  python3 -m venv "$VENV"
fi
"${VENV}/bin/pip" install -q pytest requests jsonschema pyyaml
cd "$ROOT"
"${VENV}/bin/python" -m pytest tests/test_paper_hardening.py tests/test_paper_live.py tests/test_live_shacl_http.py tests/test_live_fabric_shacl_http.py --noconftest -q --tb=line

echo "=== fabric smoke (WSL, SHACL=true) ==="
cd "$ROOT/fabric/client"
USE_SHACL=true npm run smoke
