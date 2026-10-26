#!/usr/bin/env python3
"""Evaluation figures from eval/results.

Primary source is the four-validator LAN campaign (default tag lan4d) and
its summary JSON with bootstrap intervals (eval/summarize_cloud.py). The
earlier four-region WAN run (wan4, five lifecycles) and the Fabric
test-network run (fabric_cloud.json) appear only where they add a verdict
or a geography comparison; their sample sizes are printed on the panels.
"""
from __future__ import print_function

import argparse
import csv
import glob
import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

ROOT = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(ROOT, "results")
OUT = os.path.join(ROOT, "figures")

DIRECT = "#4C78A8"
SHACL = "#F58518"
DELTA = "#54A24B"
RED = "#E45756"
GREY = "#BAB0AC"
MUTED = "#9D755D"

MODES = ("direct", "shacl", "delta")
COLORS = {"direct": DIRECT, "shacl": SHACL, "delta": DELTA}
PRETTY = {"direct": "Direct", "shacl": "SHACL", "delta": "SHACL+$\\Delta$"}
CONTAINERS = ("bdb", "tm", "mongo", "shacl")
CONTAINER_LABEL = {"bdb": "BigchainDB", "tm": "Tendermint", "mongo": "MongoDB", "shacl": "SHACL service"}

plt.rcParams.update({
    "font.size": 9,
    "axes.titlesize": 10,
    "legend.fontsize": 8,
    "pdf.fonttype": 42,
    "ps.fonttype": 42,
    "axes.spines.top": False,
    "axes.spines.right": False,
})


def load(*parts):
    path = os.path.join(RES, *parts)
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def load_campaign(tag):
    return dict((m, load(tag, "bdb_%s_%s.json" % (tag, m)) or {}) for m in MODES)


def save(fig, name):
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, name + ".pdf"))
    fig.savefig(os.path.join(OUT, name + ".png"), dpi=200)
    plt.close(fig)
    print("wrote", name)


def ci_err(block):
    """Asymmetric error from a summary block with ci95_median."""
    if not block or block.get("median") is None:
        return 0.0, 0.0
    ci = block.get("ci95_median")
    if not ci:
        return minmax_err(block)
    return max(0.0, block["median"] - ci["lo"]), max(0.0, ci["hi"] - block["median"])


def minmax_err(block):
    if not block or block.get("median") is None:
        return 0.0, 0.0
    med = block["median"]
    lo = block.get("min")
    hi = block.get("max")
    lo = med if lo is None else lo
    hi = med if hi is None else hi
    return max(0.0, med - lo), max(0.0, hi - med)


def cdf(ax, samples, label, color, style="-"):
    if not samples:
        return
    ordered = np.sort(np.array(samples, dtype=float))
    y = np.arange(1, len(ordered) + 1) / float(len(ordered))
    ax.step(ordered, y, where="post", label=label, color=color, linestyle=style)


