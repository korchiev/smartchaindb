#!/usr/bin/env python3
import subprocess
print(subprocess.check_output(
    ["docker", "events", "--since", "10m", "--until", "0s",
     "--filter", "container=smartchaindb-bigchaindb-1",
     "--filter", "container=smartchaindb-tendermint-1",
     "--filter", "container=smartchaindb-mongodb-1"],
    text=True,
))
