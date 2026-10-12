#!/usr/bin/env python3
"""Build the evaluation-section PDF in the CIKM manuscript register.

Mirrors eval/paper/evaluation.tex (Times, numbered subsections, run-in
subsubsection titles, bold run-in topic labels, short captions).
"""
from __future__ import print_function

import os

from fpdf import FPDF

HERE = os.path.dirname(os.path.abspath(__file__))
FIG = os.path.abspath(os.path.join(HERE, "..", "figures"))
OUT = os.path.join(HERE, "evaluation.pdf")

LEAD = 5.0
SIZE = 10.5


class Paper(FPDF):
    def header(self):
        if self.page_no() == 1:
            return
        self.set_font("Times", "I", 9)
        self.set_text_color(80, 80, 80)
        self.cell(0, 6, "Knowledge-Aware Blockchain Transaction Validation with SHACL  |  Evaluation (WWW 2027 draft)", align="C")
        self.ln(4)
        self.set_draw_color(160, 160, 160)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(3)
        self.set_text_color(0, 0, 0)

    def footer(self):
        self.set_y(-14)
        self.set_font("Times", "I", 9)
        self.set_text_color(80, 80, 80)
        self.cell(0, 8, str(self.page_no()), align="C")
        self.set_text_color(0, 0, 0)


def body(pdf, text):
    pdf.set_font("Times", "", SIZE)
    pdf.set_text_color(0, 0, 0)
    pdf.multi_cell(0, LEAD, text)
    pdf.ln(1.4)


def runin(pdf, label, text):
    """Bold run-in label followed by normal text in the same paragraph."""
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Times", "B", SIZE)
    pdf.write(LEAD, label + " ")
    pdf.set_font("Times", "", SIZE)
    pdf.write(LEAD, text)
    pdf.ln(LEAD + 1.4)


def section(pdf, number, title):
    pdf.ln(3)
    if pdf.get_y() > pdf.h - pdf.b_margin - 30:
        pdf.add_page()
    pdf.set_font("Times", "B", 13)
    pdf.multi_cell(0, 7, "{}  {}".format(number, title))
    pdf.ln(1.5)


def subsection(pdf, number, title):
    pdf.ln(1.5)
    if pdf.get_y() > pdf.h - pdf.b_margin - 24:
        pdf.add_page()
    pdf.set_font("Times", "B", 11.5)
    pdf.multi_cell(0, 6, "{}  {}".format(number, title))
    pdf.ln(0.8)


def subsubsection(pdf, number, title, text):
    """Numbered italic run-in title (ACM style) followed by the paragraph."""
    pdf.ln(0.6)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Times", "I", SIZE)
    pdf.write(LEAD, "{}  {}.  ".format(number, title))
    pdf.set_font("Times", "", SIZE)
    pdf.write(LEAD, text)
    pdf.ln(LEAD + 1.4)


def fig(pdf, filename, caption, max_h=90):
    path = os.path.join(FIG, filename)
    if not os.path.exists(path):
        body(pdf, "[Missing figure: {}]".format(filename))
        return
    if pdf.get_y() > pdf.h - pdf.b_margin - max_h - 20:
        pdf.add_page()
    pdf.image(path, w=pdf.epw)
    pdf.ln(1)
    pdf.set_font("Times", "B", 9)
    label, _, rest = caption.partition(":")
    pdf.write(4.2, label + ":")
    pdf.set_font("Times", "", 9)
    pdf.write(4.2, rest)
    pdf.ln(6.5)


def table(pdf, headers, rows, col_w=None, caption=None):
    n = len(headers)
    if col_w is None:
        col_w = [pdf.epw / n] * n
    row_h = 6.0
    need = row_h * (len(rows) + 2) + 10
    if pdf.get_y() + need > pdf.h - pdf.b_margin:
        pdf.add_page()
    if caption:
        pdf.set_font("Times", "B", 9)
        label, _, rest = caption.partition(":")
        pdf.write(4.2, label + ":")
        pdf.set_font("Times", "", 9)
        pdf.write(4.2, rest)
        pdf.ln(5.5)
    pdf.set_font("Times", "B", 8.5)
    pdf.set_fill_color(240, 240, 240)
    for i, h in enumerate(headers):
        pdf.cell(col_w[i], row_h, h, border=1, fill=True, align="C")
    pdf.ln(row_h)
    pdf.set_font("Times", "", 8.5)
    for r, row in enumerate(rows):
        fill = r % 2 == 1
        if fill:
            pdf.set_fill_color(248, 248, 248)
        for i, cell in enumerate(row):
            pdf.cell(col_w[i], row_h, str(cell), border=1, fill=fill, align="C" if i else "L")
        pdf.ln(row_h)
    pdf.ln(3)