# ------------------------------------------------------------- figure 1: phases
def fig_phases(summary):
    val = (summary["modes"].get("delta") or {}).get("validation") or {}
    if not val:
        return
    fig, ax = plt.subplots(figsize=(6.4, 3.3))
    conds = (("direct", "Direct"), ("shacl_miss", "SHACL miss"), ("delta_hit", "$\\Delta$ hit"), ("value_change", "Value change\n(must miss)"))
    layers = (
        ("dep_fetch", "Dependency fetch", "#72B7B2"),
        ("direct", "Imperative checks", DIRECT),
        ("rdf", "RDF build", "#B279A2"),
        ("engine_parse", "Engine: parse", "#FFBF79"),
        ("engine_shacl", "Engine: SHACL", SHACL),
        ("engine_state", "Engine: state checks", MUTED),
        ("http_overhead", "HTTP transport", GREY),
        ("cache_lookup", "Cache lookup", DELTA),
    )
    x = np.arange(len(conds))
    bottoms = np.zeros(len(conds))
    for key, label, color in layers:
        vals = []
        for cond, _ in conds:
            ph = (val.get(cond) or {}).get("phases") or {}
            if key == "http_overhead":
                http = (ph.get("http") or {}).get("median") or 0.0
                eng = (ph.get("engine_total") or {}).get("median") or 0.0
                vals.append(max(0.0, http - eng))
            else:
                vals.append((ph.get(key) or {}).get("median") or 0.0)
        vals = np.array(vals)
        if vals.sum() <= 0:
            continue
        ax.bar(x, vals, 0.6, bottom=bottoms, color=color, label=label, edgecolor="white", linewidth=0.4)
        bottoms += vals
    for i, (cond, _) in enumerate(conds):
        block = val.get(cond) or {}
        med = block.get("median")
        if med is None:
            continue
        lo, hi = ci_err(block)
        ax.errorbar(i, med, yerr=[[lo], [hi]], fmt="none", ecolor="black", capsize=3, lw=0.8)
        ax.text(i, med + 1.0, "%.1f ms" % med, ha="center", va="bottom", fontsize=8)
    ax.set_xticks(x)
    ax.set_xticklabels([lab for _, lab in conds])
    ax.set_ylabel("Median per validation (ms)")
    ax.set_ylim(0, max(bottoms) * 1.9)
    n = (val.get("shacl_miss") or {}).get("n", "?")
    ax.set_title("Direct, miss, and hit: n=%s. Value change: one probe." % n)
    ax.legend(frameon=False, ncol=2, loc="upper left", fontsize=7)
    save(fig, "fig_validation_phases")


# -------------------------------------------------------- figure 2: state sweep
def fig_state(summary):
    sweep = (summary["modes"].get("delta") or {}).get("state_sweep") or []
    if not sweep:
        return
    fig, ax = plt.subplots(figsize=(5.4, 3.3))
    series = (("direct", "Direct", DIRECT), ("shacl_miss", "SHACL miss", SHACL), ("delta_hit", "$\\Delta$ hit", DELTA))
    for noidx, style, suffix in ((False, "-", "indexed"), (True, "--", "no indexes")):
        rows = sorted([s for s in sweep if s["noidx"] == noidx], key=lambda s: s["size"])
        if not rows:
            continue
        xs = [r["size"] for r in rows]
        for key, label, color in series:
            ys = [(r["conditions"].get(key) or {}).get("median") for r in rows]
            if any(y is None for y in ys):
                continue
            ax.plot(xs, ys, marker="o", linestyle=style, color=color, label="%s, %s" % (label, suffix))
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("Synthetic workflow units")
    ax.set_ylabel("Median validation (ms, log)")
    ax.set_title("Validation cost vs. ledger size")
    ax.legend(frameon=False, ncol=2, fontsize=7)
    save(fig, "fig_state_sweep")


# ----------------------------------------------------------- figure 3: sequence
def fig_sequence(summary):
    seq = (summary["modes"].get("delta") or {}).get("delta_sequence") or {}
    if not seq:
        return
    order = ["delta/signal", "delta/nosignal", "entity/signal", "entity/nosignal", "flush/signal", "flush/nosignal"]
    order = [k for k in order if k in seq]
    labels = []
    for k in order:
        pol, sig = k.split("/")
        labels.append("%s\n%s" % ({"delta": "$\\Delta$", "entity": "Entity", "flush": "Flush"}[pol],
                                  "signal" if sig == "signal" else "no signal"))
    fields = (("unrelated_preserved", "Unrelated commit: verdict kept", DELTA),
              ("relevant_invalidated", "Relevant commit: verdict dropped", SHACL),
              ("stale_reuse", "Stale verdict reused", RED))
    fig, ax = plt.subplots(figsize=(6.4, 3.2))
    x = np.arange(len(order))
    w = 0.26
    total = max(seq[k].get("sequences", 0) for k in order) or 1
    for off, (field, label, color) in zip((-w, 0, w), fields):
        vals = [seq[k].get(field, 0) for k in order]
        bars = ax.bar(x + off, vals, w, color=color, label=label)
        for bar, v in zip(bars, vals):
            ax.text(bar.get_x() + bar.get_width() / 2.0, v + 0.15, str(v), ha="center", fontsize=7)
    ax.axhline(total, color="black", lw=0.6, ls=":")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=8)
    ax.set_ylabel("Sequences (of %d)" % total)
    ax.set_ylim(0, total * 1.35)
    ax.set_title("Cache policy under a dependency change")
    ax.legend(frameon=False, ncol=1, loc="upper right", fontsize=7)
    save(fig, "fig_delta_sequence")


