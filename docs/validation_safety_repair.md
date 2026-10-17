# Validation safety repairs: first implementation batch

Prepared on 2026-10-17 from `shacl_delta` commit
`b07c5e7dd86f8bf9df36ed8ae0ed22721fe74f7d`, on local branch
`fix/shacl-validation-safety`. Historical experiment outputs are untouched.

This batch repairs specific failures identified in the correctness audit. It
does not establish full marketplace correctness, a complete cache soundness
theorem, cross-platform semantic equivalence, or production readiness.

## Changes

| Area | Implemented behavior |
| --- | --- |
| Shared authentication | Direct, SHACL and SHACL+delta verify transaction IDs, real fulfillment signatures, owner/condition binding and declared actors before domain validation or cache reuse. Linked inputs are checked for existence, valid indexes, duplicate spends and ownership. |
| Spending | SELL and TRANSFER require linked inputs and matching assets. TRANSFER conserves amounts. SELL checks the referenced offer, intended buyer, asset quantity and recipient conditions. These checks do not fund synthetic marketplace payment outputs. |
| RDF extraction | State rules follow the single transaction root and declared paths. Nested `metadata.operation` cannot replace dispatch. Requested shape and root type must match the root operation. Nested policy objects and known collection fields are preserved; ambiguous scalar fields and conflicting asset IDs fail. Turtle strings use escaped JSON string syntax and field names are constrained. |
| State availability | The sidecar cannot accept transactions with an unavailable database or after state-query errors. Python requires protocol 2 and a completed state phase for a positive response. Operational errors are not cached semantic rejections. |
| Accepted block prefix | Python lookups and sidecar queries include earlier accepted transactions in the current block. Effective advertisement status and duplicate-return checks see that prefix. Active-advertisement checks read the separately stored metadata. |
| Time | DeliverTx uses the BeginBlock header timestamp, normalized to milliseconds. CheckTx uses speculative time without inheriting the last block clock. Direct offer expiry preserves timezone offsets and fractional seconds. Sidecar time-dependent verdicts carry the earliest observed expiry deadline; cache lookup checks it against the current validation context. Temporal rejections are not cached. |
| Cache conservatism | A nonempty accepted prefix bypasses cache lookup and insertion. An unavailable required derived-query projection also bypasses caching. Plain SHACL skips cache projection work. Commit invalidation distinguishes writes from reads, so an unrelated offer no longer evicts other offers merely because they read the same advertisement. |
| Deployment wiring | The sidecar image and one-node Compose bindings include the extracted JavaScript modules. The sidecar update script transfers all modules and recreates its mounts. |

Authentication runs on every attempt. Domain cache hits cannot substitute for
signature or spent-input checks. Existing legacy checks may also perform
signature checks; this batch does not optimize those duplicate costs away.

## Verification

The focused regression suites pass **111 Python tests and 14 Node tests**.
The Python suites include real Ed25519 signing and verification, transaction
hashing, model dispatch, response validation, dependency projection and cache
behavior. The Node tests use the actual RDF parser, SHACL engine and shapes.

An offline integration regression constructs, signs, serializes and validates
the seven-step CREATE / ADVERTISEMENT / UPDATE_ADV / BUY_OFFER / SELL /
REQUEST_RETURN / SELLER_ACCEPT_RETURN workflow. It runs both with each step
committed separately and with all seven steps in one accepted block prefix.
The HTTP transport is replaced by a Node subprocess; database reads use
normalized in-memory records. A passing workflow establishes coverage of that
trace, not equality of the full accepted transaction languages.

The ABCI time regressions execute the actual extracted CheckTx and DeliverTx
methods against small infrastructure stubs. They do not exercise a running
Tendermint connection. Database/ABCI infrastructure imports are also stubbed
in the isolated Python security tests; cryptography and transaction code are
real. The broad legacy test suite was not run.

Reproduce in an environment with the project's Python dependencies, pytest,
and sidecar npm dependencies installed:

