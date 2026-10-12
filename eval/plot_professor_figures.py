#!/usr/bin/env python3
"""Professor-letter figures from eval/results JSON (BDB + Fabric)."""
from __future__ import print_function

import glob
import json
import os

import matplotlib.pyplot as plt
import numpy as np

ROOT = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(ROOT, "results")
OUT = os.path.join(ROOT, "figures")

DIRECT = "#4C78A8"
SHACL = "#F58518"
DELTA = "#54A24B"
MUTED = "#9D755D"

plt.rcParams.update(
    {
        "font.size": 10,
        "axes.titlesize": 11,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
        "axes.spines.top": False,
        "axes.spines.right": False,
    }
)


def load(name):
    path = os.path.join(RES, name)
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def median_of(block, *keys):
    cur = block
    for key in keys:
        if not isinstance(cur, dict) or key not in cur:
            return None
        cur = cur[key]
    if isinstance(cur, dict):
        return cur.get("median")
    return cur


def samples_of(block, *keys):
    cur = block
    for key in keys:
        if not isinstance(cur, dict) or key not in cur:
            return []
        cur = cur[key]
    if isinstance(cur, dict):
        return list(cur.get("samples") or [])
    return []


def err_from(summary):
    if not summary:
        return 0, 0
    med = summary.get("median", 0)
    return max(0, med - summary.get("min", med)), max(0, summary.get("max", med) - med)


def save(fig, name):
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, name + ".pdf"))
    fig.savefig(os.path.join(OUT, name + ".png"), dpi=200)
    plt.close(fig)
    print("wrote", name)


def cdf(ax, samples, label, color):
    if not samples:
        return
    ordered = np.sort(np.array(samples, dtype=float))
    y = np.arange(1, len(ordered) + 1) / float(len(ordered))
    ax.step(ordered, y, where="post", label=label, color=color)


def fig_validation(bdb, fabric):
    fig, axes = plt.subplots(1, 2, figsize=(9.2, 3.4), sharey=False)
    panels = [("SmartChainDB", bdb.get("validation_layer") if bdb else None), ("Fabric", fabric.get("validation_layer") if fabric else None)]
    for ax, (title, layer) in zip(axes, panels):
        if not layer:
            ax.set_title(title + " (no data)")
            continue
        labels = ["SHACL miss", "Δ hit", "Value change"]
        keys = ["shacl_http_miss", "shacl_delta_hit", "value_change_miss"]
        colors = [SHACL, DELTA, "#E45756"]
        meds = []
        lows = []
        highs = []
        for key in keys:
            row = layer.get(key) or {}
            med = row.get("median") or (row.get("samples") or [0])[0]
            if med <= 0:
                med = 0.001
            meds.append(med)
            lo, hi = err_from(row)
            lows.append(lo)
            highs.append(hi)
        if layer.get("direct_rdf"):
            labels = ["Direct"] + labels
            keys = ["direct_rdf"] + keys
            colors = [DIRECT] + colors
            row = layer["direct_rdf"]
            meds.insert(0, row.get("median", 0))
            lo, hi = err_from(row)
            lows.insert(0, lo)
            highs.insert(0, hi)
        x = np.arange(len(labels))
        ax.bar(x, meds, color=colors, yerr=[lows, highs], capsize=3, width=0.7)
        ax.set_yscale("log")
        ax.set_xticks(x)
        ax.set_xticklabels(labels, rotation=20, ha="right")
        ax.set_title("{} validation layer".format(title))
        ax.set_ylabel("ms (log)")
        n = (layer.get("shacl_http_miss") or {}).get("n", "?")
        ax.text(0.02, 0.95, "n={}".format(n), transform=ax.transAxes, va="top")
    save(fig, "fig_validation_both")


def fig_e2e(bdb_modes, fabric):
    fig, axes = plt.subplots(1, 2, figsize=(9.2, 3.4))
    names = ["direct", "shacl", "delta"]
    colors = [DIRECT, SHACL, DELTA]
    pretty = ["Direct", "SHACL", "SHACL+$\\Delta$"]

    def panel(ax, title, totals):
        xs = []
        meds = []
        lows = []
        highs = []
        cols = []
        labs = []
        for name, color, lab in zip(names, colors, pretty):
            row = totals.get(name)
            if not row:
                continue
            xs.append(len(xs))
            meds.append(row.get("median", 0) / 1000.0)
            lo, hi = err_from(row)
            lows.append(lo / 1000.0)
            highs.append(hi / 1000.0)
            cols.append(color)
            labs.append(lab)
        ax.bar(xs, meds, color=cols, yerr=[lows, highs], capsize=4, width=0.55)
        ax.set_xticks(xs)
        ax.set_xticklabels(labs)
        ax.set_ylabel("Full lifecycle (s)")
        ax.set_title(title)

    bdb_tot = {}
    for name in names:
        blob = bdb_modes.get(name) or {}
        if blob.get("e2e"):
            bdb_tot[name] = blob["e2e"]["total"]
    fab_tot = {}
    if fabric:
        for name in names:
            mode = (fabric.get("modes") or {}).get(name) or {}
            if mode.get("e2e"):
                fab_tot[name] = mode["e2e"]["total"]
    panel(axes[0], "SmartChainDB E2E (n=5)", bdb_tot)
    panel(axes[1], "Fabric E2E (n repeats)", fab_tot)
    save(fig, "fig_e2e_both")


