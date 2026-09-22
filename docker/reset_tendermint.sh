#!/bin/bash
set -euo pipefail
cd /mnt/c/Users/korchien/Research/smartchaindb
docker compose stop tendermint bigchaindb
docker exec smartchaindb-mongodb-1 mongo -u admin -p admin --authenticationDatabase admin --quiet --eval 'db.getSiblingDB("bigchain").dropDatabase()'
docker run --rm -v /mnt/c/Users/korchien/Research/smartchaindb/docker/data/tendermint:/tendermint alpine \
  sh -c "rm -rf /tendermint/config /tendermint/data && mkdir -p /tendermint && chmod -R 0777 /tendermint"
docker compose up -d tendermint bigchaindb
docker compose ps
