#!/usr/bin/env python3
"""Evaluation figures from eval/results JSON.

SmartChainDB: 4-validator DigitalOcean campaigns (LAN tag lan4c, WAN tag wan4).
Fabric: cloud run (fabric_cloud.json), falling back to the workstation run.
"""
from __future__ import print_function

import argparse
import csv
import glob
import json
import os

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Patch

ROOT = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(ROOT, "results")
OUT = os.path.join(ROOT, "figures")

DIRECT = "#4C78A8"
SHACL = "#F58518"
DELTA = "#54A24B"
MUTED = "#9D755D"
RED = "#E45756"

MODES = ("direct", "shacl", "delta")
COLORS = {"direct": DIRECT, "shacl": SHACL, "delta": DELTA}
PRETTY = {"direct": "Direct", "shacl": "SHACL", "delta": "SHACL+$\\Delta$"}
CONTAINERS = ("bdb", "tm", "mongo", "shacl")
CONTAINER_LABEL = {"bdb": "BigchainDB", "tm": "Tendermint", "mongo": "MongoDB", "shacl": "SHACL engine"}

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


def load(*parts):
    path = os.path.join(RES, *parts)
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def load_campaign(tag):
    return dict((m, load(tag, "bdb_%s_%s.json" % (tag, m)) or {}) for m in MODES)


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


def fabric_modes(fabric):
    return (fabric or {}).get("modes") or {}


def save(fig, name):
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, name + ".pdf"))
    fig.savefig(os.path.join(OUT, name + ".png"), dpi=200)
    plt.close(fig)
    print("wrote", name)


def cdf(ax, samples, label, color, style="-"):
    if not samples:
        return
    ordered = np.sort(np.array(samples, dtype=float))
    y = np.arange(1, len(ordered) + 1) / float(len(ordered))
    ax.step(ordered, y, where="post", label=label, color=color, linestyle=style)


def fig_validation(layer_bdb, layer_fab):
    fig, axes = plt.subplots(1, 2, figsize=(9.2, 3.4))
    panels = (("SmartChainDB", layer_bdb), ("Fabric", layer_fab))
    for ax, (title, layer) in zip(axes, panels):
        if not layer:
            ax.set_title(title + " (no data)")
            continue
        keys = ["direct_rdf", "shacl_http_miss", "shacl_delta_hit", "value_change_miss"]
        labels = ["Direct", "SHACL miss", "$\\Delta$ hit", "Value change"]
        colors = [DIRECT, SHACL, DELTA, RED]
        xs, meds, lows, highs, cols, labs, below = [], [], [], [], [], [], []
        for key, lab, col in zip(keys, labels, colors):
            row = layer.get(key)
            if not row:
                continue
            med = row.get("median") or (row.get("samples") or [0])[0]
            lo, hi = err_from(row)
            xs.append(len(xs))
            # Fabric timestamps have 1 ms resolution, so a hit records as 0.
            below.append(med <= 0)
            meds.append(1.0 if med <= 0 else med)
            lows.append(0 if med <= 0 else min(lo, med * 0.999))
            highs.append(0 if med <= 0 else hi)
            cols.append(col)
            labs.append(lab)
        bars = ax.bar(xs, meds, color=cols, yerr=[lows, highs], capsize=3, width=0.7)
        for bar, col, flag in zip(bars, cols, below):
            if flag:
                bar.set_facecolor("white")
                bar.set_edgecolor(col)
                bar.set_hatch("//")
                ax.text(bar.get_x() + bar.get_width() / 2.0, 1.15, "<1 ms", ha="center", va="bottom", fontsize=8)
        ax.set_yscale("log")
        ax.set_xticks(xs)
        ax.set_xticklabels(labs, rotation=20, ha="right")
        ax.set_title("{} validator".format(title))
        ax.set_ylabel("ms (log)")
        n = (layer.get("shacl_http_miss") or {}).get("n", "?")
        ax.text(0.02, 0.95, "n={}".format(n), transform=ax.transAxes, va="top")
    save(fig, "fig_validation_both")


