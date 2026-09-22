#!/usr/bin/env bash
# Apply WAN delay/jitter to Fabric docker containers.
# Usage: bash fabric/scripts/wan_profile.sh 40 5
set -euo pipefail
DELAY_MS="${1:-40}"
JITTER_MS="${2:-5}"
CONTAINERS=(peer0.org1.example.com peer0.org2.example.com orderer.example.com)

echo "Applying ${DELAY_MS}ms delay +/- ${JITTER_MS}ms jitter"
for c in "${CONTAINERS[@]}"; do
  docker exec -u root "$c" sh -c "apk add --no-cache iproute2 >/dev/null 2>&1 || apt-get update >/dev/null && apt-get install -y iproute2 >/dev/null 2>&1 || true"
  docker exec -u root "$c" sh -c "tc qdisc del dev eth0 root 2>/dev/null || true; tc qdisc add dev eth0 root netem delay ${DELAY_MS}ms ${JITTER_MS}ms"
  echo "  $c ok"
done