# -------------------------------------------------------- figure 4: lifecycles
OPS = (("CREATE", "Create"), ("ADVERTISEMENT", "Advertise"), ("UPDATE_ADV", "UpdateAdv"), ("BUY_OFFER", "BuyOffer"),
       ("SELL", "Sell"), ("REQUEST_RETURN", "ReqReturn"), ("SELLER_ACCEPT_RETURN", "AcceptReturn"))


def fig_e2e(summary, wan, wan_summary):
    fig, axes = plt.subplots(1, 2, figsize=(9.2, 3.3), gridspec_kw={"width_ratios": [1, 1.6]})
    ax = axes[0]
    width = 0.36
    n_lan = None
    n_wan = None
    for offset, label, hatch, source in ((-width / 2, "LAN", "", "lan"), (width / 2, "WAN", "//", "wan")):
        for i, mode in enumerate(MODES):
            if source == "lan":
                block = (summary["modes"].get(mode) or {}).get("e2e_total")
                err = ci_err(block)
                n_lan = (block or {}).get("n", n_lan)
            else:
                block = ((wan_summary or {}).get("modes", {}).get(mode) or {}).get("e2e_total")
                if block is None:
                    block = ((wan.get(mode) or {}).get("e2e") or {}).get("total")
                err = minmax_err(block)
                n_wan = (block or {}).get("n", n_wan)
            if not block or block.get("median") is None:
                continue
            ax.bar(i + offset, block["median"] / 1000.0, width, color=COLORS[mode], hatch=hatch,
                   edgecolor="white" if not hatch else "black", linewidth=0.4,
                   yerr=[[err[0] / 1000.0], [err[1] / 1000.0]], capsize=3, label=label if i == 0 else None)
    ax.set_xticks(range(len(MODES)))
    ax.set_xticklabels([PRETTY[m] for m in MODES])
    ax.set_ylabel("Seven-step lifecycle (s)")
    ax.set_title("LAN n=%s (95%% CI), WAN n=%s (min-max)" % (n_lan, n_wan), fontsize=9)
    ax.set_ylim(0, ax.get_ylim()[1] * 1.15)
    ax.legend(frameon=False, loc="upper left", ncol=2)

    ax = axes[1]
    x = np.arange(len(OPS))
    w = 0.26
    for off, mode in zip((-w, 0, w), MODES):
        by_op = (summary["modes"].get(mode) or {}).get("e2e_by_op") or {}
        meds = [(by_op.get(op) or {}).get("median") or 0 for op, _ in OPS]
        errs = [ci_err(by_op.get(op)) for op, _ in OPS]
        ax.bar(x + off, meds, w, color=COLORS[mode], label=PRETTY[mode],
               yerr=[[e[0] for e in errs], [e[1] for e in errs]], capsize=2, error_kw={"lw": 0.6})
    ax.set_xticks(x)
    ax.set_xticklabels([lab for _, lab in OPS], fontsize=8)
    ax.set_ylabel("Commit latency (ms)")
    ax.set_title("Per-operation commit, LAN (median, 95% CI)", fontsize=9)
    ax.set_ylim(0, ax.get_ylim()[1] * 1.15)
    ax.legend(frameon=False, ncol=3, loc="upper left")
    save(fig, "fig_e2e_both")


