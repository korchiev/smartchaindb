#!/usr/bin/env python3
"""Copy latest fail-closed / mutate blocks into the professor JSON files."""
from __future__ import print_function

import json
import os

ROOT = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(ROOT, "results")


def main():
    for mode in ("direct", "shacl", "delta"):
        fc_path = os.path.join(RES, "bdb_fc_{}.json".format(mode))
        dest_path = os.path.join(RES, "bdb_{}.json".format(mode))
        if not os.path.exists(fc_path) or not os.path.exists(dest_path):
            print("skip", mode, "missing", fc_path if not os.path.exists(fc_path) else dest_path)
            continue
        with open(fc_path, "r", encoding="utf-8") as handle:
            fc = json.load(handle)
        with open(dest_path, "r", encoding="utf-8") as handle:
            dest = json.load(handle)
        dest["mix_mutate"] = fc["mix_mutate"]
        dest["fail_closed"] = fc["fail_closed"]
        dest["fail_closed_source"] = "4-validator LAN re-run 2026-10-10"
        with open(dest_path, "w", encoding="utf-8") as handle:
            json.dump(dest, handle, indent=2)
        print(
            mode,
            "mutate abort",
            dest["mix_mutate"].get("abort_rate"),
            "stolen rejected",
            dest["fail_closed"].get("rejected"),
            dest["fail_closed"].get("status"),
        )


if __name__ == "__main__":
    main()
