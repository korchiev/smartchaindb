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


def run(ip, remote, timeout=None, check=True, retries=4):
    """Run a remote command. Retry when SSH itself cannot connect, so a short
    network blip does not abort a campaign that is still running remotely."""
    last = None
    for attempt in range(retries):
        print("+", ip, remote[:160], flush=True)
        try:
            proc = subprocess.run(SSH + ["root@" + ip, remote], timeout=timeout)
        except subprocess.TimeoutExpired:
            last = "timeout"
            print("ssh %s timed out, retry %d" % (ip, attempt + 1), flush=True)
            time.sleep(5 * (attempt + 1))
            continue
        if proc.returncode == 0:
            return 0
        last = proc.returncode
        if proc.returncode == 255 and attempt < retries - 1:
            print("ssh %s connection failed, retry %d" % (ip, attempt + 1), flush=True)
            time.sleep(5 * (attempt + 1))
            continue
        break
    if check:
        raise SystemExit("ssh %s failed (%s)" % (ip, last))
    return 255 if last == "timeout" else last


def fetch(ip, remote, local):
    for attempt in range(4):
        proc = subprocess.run(SCP + ["root@%s:%s" % (ip, remote), local])
        if proc.returncode == 0:
            return
        print("scp retry %d from %s: %s" % (attempt + 1, ip, remote), flush=True)
        time.sleep(5 * (attempt + 1))
    raise SystemExit("scp from %s failed: %s" % (ip, remote))


def run_detached(ip, remote, log_remote, timeout, ok_marker="WROTE"):
    """Start remote work in its own session and poll the log.

    The campaign used to hold one SSH session open for the whole workload.
    When that session dropped, the workload died with it. setsid keeps the
    job running across a disconnect; the poll just waits for it to finish.
    """
    launch = ("rm -f %s; setsid nohup bash -c '%s' > %s 2>&1 < /dev/null & echo STARTED"
              % (log_remote, remote.replace("'", "'\\''"), log_remote))
    run(ip, launch, timeout=90)
    deadline = time.time() + timeout
    probe = ("if grep -q 'T''raceback' %s; then cat %s; exit 2; fi; "
             "if grep -q %s %s; then exit 0; fi; exit 1"
             % (log_remote, log_remote, ok_marker, log_remote))
    while time.time() < deadline:
        code = run(ip, probe, timeout=45, check=False)
        if code == 0:
            return
        if code == 2:
            raise SystemExit("remote command failed; log %s:%s" % (ip, log_remote))
        if code == 255:
            print("SSH_DOWN %s" % ip, flush=True)
        time.sleep(15)
    raise SystemExit("timed out waiting for %s:%s" % (ip, log_remote))


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
        run(v["public"], "kill $(cat /tmp/cpu_%s.pid) 2>/dev/null; rm -f /tmp/cpu_%s.csv; " % (tag, tag)
            + CPU_LOOP.format(tag=tag), timeout=30)


def cpu_stop(validators, tag, dest):
    for v in validators:
        run(v["public"], "kill $(cat /tmp/cpu_%s.pid) 2>/dev/null; true" % tag, timeout=30, check=False)
        fetch(v["public"], "/tmp/cpu_%s.csv" % tag, os.path.join(dest, "cpu_%s_%s.csv" % (tag, v["name"])))


DRIVER = "python -u /usr/src/app/eval/bdb_professor_eval.py"
SEEDER = "python -u /usr/src/app/eval/seed_state.py"


def driver_env(args):
    return (
        "-e N_OFFER=%s -e N_E2E=%s -e N_VAL=%s -e N_DISJOINT=%s -e MATRIX_REPS=%s -e SEQ_REPS=%s "
        "-e N_RATIO=%s -e OPEN_RATES=%s -e OPEN_DURATION=%s -e N_LOAD=16"
        % (args.n_offer, args.n_e2e, args.n_val, args.n_disjoint, args.matrix_reps, args.seq_reps,
           args.n_ratio, args.open_rates, args.open_duration)
    )


