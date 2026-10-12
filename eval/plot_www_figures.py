#!/usr/bin/env python3
"""Paper figures for WWW: Direct vs SHACL vs SHACL+Δ.

Reads eval/www_results.json (replace after a new run) and writes PDF+PNG.
"""
from __future__ import print_function

import json
import os

import matplotlib.pyplot as plt
import numpy as np

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(ROOT, "www_results.json")
OUT = os.path.join(ROOT, "figures")

plt.rcParams.update(
    {
        "font.size": 10,
        "axes.titlesize": 11,
        "axes.labelsize": 10,
        "legend.fontsize": 9,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
        "axes.spines.top": False,
        "axes.spines.right": False,
    }
)

DIRECT = "#4C78A8"
SHACL = "#F58518"
DELTA = "#54A24B"
CHANGE = "#E45756"


def load():
    with open(DATA, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _err(row):
    return row["median"] - row["min"], row["max"] - row["median"]


def fig_validation(data):
    v = data["validation_layer_buy_offer_ms"]
    labels = ["Direct\n(RDF only)", "SHACL\n(HTTP miss)", "SHACL+$\\Delta$\n(cache hit)", "Value change\n(must miss)"]
    keys = ["direct_rdf", "shacl_http_miss", "shacl_delta_hit", "value_change_miss"]
    colors = [DIRECT, SHACL, DELTA, CHANGE]
    med = [v[k]["median"] for k in keys]
    low = [v[k]["median"] - v[k]["min"] for k in keys]
    high = [v[k]["max"] - v[k]["median"] for k in keys]

    fig, ax = plt.subplots(figsize=(6.2, 3.4))
    x = np.arange(len(labels))
    ax.bar(x, med, color=colors, width=0.62, yerr=[low, high], capsize=4, ecolor="#333333")
    ax.set_yscale("log")
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_ylabel("Validation time (ms, log)")
    ax.set_title("BUY_OFFER validation layer (n=7, live SHACL engine)")
    for i, val in enumerate(med):
        ax.text(i, val * 1.15, "{:.2f}".format(val), ha="center", va="bottom", fontsize=8)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "fig1_validation_layer.pdf"))
    fig.savefig(os.path.join(OUT, "fig1_validation_layer.png"), dpi=200)
    plt.close(fig)


def fig_e2e_total(data):
    e = data["e2e_lifecycle_ms"]
    totals = {
        "Direct": sum(e["direct"]),
        "SHACL": sum(e["shacl"]),
        "SHACL+$\\Delta$": sum(e["delta"]),
    }
    fig, ax = plt.subplots(figsize=(5.2, 3.2))
    names = list(totals.keys())
    vals = [totals[n] / 1000.0 for n in names]
    ax.bar(names, vals, color=[DIRECT, SHACL, DELTA], width=0.55)
    ax.set_ylabel("Full lifecycle (s)")
    ax.set_title("Marketplace E2E (CREATE$\\rightarrow$return, n=1)")
    for i, val in enumerate(vals):
        ax.text(i, val + 0.03, "{:.2f}s".format(val), ha="center", va="bottom", fontsize=9)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "fig2_e2e_total.pdf"))
    fig.savefig(os.path.join(OUT, "fig2_e2e_total.png"), dpi=200)
    plt.close(fig)


def fig_e2e_ops(data):
    e = data["e2e_lifecycle_ms"]
    ops = e["ops"]
    x = np.arange(len(ops))
    w = 0.26
    fig, ax = plt.subplots(figsize=(8.2, 3.6))
    ax.bar(x - w, e["direct"], width=w, label="Direct", color=DIRECT)
    ax.bar(x, e["shacl"], width=w, label="SHACL", color=SHACL)
    ax.bar(x + w, e["delta"], width=w, label="SHACL+$\\Delta$", color=DELTA)
    ax.set_xticks(x)
    ax.set_xticklabels(["CREATE", "ADV", "UPD", "OFFER", "SELL", "RET", "ACC"], rotation=0)
    ax.set_ylabel("Commit latency (ms)")
    ax.set_title("Per-operation E2E (n=1; consensus dominates)")
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "fig3_e2e_ops.pdf"))
    fig.savefig(os.path.join(OUT, "fig3_e2e_ops.png"), dpi=200)
    plt.close(fig)


def fig_where_time_goes(data):
    """BUY_OFFER: validation slice vs the rest of E2E (commit/network)."""
    v = data["validation_layer_buy_offer_ms"]
    e = data["e2e_lifecycle_ms"]
    # Linear lifecycle: first Δ BUY_OFFER is a miss. Do not invent a hit E2E bar.
    offer = [
        ("Direct", v["direct_rdf"]["median"], e["direct"][3]),
        ("SHACL", v["shacl_http_miss"]["median"], e["shacl"][3]),
        ("SHACL+$\\Delta$\n(first offer)", v["shacl_http_miss"]["median"], e["delta"][3]),
    ]
    labels = [row[0] for row in offer]
    val = [row[1] for row in offer]
    rest = [max(row[2] - row[1], 0) for row in offer]
    fig, ax = plt.subplots(figsize=(5.8, 3.4))
    x = np.arange(len(labels))
    ax.bar(x, val, label="Validation", color=SHACL)
    ax.bar(x, rest, bottom=val, label="Commit / network", color=DIRECT)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=9)
    ax.set_ylabel("BUY_OFFER time (ms)")
    ax.set_title("Where time goes: validation vs consensus")
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "fig4_where_time_goes.pdf"))
    fig.savefig(os.path.join(OUT, "fig4_where_time_goes.png"), dpi=200)
    plt.close(fig)


def main():
    os.makedirs(OUT, exist_ok=True)
    data = load()
    fig_validation(data)
    fig_e2e_total(data)
    fig_e2e_ops(data)
    fig_where_time_goes(data)
    print("wrote figures to", OUT)


if __name__ == "__main__":
    main()
