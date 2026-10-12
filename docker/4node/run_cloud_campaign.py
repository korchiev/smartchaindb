#!/usr/bin/env python3
"""Run the marketplace campaign on the four DigitalOcean validators.

Every validator is switched to the same mode before the driver runs, because
Tendermint executes each transaction on all four nodes. The driver runs on the
client droplet so commit latency includes the client-to-validator hop; the
in-process validator microbenchmark runs inside scdb-v1. Container CPU is
sampled on every validator for the duration of each mode.
"""
from __future__ import print_function

import argparse
import os
import subprocess
import sys
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
KEY = os.path.join(os.path.expanduser("~"), ".ssh", "id_rsa")
OPTS = [
    "-i", KEY,
    "-o", "StrictHostKeyChecking=accept-new",
    "-o", "BatchMode=yes",
    "-o", "ConnectTimeout=20",
]
SSH = ["ssh"] + OPTS + ["-o", "ServerAliveInterval=30"]
SCP = ["scp"] + OPTS

CPU_LOOP = (
    "setsid nohup bash -c 'while true; do "
    "docker stats --no-stream --format \"$(date +%s.%N),{{{{.Name}}}},{{{{.CPUPerc}}}},{{{{.MemUsage}}}}\" "
    ">> /tmp/cpu_{tag}.csv; sleep 1; done' >/dev/null 2>&1 < /dev/null & echo $! > /tmp/cpu_{tag}.pid"
)


def load_hosts(path):
    vals = {}
    with open(path) as handle:
        for line in handle:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            vals[k] = v
    validators = []
    for i in range(1, 5):
        validators.append({
            "name": "scdb-v%d" % i,
            "public": vals["SCDB_V%d_PUBLIC" % i],
            "private": vals.get("SCDB_V%d_PRIVATE" % i, vals["SCDB_V%d_PUBLIC" % i]),
        })
    client = vals.get("SCDB_CLIENT_PUBLIC")
    return validators, client


def run(ip, remote, timeout=None, check=True):
    print("+", ip, remote[:160], flush=True)
    proc = subprocess.run(SSH + ["root@" + ip, remote], timeout=timeout)
    if check and proc.returncode != 0:
        raise SystemExit("ssh %s failed (%s)" % (ip, proc.returncode))
    return proc.returncode


def fetch(ip, remote, local):
    proc = subprocess.run(SCP + ["root@%s:%s" % (ip, remote), local])
    if proc.returncode != 0:
        raise SystemExit("scp from %s failed: %s" % (ip, remote))


def wait_ready(validators):
    remote = (
        "for i in $(seq 1 40); do "
        "curl -sf http://127.0.0.1:9984/ >/dev/null && "
        "curl -sf http://127.0.0.1:26657/net_info | grep -q '\"n_peers\": \"3\"' "
        "&& echo READY && exit 0; sleep 3; done; echo NOT_READY; exit 1"
    )
    for v in validators:
        run(v["public"], remote, timeout=180)


def switch_mode(validators, mode):
    print("=== switch", mode, "===", flush=True)
    for v in validators:
        run(v["public"], "bash /root/smartchaindb/docker/4node/set_mode.sh " + mode, timeout=180)
    for v in validators:
        run(v["public"], "docker restart scdb-node-tm-1", timeout=60)
    wait_ready(validators)


def cpu_start(validators, tag):
    for v in validators:
        run(v["public"], "rm -f /tmp/cpu_%s.csv; " % tag + CPU_LOOP.format(tag=tag), timeout=30)


def cpu_stop(validators, tag, dest):
    for v in validators:
        run(v["public"], "kill $(cat /tmp/cpu_%s.pid) 2>/dev/null; true" % tag, timeout=30, check=False)
        fetch(v["public"], "/tmp/cpu_%s.csv" % tag, os.path.join(dest, "cpu_%s_%s.csv" % (tag, v["name"])))


def run_mode(validators, client, mode, args, dest):
    switch_mode(validators, mode)
    tag = "%s_%s" % (args.tag, mode)
    env = "-e N_OFFER=%s -e N_E2E=%s -e N_VAL=20 -e N_LOAD=16" % (args.n_offer, args.n_e2e)
    flags = []
    if args.only_fail_closed:
        flags.append("--only-fail-closed")
    if args.wan:
        flags.append("--wan")

    v1 = validators[0]
    if mode == "delta" and not args.only_fail_closed and not args.wan:
        run(
            v1["public"],
            "docker exec %s -e BDB_API=http://127.0.0.1:9984/api/v1 scdb-node-bdb-1 "
            "python -u /usr/src/app/eval/bdb_professor_eval.py --live-mode delta "
            "--skip-e2e --skip-mixes --skip-load --skip-conflict --out /tmp/%s_val.json "
            "&& docker cp scdb-node-bdb-1:/tmp/%s_val.json /tmp/%s_val.json" % (env, tag, tag, tag),
            timeout=1800,
        )
        fetch(v1["public"], "/tmp/%s_val.json" % tag, os.path.join(dest, "bdb_%s_val.json" % tag))

    cpu_start(validators, tag)
    try:
        api = "http://%s:9984/api/v1" % v1["private"]
        if client:
            run(
                client,
                "mkdir -p /root/out && docker run --rm --network host "
                "-v /root/smartchaindb/bigchaindb:/usr/src/app/bigchaindb "
                "-v /root/smartchaindb/eval:/usr/src/app/eval "
                "-v /root/out:/out %s -e BDB_API=%s smartchaindb-bigchaindb "
                "python -u /usr/src/app/eval/bdb_professor_eval.py --live-mode %s --skip-validation %s "
                "--out /out/bdb_%s.json" % (env, api, mode, " ".join(flags), tag),
                timeout=7200,
            )
            fetch(client, "/root/out/bdb_%s.json" % tag, os.path.join(dest, "bdb_%s.json" % tag))
        else:
            run(
                v1["public"],
                "docker exec %s -e BDB_API=http://127.0.0.1:9984/api/v1 scdb-node-bdb-1 "
                "python -u /usr/src/app/eval/bdb_professor_eval.py --live-mode %s --skip-validation %s "
                "--out /tmp/bdb_%s.json && docker cp scdb-node-bdb-1:/tmp/bdb_%s.json /tmp/bdb_%s.json"
                % (env, mode, " ".join(flags), tag, tag, tag),
                timeout=7200,
            )
            fetch(v1["public"], "/tmp/bdb_%s.json" % tag, os.path.join(dest, "bdb_%s.json" % tag))
    finally:
        cpu_stop(validators, tag, dest)
    print("saved", os.path.join(dest, "bdb_%s.json" % tag), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--hosts", default=os.path.join(os.path.dirname(__file__), "hosts.lan.env"))
    parser.add_argument("--modes", default="direct,shacl,delta")
    parser.add_argument("--only-fail-closed", action="store_true")
    parser.add_argument("--wan", action="store_true")
    parser.add_argument("--no-client", action="store_true")
    parser.add_argument("--tag", default="lan4")
    parser.add_argument("--n-offer", default="20")
    parser.add_argument("--n-e2e", default="5")
    args = parser.parse_args()
    validators, client = load_hosts(args.hosts)
    if args.no_client:
        client = None
    dest = os.path.join(ROOT, "eval", "results", args.tag)
    if not os.path.isdir(dest):
        os.makedirs(dest)
    for mode in [m.strip() for m in args.modes.split(",") if m.strip()]:
        run_mode(validators, client, mode, args, dest)
    return 0


if __name__ == "__main__":
    sys.exit(main())