def fig_cdf_offers(bdb_modes, fabric):
    fig, axes = plt.subplots(1, 2, figsize=(9.2, 3.6))
    for ax, title, source in (
        (axes[0], "SmartChainDB BUY_OFFER CDF (shared ad)", bdb_modes),
        (axes[1], "Fabric SubmitBuyOffer CDF (shared ad)", None),
    ):
        if title.startswith("SmartChainDB"):
            for name, color, lab in (("direct", DIRECT, "Direct"), ("shacl", SHACL, "SHACL"), ("delta", DELTA, "SHACL+$\\Delta$")):
                samples = samples_of(source.get(name) or {}, "mix_shared", "commit")
                cdf(ax, samples, lab, color)
        else:
            if fabric:
                for name, color, lab in (("direct", DIRECT, "Direct"), ("shacl", SHACL, "SHACL"), ("delta", DELTA, "SHACL+$\\Delta$")):
                    samples = samples_of((fabric.get("modes") or {}).get(name) or {}, "mix_shared", "commit")
                    cdf(ax, samples, lab, color)
        ax.set_xlabel("Commit latency (ms)")
        ax.set_ylabel("CDF")
        ax.set_title(title)
        ax.set_ylim(0, 1.02)
        ax.legend(frameon=False, loc="lower right")
    save(fig, "fig_cdf_shared_offer")


def fig_hits(bdb_modes, fabric):
    fig, axes = plt.subplots(1, 2, figsize=(9.2, 3.6))

    def bars(ax, title, rows):
        mixes = ["shared_ad", "mutating_ad", "disjoint"]
        x = np.arange(len(mixes))
        w = 0.25
        hits = []
        misses = []
        inv = []
        for mix in mixes:
            row = rows.get(mix) or {}
            stats = row.get("stats") or {}
            cache = stats.get("cache") if "cache" in stats else stats
            hits.append(cache.get("hits", 0) if isinstance(cache, dict) else 0)
            misses.append(cache.get("misses", 0) if isinstance(cache, dict) else 0)
            inv.append(cache.get("invalidations", 0) if isinstance(cache, dict) else 0)
        ax.bar(x - w, hits, width=w, label="hits", color=DELTA)
        ax.bar(x, misses, width=w, label="misses", color=SHACL)
        ax.bar(x + w, inv, width=w, label="invalidations", color="#E45756")
        ax.set_xticks(x)
        ax.set_xticklabels(["Shared ad", "Mutating ad", "Disjoint"])
        ax.set_ylabel("Count")
        ax.set_title(title)
        ax.legend(frameon=False)

    bdb_delta = bdb_modes.get("delta") or {}
    bars(
        axes[0],
        "SmartChainDB SHACL+$\\Delta$ cache",
        {
            "shared_ad": bdb_delta.get("mix_shared"),
            "mutating_ad": bdb_delta.get("mix_mutate"),
            "disjoint": bdb_delta.get("mix_disjoint"),
        },
    )
    fab_delta = ((fabric or {}).get("modes") or {}).get("delta") or {}
    bars(
        axes[1],
        "Fabric SHACL+$\\Delta$ cache",
        {
            "shared_ad": fab_delta.get("mix_shared"),
            "mutating_ad": fab_delta.get("mix_mutate"),
            "disjoint": fab_delta.get("mix_disjoint"),
        },
    )
    save(fig, "fig_hit_miss_invalidation")


def _abort_rate(blob):
    if not blob:
        return None
    rate = blob.get("abort_rate")
    if rate is not None:
        return 100.0 * rate
    attempted = blob.get("attempted") or blob.get("attempted_offers") or 0
    rejected = blob.get("rejected") or 0
    return 100.0 * rejected / float(attempted) if attempted else 0.0


def _stolen_rejected(blob):
    if not blob:
        return None
    fc = blob.get("fail_closed") or {}
    if "rejected" not in fc:
        return None
    return 100.0 if fc.get("rejected") else 0.0