# --------------------------------------------------------- figure 5: offer CDFs
def fig_cdf(lan, wan):
    fig, axes = plt.subplots(1, 2, figsize=(9.2, 3.3))
    for mode in MODES:
        shared = ((lan.get(mode) or {}).get("mix_shared") or {}).get("commit") or {}
        disjoint = ((lan.get(mode) or {}).get("mix_disjoint") or {}).get("commit") or {}
        cdf(axes[0], shared.get("samples"), PRETTY[mode], COLORS[mode])
        cdf(axes[1], disjoint.get("samples"), PRETTY[mode] + " LAN", COLORS[mode])
        wshared = ((wan.get(mode) or {}).get("mix_shared") or {}).get("commit") or {}
        cdf(axes[1], wshared.get("samples"), PRETTY[mode] + " WAN (shared)", COLORS[mode], "--")
    n_sh = (((lan.get("delta") or {}).get("mix_shared") or {}).get("commit") or {}).get("n", "?")
    n_dj = (((lan.get("delta") or {}).get("mix_disjoint") or {}).get("commit") or {}).get("n", "?")
    n_w = (((wan.get("delta") or {}).get("mix_shared") or {}).get("commit") or {}).get("n", "?")
    axes[0].set_title("BuyOffers on one advertisement, LAN (n=%s)" % n_sh, fontsize=9)
    axes[1].set_title("Disjoint assets LAN (n=%s); WAN shared (n=%s)" % (n_dj, n_w), fontsize=9)
    for ax in axes:
        ax.set_xlabel("Commit latency (ms)")
        ax.set_ylabel("CDF")
        ax.set_ylim(0, 1.02)
        ax.legend(frameon=False, loc="lower right", fontsize=7)
    save(fig, "fig_cdf_offers")


# ---------------------------------------------------------- figure 6: open loop
def fig_open(summary):
    fig, axes = plt.subplots(1, 2, figsize=(9.2, 3.3))
    for mode in MODES:
        rows = (summary["modes"].get(mode) or {}).get("load_open") or []
        if not rows:
            continue
        xs = [r["offered_rate"] for r in rows]
        axes[0].plot(xs, [r["committed_tps_wall"] for r in rows], marker="o", color=COLORS[mode], label=PRETTY[mode])
        lat = [((r.get("latency_client") or {}).get("median") or np.nan) / 1000.0 for r in rows]
        err = [ci_err(r.get("latency_client")) for r in rows]
        axes[1].errorbar(xs, lat, yerr=[[e[0] / 1000.0 for e in err], [e[1] / 1000.0 for e in err]],
                         marker="o", color=COLORS[mode], label=PRETTY[mode], capsize=2, lw=1)
    xs_all = sorted({r["offered_rate"] for m in MODES for r in ((summary["modes"].get(m) or {}).get("load_open") or [])})
    axes[0].plot(xs_all, xs_all, color="black", lw=0.6, ls=":", label="offered = committed")
    axes[0].set_ylabel("Committed (tx/s, wall clock incl. drain)")
    axes[0].set_title("Open-loop throughput, 4-validator LAN", fontsize=9)
    axes[1].set_yscale("log")
    axes[1].set_ylabel("Client-observed commit latency (s, log)")
    axes[1].set_title("Latency at each offered rate (16 samples, 95% CI)", fontsize=9)
    for ax in axes:
        ax.set_xscale("log", base=2)
        ax.set_xticks(xs_all)
        ax.set_xticklabels([("%d" % x) for x in xs_all])
        ax.set_xlabel("Offered rate (tx/s)")
        ax.legend(frameon=False, fontsize=7)
    save(fig, "fig_open_loop")


