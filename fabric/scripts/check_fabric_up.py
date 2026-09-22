#!/usr/bin/env python3
import json
import subprocess
import urllib.request

print("=== docker fabric ===")
out = subprocess.check_output(
    ["docker", "ps", "--format", "{{.Names}}\t{{.Status}}\t{{.Ports}}"],
    text=True,
)
for line in out.splitlines():
    low = line.lower()
    if any(x in low for x in ("peer", "orderer", "ca", "couch", "fabric")):
        print(line)
if "peer0.org1" not in out:
    print("NO_ORG1_PEER")

print("=== fabric shacl :3001 ===")
try:
    with urllib.request.urlopen("http://127.0.0.1:3001/", timeout=3) as r:
        print(r.read().decode()[:400])
except Exception as exc:
    print("DOWN", type(exc).__name__, exc)

print("=== peer 7051 ===")
try:
    s = subprocess.run(
        ["bash", "-lc", "timeout 2 bash -c 'echo >/dev/tcp/127.0.0.1/7051' && echo OPEN || echo CLOSED"],
        capture_output=True,
        text=True,
    )
    print((s.stdout or s.stderr).strip())
except Exception as exc:
    print(exc)