def fig_e2e(lan, wan, fabric):
    fig, axes = plt.subplots(1, 2, figsize=(9.2, 3.4))
    ax = axes[0]
    width = 0.36
    for offset, campaign, label, hatch in ((-width / 2, lan, "LAN", ""), (width / 2, wan, "WAN", "//")):
        for i, mode in enumerate(MODES):
            row = ((campaign.get(mode) or {}).get("e2e") or {}).get("total")
            if not row:
                continue
            lo, hi = err_from(row)
            ax.bar(i + offset, row["median"] / 1000.0, width, color=COLORS[mode], hatch=hatch,
                   edgecolor="white" if not hatch else "black", linewidth=0.4,
                   yerr=[[lo / 1000.0], [hi / 1000.0]], capsize=3,
                   label=label if i == 0 else None)
    ax.set_xticks(range(len(MODES)))
    ax.set_xticklabels([PRETTY[m] for m in MODES])
    ax.set_ylabel("Full lifecycle (s)")
    ax.set_title("SmartChainDB, 4 validators (n=5)")
    ax.set_ylim(0, ax.get_ylim()[1] * 1.2)
    ax.legend(frameon=False, loc="upper center", ncol=2)

    ax = axes[1]
    xs = []
    for i, mode in enumerate(MODES):
        row = (fabric_modes(fabric).get(mode) or {}).get("e2e", {}).get("total")
        if not row:
            continue
        lo, hi = err_from(row)
        ax.bar(i, row["median"] / 1000.0, 0.55, color=COLORS[mode], yerr=[[lo / 1000.0], [hi / 1000.0]], capsize=3)
        xs.append(i)
    ax.set_xticks(range(len(MODES)))
    ax.set_xticklabels([PRETTY[m] for m in MODES])
    ax.set_ylabel("Full lifecycle (s)")
    ax.set_title("Fabric test-network (n=5)")
    save(fig, "fig_e2e_both")


OPS = (("CREATE", "Create"), ("ADVERTISEMENT", "Advertise"), ("UPDATE_ADV", "UpdateAdv"), ("BUY_OFFER", "BuyOffer"),
       ("SELL", "Sell"), ("REQUEST_RETURN", "ReqReturn"), ("SELLER_ACCEPT_RETURN", "AcceptReturn"))


def fig_ops(lan):
    fig, ax = plt.subplots(figsize=(9.2, 3.2))
    x = np.arange(len(OPS))
    w = 0.26
    for off, mode in zip((-w, 0, w), MODES):
        by_op = ((lan.get(mode) or {}).get("e2e") or {}).get("by_op") or {}
        meds = [(by_op.get(op) or {}).get("median", 0) for op, _ in OPS]
        ax.bar(x + off, meds, w, color=COLORS[mode], label=PRETTY[mode])
    ax.set_xticks(x)
    ax.set_xticklabels([lab for _, lab in OPS])
    ax.set_ylabel("Commit latency (ms)")
    ax.set_title("Per-operation commit latency, 4-validator LAN (median of 5 trials)")
    ax.legend(frameon=False, ncol=3, loc="lower right")
    save(fig, "fig3_e2e_ops")


def fig_cdf_offers(lan, fabric):
    fig, axes = plt.subplots(1, 2, figsize=(9.2, 3.6))
    for mode in MODES:
        cdf(axes[0], samples_of(lan.get(mode) or {}, "mix_shared", "commit"), PRETTY[mode], COLORS[mode])
        cdf(axes[1], samples_of(fabric_modes(fabric).get(mode) or {}, "mix_shared", "commit"), PRETTY[mode], COLORS[mode])
    for ax, title in ((axes[0], "SmartChainDB BuyOffer, shared ad (LAN)"), (axes[1], "Fabric BuyOffer, shared ad")):
        ax.set_xlabel("Commit latency (ms)")
        ax.set_ylabel("CDF")
        ax.set_title(title)
        ax.set_ylim(0, 1.02)
        ax.legend(frameon=False, loc="lower right")
    save(fig, "fig_cdf_shared_offer")


def _cache(blob, process):
    stats = (blob or {}).get("stats") or {}
    if process == "abci":
        stats = stats.get("abci") or {}
    cache = stats.get("cache") if "cache" in stats else stats
    return cache if isinstance(cache, dict) else {}