# ------------------------------------------ compact paper system-boundary figure
def fig_system_boundary(summary):
    fig, axes = plt.subplots(1, 2, figsize=(8.8, 3.0))

    ax = axes[0]
    blocks = [(summary["modes"].get(mode) or {}).get("e2e_total") for mode in MODES]
    medians = [(block or {}).get("median", 0) / 1000.0 for block in blocks]
    errors = [ci_err(block) for block in blocks]
    x = np.arange(len(MODES))
    ax.bar(
        x,
        medians,
        0.62,
        color=[COLORS[mode] for mode in MODES],
        yerr=[
            [error[0] / 1000.0 for error in errors],
            [error[1] / 1000.0 for error in errors],
        ],
        capsize=3,
    )
    ax.set_xticks(x)
    ax.set_xticklabels([PRETTY[mode] for mode in MODES])
    ax.set_ylabel("Seven-step lifecycle (s)")
    ax.set_title("Lifecycle latency (n=30, 95% CI)")
    ax.set_ylim(0, max(medians) * 1.3)

    ax = axes[1]
    offered = []
    for mode in MODES:
        rows = (summary["modes"].get(mode) or {}).get("load_open") or []
        if not rows:
            continue
        xs = [row["offered_rate"] for row in rows]
        offered.extend(xs)
        ax.plot(
            xs,
            [row["committed_tps_wall"] for row in rows],
            marker="o",
            color=COLORS[mode],
            label=PRETTY[mode],
        )
    offered = sorted(set(offered))
    ax.plot(offered, offered, color="black", lw=0.6, ls=":", label="offered = committed")
    ax.set_xscale("log", base=2)
    ax.set_xticks(offered)
    ax.set_xticklabels(["%d" % value for value in offered])
    ax.set_xlabel("Offered rate (tx/s)")
    ax.set_ylabel("Committed (tx/s, incl. drain)")
    ax.set_title("Open-loop capacity boundary")
    ax.legend(frameon=False, fontsize=7)
    save(fig, "fig_system_boundary")


def fig_fabric(fabric):
    """Fabric test network: verdict agreement and lifecycle, not a speed race."""
    modes = (fabric or {}).get("modes") or {}
    if not all(modes.get(mode) for mode in MODES):
        return
    fig, axes = plt.subplots(1, 2, figsize=(7.6, 2.8))
    x = np.arange(len(MODES))

    ax = axes[0]
    medians, lows, highs = [], [], []
    for mode in MODES:
        total = ((modes[mode].get("e2e") or {}).get("total") or {})
        median = float(total.get("median") or 0) / 1000.0
        medians.append(median)
        lows.append(max(0.0, median - float(total.get("min") or 0) / 1000.0))
        highs.append(max(0.0, float(total.get("max") or 0) / 1000.0 - median))
    ax.bar(x, medians, 0.62, color=[COLORS[mode] for mode in MODES],
           yerr=[lows, highs], capsize=3)
    ax.set_xticks(x)
    ax.set_xticklabels([PRETTY[mode] for mode in MODES])
    ax.set_ylabel("Seven-step lifecycle (s)")
    ax.set_title("Lifecycle (n=5, min–max)")
    ax.set_ylim(0, max(medians) * 1.28)

    ax = axes[1]
    width = 0.36
    owner, after = [], []
    for mode in MODES:
        blob = modes[mode]
        owner.append(100.0 if (blob.get("fail_closed") or {}).get("rejected") else 0.0)
        mutate = blob.get("mix_mutate") or {}
        after_n = float((mutate.get("after_close") or {}).get("n") or 0)
        after.append(100.0 * float(mutate.get("rejected") or 0) / after_n if after_n else 0.0)
    ax.bar(x - width / 2.0, owner, width, color=GREY, edgecolor="black", linewidth=0.4,
           label="Non-owner advertisement")
    ax.bar(x + width / 2.0, after, width, color=RED, edgecolor="black", linewidth=0.4,
           label="Offers after close")
    for xpos, value, text in (
        (x - width / 2.0, owner, "1/1"),
        (x + width / 2.0, after, "10/10"),
    ):
        for px, py in zip(xpos, value):
            ax.text(px, py + 3, text, ha="center", va="bottom", fontsize=7)
    ax.set_xticks(x)
    ax.set_xticklabels([PRETTY[mode] for mode in MODES])
    ax.set_ylim(0, 130)
    ax.set_ylabel("Rejected (%)")
    ax.set_title("Rules that travel")
    ax.legend(frameon=False, fontsize=7, loc="upper right")
    save(fig, "fig_fabric")