def client_cmd(client_env, api, tm_rpc, driver_args, out_name, background=False):
    """Driver on the client droplet, inside the BigchainDB image, host network."""
    cmd = (
        "mkdir -p /root/out && docker run --rm --network host "
        "-v /root/smartchaindb/bigchaindb:/usr/src/app/bigchaindb "
        "-v /root/smartchaindb/eval:/usr/src/app/eval "
        "-v /root/out:/out %s -e BDB_API=%s -e TM_RPC=%s smartchaindb-bigchaindb %s %s --out /out/%s"
        % (client_env, api, tm_rpc, DRIVER, driver_args, out_name)
    )
    if background:
        cmd = ("rm -f /root/out/%s.log; setsid nohup bash -c '%s' > /root/out/%s.log 2>&1 < /dev/null & echo STARTED"
               % (out_name, cmd.replace("'", "'\\''"), out_name))
    return cmd


def inprocess(v1, env, tag, label=None, skip_sequence=False, dest=None):
    """Validator microbenchmark + Δ sequence inside scdb-v1's bdb container."""
    extra = " --state-label %s" % label if label else ""
    if skip_sequence:
        extra += " --skip-sequence"
    name = "%s_val%s.json" % (tag, ("_" + label) if label else "")
    run_detached(
        v1["public"],
        "docker exec %s -e BDB_API=http://127.0.0.1:9984/api/v1 scdb-node-bdb-1 %s --live-mode delta "
        "--only-inprocess%s --out /tmp/%s && docker cp scdb-node-bdb-1:/tmp/%s /tmp/%s && echo COPIED"
        % (env, DRIVER, extra, name, name, name),
        "/tmp/%s.log" % name,
        5400,
        ok_marker="COPIED",
    )
    fetch(v1["public"], "/tmp/%s" % name, os.path.join(dest, "bdb_" + name))


def engine_down(validators, client, env, api, tm_rpc, mode, tag, dest):
    """Fail-closed under engine failure: the driver sets up an ad, signals,
    we stop every SHACL sidecar, it submits offers, we restart the sidecars."""
    name = "bdb_%s_engine_down.json" % tag
    run(client, "rm -f /root/out/engine_down.flag; " + client_cmd(env, api, tm_rpc, "--live-mode %s --only-engine-down" % mode, name, background=True), timeout=60)
    run(client, "for i in $(seq 1 120); do grep -q READY_FOR_ENGINE_DOWN /root/out/%s.log && exit 0; "
                "grep -q 'T''raceback' /root/out/%s.log && cat /root/out/%s.log && exit 1; sleep 2; done; exit 1" % (name, name, name), timeout=300)
    try:
        for v in validators:
            run(v["public"], "docker stop scdb-node-shacl-1 >/dev/null && echo stopped $(hostname)", timeout=60)
        run(client, "touch /root/out/engine_down.flag", timeout=30)
        run(client, "for i in $(seq 1 300); do grep -q WROTE /root/out/%s.log && exit 0; "
                    "grep -q 'T''raceback' /root/out/%s.log && cat /root/out/%s.log && exit 1; sleep 2; done; exit 1" % (name, name, name), timeout=700)
        fetch(client, "/root/out/" + name, os.path.join(dest, name))
    finally:
        for v in validators:
            run(v["public"], "docker start scdb-node-shacl-1 >/dev/null && echo started $(hostname)", timeout=60, check=False)
        run(client, "rm -f /root/out/engine_down.flag", timeout=30, check=False)
    wait_ready(validators)


def state_sweep(validators, env, tag, sizes, dest):
    """Seed identical synthetic ledgers on every validator, microbench on v1
    at each size, with and without the marketplace indexes. Cleans up."""
    v1 = validators[0]
    try:
        for size in sizes:
            for v in validators:
                run_detached(v["public"], "docker exec scdb-node-bdb-1 %s --target %d && echo SEED_DONE" % (SEEDER, size),
                             "/tmp/seed_state.log", 3600, ok_marker="SEED_DONE")
            inprocess(v1, env, tag, label="state%d" % size, skip_sequence=True, dest=dest)
            for v in validators:
                run_detached(v["public"], "docker exec scdb-node-bdb-1 %s --indexes off && echo SEED_DONE" % SEEDER,
                             "/tmp/seed_state.log", 600, ok_marker="SEED_DONE")
            inprocess(v1, env, tag, label="state%d_noidx" % size, skip_sequence=True, dest=dest)
            for v in validators:
                run_detached(v["public"], "docker exec scdb-node-bdb-1 %s --indexes on && echo SEED_DONE" % SEEDER,
                             "/tmp/seed_state.log", 1800, ok_marker="SEED_DONE")
    finally:
        for v in validators:
            run(v["public"], "docker exec scdb-node-bdb-1 %s --reset --indexes on" % SEEDER, timeout=1800, check=False)