def fig_hits(lan, fabric):
    delta = lan.get("delta") or {}
    fab = fabric_modes(fabric).get("delta") or {}
    panels = (
        ("SmartChainDB HTTP process", delta, "web"),
        ("SmartChainDB consensus (ABCI)", delta, "abci"),
        ("Fabric client", fab, "web"),
    )
    mixes = (("mix_shared", "Shared"), ("mix_mutate", "Mutating"), ("mix_disjoint", "Disjoint"))
    fig, axes = plt.subplots(1, 3, figsize=(10.4, 3.4), sharey=True)
    x = np.arange(len(mixes))
    w = 0.26
    for ax, (title, blob, process) in zip(axes, panels):
        rows = [_cache(blob.get(key), process) for key, _ in mixes]
        for off, field, color in ((-w, "hits", DELTA), (0, "misses", SHACL), (w, "invalidations", RED)):
            vals = [r.get(field, 0) for r in rows]
            bars = ax.bar(x + off, vals, width=w, label=field, color=color)
            for bar, val in zip(bars, vals):
                ax.text(bar.get_x() + bar.get_width() / 2.0, val + 0.8, str(val), ha="center", fontsize=7)
        ax.set_xticks(x)
        ax.set_xticklabels([lab for _, lab in mixes])
        ax.set_title(title, fontsize=10)
    axes[0].set_ylabel("Count")
    axes[0].legend(frameon=False, loc="upper right", fontsize=8)
    save(fig, "fig_hit_miss_invalidation")


def _abort_rate(blob):
    if not blob:
        return None
    rate = blob.get("abort_rate")
    if rate is not None:
        return 100.0 * rate
    attempted = blob.get("attempted") or 0
    return 100.0 * (blob.get("rejected") or 0) / float(attempted) if attempted else 0.0


def fig_abort(lan, fabric):
    fig, axes = plt.subplots(1, 2, figsize=(8.6, 3.6))
    rows = [(PRETTY[m], lan.get(m) or {}, COLORS[m]) for m in MODES]
    rows.append(("Fabric $\\Delta$", fabric_modes(fabric).get("delta") or {}, MUTED))
    labels, mutate, stolen, colors = [], [], [], []
    for plat, blob, color in rows:
        rate = _abort_rate(blob.get("mix_mutate"))
        if rate is None:
            continue
        labels.append(plat)
        mutate.append(rate)
        stolen.append(100.0 if (blob.get("fail_closed") or {}).get("rejected") else 0.0)
        colors.append(color)
    for ax, vals, title, ylabel in (
        (axes[0], mutate, "Offers after CLOSE (n=20, half after)", "Reject rate (%)"),
        (axes[1], stolen, "Stolen advertisement", "Rejected (%)"),
    ):
        bars = ax.bar(labels, vals, color=colors, width=0.62)
        ax.set_ylabel(ylabel)
        ax.set_ylim(0, 115)
        ax.set_title(title)
        for bar, val in zip(bars, vals):
            ax.text(bar.get_x() + bar.get_width() / 2.0, val + 3, "{:.0f}%".format(val), ha="center", va="bottom", fontsize=8)
    save(fig, "fig_abort_rate")


def fig_load(lan, wan, fabric):
    fig, axes = plt.subplots(1, 2, figsize=(9.2, 3.6))
    for campaign, style, tag in ((lan, "-", "LAN"), (wan, "--", "WAN")):
        for mode in MODES:
            rows = (campaign.get(mode) or {}).get("load") or []
            if rows:
                axes[0].plot([r["concurrency"] for r in rows], [r["committed_tps"] for r in rows], marker="o",
                             linestyle=style, color=COLORS[mode], label="{} {}".format(PRETTY[mode], tag))
    for mode in MODES:
        rows = (fabric_modes(fabric).get(mode) or {}).get("load") or []
        if rows:
            axes[1].plot([r.get("concurrency", r.get("c")) for r in rows], [r["committed_tps"] for r in rows],
                         marker="o", color=COLORS[mode], label=PRETTY[mode])
    axes[0].set_title("SmartChainDB, 4 validators")
    axes[1].set_title("Fabric test-network")
    for ax in axes:
        ax.set_xlabel("Concurrent issuers $C$")
        ax.set_ylabel("Committed (tx/s)")
        ax.set_xscale("log", base=2)
        ax.set_xticks([1, 2, 4, 8])
        ax.set_xticklabels(["1", "2", "4", "8"])
        ax.set_ylim(bottom=0)
        ax.legend(frameon=False, fontsize=7)
    save(fig, "fig_saturation")