# ------------------------------------------------------ figure 7: verdict matrix
CASE_ORDER = ("CREATE", "ADVERTISEMENT", "UPDATE_ADV", "BUY_OFFER", "SELL", "REQUEST_RETURN", "SELLER_ACCEPT_RETURN")


def fig_matrix(lan, fabric):
    rows = []
    expected = {}
    for mode in MODES:
        sm = (lan.get(mode) or {}).get("semantic_matrix") or {}
        for r in sm.get("rows", []):
            key = (r["op"], r["case"])
            expected[key] = r["expected"]
    keys = sorted(expected, key=lambda k: (CASE_ORDER.index(k[0]) if k[0] in CASE_ORDER else 99, k[1] != "valid", k[1]))
    if not keys:
        return
    grid = np.zeros((len(keys), len(MODES)))
    for j, mode in enumerate(MODES):
        sm = (lan.get(mode) or {}).get("semantic_matrix") or {}
        per = {}
        for r in sm.get("rows", []):
            per.setdefault((r["op"], r["case"]), []).append(bool(r["as_expected"]))
        for i, key in enumerate(keys):
            flags = per.get(key) or []
            grid[i, j] = (sum(flags) / float(len(flags))) if flags else np.nan
    fig, axes = plt.subplots(1, 2, figsize=(9.2, 5.6), gridspec_kw={"width_ratios": [1.15, 1]})
    ax = axes[0]
    cmap = matplotlib.colors.ListedColormap([RED, "#F2CF5B", DELTA])
    norm = matplotlib.colors.BoundaryNorm([-0.01, 0.34, 0.99, 1.01], cmap.N)
    ax.imshow(grid, cmap=cmap, norm=norm, aspect="auto")
    ax.set_xticks(range(len(MODES)))
    ax.set_xticklabels([PRETTY[m] for m in MODES])
    ax.set_yticks(range(len(keys)))
    ax.set_yticklabels(["%s / %s (%s)" % (op.replace("_", " ").title().replace(" ", ""), case, expected[(op, case)][:3])
                        for op, case in keys], fontsize=7)
    for i in range(len(keys)):
        for j in range(len(MODES)):
            v = grid[i, j]
            if not np.isnan(v):
                ax.text(j, i, "%d/%d" % (round(v * 3), 3), ha="center", va="center", fontsize=7,
                        color="white" if v < 0.34 else "black")
    ax.set_title("Semantic matrix: executions matching the expected verdict", fontsize=9)
    ax.tick_params(axis="x", length=0)

    ax = axes[1]
    labels, mutate, stolen, down, colors = [], [], [], [], []
    for mode in MODES:
        blob = lan.get(mode) or {}
        mm = blob.get("mix_mutate") or {}
        att = mm.get("attempted") or 0
        rate = mm.get("abort_rate")
        labels.append(PRETTY[mode])
        mutate.append(100.0 * rate if rate is not None else (100.0 * (mm.get("rejected") or 0) / att if att else 0))
        stolen.append(100.0 if (blob.get("fail_closed") or {}).get("rejected") else 0.0)
        ed = load(TAG, "bdb_%s_%s_engine_down.json" % (TAG, mode))
        if ed and ed.get("engine_down"):
            probes = ed["engine_down"].get("probes") or []
            down.append(100.0 * sum(1 for p in probes if p.get("outcome") == "rejected") / float(len(probes) or 1))
        else:
            down.append(np.nan)
        colors.append(COLORS[mode])
    fab = ((fabric or {}).get("modes") or {}).get("delta") or {}
    if fab:
        labels.append("Fabric\nSHACL+$\\Delta$")
        mutate.append(100.0 * (fab.get("mix_mutate") or {}).get("abort_rate", 0))
        stolen.append(100.0 if (fab.get("fail_closed") or {}).get("rejected") else 0.0)
        down.append(np.nan)
        colors.append(MUTED)
    x = np.arange(len(labels))
    w = 0.26
    for off, vals, label, hatch in ((-w, mutate, "Offers after CLOSE rejected", ""),
                                    (0, stolen, "Non-owner advertisement rejected", "//"),
                                    (w, down, "Offers with engine stopped rejected", "..")):
        vv = [0 if np.isnan(v) else v for v in vals]
        bars = ax.bar(x + off, vv, w, color=colors, hatch=hatch, edgecolor="black", linewidth=0.4, label=label)
        for bar, v in zip(bars, vals):
            txt = "n/a" if np.isnan(v) else "%.0f%%" % v
            ax.text(bar.get_x() + bar.get_width() / 2.0, (0 if np.isnan(v) else v) + 2, txt, ha="center",
                    va="bottom", fontsize=6, rotation=90)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=8)
    ax.set_ylim(0, 135)
    ax.set_ylabel("Rejected (%)")
    ax.set_title("Fail-closed outcomes", fontsize=9)
    handles = [Patch(facecolor="white", edgecolor="black", label="Offers after CLOSE (expect 50%)"),
               Patch(facecolor="white", edgecolor="black", hatch="//", label="Non-owner advertisement"),
               Patch(facecolor="white", edgecolor="black", hatch="..", label="Engine stopped")]
    ax.legend(handles=handles, frameon=False, fontsize=7, loc="upper right")
    save(fig, "fig_verdicts")


