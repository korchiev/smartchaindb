#!/usr/bin/env python3
"""Create (or reuse) the DigitalOcean 4-validator LAN and bring it up.

Steps: provision droplets (token from ~/.digitalocean_token, never in the
repo) -> install Docker -> push the committed tree (git archive HEAD) ->
generate a fresh 4-validator genesis on v1 with the private IPs -> install
one Tendermint home per validator -> start every validator -> build the
driver image on the client -> write docker/4node/hosts.lan.env (gitignored).

  python docker/4node/bootstrap_lan.py --provision      # new droplets
  python docker/4node/bootstrap_lan.py --deploy-only    # push code + restart
"""
from __future__ import print_function

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
HERE = os.path.dirname(os.path.abspath(__file__))
HOSTS = os.path.join(HERE, "hosts.lan.env")
KEY = os.path.join(os.path.expanduser("~"), ".ssh", "id_rsa")
OPTS = ["-i", KEY, "-o", "StrictHostKeyChecking=accept-new", "-o", "BatchMode=yes", "-o", "ConnectTimeout=20"]
SSH = ["ssh"] + OPTS
SCP = ["scp"] + OPTS
API = "https://api.digitalocean.com/v2"
NAMES = ["scdb-v1", "scdb-v2", "scdb-v3", "scdb-v4", "scdb-client"]


def sh(cmd, check=True, retries=1, **kw):
    for attempt in range(retries):
        print("+", " ".join(cmd[-2:])[:200], flush=True)
        rc = subprocess.call(cmd, **kw)
        if rc == 0:
            return 0
        if attempt < retries - 1:
            time.sleep(10)
    if check:
        raise SystemExit("failed (%s): %s" % (rc, cmd[-1][:120]))
    return rc


def ssh(ip, remote, **kw):
    return sh(SSH + ["root@" + ip, remote], **kw)


def scp(local, ip, remote, **kw):
    return sh(SCP + [local, "root@%s:%s" % (ip, remote)], **kw)


