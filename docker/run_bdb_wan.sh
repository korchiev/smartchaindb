#!/bin/bash
set -euo pipefail
cd /mnt/c/Users/korchien/Research/smartchaindb
export BIGCHAINDB_SHACL_ENABLED=true
export BIGCHAINDB_SHACL_CACHE=true
export BIGCHAINDB_SERVER_WORKERS=1
docker compose up -d --force-recreate tendermint bigchaindb
ok=0
for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25; do
  if curl -sf http://127.0.0.1:9984 >/dev/null && curl -sf http://127.0.0.1:26657/status >/dev/null; then
    ok=1
    break
  fi
  sleep 2
done
if [ "$ok" != 1 ]; then
  echo "unhealthy"
  exit 1
fi
sleep 5
docker exec -u root smartchaindb-tendermint-1 sh -c 'tc qdisc del dev eth0 root 2>/dev/null || true; tc qdisc add dev eth0 root netem delay 40ms 5ms; tc qdisc show dev eth0'
docker cp eval/bdb_professor_eval.py smartchaindb-bigchaindb-1:/tmp/bdb_professor_eval.py
docker exec -e N_OFFER=20 smartchaindb-bigchaindb-1 python /tmp/bdb_professor_eval.py --live-mode delta --out /tmp/bdb_wan.json --wan --skip-validation --skip-e2e --skip-load --skip-conflict
docker cp smartchaindb-bigchaindb-1:/tmp/bdb_wan.json /mnt/c/Users/korchien/Research/smartchaindb/eval/results/bdb_wan.json
docker exec -u root smartchaindb-tendermint-1 sh -c 'tc qdisc del dev eth0 root 2>/dev/null || true'
echo WAN_OK