# --------------------------------------------------------- figure 8: counters
def fig_counters(summary):
    delta = summary["modes"].get("delta") or {}
    mixes = (("shared", "Shared ad\n(500 offers)"), ("mutate", "Mutating ad\n(500 offers)"), ("disjoint", "Disjoint\n(200 tx)"))
    fields = (("hits", "Hits", DELTA), ("cold_misses", "Cold misses", SHACL),
              ("dep_change_misses", "Dependency-change misses", RED), ("retirements", "Retired on commit", MUTED),
              ("dep_invalidations", "Cross-tx dependency invalidations", GREY))
    fig, axes = plt.subplots(1, 3, figsize=(10.4, 3.3), gridspec_kw={"width_ratios": [1, 1, 1.1]})
    for ax, side, title in ((axes[0], "web", "Admission (web process)"), (axes[1], "abci", "Consensus (ABCI process)")):
        x = np.arange(len(mixes))
        w = 0.16
        for k, (field, label, color) in enumerate(fields):
            vals = [((delta.get(mix) or {}).get("cache") or {}).get(side, {}).get(field, 0) or 0 for mix, _ in mixes]
            bars = ax.bar(x + (k - 2) * w, vals, w, color=color, label=label)
            for bar, v in zip(bars, vals):
                if v:
                    ax.text(bar.get_x() + bar.get_width() / 2.0, v + 8, str(v), ha="center", fontsize=6, rotation=90)
        ax.set_xticks(x)
        ax.set_xticklabels([lab for _, lab in mixes], fontsize=8)
        ax.set_title(title, fontsize=9)
        ax.set_ylim(0, ax.get_ylim()[1] * 1.25)
    axes[0].set_ylabel("Count over the mix")
    axes[0].legend(frameon=False, fontsize=6, loc="upper right")

    ax = axes[2]
    ratio = delta.get("update_ratio") or []
    if ratio:
        ps = [r["p"] for r in ratio]
        hits = [(r["cache"]["web"].get("hits") or 0) for r in ratio]
        dep = [(r["cache"]["web"].get("dep_change_misses") or 0) for r in ratio]
        ax.plot(ps, hits, marker="o", color=DELTA, label="Admission hits")
        ax.plot(ps, dep, marker="s", color=RED, label="Dependency-change misses")
        ax2 = ax.twinx()
        lat = [(r["latency"] or {}).get("median") or np.nan for r in ratio]
        err = [ci_err(r.get("latency")) for r in ratio]
        ax2.errorbar(ps, lat, yerr=[[e[0] for e in err], [e[1] for e in err]], marker="^", color="black", lw=0.8,
                     capsize=2, label="Commit latency (ms)")
        ax2.set_ylabel("Commit latency (ms)")
        ax2.set_ylim(0, max(l for l in lat if not np.isnan(l)) * 1.6)
        ax2.spines["top"].set_visible(False)
        h1, l1 = ax.get_legend_handles_labels()
        h2, l2 = ax2.get_legend_handles_labels()
        ax.set_ylim(0, max(hits) * 1.6)
        ax.legend(h1 + h2, l1 + l2, frameon=False, fontsize=6, loc="upper left", ncol=3)
        n = ratio[0].get("n", "?")
        ax.set_title("Fraction of offers whose ad is updated (n=%s each)" % n, fontsize=9)
        ax.set_xlabel("Fraction of relevant updates")
        ax.set_ylabel("Count")
    save(fig, "fig_cache_counters")


