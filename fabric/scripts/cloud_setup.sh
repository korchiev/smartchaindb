#!/bin/bash
# Install Fabric 2.5.12 test-network prerequisites on a fresh Ubuntu droplet
# and deploy the marketplace chaincode. Run from the repo root as root.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

while fuser /var/lib/dpkg/lock-frontend >/dev/null 2>&1; do sleep 3; done
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq jq curl git build-essential >/dev/null

if ! command -v docker >/dev/null; then
  curl -fsSL https://get.docker.com | sh
fi
if ! command -v go >/dev/null; then
  curl -fsSL https://go.dev/dl/go1.22.12.linux-amd64.tar.gz | tar -C /usr/local -xz
  ln -sf /usr/local/go/bin/go /usr/local/bin/go
fi
if ! command -v node >/dev/null; then
  curl -fsSL https://deb.nodesource.com/setup_18.x | bash -
  apt-get install -y -qq nodejs >/dev/null
fi

cd "$HOME"
if [ ! -d fabric-samples ]; then
  curl -sSLO https://raw.githubusercontent.com/hyperledger/fabric/main/scripts/install-fabric.sh
  chmod +x install-fabric.sh
  ./install-fabric.sh --fabric-version 2.5.12 docker samples binary
fi
export PATH="$HOME/fabric-samples/bin:$PATH"

bash "$ROOT/fabric/scripts/setup_fabric.sh" \
  --samples-path "$HOME/fabric-samples" \
  --chaincode-name marketplace \
  --chaincode-lang go \
  --chaincode-path "$ROOT/fabric/chaincode/marketplace"

cd "$ROOT/fabric/shacl" && npm install --silent
cd "$ROOT/fabric/client" && npm install --silent
echo FABRIC_READY
