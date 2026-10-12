#!/usr/bin/env python3
"""Summarize a cloud campaign directory (eval/results/<tag>/) into one JSON."""
from __future__ import print_function

import argparse
import csv
import glob
import json
import os
from collections import defaultdict

MODES = ("direct", "shacl", "delta")


def med(s):
    return None if not s else s.get("median")


def p95(s):
    return None if not s else s.get("p95")


def cache_pair(stats):
    stats = stats or {}
    web = stats.get("cache") or {}
    abci = (stats.get("abci") or {}).get("cache") or {}
    conflict = (stats.get("abci") or {}).get("conflict") or {}
    return {"web": web, "abci": abci, "abci_conflict": conflict}


def cpu_summary(paths):
    per = defaultdict(list)
    for path in paths:
        host = os.path.basename(path).rsplit("_", 1)[-1].replace(".csv", "")
        with open(path) as handle:
            for row in csv.reader(handle):
                if len(row) < 3:
                    continue
                try:
                    pct = float(row[2].rstrip("%"))
                except ValueError:
                    continue
                name = row[1].replace("scdb-node-", "").replace("-1", "")
                per[(host, name)].append(pct)
    out = {}
    for (host, name), vals in sorted(per.items()):
        vals.sort()
        out.setdefault(host, {})[name] = {
            "n": len(vals),
            "mean": sum(vals) / len(vals),
            "p95": vals[int(round(0.95 * (len(vals) - 1)))],
            "max": vals[-1],
        }
    return out


def summarize(tag_dir, tag):
    out = {"tag": tag, "modes": {}}
    for mode in MODES:
        path = os.path.join(tag_dir, "bdb_%s_%s.json" % (tag, mode))
        if not os.path.exists(path):
            continue
        with open(path) as handle:
            d = json.load(handle)
        m = {}
        e2e = d.get("e2e") or {}
        m["e2e_total"] = {k: (e2e.get("total") or {}).get(k) for k in ("median", "mean", "min", "max", "n")}
        m["e2e_by_op_median"] = {op: med(v) for op, v in (e2e.get("by_op") or {}).items()}
        sh = d.get("mix_shared") or {}
        m["shared"] = {
            "committed": sh.get("committed"),
            "median": med(sh.get("commit")),
            "p95": p95(sh.get("commit")),
            "samples": (sh.get("commit") or {}).get("samples"),
            "validate_first_median": med(sh.get("validate_first")),
            "validate_second_median": med(sh.get("validate_second")),
            "cache": cache_pair(sh.get("stats")),
        }
        mu = d.get("mix_mutate") or {}
        m["mutate"] = {
            "committed": mu.get("committed"),
            "rejected": mu.get("rejected"),
            "abort_rate": mu.get("abort_rate"),
            "before_median": med(mu.get("before_close")),
            "after_median": med(mu.get("after_close")),
            "cache": cache_pair(mu.get("stats")),
        }
        dj = d.get("mix_disjoint") or {}
        m["disjoint"] = {
            "committed": dj.get("committed"),
            "median": med(dj.get("commit")),
            "cache": cache_pair(dj.get("stats")),
        }
        fc = d.get("fail_closed") or {}
        m["fail_closed"] = {"status": fc.get("status"), "rejected": fc.get("rejected"), "ms": fc.get("ms")}
        cf = d.get("conflict") or {}
        m["conflict"] = {
            "committed": cf.get("committed"),
            "rejected": cf.get("rejected"),
            "cache": cache_pair(cf.get("stats")),
        }
        m["load"] = [
            {
                "c": row.get("concurrency"),
                "committed_tps": row.get("committed_tps"),
                "offered_tps": row.get("offered_tps"),
                "rejected": row.get("rejected"),
                "latency_median": med(row.get("latency")),
            }
            for row in (d.get("load") or [])
        ]
        val_path = os.path.join(tag_dir, "bdb_%s_%s_val.json" % (tag, mode))
        if os.path.exists(val_path):
            with open(val_path) as handle:
                vl = json.load(handle).get("validation_layer") or {}
            m["validation"] = {
                k: {kk: v.get(kk) for kk in ("median", "p95", "max", "n")}
                for k, v in vl.items() if isinstance(v, dict) and "median" in v
            }
        m["cpu"] = cpu_summary(glob.glob(os.path.join(tag_dir, "cpu_%s_%s_*.csv" % (tag, mode))))
        out["modes"][mode] = m
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("tag")
    args = parser.parse_args()
    root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results", args.tag)
    data = summarize(root, args.tag)
    out = os.path.join(root, "summary_%s.json" % args.tag)
    with open(out, "w") as handle:
        json.dump(data, handle, indent=2)
    for mode, m in data["modes"].items():
        print("==", mode)
        print("  e2e median %.0f ms  shared median %.0f p95 %.0f  mutate %s/%s  fail_closed %s %.0f ms" % (
            m["e2e_total"]["median"], m["shared"]["median"], m["shared"]["p95"],
            m["mutate"]["rejected"], m["mutate"]["committed"] + m["mutate"]["rejected"],
            m["fail_closed"]["status"], m["fail_closed"]["ms"]))
        print("  conflict committed/rejected %s/%s" % (m["conflict"]["committed"], m["conflict"]["rejected"]))
        for mix in ("shared", "mutate", "disjoint"):
            c = m[mix]["cache"]
            print("  %-8s web %s | abci %s" % (mix, c["web"], c["abci"]))
        print("  load", [(r["c"], round(r["committed_tps"], 2)) for r in m["load"]])
        if "validation" in m:
            print("  validation", {k: round(v["median"], 3) for k, v in m["validation"].items()})
        for host, conts in m["cpu"].items():
            print("  cpu", host, {k: round(v["mean"], 1) for k, v in conts.items()})
    print("wrote", out)


if __name__ == "__main__":
    main()