# --------------------------------------------------------------- figure 9: CPU
def cpu_means(tag, mode):
    per_host = {}
    for path in glob.glob(os.path.join(RES, tag, "cpu_%s_%s_*.csv" % (tag, mode))):
        host = os.path.basename(path).rsplit("_", 1)[-1][:-4]
        vals = {}
        with open(path) as handle:
            for row in csv.reader(handle):
                if len(row) < 3:
                    continue
                try:
                    pct = float(row[2].rstrip("%"))
                except ValueError:
                    continue
                name = row[1].replace("scdb-node-", "").rsplit("-", 1)[0]
                vals.setdefault(name, []).append(pct)
        per_host[host] = dict((k, float(np.mean(v))) for k, v in vals.items())
    return per_host


def fig_cpu(tag):
    fig, ax = plt.subplots(figsize=(6.0, 3.1))
    x = np.arange(len(CONTAINERS))
    w = 0.26
    drew = False
    for off, mode in zip((-w, 0, w), MODES):
        per_host = cpu_means(tag, mode)
        if not per_host:
            continue
        drew = True
        means, lows, highs = [], [], []
        for name in CONTAINERS:
            vals = [h.get(name, 0.0) for h in per_host.values()]
            m = float(np.mean(vals))
            means.append(m)
            lows.append(m - min(vals))
            highs.append(max(vals) - m)
        ax.bar(x + off, means, w, yerr=[lows, highs], capsize=2, color=COLORS[mode], label=PRETTY[mode])
    if not drew:
        plt.close(fig)
        return
    ax.set_xticks(x)
    ax.set_xticklabels([CONTAINER_LABEL[c] for c in CONTAINERS])
    ax.set_ylabel("Mean CPU (% of one core)")
    ax.set_title("Container CPU per validator over the live workloads (bar = mean of 4, whisker = range)", fontsize=9)
    ax.legend(frameon=False)
    save(fig, "fig_cpu_bdb")


TAG = "lan4d"


def main():
    global TAG
    parser = argparse.ArgumentParser()
    parser.add_argument("--lan", default="lan4d")
    parser.add_argument("--wan", default="wan4")
    args = parser.parse_args()
    TAG = args.lan
    os.makedirs(OUT, exist_ok=True)
    summary = load(args.lan, "summary_%s.json" % args.lan)
    if summary is None:
        raise SystemExit("run eval/summarize_cloud.py %s first" % args.lan)
    lan = load_campaign(args.lan)
    wan = load_campaign(args.wan)
    wan_summary = load(args.wan, "summary_%s.json" % args.wan)
    fabric = load("fabric_cloud.json") or load("fabric.json")
    fig_phases(summary)
    fig_state(summary)
    fig_sequence(summary)
    fig_e2e(summary, wan, wan_summary)
    fig_cdf(lan, wan)
    fig_open(summary)
    fig_system_boundary(summary)
    fig_fabric(fabric)
    fig_matrix(lan, fabric)
    fig_counters(summary)
    fig_cpu(args.lan)
    print("figures in", OUT)


if __name__ == "__main__":
    main()
