#!/usr/bin/env python3
from pathlib import Path

src = Path("/mnt/c/Users/korchien/Research/smartchaindb/fabric/scripts/setup_fabric.sh")
dst = Path("/home/korchien/setup_fabric.sh")
text = src.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
dst.write_bytes(text)
dst.chmod(0o755)
print("Wrote", dst)