def fig_abort(bdb_modes, fabric):
    fig, axes = plt.subplots(1, 2, figsize=(8.6, 3.6))
    rows = (
        ("Direct", bdb_modes.get("direct") or {}, DIRECT),
        ("SHACL", bdb_modes.get("shacl") or {}, SHACL),
        (r"SHACL+$\Delta$", bdb_modes.get("delta") or {}, DELTA),
        (r"Fabric $\Delta$", ((fabric or {}).get("modes") or {}).get("delta") or {}, MUTED),
    )
    labels, mutate, stolen, colors = [], [], [], []
    for plat, blob, color in rows:
        rate = _abort_rate(blob.get("mix_mutate"))
        if rate is None:
            continue
        labels.append(plat)
        mutate.append(rate)
        stolen_rate = _stolen_rejected(blob)
        stolen.append(stolen_rate if stolen_rate is not None else 0.0)
        colors.append(color)
    for ax, vals, title, ylabel in (
        (axes[0], mutate, "Offers after CLOSE (n=20, half after CLOSE)", "Reject rate (%)"),
        (axes[1], stolen, "Stolen advertisement", "Rejected (%)"),
    ):
        bars = ax.bar(labels, vals, color=colors, width=0.62)
        ax.set_ylabel(ylabel)
        ax.set_ylim(0, 115)
        ax.set_title(title)
        for bar, val in zip(bars, vals):
            ax.text(bar.get_x() + bar.get_width() / 2.0, val + 3, "{:.0f}%".format(val), ha="center", va="bottom", fontsize=8)
    save(fig, "fig_abort_rate")


def fig_load(bdb_modes, fabric):
    fig, axes = plt.subplots(1, 2, figsize=(9.2, 3.6))
    for ax, title, rows_by_mode in (
        (axes[0], "SmartChainDB 1-node saturation", bdb_modes),
        (axes[1], "Fabric test-network saturation", (fabric or {}).get("modes") or {}),
    ):
        for name, color, lab in (("direct", DIRECT, "Direct"), ("shacl", SHACL, "SHACL"), ("delta", DELTA, "SHACL+$\\Delta$")):
            load = (rows_by_mode.get(name) or {}).get("load") or []
            if not load:
                continue
            xs = [row["offered_tps"] for row in load]
            ys = [row["committed_tps"] for row in load]
            ax.plot(xs, ys, marker="o", label=lab, color=color)
        ax.set_xlabel("Offered load (tx/s)")
        ax.set_ylabel("Committed (tx/s)")
        ax.set_title(title)
        ax.legend(frameon=False)
    save(fig, "fig_saturation")


def fig_wan(bdb_wan, fabric_wan, bdb_delta, fabric_lan):
    fig, axes = plt.subplots(1, 2, figsize=(9.2, 3.6))
    cdf(axes[0], samples_of(bdb_delta or {}, "mix_shared", "commit"), "LAN Δ", DELTA)
    cdf(axes[0], samples_of(bdb_wan or {}, "mix_shared", "commit"), "WAN 40ms Δ", MUTED)
    axes[0].set_title("SmartChainDB shared-ad CDF")
    axes[0].set_xlabel("ms")
    axes[0].set_ylabel("CDF")
    axes[0].legend(frameon=False)
    fab_lan = ((fabric_lan or {}).get("modes") or {}).get("delta") or {}
    fab_wan = ((fabric_wan or {}).get("modes") or {}).get("delta") or {}
    cdf(axes[1], samples_of(fab_lan, "mix_shared", "commit"), "LAN Δ", DELTA)
    cdf(axes[1], samples_of(fab_wan, "mix_shared", "commit"), "WAN 40ms Δ", MUTED)
    axes[1].set_title("Fabric shared-ad CDF")
    axes[1].set_xlabel("ms")
    axes[1].legend(frameon=False)
    save(fig, "fig_wan_cdf")


def fig_cpu():
    path = os.path.join(RES, "cpu_bdb.csv")
    if not os.path.exists(path):
        return
    names = {}
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            parts = line.strip().split(",")
            if len(parts) < 2:
                continue
            name = parts[0]
            cpu = parts[1].replace("%", "")
            try:
                val = float(cpu)
            except ValueError:
                continue
            names.setdefault(name, []).append(val)
    if not names:
        return
    fig, ax = plt.subplots(figsize=(6.6, 3.4))
    for name, series in names.items():
        ax.plot(series, label=name.replace("smartchaindb-", ""))
    ax.set_xlabel("Sample (1 s)")
    ax.set_ylabel("CPU % (docker stats)")
    ax.set_title("Matcher / node CPU during BDB eval")
    ax.legend(frameon=False, fontsize=8)
    save(fig, "fig_cpu_bdb")


def main():
    os.makedirs(OUT, exist_ok=True)
    bdb_modes = {
        "direct": load("bdb_direct.json"),
        "shacl": load("bdb_shacl.json"),
        "delta": load("bdb_delta.json"),
    }
    fabric = load("fabric.json")
    bdb_wan = load("bdb_wan.json")
    fabric_wan = load("fabric_wan.json")
    fig_validation(bdb_modes.get("delta") or {}, fabric)
    fig_e2e(bdb_modes, fabric)
    fig_cdf_offers(bdb_modes, fabric)
    fig_hits(bdb_modes, fabric)
    fig_abort(bdb_modes, fabric)
    fig_load(bdb_modes, fabric)
    fig_wan(bdb_wan, fabric_wan, bdb_modes.get("delta"), fabric)
    fig_cpu()
    print("figures in", OUT)


if __name__ == "__main__":
    main()
