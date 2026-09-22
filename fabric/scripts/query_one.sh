#!/bin/bash
set -euo pipefail
export PATH="$HOME/fabric-samples/bin:$PATH"
export FABRIC_CFG_PATH="$HOME/fabric-samples/config"
cd "$HOME/fabric-samples/test-network"
# shellcheck disable=SC1091
. scripts/envVar.sh
setGlobals 1
FN="${1:-ReadBuyOffer}"
ARG="${2:-}"
if [ -n "$ARG" ]; then
  peer chaincode query -C mychannel -n marketplace -c "{\"Args\":[\"$FN\",\"$ARG\"]}"
else
  peer chaincode query -C mychannel -n marketplace -c "{\"Args\":[\"$FN\"]}"
fi
echo
