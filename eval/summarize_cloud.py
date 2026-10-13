#!/usr/bin/env python3
"""Summarize a cloud campaign directory (eval/results/<tag>/) into one JSON.

Medians carry bootstrap 95% confidence intervals (percentile bootstrap,
2,000 resamples, fixed seed). Cross-mode verdict disagreement for the
semantic matrix is computed when more than one mode is present.
"""
from __future__ import print_function

import argparse
import csv
import glob
import json
import os
import random
from collections import defaultdict

MODES = ("direct", "shacl", "delta")
B = 2000


def med(s):
    return None if not s else s.get("median")


def p95(s):
    return None if not s else s.get("p95")


def boot_ci(samples, stat="median", b=B, seed=7):
    """Percentile-bootstrap 95% CI of the median (or mean) of ``samples``."""
    xs = [float(x) for x in (samples or []) if x is not None]
    if len(xs) < 2:
        return None
    rng = random.Random(seed)
    n = len(xs)

    def st(v):
        if stat == "mean":
            return sum(v) / len(v)
        v = sorted(v)
        return v[n // 2] if n % 2 else 0.5 * (v[n // 2 - 1] + v[n // 2])

    reps = sorted(st([xs[rng.randrange(n)] for _ in range(n)]) for _ in range(b))
    return {"lo": reps[int(0.025 * b)], "hi": reps[int(0.975 * b)], "n": n}


def stat_block(s):
    """Summary dict with CI from a driver ``summarize()`` block."""
    if not s:
        return None
    out = {k: s.get(k) for k in ("n", "mean", "median", "p95", "min", "max")}
    out["ci95_median"] = boot_ci(s.get("samples"))
    return out


def cache_pair(stats):
    stats = stats or {}
    web = stats.get("cache") or {}
    abci = (stats.get("abci") or {}).get("cache") or {}
    rs_web = stats.get("read_set") or {}
    rs_abci = (stats.get("abci") or {}).get("read_set") or {}
    return {"web": web, "abci": abci, "read_set_web": rs_web, "read_set_abci": rs_abci,
            "memory_web": stats.get("cache_memory"), "memory_abci": (stats.get("abci") or {}).get("cache_memory")}


def phases(block):
    """Median per phase from a PhaseTimer snapshot."""
    out = {}
    for name, v in (block or {}).items():
        if isinstance(v, dict):
            out[name] = {k: v.get(k) for k in ("n", "median", "mean", "p95") if k in v}
    return out


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


def load_json(path):
    if not os.path.exists(path):
        return None
    with open(path) as handle:
        return json.load(handle)


def summarize_mode(tag_dir, tag, mode):
    d = load_json(os.path.join(tag_dir, "bdb_%s_%s.json" % (tag, mode)))
    if d is None:
        return None
    m = {"n": {k: d.get(k) for k in ("n_e2e", "n_offer", "n_disjoint", "n_val", "matrix_reps")}}
    e2e = d.get("e2e") or {}
    m["e2e_total"] = stat_block(e2e.get("total"))
    m["e2e_by_op"] = {op: stat_block(v) for op, v in (e2e.get("by_op") or {}).items()}
    sh = d.get("mix_shared") or {}
    m["shared"] = {
        "committed": sh.get("committed"), "rejected": sh.get("rejected"),
        "commit": stat_block(sh.get("commit")),
        "validate_first": stat_block(sh.get("validate_first")),
        "validate_second": stat_block(sh.get("validate_second")),
        "cache": cache_pair(sh.get("stats")),
    }
    mu = d.get("mix_mutate") or {}
    m["mutate"] = {
        "committed": mu.get("committed"), "rejected": mu.get("rejected"), "abort_rate": mu.get("abort_rate"),
        "before_close": stat_block(mu.get("before_close")), "after_close": stat_block(mu.get("after_close")),
        "cache": cache_pair(mu.get("stats")),
    }
    dj = d.get("mix_disjoint") or {}
    m["disjoint"] = {"committed": dj.get("committed"), "commit": stat_block(dj.get("commit")),
                     "cache": cache_pair(dj.get("stats"))}
    fc = d.get("fail_closed") or {}
    m["fail_closed"] = {"status": fc.get("status"), "rejected": fc.get("rejected"), "ms": fc.get("ms")}

    sm = d.get("semantic_matrix")
    if sm:
        m["matrix"] = {
            "cases": sm.get("cases"), "mismatches": sm.get("mismatches"), "errors_5xx": sm.get("errors_5xx"),
            "mismatch_rate": sm.get("mismatch_rate"),
            "by_case": {"%s/%s" % (r["op"], r["case"]): r["outcome"] for r in sm.get("rows", [])},
            "mismatch_rows": [{k: r[k] for k in ("op", "case", "expected", "status", "outcome", "body")}
                              for r in sm.get("rows", []) if not r.get("as_expected")],
        }
    ur = d.get("update_ratio")
    if ur:
        m["update_ratio"] = [{
            "p": row["relevant_ratio"], "n": row["n"], "committed": row["committed"], "rejected": row["rejected"],
            "latency": stat_block(row.get("latency")), "cache": cache_pair(row.get("stats")),
        } for row in ur]
    lo = d.get("load_open")
    if lo:
        m["load_open"] = [{
            "offered_rate": r["offered_rate"], "achieved_offered_rate": r.get("achieved_offered_rate"),
            "attempted": r["attempted"], "committed_ok": r["committed_ok"], "committed_rejected": r["committed_rejected"],
            "lost": r.get("lost"), "still_unconfirmed": r.get("still_unconfirmed"), "rpc": r.get("rpc"),
            "committed_tps_wall": r["committed_tps_wall"], "committed_tps_blockspan": r["committed_tps_blockspan"],
            "blocks": r.get("blocks"), "latency_block": stat_block(r.get("latency_block_ms")),
            "latency_client": stat_block(r.get("latency_client_ms")), "cache": cache_pair(r.get("stats")),
        } for r in lo]
    m["load_closed"] = [{
        "c": row.get("concurrency"), "committed_tps": row.get("committed_tps"), "offered_tps": row.get("offered_tps"),
        "rejected": row.get("rejected"), "latency": stat_block(row.get("latency")),
    } for row in (d.get("load") or [])]

    ed = load_json(os.path.join(tag_dir, "bdb_%s_%s_engine_down.json" % (tag, mode)))
    if ed and ed.get("engine_down"):
        e = ed["engine_down"]
        m["engine_down"] = {"all_rejected": e.get("all_rejected"), "any_committed": e.get("any_committed"),
                            "probes": [{k: p.get(k) for k in ("status", "outcome", "ms", "validate_status", "body")}
                                       for p in e.get("probes", [])]}

    val = load_json(os.path.join(tag_dir, "bdb_%s_%s_val.json" % (tag, mode)))
    if val:
        vl = val.get("validation_layer") or {}
        m["validation"] = {k: dict(stat_block(v), phases=phases(v.get("phases")))
                           for k, v in vl.items() if isinstance(v, dict) and "median" in v}
        if "value_change" in vl:
            m["validation"]["value_change"]["rejected"] = vl["value_change"].get("rejected")
        m["validation_cache_stats"] = {"after_hits": vl.get("delta_stats_hits"), "after_change": vl.get("delta_stats_after")}
        seq = val.get("delta_sequence")
        if seq:
            m["delta_sequence"] = seq.get("summary")
            m["delta_sequence_step_ms"] = {}
            for row in seq.get("rows", []):
                key = "%s/%s" % (row["policy"], "signal" if row["commit_signal"] else "nosignal")
                for s in row["steps"]:
                    m["delta_sequence_step_ms"].setdefault(key, {}).setdefault(s["step"], []).append(s["ms"])
            for key, steps in m["delta_sequence_step_ms"].items():
                for step, xs in steps.items():
                    xs.sort()
                    steps[step] = {"n": len(xs), "median": xs[len(xs) // 2]}
        m["server_stats_after_inprocess"] = cache_pair(val.get("server_stats"))

    states = []
    for path in sorted(glob.glob(os.path.join(tag_dir, "bdb_%s_%s_val_state*.json" % (tag, mode)))):
        sv = load_json(path)
        vl = (sv or {}).get("validation_layer") or {}
        label = (sv or {}).get("state_label") or os.path.basename(path)
        states.append({"label": label,
                       "noidx": label.endswith("_noidx"),
                       "size": int("".join(ch for ch in label.split("_")[0] if ch.isdigit()) or 0),
                       "conditions": {k: dict(stat_block(v), phases=phases(v.get("phases")))
                                      for k, v in vl.items() if isinstance(v, dict) and "median" in v}})
    if states:
        m["state_sweep"] = sorted(states, key=lambda s: (s["noidx"], s["size"]))

    m["cpu"] = cpu_summary(glob.glob(os.path.join(tag_dir, "cpu_%s_%s_*.csv" % (tag, mode))))
    return m


def cross_mode_matrix(modes):
    """Disagreement between modes on identical (op, case) verdicts."""
    present = {mode: m["matrix"]["by_case"] for mode, m in modes.items() if m and m.get("matrix")}
    if len(present) < 2:
        return None
    keys = set.intersection(*(set(v.keys()) for v in present.values()))
    out = {}
    names = sorted(present)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            dis = [k for k in sorted(keys) if present[a][k] != present[b][k]]
            out["%s-vs-%s" % (a, b)] = {"cases": len(keys), "disagreements": len(dis), "which": dis}
    return out


def summarize(tag_dir, tag):
    out = {"tag": tag, "modes": {}}
    for mode in MODES:
        m = summarize_mode(tag_dir, tag, mode)
        if m is not None:
            out["modes"][mode] = m
    out["matrix_cross_mode"] = cross_mode_matrix(out["modes"])
    return out


def fmt(block, key="median"):
    if not block or block.get(key) is None:
        return "n/a"
    ci = block.get("ci95_median")
    if ci:
        return "%.0f [%.0f, %.0f]" % (block[key], ci["lo"], ci["hi"])
    return "%.0f" % block[key]


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
        print("  e2e total ms %s | shared commit %s | mutate %s/%s rejected | fail-closed %s" % (
            fmt(m["e2e_total"]), fmt(m["shared"]["commit"]), m["mutate"]["rejected"],
            (m["mutate"]["committed"] or 0) + (m["mutate"]["rejected"] or 0), m["fail_closed"]["status"]))
        for mix in ("shared", "mutate", "disjoint"):
            c = m[mix]["cache"]
            print("  %-8s web %s" % (mix, {k: c["web"].get(k) for k in ("hits", "cold_misses", "dep_change_misses")}))
            print("  %-8s abci %s" % ("", {k: c["abci"].get(k) for k in ("hits", "cold_misses", "dep_change_misses", "retirements", "dep_invalidations")}))
            print("  %-8s read-set abci %s" % ("", {k: c["read_set_abci"].get(k) for k in ("checks", "uncovered")}))
        if m.get("matrix"):
            print("  matrix cases %s mismatches %s 5xx %s" % (m["matrix"]["cases"], m["matrix"]["mismatches"], m["matrix"]["errors_5xx"]))
        if m.get("engine_down"):
            print("  engine-down all_rejected %s" % m["engine_down"]["all_rejected"])
        if m.get("update_ratio"):
            print("  ratio", [(r["p"], r["cache"]["web"].get("hits"), r["cache"]["web"].get("dep_change_misses")) for r in m["update_ratio"]])
        if m.get("load_open"):
            print("  open-loop", [(r["offered_rate"], round(r["committed_tps_wall"], 2), r["committed_ok"], r["lost"]) for r in m["load_open"]])
        if m.get("validation"):
            print("  validation", {k: fmt(v) for k, v in m["validation"].items()})
        if m.get("delta_sequence"):
            print("  sequence", m["delta_sequence"])
        if m.get("state_sweep"):
            print("  state", [(s["label"], round(s["conditions"].get("shacl_miss", {}).get("median") or 0, 1)) for s in m["state_sweep"]])
        for host, conts in m["cpu"].items():
            print("  cpu", host, {k: round(v["mean"], 1) for k, v in conts.items()})
    if data.get("matrix_cross_mode"):
        print("== matrix cross-mode", {k: v["disagreements"] for k, v in data["matrix_cross_mode"].items()})
    print("wrote", out)


if __name__ == "__main__":
    main()