# ---------------------------------------------------------------- DigitalOcean
def do_req(method, path, body=None):
    token = open(os.path.join(os.path.expanduser("~"), ".digitalocean_token")).read().strip()
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(API + path, data=data, method=method, headers={
        "Authorization": "Bearer " + token, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raise SystemExit("HTTP %s %s %s\n%s" % (exc.code, method, path, exc.read().decode()))


def my_ip():
    with urllib.request.urlopen("https://api.ipify.org", timeout=20) as resp:
        return resp.read().decode().strip()


def provision(region, size_v, size_c):
    pub = open(os.path.join(os.path.expanduser("~"), ".ssh", "id_rsa.pub")).read().strip()
    keys = do_req("GET", "/account/keys?per_page=200")["ssh_keys"]
    key = next((k for k in keys if k["public_key"].split()[1] == pub.split()[1]), None)
    if key is None:
        key = do_req("POST", "/account/keys", {"name": "scdb-bootstrap", "public_key": pub})["ssh_key"]
    for tag in ("scdb-validator", "scdb-client"):
        try:
            do_req("POST", "/tags", {"name": tag})
        except SystemExit:
            pass
    vpcs = do_req("GET", "/vpcs?per_page=200")["vpcs"]
    vpc = next((v for v in vpcs if v["region"] == region and v["name"] == "scdb-lan"), None)
    if vpc is None:
        vpc = do_req("POST", "/vpcs", {"name": "scdb-lan", "region": region})["vpc"]
    me = my_ip() + "/32"
    fw_body = {
        "name": "scdb-lan",
        "inbound_rules": [
            {"protocol": "tcp", "ports": "22", "sources": {"addresses": [me]}},
            {"protocol": "tcp", "ports": "26656", "sources": {"tags": ["scdb-validator"]}},
            {"protocol": "tcp", "ports": "26657", "sources": {"tags": ["scdb-validator", "scdb-client"]}},
            {"protocol": "tcp", "ports": "9984", "sources": {"tags": ["scdb-client"], "addresses": [me]}},
            {"protocol": "icmp", "sources": {"tags": ["scdb-validator", "scdb-client"], "addresses": [me]}},
        ],
        "outbound_rules": [
            {"protocol": "tcp", "ports": "all", "destinations": {"addresses": ["0.0.0.0/0", "::/0"]}},
            {"protocol": "udp", "ports": "all", "destinations": {"addresses": ["0.0.0.0/0", "::/0"]}},
            {"protocol": "icmp", "destinations": {"addresses": ["0.0.0.0/0", "::/0"]}},
        ],
        "tags": ["scdb-validator", "scdb-client"],
    }
    fws = do_req("GET", "/firewalls?per_page=200").get("firewalls", [])
    fw = next((f for f in fws if f["name"] == "scdb-lan"), None)
    if fw is None:
        do_req("POST", "/firewalls", fw_body)
    else:
        do_req("PUT", "/firewalls/" + fw["id"], fw_body)  # refresh allowed source address
    have = {d["name"] for d in do_req("GET", "/droplets?per_page=200")["droplets"]}
    common = {"region": region, "image": "ubuntu-24-04-x64", "ssh_keys": [key["id"]],
              "vpc_uuid": vpc["id"], "monitoring": True}
    vals = [n for n in NAMES[:4] if n not in have]
    if vals:
        do_req("POST", "/droplets", dict(common, names=vals, size=size_v, tags=["scdb-validator"]))
    if "scdb-client" not in have:
        do_req("POST", "/droplets", dict(common, names=["scdb-client"], size=size_c, tags=["scdb-client"]))
    for _ in range(60):
        drops = [d for d in do_req("GET", "/droplets?per_page=200")["droplets"] if d["name"] in NAMES]
        if len(drops) == 5 and all(d["status"] == "active" for d in drops):
            break
        print("waiting", [(d["name"], d["status"]) for d in drops], flush=True)
        time.sleep(8)
    else:
        raise SystemExit("droplets did not become active")
    hosts = {}
    for d in drops:
        pub_ip = next(n["ip_address"] for n in d["networks"]["v4"] if n["type"] == "public")
        priv_ip = next(n["ip_address"] for n in d["networks"]["v4"] if n["type"] == "private")
        hosts[d["name"]] = (pub_ip, priv_ip)
    with open(HOSTS, "w", newline="\n") as fh:
        fh.write("# DigitalOcean %s LAN, created %s. Gitignored.\n" % (region, time.strftime("%Y-%m-%d")))
        fh.write("# Validators: %s. Client: %s. SSH/9984 allowed from %s.\n" % (size_v, size_c, me))
        for i in range(1, 5):
            fh.write("SCDB_V%d_PUBLIC=%s\nSCDB_V%d_PRIVATE=%s\n" % (i, hosts["scdb-v%d" % i][0], i, hosts["scdb-v%d" % i][1]))
        fh.write("SCDB_CLIENT_PUBLIC=%s\nSCDB_CLIENT_PRIVATE=%s\n" % hosts["scdb-client"])
    print("wrote", HOSTS)


def load_hosts():
    vals = {}
    with open(HOSTS) as fh:
        for line in fh:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                vals[k] = v
    validators = [(vals["SCDB_V%d_PUBLIC" % i], vals["SCDB_V%d_PRIVATE" % i]) for i in range(1, 5)]
    return validators, vals["SCDB_CLIENT_PUBLIC"]


# ------------------------------------------------------------------- the hosts
def wait_ssh(ips):
    for ip in ips:
        ssh(ip, "cloud-init status --wait >/dev/null 2>&1; echo ssh-ok $(hostname)", retries=15)


def install_docker(ips):
    procs = []
    for ip in ips:
        cmd = SSH + ["root@" + ip,
                     "command -v docker >/dev/null && echo have-docker && exit 0; "
                     "while fuser /var/lib/dpkg/lock-frontend >/dev/null 2>&1; do sleep 3; done; "
                     "curl -fsSL https://get.docker.com | sh >/dev/null 2>&1 && docker --version"]
        procs.append((ip, subprocess.Popen(cmd)))
    for ip, p in procs:
        if p.wait() != 0:
            raise SystemExit("docker install failed on " + ip)


def make_archive():
    tar = os.path.join(tempfile.gettempdir(), "scdb_head.tar")
    sh(["git", "-C", ROOT, "archive", "--format=tar", "-o", tar, "HEAD"])
    return tar


def deploy(validators, client, tar, with_env=True):
    env = os.path.join(ROOT, ".env")
    for pub, _ in validators:
        scp(tar, pub, "/root/scdb.tar")
        if with_env:
            scp(env, pub, "/root/scdb.env")
        ssh(pub, "mkdir -p /root/smartchaindb && tar -xf /root/scdb.tar -C /root/smartchaindb "
                 "&& (test -f /root/scdb.env && mv /root/scdb.env /root/smartchaindb/.env || true) "
                 "&& sed -i 's/\\r$//' /root/smartchaindb/docker/4node/*.sh && echo deployed")
    scp(tar, client, "/root/scdb.tar")
    scp(env, client, "/root/scdb.env")
    ssh(client, "mkdir -p /root/smartchaindb /root/out && tar -xf /root/scdb.tar -C /root/smartchaindb "
                "&& mv /root/scdb.env /root/smartchaindb/.env && echo deployed-client")


def build_images(validators, client):
    """Build images in parallel on every host (long). Mongo/Tendermint pulled too."""
    procs = []
    for pub, _ in validators:
        cmd = SSH + ["root@" + pub,
                     "cd /root/smartchaindb && docker compose --env-file .env -f docker-compose.onenode.yml build "
                     ">/var/log/scdb-build.log 2>&1 && docker pull mongo:3.6 >/dev/null && "
                     "docker pull tendermint/tendermint:v0.31.5 >/dev/null && echo BUILD_DONE $(hostname)"]
        procs.append((pub, subprocess.Popen(cmd)))
    cmd = SSH + ["root@" + client,
                 "cd /root/smartchaindb && docker build -t smartchaindb-bigchaindb -f Dockerfile-dev . "
                 ">/var/log/scdb-build.log 2>&1 && echo BUILD_DONE client"]
    procs.append((client, subprocess.Popen(cmd)))
    for ip, p in procs:
        if p.wait() != 0:
            raise SystemExit("image build failed on %s (see /var/log/scdb-build.log)" % ip)


def genesis(validators):
    """Fresh keys + 4-validator genesis generated on v1, homes installed everywhere."""
    v1 = validators[0][0]
    hosts_map = os.path.join(tempfile.gettempdir(), "hosts.lan.map")
    with open(hosts_map, "w", newline="\n") as fh:
        for i, (_, priv) in enumerate(validators, 1):
            fh.write("%d %s\n" % (i, priv))
    scp(hosts_map, v1, "/root/hosts.map")
    ssh(v1, "set -e; rm -rf /root/gen && mkdir -p /root/gen && cd /root/gen "
            "&& cp /root/smartchaindb/docker/4node/gen_genesis.sh /root/smartchaindb/docker/4node/merge_genesis.py "
            "/root/smartchaindb/docker/4node/run.sh . && cp /root/hosts.map hosts.map "
            "&& bash gen_genesis.sh >/dev/null 2>&1 "
            "&& for i in 1 2 3 4; do cp run.sh n$i/run.sh; chmod +x n$i/run.sh; done "
            "&& tar -czf /root/homes.tgz n1 n2 n3 n4 && cat n1/node.env")
    local = os.path.join(tempfile.gettempdir(), "scdb_homes.tgz")
    sh(SCP + ["root@%s:/root/homes.tgz" % v1, local])
    for i, (pub, _) in enumerate(validators, 1):
        scp(local, pub, "/root/homes.tgz")
        ssh(pub, "set -e; rm -rf /tmp/h && mkdir -p /tmp/h && tar -xzf /root/homes.tgz -C /tmp/h "
                 "&& rm -rf /root/smartchaindb/docker/4node/node && mv /tmp/h/n%d /root/smartchaindb/docker/4node/node "
                 "&& cp /root/smartchaindb/docker/4node/node/node.env /root/smartchaindb/docker/4node/node.env "
                 "&& grep TM_EXTERNAL /root/smartchaindb/docker/4node/node.env" % i)


def up(validators):
    for pub, _ in validators:
        ssh(pub, "cd /root/smartchaindb && bash docker/4node/host_up.sh >/var/log/scdb-up.log 2>&1; tail -1 /var/log/scdb-up.log")


def restart_code(validators):
    """After a code push: restart the containers that mount the tree."""
    for pub, _ in validators:
        ssh(pub, "docker restart scdb-node-shacl-1 scdb-node-bdb-1 >/dev/null && echo restarted $(hostname)")


def wait_ready(validators):
    probe = ("for i in $(seq 1 60); do curl -sf http://127.0.0.1:9984/ >/dev/null && "
             "curl -sf http://127.0.0.1:26657/net_info | grep -q '\"n_peers\": \"3\"' && echo READY $(hostname) && exit 0; "
             "sleep 3; done; echo NOT_READY $(hostname); curl -s http://127.0.0.1:26657/net_info | head -c 400; exit 1")
    for pub, _ in validators:
        ssh(pub, probe)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--provision", action="store_true", help="create droplets, VPC, firewall")
    parser.add_argument("--region", default="nyc3")
    parser.add_argument("--size-validator", default="s-4vcpu-8gb-amd")
    parser.add_argument("--size-client", default="s-2vcpu-4gb-amd")
    parser.add_argument("--deploy-only", action="store_true", help="push HEAD and restart bdb/shacl")
    args = parser.parse_args()

    if args.provision:
        provision(args.region, args.size_validator, args.size_client)
    validators, client = load_hosts()
    pubs = [v[0] for v in validators] + [client]
    tar = make_archive()
    if args.deploy_only:
        deploy(validators, client, tar, with_env=False)
        restart_code(validators)
        wait_ready(validators)
        return 0
    wait_ssh(pubs)
    install_docker(pubs)
    deploy(validators, client, tar)
    build_images(validators, client)
    genesis(validators)
    up(validators)
    wait_ready(validators)
    print("LAN ready:", [v[0] for v in validators], "client", client)
    return 0


if __name__ == "__main__":
    sys.exit(main())
