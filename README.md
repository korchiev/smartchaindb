<!---
SPDX-License-Identifier: (Apache-2.0 AND CC-BY-4.0)
Code is Apache-2.0 and docs are CC-BY-4.0
--->

# Artifact: shapes as contracts

This repository is the implementation behind an anonymous WWW submission on declarative transaction validation. It is a BigchainDB-based ledger with Tendermint consensus. Structural rules are W3C SHACL shapes. Ownership, advertisement status, linkage, and uniqueness are ledger-state checks in code. An optional cache reuses a verdict when the dependencies of that same transaction are unchanged.

Use the anonymous URL supplied with the submission. Do not replace it with a named GitHub account. A previous anonymous link now redirects to a public repository whose default branch is an old snapshot and whose page shows an author name. That page is not this artifact.

## Three modes

One code base, switched by environment variables. `docker/4node/set_mode.sh` sets them.

| Mode | SHACL | Verdict cache | What a reviewer should expect |
| --- | --- | --- | --- |
| `direct` | off | off | The ledger's existing imperative checks. Two uniqueness rules are absent. |
| `shacl` | on | off | Structural shapes plus state checks at every validation point. |
| `delta` | on | on | The same checks, with reuse when the projection hash matches. |

Shapes are loaded once, when the SHACL service starts. Each check still parses that transaction, runs the SHACL engine, and, if the shape passes, runs the state checks. Those steps are why a SHACL check is slower than `direct` after startup.

## Where to read the code

| Question | Path |
| --- | --- |
| Where is a transaction accepted or rejected? | `bigchaindb/common/shacl_validator.py` |
| What does a cached verdict depend on? | `bigchaindb/common/shacl_delta.py` |
| Structural shapes (Turtle) | `bigchaindb/backend/localshacl/shapes/shapes/` |
| State checks (ownership, status, linkage, uniqueness) | `bigchaindb/backend/localshacl/shapes/state_validator.js` |
| SHACL service entry point | `bigchaindb/backend/localshacl/shapes/index.js` |
| Switch `direct` / `shacl` / `delta` on one node | `docker/4node/set_mode.sh` |
| Campaign driver and plots | `eval/bdb_professor_eval.py`, `eval/plot_professor_figures.py` |
| Separate Fabric pre-check | `fabric/` |

On this ledger, validation runs at HTTP admission, at Tendermint CheckTx, and at DeliverTx. Admission and consensus are different processes. Each has its own verdict cache. Commit notifications reach only the consensus cache, so a hit measured in the paper is the same transaction checked at CheckTx and then at DeliverTx. Different offers do not share a verdict.

The Fabric integration is a client-side check before endorsement. Its shapes and conversion code are not the ledger's. Chaincode remains the authority.

## Run one node

Requirements: Docker, Docker Compose, and a built image of this repository. From the repository root, with the compose file that includes Tendermint:

```bash
# direct
BIGCHAINDB_SHACL_ENABLED=false BIGCHAINDB_SHACL_CACHE=false docker compose up -d

# shacl
BIGCHAINDB_SHACL_ENABLED=true BIGCHAINDB_SHACL_CACHE=false docker compose up -d

# delta
BIGCHAINDB_SHACL_ENABLED=true BIGCHAINDB_SHACL_CACHE=true docker compose up -d
```

The HTTP API listens on port 9984. If the SHACL service is unreachable, `shacl` and `delta` reject the transaction. They do not fail open.

`docker/4node/set_mode.sh direct|shacl|delta` is the script used on the four-validator deployment. It recreates the ledger container for that host. Tendermint must be restarted after the recreate so it reconnects.

## What the reported runs measured

The evaluation compared the three modes. It did not rank this ledger against Fabric by throughput.

- Conformance: SHACL reproduces a 24-case suite on which `direct` misses two uniqueness rules (66 of 72 versus 72 of 72).
- One repeated check of the same pending offer: a full SHACL evaluation is about 19.5 ms and a complete cache hit is about 4.6 ms. The value-change case is a single probe.
- Low-load lifecycle latency is dominated by consensus, about 4.3 s for seven operations, with overlapping intervals.
- Under a stream of distinct transactions the cache mostly misses, so `shacl` and `delta` commit fewer transactions than `direct`. That is a load limitation, not evidence that reuse failed on a repeated check.
- Conflict detection and early termination were not established. The paper does not claim them.

Traces used for the figures live under `eval/results/` when that directory is in the archive. Regenerating the figures from those traces:

```bash
python eval/plot_professor_figures.py
```

## What not to look for

- No author names, institution, or identified repository URL belong in this file.
- No claim that projections are derived automatically from shapes. They are written per transaction type in `shacl_delta.py` to match the dependencies the validator reads.
- No claim that admission and CheckTx share a cache.
- This branch is the artifact. It contains `shacl_validator.py` and `shacl_delta.py`.