def run_mode(validators, client, mode, args, dest):
    switch_mode(validators, mode)
    tag = "%s_%s" % (args.tag, mode)
    env = driver_env(args)
    v1 = validators[0]
    api = "http://%s:9984/api/v1" % v1["private"]
    tm_rpc = "http://%s:26657" % v1["private"]

    if args.only_fail_closed:
        run(client, client_cmd(env, api, tm_rpc, "--live-mode %s --only-fail-closed%s" % (mode, " --wan" if args.wan else ""),
                               "bdb_%s.json" % tag), timeout=3600)
        fetch(client, "/root/out/bdb_%s.json" % tag, os.path.join(dest, "bdb_%s.json" % tag))
        return

    if args.only_engine_down:
        engine_down(validators, client, env, api, tm_rpc, mode, tag, dest)
        return

    if mode == "delta" and not args.wan and not args.skip_inprocess:
        inprocess(v1, env, tag, dest=dest)

    flags = ["--skip-validation", "--skip-conflict"]
    if not args.closed_loop:
        flags.append("--skip-load")
    if args.skip_open_load:
        flags.append("--skip-open-load")
    if args.wan:
        flags.append("--wan")
    out_name = "bdb_%s.json" % tag
    cpu_start(validators, tag)
    try:
        run_detached(client, client_cmd(env, api, tm_rpc, "--live-mode %s %s" % (mode, " ".join(flags)), out_name),
                     "/root/out/%s.log" % out_name, 14400)
        fetch(client, "/root/out/%s" % out_name, os.path.join(dest, out_name))
    finally:
        cpu_stop(validators, tag, dest)
    print("saved", os.path.join(dest, "bdb_%s.json" % tag), flush=True)

    if mode in ("shacl", "delta") and not args.wan and not args.skip_engine_down:
        engine_down(validators, client, env, api, tm_rpc, mode, tag, dest)

    if mode == "delta" and args.state_sizes and not args.wan:
        sizes = [int(s) for s in args.state_sizes.split(",") if s.strip()]
        state_sweep(validators, env, tag, sizes, dest)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--hosts", default=os.path.join(os.path.dirname(__file__), "hosts.lan.env"))
    parser.add_argument("--modes", default="direct,shacl,delta")
    parser.add_argument("--only-fail-closed", action="store_true")
    parser.add_argument("--only-engine-down", action="store_true")
    parser.add_argument("--wan", action="store_true")
    parser.add_argument("--tag", default="lan4")
    parser.add_argument("--n-offer", default="500")
    parser.add_argument("--n-e2e", default="30")
    parser.add_argument("--n-val", default="200")
    parser.add_argument("--n-disjoint", default="200")
    parser.add_argument("--matrix-reps", default="3")
    parser.add_argument("--seq-reps", default="2")
    parser.add_argument("--n-ratio", default="60")
    parser.add_argument("--open-rates", default="5,10,20,40,80,160")
    parser.add_argument("--open-duration", default="20")
    parser.add_argument("--state-sizes", default="", help="e.g. 1000,10000,100000 (delta mode only)")
    parser.add_argument("--closed-loop", action="store_true", help="also run the old closed-loop load")
    parser.add_argument("--skip-open-load", action="store_true")
    parser.add_argument("--skip-engine-down", action="store_true")
    parser.add_argument("--skip-inprocess", action="store_true")
    args = parser.parse_args()
    validators, client = load_hosts(args.hosts)
    if not client:
        raise SystemExit("hosts file has no SCDB_CLIENT_PUBLIC; the driver runs on the client droplet")
    dest = os.path.join(ROOT, "eval", "results", args.tag)
    if not os.path.isdir(dest):
        os.makedirs(dest)
    for mode in [m.strip() for m in args.modes.split(",") if m.strip()]:
        run_mode(validators, client, mode, args, dest)
    return 0


if __name__ == "__main__":
    sys.exit(main())
