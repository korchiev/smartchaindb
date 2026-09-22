#!/usr/bin/env python3
from pathlib import Path
import os
import pwd

bashrc = Path("/home/korchien/.bashrc")
lines = bashrc.read_text().splitlines()
lines = [line for line in lines if "fabric-samples/bin" not in line]
lines.append("export PATH=$HOME/fabric-samples/bin:$PATH")
bashrc.write_text("\n".join(lines) + "\n")
user = pwd.getpwnam("korchien")
os.chown(bashrc, user.pw_uid, user.pw_gid)
print("Updated bashrc tail:")
print("\n".join(bashrc.read_text().splitlines()[-5:]))
