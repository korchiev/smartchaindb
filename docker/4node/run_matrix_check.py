"""One-off: semantic matrix on the client droplet against v1."""
import os
import subprocess
import sys

KEY = os.path.expanduser("~/.ssh/id_rsa")
OPTS = ["-i", KEY, "-o", "StrictHostKeyChecking=accept-new", "-o", "BatchMode=yes", "-o", "ConnectTimeout=20"]
REMOTE = (
    "mkdir -p /root/out && docker run --rm --network host "
    "-v /root/smartchaindb/bigchaindb:/usr/src/app/bigchaindb "
    "-v /root/smartchaindb/eval:/usr/src/app/eval -v /root/out:/out "
    "-e MATRIX_REPS=1 -e BDB_API=http://10.108.0.3:9984/api/v1 smartchaindb-bigchaindb "
    "python -u /usr/src/app/eval/bdb_professor_eval.py --live-mode delta "
    "--skip-validation --skip-e2e --skip-mixes --skip-load --skip-open-load --skip-ratio --skip-conflict "
    "--out /out/matrix_check.json"
)


def main():
    return subprocess.call(["ssh"] + OPTS + ["root@104.131.73.177", REMOTE])


if __name__ == "__main__":
    sys.exit(main())
