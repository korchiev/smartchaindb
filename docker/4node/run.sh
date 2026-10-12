#!/bin/sh
# Peer list is written next to the Tendermint home as node.env.
set -eu
. /tendermint/node.env
exec tendermint node \
  --consensus.create_empty_blocks=false \
  --proxy_app=tcp://bdb:26658 \
  --p2p.laddr=tcp://0.0.0.0:26656 \
  --rpc.laddr=tcp://0.0.0.0:26657 \
  --p2p.persistent_peers="$TM_PEERS" \
  --p2p.pex=false
