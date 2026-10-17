"""Copy sidecar modules and recreate its bind mounts on the validators.

Restarting BigchainDB would drop Tendermint's ABCI connection, so this path
leaves it running. Protocol upgrades also require a coordinated BigchainDB
deployment; do not use this script alone for the initial protocol-v2 rollout.
"""
import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
KEY = os.path.expanduser("~/.ssh/id_rsa")
OPTS = ["-i", KEY, "-o", "BatchMode=yes", "-o", "ConnectTimeout=20"]
IPS = ["167.99.122.69", "167.172.243.156", "165.227.117.106", "143.198.12.98"]
LOCAL = os.path.join(ROOT, "bigchaindb", "backend", "localshacl", "shapes")
REMOTE = "/root/smartchaindb/bigchaindb/backend/localshacl/shapes/"
MODULES = ("index.js", "transaction_graph.js", "state_context.js", "state_validator.js")


def main():
    for ip in IPS:
        if subprocess.call(["scp"] + OPTS + [os.path.join(LOCAL, name) for name in MODULES]
                           + ["root@%s:%s" % (ip, REMOTE)]) != 0:
            return 1
        if subprocess.call(["scp"] + OPTS + [os.path.join(ROOT, "docker-compose.onenode.yml"),
                           "root@%s:/root/smartchaindb/docker-compose.onenode.yml" % ip]) != 0:
            return 1
        if subprocess.call(["ssh"] + OPTS + ["root@" + ip,
                           "cd /root/smartchaindb && docker compose --env-file .env "
                           "--env-file docker/4node/node.env -f docker-compose.onenode.yml "
                           "up -d --no-deps --force-recreate shacl"]) != 0:
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
