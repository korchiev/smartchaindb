"""Copy the SHACL sidecar onto the validators and restart only that container.

Restarting BigchainDB would drop Tendermint's ABCI connection, so this path
leaves it running. The sidecar mounts index.js from the tree.
"""
import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
KEY = os.path.expanduser("~/.ssh/id_rsa")
OPTS = ["-i", KEY, "-o", "BatchMode=yes", "-o", "ConnectTimeout=20"]
IPS = ["167.99.122.69", "167.172.243.156", "165.227.117.106", "143.198.12.98"]
LOCAL = os.path.join(ROOT, "bigchaindb", "backend", "localshacl", "shapes", "index.js")
REMOTE = "/root/smartchaindb/bigchaindb/backend/localshacl/shapes/index.js"


def main():
    for ip in IPS:
        if subprocess.call(["scp"] + OPTS + [LOCAL, "root@%s:%s" % (ip, REMOTE)]) != 0:
            return 1
        if subprocess.call(["ssh"] + OPTS + ["root@" + ip,
                           "docker restart scdb-node-shacl-1 >/dev/null && echo shacl-restarted $(hostname)"]) != 0:
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