def fig_wan(lan, wan):
    fig, ax = plt.subplots(figsize=(5.6, 3.4))
    for mode in MODES:
        cdf(ax, samples_of(lan.get(mode) or {}, "mix_shared", "commit"), PRETTY[mode] + " LAN", COLORS[mode], "-")
        cdf(ax, samples_of(wan.get(mode) or {}, "mix_shared", "commit"), PRETTY[mode] + " WAN", COLORS[mode], "--")
    ax.set_xlabel("Commit latency (ms)")
    ax.set_ylabel("CDF")
    ax.set_ylim(0, 1.02)
    ax.set_title("SmartChainDB shared-ad BuyOffer, LAN vs WAN")
    ax.legend(frameon=False, fontsize=7, loc="lower right")
    save(fig, "fig_wan_cdf")


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
    fig, ax = plt.subplots(figsize=(6.6, 3.4))
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
    ax.set_title("Per-validator container CPU, 4-validator LAN")
    ax.legend(frameon=False)
    save(fig, "fig_cpu_bdb")


def validation_split(campaign, layer):
    """Per committed shared-ad BuyOffer on the receiving validator: HTTP admission,
    CheckTx and DeliverTx each validate once. Under SHACL+Delta the HTTP call hits
    (the driver pre-validated the offer), CheckTx misses and DeliverTx hits."""
    direct = (layer.get("direct_rdf") or {}).get("median", 0.0)
    miss = (layer.get("shacl_http_miss") or {}).get("median", 0.0)
    hit = (layer.get("shacl_delta_hit") or {}).get("median", 0.0)
    cost = {"direct": 3 * direct, "shacl": 3 * miss, "delta": miss + 2 * hit}
    out = {}
    for mode in MODES:
        commit = ((campaign.get(mode) or {}).get("mix_shared") or {}).get("commit") or {}
        if commit.get("median"):
            out[mode] = (cost[mode], commit["median"] - cost[mode])
    return out


def fig_where(lan, wan, layer_lan, layer_wan):
    fig, ax = plt.subplots(figsize=(6.6, 3.4))
    labels, val, rest, cols = [], [], [], []
    for name, campaign, layer in (("LAN", lan, layer_lan), ("WAN", wan, layer_wan or layer_lan)):
        split = validation_split(campaign, layer)
        for mode in MODES:
            if mode not in split:
                continue
            labels.append("{}\n{}".format(PRETTY[mode], name))
            val.append(split[mode][0])
            rest.append(split[mode][1])
            cols.append(COLORS[mode])
    if not labels:
        plt.close(fig)
        return
    x = np.arange(len(labels))
    ax.bar(x, rest, 0.6, color="#BAB0AC", label="Consensus, gossip, HTTP")
    ax.bar(x, val, 0.6, bottom=rest, color=cols, label="Validation (estimated)")
    for i in range(len(labels)):
        share = 100.0 * val[i] / (val[i] + rest[i])
        ax.text(x[i], val[i] + rest[i] + 15, "{:.1f}%".format(share), ha="center", fontsize=8)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=8)
    ax.set_ylabel("Median commit latency (ms)")
    ax.set_ylim(0, 1.3 * max(v + r for v, r in zip(val, rest)))
    ax.set_title("Where a shared-ad BuyOffer spends its time")
    handles = [
        Patch(facecolor="#BAB0AC", label="Consensus, gossip, HTTP"),
        Patch(facecolor="white", edgecolor="black", label="Validation (estimated; colour = treatment)"),
    ]
    ax.legend(handles=handles, frameon=False, fontsize=8, loc="upper left", ncol=2)
    save(fig, "fig4_where_time_goes")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--lan", default="lan4c")
    parser.add_argument("--wan", default="wan4")
    args = parser.parse_args()
    os.makedirs(OUT, exist_ok=True)
    lan = load_campaign(args.lan)
    wan = load_campaign(args.wan)
    fabric = load("fabric_cloud.json") or load("fabric.json")
    layer_bdb = (load(args.lan, "bdb_%s_delta_val.json" % args.lan) or {}).get("validation_layer") or {}
    layer_fab = (fabric or {}).get("validation_layer") or {}
    fig_validation(layer_bdb, layer_fab)
    fig_e2e(lan, wan, fabric)
    fig_ops(lan)
    fig_cdf_offers(lan, fabric)
    fig_hits(lan, fabric)
    fig_abort(lan, fabric)
    fig_load(lan, wan, fabric)
    fig_wan(lan, wan)
    fig_cpu(args.lan)
    layer_wan = (load(args.wan, "bdb_%s_delta_val.json" % args.wan) or {}).get("validation_layer") or {}
    fig_where(lan, wan, layer_bdb, layer_wan)
    print("figures in", OUT)


if __name__ == "__main__":
    main()
