#!/usr/bin/env bash
set -euo pipefail

# Simple wrapper to start Fabric test-network and deploy this chaincode
# Usage:
#   bash fabric/scripts/setup_fabric.sh \
#     --samples-path "$HOME/fabric-samples" \
#     --chaincode-name marketplace \
#     --chaincode-lang golang \
#     --chaincode-path "$(pwd)/fabric/chaincode/marketplace"

SAMPLES_PATH=""
CC_NAME="marketplace"
CC_LANG="go"
CC_PATH=""
CHANNEL_NAME="mychannel"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --samples-path) SAMPLES_PATH="$2"; shift 2;;
    --chaincode-name) CC_NAME="$2"; shift 2;;
    --chaincode-lang) CC_LANG="$2"; shift 2;; # use "go" not "golang"
    --chaincode-path) CC_PATH="$2"; shift 2;;
    --channel) CHANNEL_NAME="$2"; shift 2;;
    *) echo "Unknown arg: $1"; exit 1;;
  esac
done

if [[ -z "$SAMPLES_PATH" || -z "$CC_PATH" ]]; then
  echo "Missing --samples-path or --chaincode-path"; exit 1;
fi

pushd "$SAMPLES_PATH/test-network" >/dev/null

echo "[+] Bringing up test network"
./network.sh down || true
./network.sh up createChannel -c "$CHANNEL_NAME"

echo "[+] Deploying chaincode: $CC_NAME"
./network.sh deployCC -c "$CHANNEL_NAME" -ccn "$CC_NAME" -ccp "$CC_PATH" -ccl "$CC_LANG"

echo "[+] Test network is ready."
echo "Export these for the client:"
echo "  export FABRIC_CONNECTION_PROFILE=\"$SAMPLES_PATH/test-network/organizations/peerOrganizations/org1.example.com/connection-org1.json\""
echo "  export FABRIC_WALLET_DIR=\"$SAMPLES_PATH/test-network/application-javascript/wallet\""
echo "  export FABRIC_IDENTITY=\"appUser\""
echo "  export FABRIC_CHANNEL=\"$CHANNEL_NAME\""
echo "  export FABRIC_CONTRACT=\"$CC_NAME\""

popd >/dev/null