def build():
    pdf = Paper(format="A4", unit="mm")
    pdf.set_margins(18, 16, 18)
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()

    pdf.set_font("Times", "B", 16)
    pdf.multi_cell(0, 8, "Knowledge-Aware Blockchain Transaction Validation with SHACL: Evaluation Section", align="C")
    pdf.ln(1)
    pdf.set_font("Times", "I", 11)
    pdf.multi_cell(0, 5.5, "WWW 2027 draft  |  latency and load measured 7 Oct 2026; fail-closed re-measured 10 Oct 2026", align="C")
    pdf.ln(4)

    # ------------------------------------------------------------------ 5
    section(pdf, "5", "Evaluation")

    subsection(pdf, "5.1", "Evaluation Objectives and Scope")
    body(
        pdf,
        "Our evaluation addresses whether declarative specifications of marketplace validation semantics can "
        "be enforced on the commit path of a permissioned ledger at a cost that is small relative to consensus, "
        "while remaining authoritative when the blockchain state those specifications depend upon changes. We "
        "specifically evaluate trade-offs between (1) imperative validation, where ownership, "
        "advertisement-status, and offer-linkage rules are embedded in engine code, and (2) declarative SHACL "
        "constraints, where the same rules are explicit, inspectable, and amenable to dependency-aware "
        "re-validation.",
    )
    runin(
        pdf,
        "Evaluation criteria.",
        "Given the inherent declarative overhead (RDF materialization, HTTP invocation of the constraint engine, "
        "and graph evaluation), we consider parity with the imperative Direct baseline within the "
        "consensus-dominated latency envelope a success, as the value proposition extends beyond validation "
        "speed to include: (1) inspectability and portability of the constraints themselves, (2) "
        "dependency-aware re-validation in which cached verdicts are reused only while the referenced state is "
        "unchanged, and (3) fail-closed rejection of semantically invalid transactions. We compare Direct, "
        "SHACL, and SHACL+Delta within SmartChainDB (BigchainDB on Tendermint) to isolate the impact of the "
        "validation paradigm from consensus differences, and we port the same shapes and treatments to "
        "Hyperledger Fabric 2.5 to assess whether the observed behavior is specific to one engine.",
    )
    body(
        pdf,
        "The focus of our evaluation is not overall system throughput, as ledger throughput depends on "
        "consensus protocol, block parameters, network topology, and storage backend, which are outside our "
        "scope. Rather, we aim to understand the impact of the validation paradigm on per-transaction cost, on "
        "the commit-path latency envelope, and on correctness under state change. We therefore report "
        "within-engine comparisons and interpret the Fabric panel as a portability reference rather than as a "
        "cross-platform ranking.",
    )
    body(pdf, "Our evaluation addresses four research questions:")
    runin(
        pdf,
        "RQ1: Declarative overhead and differential re-validation.",
        "What is the per-transaction validation cost of SHACL relative to Direct, and under what conditions "
        "does SHACL+Delta reuse a cached verdict rather than re-executing constraint evaluation?",
    )
    runin(
        pdf,
        "RQ2: End-to-end impact.",
        "How do the three approaches compare in committed lifecycle latency, in the commit-latency "
        "distribution of contended offers, and in achieved throughput under closed-loop load, and what "
        "fraction of end-to-end time is attributable to validation?",
    )
    runin(
        pdf,
        "RQ3: Fail-closed correctness.",
        "Do SHACL and SHACL+Delta reject semantically invalid transactions (advertisements by a non-owner, "
        "offers against a closed advertisement) with the same outcomes as Direct, and does verdict caching "
        "preserve those outcomes when the referenced state changes?",
    )
    runin(
        pdf,
        "RQ4: Portability.",
        "Do the same shapes and treatments exhibit the same qualitative behavior on Hyperledger Fabric, whose "
        "execute-order-validate pipeline differs from Tendermint's order-execute model?",
    )

    subsection(pdf, "5.2", "Experimental Setup")
    subsubsection(
        pdf,
        "5.2.1",
        "Hardware and Environment",
        "All experiments were conducted on a single workstation running WSL2 with Docker Engine 27.5.1. "
        "Latency and load experiments use one SmartChainDB validator (Tendermint v0.31.5, MongoDB 3.6, one "
        "gunicorn worker) together with the SHACL constraint engine as a sidecar container. Fail-closed "
        "experiments were re-run on a four-validator LAN deployment (four Tendermint voting keys, four "
        "MongoDB/SHACL/BigchainDB replicas, full mesh with n_peers=3). The Fabric deployment is the 2.5.12 "
        "test-network with two endorsing peers (one per organization), a single orderer, and Go marketplace "
        "chaincode. Table 1 summarizes the configurations.",
    )
    table(
        pdf,
        ["Engine", "Topology", "Validation path"],
        [
            ["SmartChainDB", "1 validator (latency, load); 4 validators (fail-closed)", "HTTP -> Direct/SHACL -> CheckTx/DeliverTx"],
            ["Fabric 2.5.12", "2 peers, 1 orderer", "client reads world state -> SHACL -> endorse/order/commit"],
        ],
        col_w=[34, 70, 70],
        caption="Table 1: Deployments under test.",
    )
    subsubsection(
        pdf,
        "5.2.2",
        "Implementations",
        "We evaluate three implementations of identical marketplace transaction semantics on each engine.",
    )
    runin(
        pdf,
        "Direct:",
        "Imperative validation integrated in the engine (server-side Python methods in SmartChainDB; Go "
        "chaincode with MVCC version checks on Fabric). Validation logic is implemented procedurally within the "
        "platform rather than as declarative constraints. This serves as the baseline against which declarative "
        "overhead is measured.",
    )
    runin(
        pdf,
        "SHACL:",
        "Declarative validation without optimization. Each transaction is converted to RDF, merged with the "
        "referenced blockchain state (asset ownership, effective advertisement status, offer linkage), and "
        "validated against the shape repository over HTTP. Validation results are not cached; every validation "
        "phase re-executes constraint evaluation. The engine is fail-closed: a constraint violation or an "
        "unreachable engine rejects the transaction.",
    )
    runin(
        pdf,
        "SHACL+Delta:",
        "SHACL validation with differential re-validation. Verdicts are cached under the key (tx-id, "
        "dependency-state hash), where the hash is computed over the values of the referenced entities "
        "(current owner, effective advertisement status, offer state). A cached verdict is reused only if the "
        "recomputed hash matches; committed transactions invalidate reverse-indexed entries; and a conflict "
        "tracker may abort an in-flight validation if a dependency generation advances during the HTTP "
        "round-trip.",
    )
    body(
        pdf,
        "All three treatments share the same client, the same transaction types, and the same state transitions "
        "on a given engine, differing only in how validation is specified and executed. On Fabric, SHACL and "
        "SHACL+Delta are evaluated in the client before endorsement, and the Delta variant issues a second "
        "SHACL call against the same facts to emulate the re-validation that Tendermint performs natively in "
        "CheckTx.",
    )
    subsubsection(pdf, "5.2.3", "Workload Design", "")
    runin(
        pdf,
        "Goals.",
        "(1) Exercise the end-to-end dependency structure among transaction types (owner -> advertisement -> "
        "offer -> sale -> return); (2) control the position at which referenced state changes so that cache "
        "reuse, invalidation, and rejection can be attributed to specific operations; (3) support both "
        "validator-only timing and committed end-to-end timing; (4) support closed-loop load at several "
        "concurrency levels.",
    )
    runin(
        pdf,
        "Transaction universe.",
        "The framework supports seven marketplace transaction types (Create, Advertise, UpdateAdv, BuyOffer, "
        "Sell, RequestReturn, AcceptReturn). The full lifecycle experiment exercises all seven; the contention "
        "mixes and the load experiment use the Create, Advertise, UpdateAdv, and BuyOffer subset, which covers "
        "the dependency patterns central to SHACL+Delta: asset creation, ownership checks, advertisement "
        "status, and offer linkage.",
    )

    subsection(pdf, "5.3", "Workloads and Settings")
    runin(
        pdf,
        "Datasets.",
        "There is no public marketplace trace that carries the constraints under test; public token traces do "
        "not encode \"open advertisement\" or \"at most one return.\" We therefore use a synthetic generator that "
        "already exists on both backends. Each treatment commits on the order of 220 transactions (Table 2); "
        "across Direct, SHACL, and SHACL+Delta, SmartChainDB commits ~670 marketplace transactions and Fabric "
        "repeats the same mixes (~600 invokes).",
    )
    runin(
        pdf,
        "Mixes.",
        "Shared ad: one OPEN advertisement and n=20 BuyOffers against it (identical referenced facts, distinct "
        "tx-ids). Mutating ad: n/2 BuyOffers, then UpdateAdv to CLOSED, then n/2 further BuyOffers, so that "
        "the second half must be rejected. Disjoint: n=20 independent Create+Advertise+BuyOffer chains as a "
        "control with no shared state.",
    )
    runin(
        pdf,
        "Probes.",
        "A stolen-advertisement probe submits an Advertise whose advertiser is not among the Create owners. A "
        "conflict probe submits 12 concurrent BuyOffers while an UpdateAdv to CLOSED races them, exercising "
        "the conflict tracker.",
    )
    runin(
        pdf,
        "Validator microbenchmark.",
        "To isolate validation cost from consensus, one pending BuyOffer against a live OPEN advertisement is "
        "validated n=20 times in-process under each treatment, after which the advertisement is updated and "
        "the same offer is validated once more. These checks do not commit additional ledger transactions.",
    )
    runin(
        pdf,
        "Load.",
        "Closed-loop issuers post N=16 BuyOffers against one OPEN advertisement at concurrency C in "
        "{1,2,4,8}; offered and achieved rates are N divided by wall-clock time.",
    )
    runin(
        pdf,
        "Clusters.",
        "One validator for latency and load; four validators for fail-closed. Block parameters are held "
        "constant across treatments.",
    )
    runin(
        pdf,
        "Reported metrics.",
        "Validator latency (median, p95); committed latency (median, p95, min, max) and CDFs; cache hits, "
        "misses, and invalidations; reject rate; offered versus achieved throughput; and container CPU from "
        "docker stats.",
    )
    table(
        pdf,
        ["Experiment", "Ledger txs", "Repeats"],
        [
            ["Validator setup (Create+Advertise)", "2", "20 checks of one offer"],
            ["Full lifecycle", "5 x 7 = 35", "n=5 trials"],
            ["Shared ad", "2 + 20 = 22", "---"],
            ["Mutating ad", "23 posted", "10 expected rejects"],
            ["Disjoint", "20 x 3 = 60", "---"],
            ["Stolen-ad probe", "3 posted", "1 reject"],
            ["Conflict probe", "<= 15", "12 concurrent offers"],
            ["Load", "2 + 4 x 16 = 66", "C in {1,2,4,8}"],
            ["Approx. per treatment", "~223", "---"],
        ],
        col_w=[78, 40, 56],
        caption="Table 2: Committed marketplace transactions per treatment (SmartChainDB). The validator microbenchmark is in-process and excluded.",
    )

    # ------------------------------------------------------------ 5.4
    subsection(pdf, "5.4", "Experiment 1: Validation Cost and Differential Re-validation")
    subsubsection(
        pdf,
        "5.4.1",
        "Methodology",
        "We measure the validator alone, starting the clock when RDF conversion or SHACL evaluation begins and "
        "stopping it when the verdict is returned, so that Tendermint and Fabric commit paths are excluded. We "
        "then run the three contention mixes on the live ledger and record the SHACL+Delta cache counters after "
        "each mix.",
    )
    subsubsection(
        pdf,
        "5.4.2",
        "Results: Validation Latency",
        "Fig. 1 plots validator latency for the four conditions on a logarithmic axis, and Table 3 reports the "
        "summary statistics. On SmartChainDB, Direct RDF conversion takes 0.23 ms (median; p95 0.49 ms), a "
        "SHACL miss takes 13.3 ms (median; p95 57.1 ms), and a SHACL+Delta hit takes 0.007 ms. After the "
        "referenced advertisement is updated, the next validation of the same pending offer misses and takes "
        "12.3 ms. Fabric exhibits the same ordering at a higher base cost: a miss takes 26 ms, a hit under 1 ms, "
        "and a post-update miss 25 ms.",
    )
    fig(pdf, "fig_validation_both.png", "Figure 1: Validator latency for one pending BuyOffer (n=20).", max_h=86)
    table(
        pdf,
        ["Condition", "n", "Median", "p95", "Max"],
        [
            ["SmartChainDB Direct (RDF)", "20", "0.23", "0.49", "0.57"],
            ["SmartChainDB SHACL miss", "20", "13.3", "57.1", "84.7"],
            ["SmartChainDB SHACL+Delta hit", "20", "0.007", "0.008", "0.009"],
            ["SmartChainDB value-change miss", "1", "12.3", "---", "---"],
            ["Fabric SHACL miss", "20", "26", "35", "36"],
            ["Fabric SHACL+Delta hit", "20", "<1", "<1", "<1"],
            ["Fabric value-change miss", "1", "25", "---", "---"],
        ],
        col_w=[70, 18, 30, 28, 28],
        caption="Table 3: Validator latency for BuyOffer (ms).",
    )
    runin(
        pdf,
        "Overhead patterns.",
        "The SHACL miss cost is dominated by fixed components (HTTP invocation, shape loading, and graph "
        "evaluation) rather than by the size of the transaction, which is why the median is stable at ~13 ms "
        "while the tail reflects cold-engine effects on the first requests. The SHACL+Delta hit is a hash lookup "
        "on the dependency-state key and does not invoke the engine, which accounts for the three "
        "orders-of-magnitude gap between hit and miss. The post-update miss is the behavior the design requires: "
        "because the cache key is computed over the values of the referenced entities, an UpdateAdv changes the "
        "key, and the stale verdict cannot be reused. Fabric's higher miss cost reflects an additional process "
        "boundary on the endorse path rather than a different rule set.",
    )
    subsubsection(
        pdf,
        "5.4.3",
        "Results: Cache Events Across Mixes",
        "Fig. 2 reports hits, misses, and invalidations for each mix. On SmartChainDB, the shared, mutating, "
        "and disjoint mixes record 20, 21, and 36 misses respectively and no hits. This is a consequence of the "
        "cache key rather than of cache failure: every committed BuyOffer carries a fresh tx-id, so a stream of "
        "distinct offers cannot hit even when they reference identical state. Hits arise in the validator "
        "microbenchmark, where the same pending transaction is re-validated, which is the pattern that CheckTx "
        "and the mempool produce in practice. The disjoint mix records more misses than offers because each "
        "independent advertisement contributes referenced state that is also hashed.",
    )
    fig(pdf, "fig_hit_miss_invalidation.png", "Figure 2: SHACL+Delta cache events by mix.", max_h=82)
    body(
        pdf,
        "On Fabric, where the client issues a second SHACL call against the same facts before endorsement, the "
        "shared and disjoint mixes record hits (20 and 20), and the mutating mix records invalidations when the "
        "advertisement is updated. The two panels therefore reflect the same re-validation rule under different "
        "call patterns, and should not be read as the cache succeeding on one engine and failing on the other.",
    )

    # ------------------------------------------------------------ 5.5
    subsection(pdf, "5.5", "Experiment 2: End-to-End Latency and Load")
    subsubsection(
        pdf,
        "5.5.1",
        "Methodology",
        "We execute the full seven-operation lifecycle on the live ledger (n=5 trials per treatment), record the "
        "commit-latency distribution of the shared-advertisement mix, and drive closed-loop load at C in "
        "{1,2,4,8}. For one trial we additionally decompose each BuyOffer into validation time and "
        "commit/network time.",
    )
    subsubsection(
        pdf,
        "5.5.2",
        "Results: Full Lifecycle",
        "Fig. 3 and Table 4 report the committed lifecycle. SmartChainDB medians are 1.55 s (Direct), 1.79 s "
        "(SHACL), and 2.48 s (SHACL+Delta); Fabric medians are 14.5 s, 14.9 s, and 15.3 s. Across approaches, "
        "the three treatments occupy the same latency band on each engine, and the gap between engines (roughly "
        "an order of magnitude) is attributable to Fabric's endorse-order-commit pipeline rather than to "
        "validation. The per-operation decomposition (Figs. 4-5) places the SHACL slice at ~16 ms on a ~250 ms "
        "SmartChainDB commit, so validation accounts for a few percent of end-to-end time.",
    )
    fig(pdf, "fig_e2e_both.png", "Figure 3: Full marketplace lifecycle (n=5; whiskers are min-max).", max_h=80)
    table(
        pdf,
        ["Engine / treatment", "Median", "Mean", "Min", "Max"],
        [
            ["SmartChainDB Direct", "1.55", "1.82", "1.33", "2.94"],
            ["SmartChainDB SHACL", "1.79", "1.82", "1.50", "2.23"],
            ["SmartChainDB SHACL+Delta", "2.48", "2.57", "1.51", "3.70"],
            ["Fabric Direct", "14.47", "14.47", "14.40", "14.58"],
            ["Fabric SHACL", "14.90", "14.88", "14.75", "14.99"],
            ["Fabric SHACL+Delta", "15.26", "15.34", "14.91", "15.87"],
        ],
        col_w=[62, 28, 28, 28, 28],
        caption="Table 4: Full lifecycle, Create through AcceptReturn (s).",
    )
    fig(pdf, "fig3_e2e_ops.png", "Figure 4: Per-operation commit latency, SmartChainDB (one trial).", max_h=76)
    fig(pdf, "fig4_where_time_goes.png", "Figure 5: BuyOffer time decomposed into validation and commit/network.", max_h=76)
    runin(
        pdf,
        "Why Delta does not shorten the lifecycle.",
        "Each of the seven operations is a distinct transaction with a distinct tx-id, so the cache is cold at "
        "every commit and SHACL+Delta pays the full miss cost plus cache bookkeeping. SHACL+Delta therefore "
        "shows the highest SmartChainDB median and the widest min-max range in this experiment; with n=5 trials "
        "and a ~13 ms matcher on a consensus-dominated path, we do not interpret the difference as a property "
        "of the mechanism. The experiment establishes the envelope within which validation operates and "
        "confirms that differential re-validation is a validator-level optimization rather than a "
        "consensus-level one.",
    )
    subsubsection(
        pdf,
        "5.5.3",
        "Results: Shared-Advertisement Commit Distribution",
        "Fig. 6 and Table 5 show the commit-latency CDF for n=20 BuyOffers against a single OPEN advertisement. "
        "SmartChainDB medians are 179 ms (Direct), 226 ms (SHACL), and 222 ms (SHACL+Delta); Fabric medians lie "
        "between 2.06 and 2.13 s across treatments.",
    )
    fig(pdf, "fig_cdf_shared_offer.png", "Figure 6: Commit-latency CDF, shared-advertisement mix (n=20).", max_h=80)
    table(
        pdf,
        ["Treatment", "SCDB median", "SCDB p95", "Fabric median", "Fabric p95"],
        [
            ["Direct", "179", "215", "2064", "2081"],
            ["SHACL", "226", "323", "2109", "2177"],
            ["SHACL+Delta", "222", "400", "2128", "2197"],
        ],
        col_w=[40, 34, 30, 40, 30],
        caption="Table 5: Shared-advertisement BuyOffer commit latency (ms).",
    )
    body(
        pdf,
        "The ~47 ms separation between Direct and the two SHACL treatments on SmartChainDB is the declarative "
        "overhead of Section 5.4 appearing on the commit path; because the offers carry distinct tx-ids, "
        "SHACL+Delta tracks SHACL rather than Direct. The distributions overlap through the body and diverge "
        "only in the tail (SHACL+Delta p95 of 400 ms), which we attribute to HTTP jitter and retry behavior "
        "rather than to the validation algorithm. On Fabric the treatments are indistinguishable at commit, "
        "since endorsement collection dominates the ~26 ms matcher call. The mix thus characterizes the latency "
        "class of the marketplace under each treatment rather than cache effectiveness.",
    )
    subsubsection(
        pdf,
        "5.5.4",
        "Results: Offered versus Achieved Throughput",
        "Fig. 7 and Table 6 plot achieved throughput against concurrency. SmartChainDB sustains ~3.7-4.6 tx/s "
        "from C=1 to C=8 under all treatments, whereas Fabric scales with concurrency: Direct from 0.48 to "
        "3.35 tx/s, SHACL from 0.48 to 2.64 tx/s, and SHACL+Delta from 0.47 to 3.40 tx/s.",
    )
    fig(pdf, "fig_saturation.png", "Figure 7: Offered versus achieved BuyOffer rate, one validator.", max_h=80)
    table(
        pdf,
        ["Treatment", "C=1", "C=2", "C=4", "C=8"],
        [
            ["SmartChainDB (all treatments)", "~3.7", "~4.1", "~4.5", "~4.6"],
            ["Fabric Direct", "0.48", "0.95", "1.83", "3.35"],
            ["Fabric SHACL", "0.48", "0.93", "1.71", "2.64"],
            ["Fabric SHACL+Delta", "0.47", "0.91", "1.77", "3.40"],
        ],
        col_w=[62, 28, 28, 28, 28],
        caption="Table 6: Achieved BuyOffer rate (tx/s) at concurrency C.",
    )
    fig(pdf, "fig_cpu_bdb.png", "Figure 8: Container CPU during the SmartChainDB campaign (1 s samples).", max_h=76)
    runin(
        pdf,
        "Capacity patterns.",
        "SmartChainDB is flat in C because the client submits through broadcast_tx_commit, which blocks each "
        "issuer until its transaction is included in a block; the plateau therefore reflects Tendermint's block "
        "rate on this host rather than validation cost, and the treatments are indistinguishable. Fabric scales "
        "because independent endorsements overlap at the peers. The SHACL treatment on Fabric falls below Direct "
        "at C=8 (2.64 versus 3.35 tx/s) once concurrency exposes the matcher on the endorse path, and "
        "SHACL+Delta recovers to 3.40 tx/s, consistent with hits on the second SHACL call. At C=4-8 the Direct "
        "SmartChainDB run exhibits rising HTTP failures, which we attribute to single-process overload and "
        "exclude from cross-treatment comparison. The CPU trace (Fig. 8) shows the constraint engine largely "
        "idle, with short spikes in the BigchainDB worker, which is consistent with validation not being the "
        "saturating resource.",
    )

    # ------------------------------------------------------------ 5.6
    subsection(pdf, "5.6", "Experiment 3: Fail-Closed Validation Under State Change")
    subsubsection(
        pdf,
        "5.6.1",
        "Methodology",
        "We run the mutating-advertisement mix (n=20) and the stolen-advertisement probe under all three "
        "treatments on the four-validator deployment, recording the outcome and latency of every submission. "
        "We also run the conflict probe on SmartChainDB.",
    )
    subsubsection(
        pdf,
        "5.6.2",
        "Results: Rejection Behavior",
        "An earlier configuration of the SHACL engine accepted the stolen advertisement and committed offers "
        "submitted after UpdateAdv to CLOSED. The cause was that the shape consulted only the original Advertise "
        "document, whose metadata remains OPEN, and did not require the advertiser to be among the Create "
        "owners; Direct already rejected the stolen advertisement, while both engines ignored subsequent "
        "UpdateAdv status. We therefore extended the state merge so that the effective advertisement status is "
        "resolved from the latest UpdateAdv and the advertiser is checked against the Create outputs, and we "
        "included the effective status in the Delta dependency hash.",
    )
    body(
        pdf,
        "Table 7 and Fig. 9 report the re-measured outcomes. All three SmartChainDB treatments reject the stolen "
        "advertisement with HTTP 400 and reject all ten post-CLOSED offers, yielding a 50% reject rate on the "
        "mutating mix that matches the Fabric port. A rejected offer returns in 16 ms under Direct and 33-36 ms "
        "under SHACL and SHACL+Delta; a committed offer before UpdateAdv takes 0.76-0.94 s on the "
        "four-validator cluster.",
    )
    fig(pdf, "fig_abort_rate.png", "Figure 9: Reject rate on the mutating-advertisement mix and the stolen-advertisement probe (4 validators).", max_h=72)
    table(
        pdf,
        ["Check", "SmartChainDB", "Fabric"],
        [
            ["Offers after CLOSED", "10/10 rejected", "10/10 rejected"],
            ["Mutating-mix reject rate", "50%", "50%"],
            ["Stolen advertisement", "rejected (400)", "rejected"],
            ["In-flight conflict (n=12)", "0/12 aborted", "n/a"],
        ],
        col_w=[70, 52, 52],
        caption="Table 7: Fail-closed outcomes after the state-overlay fix.",
    )
    runin(
        pdf,
        "Interpretation.",
        "The 50% figure is the designed composition of the mix (half the offers precede the close and half "
        "follow it) rather than an artifact of load, and identical outcomes across Direct, SHACL, and "
        "SHACL+Delta indicate that the declarative path is now authoritative for the two constraints that "
        "previously leaked. Including effective status in the dependency hash is what allows caching and "
        "correctness to coexist: an UpdateAdv alters the key, so a verdict cached before the close cannot be "
        "reused after it. Reject and commit latencies are different clocks---a rejection is an HTTP 400 "
        "returned before consensus, whereas a commit traverses four-validator Tendermint---and should not be "
        "compared as evidence that validation is faster when it rejects. The conflict probe records 0/12 "
        "aborts because the ~13 ms validation window is short relative to block time, so the racing UpdateAdv "
        "rarely lands inside it; sequential fail-closed behavior does not depend on that race.",
    )
    subsubsection(
        pdf,
        "5.6.3",
        "Results: Four-Validator Commit Path",
        "Moving from one to four validators raises committed BuyOffer latency from ~200 ms to 0.76-0.94 s, "
        "while rejection latency is unchanged at 16-36 ms. The increase is attributable to gossip, voting, and "
        "four ABCI application paths rather than to validation, and it is identical in kind across treatments. "
        "The deployment confirms that the marketplace commits under multi-validator consensus with the same "
        "fail-closed outcomes; it does not, and by construction cannot, increase SHACL+Delta hit rate, since "
        "the cache is per process.",
    )

    subsection(pdf, "5.7", "Summary of Findings")
    body(
        pdf,
        "With respect to RQ1, declarative validation costs ~13 ms per SHACL evaluation on SmartChainDB (~26 ms "
        "on Fabric), and differential re-validation reduces that to a sub-10 microsecond lookup while the "
        "referenced state is unchanged, reverting to a full evaluation when it changes. With respect to RQ2, "
        "the three treatments occupy the same end-to-end latency class on each engine, validation accounts for "
        "a few percent of committed time, and throughput is bounded by the submission model "
        "(broadcast_tx_commit) or by endorsement overlap rather than by validation. With respect to RQ3, after "
        "resolving effective advertisement status and ownership in the state merge, SHACL and SHACL+Delta "
        "reject non-owner advertisements and post-close offers with the same outcomes as Direct, and caching "
        "preserves those outcomes because the dependency hash includes the mutated state. With respect to RQ4, "
        "the same shapes and treatments produce the same qualitative behavior on Fabric, with hit patterns that "
        "differ only in the client's re-validation call pattern.",
    )

    # ------------------------------------------------------------------ 6
    section(pdf, "6", "Limitations and Threats to Validity")
    runin(
        pdf,
        "Deployment scope.",
        "Latency and load were measured on one workstation with a single SmartChainDB validator and a two-peer "
        "Fabric test-network; the four-validator deployment is a LAN cluster rather than a geo-distributed one. "
        "An attempt to emulate WAN delay with tc netem was denied NET_ADMIN in the container runtime, so no "
        "WAN results are reported.",
    )
    runin(
        pdf,
        "Cache scope.",
        "SHACL+Delta state is in-process. With more than one gunicorn worker the cache is partitioned; we pin "
        "one worker. Additional validators exercise the commit path and do not increase hit rate.",
    )
    runin(
        pdf,
        "Construct validity.",
        "Hit rate measured over a stream of distinct BuyOffers is not an appropriate construct for differential "
        "re-validation, since each offer has a fresh tx-id; the validator microbenchmark, which re-validates "
        "one pending transaction, is the appropriate one. Rejection latency and commit latency are measured on "
        "different paths and are not directly comparable.",
    )
    runin(
        pdf,
        "Evaluation scope.",
        "The workload is synthetic by necessity: public ledgers do not record the semantic dependencies the "
        "shapes name. Each treatment commits on the order of 220 transactions, which is sized to exercise a "
        "known dependency graph under repeatable conditions rather than to characterize capacity at scale. The "
        "0/12 conflict-probe result bounds in-flight abort only for the ~13 ms matcher measured here. HTTP 500 "
        "and \"already exists\" retries may inflate tail latency.",
    )
    runin(
        pdf,
        "Cross-platform comparison.",
        "The Fabric port provides a portability reference for the same shapes and treatments. We configure both "
        "systems with identical transaction semantics, but interpret cross-platform latency and throughput "
        "cautiously because the systems differ in runtime, storage architecture, and consensus model; we do not "
        "report either engine as outperforming the other.",
    )

    section(pdf, "", "Artifacts")
    body(
        pdf,
        "JSON traces: eval/results/. Figures: eval/figures/. Drivers: eval/bdb_professor_eval.py and "
        "fabric/client/professor_eval.js. LaTeX source: eval/paper/evaluation.tex.",
    )

    pdf.output(OUT)
    print("wrote", OUT)


if __name__ == "__main__":
    build()