```bash
python -m pytest --noconftest tests/test_shacl_delta.py tests/test_paper_hardening.py tests/test_validation_security.py tests/test_validation_context.py -q
node --test bigchaindb/backend/localshacl/shapes/tests/validation.test.js
```

The implementation workspace used isolated Python dependencies and Node
v24.19.0. Tests reported an existing obsolete `looponfailroots` pytest option
and existing `datetime.utcnow()` use in the offer builder. The Docker image
still targets Node 18; its runtime and dependency installation must be checked
in the deployment environment. No Docker, live MongoDB, Tendermint cluster,
Fabric network, remote deployment, or throughput experiment was run here.

## Apply and deploy

The mail patch applies to the base commit above. Preserve any uncommitted
local work first, then apply it to a clean branch based on the matching source:

```bash
git switch -c fix/shacl-validation-safety shacl_delta
git am /path/to/SmartChainDB_safety_repairs.patch
```

If your branch has moved, review and resolve conflicts against that newer
source. Do not overwrite your uncommitted local configuration or old results.
The implementation itself was developed in a separate worktree.

Protocol 2 requires a coordinated upgrade of BigchainDB Python code and the
sidecar. New Python clients reject older sidecars. An older Python client
does not supply the new prefix/time context, so upgrading only the sidecar
does not provide the new guarantees. Do not run `docker/4node/push_shacl.py`
alone as the initial upgrade; it updates only the sidecar. No remote script
has been executed as part of this implementation.

For a research cluster, pause submission, finish a block boundary, deploy the
matching Python and sidecar versions to every validator, restart to clear
process-local caches, and verify protocol/health before resuming. Rebuild or
recreate containers as appropriate for the deployment's code mounts. Re-run
the signed workflow, expiry boundaries, same-block close/offer, duplicate
return and database-unavailability cases against the actual cluster. Compare
validator decisions and committed state before collecting performance data.

## Remaining work and paper implications

1. **Complete dependency contracts and snapshots.** The guard still checks
   identifier coverage, rather than proving coverage of predicates, negative
   query results, ordering and all values. Python projection reads and
   sidecar reads are separate; there is no shared snapshot certificate.
   Committed UPDATE_ADV ordering still inherits MongoDB `_id` sorting.
   Overlay-aware projections, ledger ordering, snapshot consistency and
   policy/schema versioning remain necessary before a general soundness claim.
2. **Full rule equivalence.** Direct and SHACL still differ outside the repaired
   cases. Add a common transition specification and differential, adversarial
   sequence tests across all treatments. Existing construction-time checks
   are not a substitute for validation of externally supplied transactions.
3. **Marketplace semantics.** BUY_OFFER and SELL still use synthetic payment
   outputs. This batch does not implement funded escrow, currency conservation,
   complete current-owner tracking, or asset/payment reversal on return.
   Return-policy enforcement also needs a shared authoritative policy source.
4. **Consensus failure handling.** Rejecting sidecar/database failures prevents
   degraded acceptance, but does not establish identical decisions when only
   some validators lose dependencies. Test the intended fail-stop/recovery
   policy and move authoritative reads into a deterministic ledger context.
5. **Fabric parity.** Fabric identity binding, deterministic time and semantics
   remain unchanged. No Fabric correctness or performance claim is established
   by the BigchainDB tests.
6. **Experiments.** Rebuild all treatments from the same repaired base, verify
   workloads are actually committed, and rerun paired repeated trials. Common
   authentication adds work; precise invalidation changes cache behavior;
   nonempty-prefix cache bypass may materially reduce gains in busy blocks.
   Historical results cannot quantify the behavior of this patch.

The strongest defensible next paper direction is dependency-certified reuse
of declarative validation over ledger state. This batch supplies concrete
repairs and regression evidence toward that direction. It does not yet supply
the complete dependency certificate, proof, or new experimental evidence
needed to present that contribution as finished.
