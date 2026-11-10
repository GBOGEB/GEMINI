# Federation Contracts, Compatibility and BD Queue

**Control:** F01 architecture/inventory; F02 inert contract+native test; F03 select R2-W2 profile; F04 hosted round-trip (gated). No merge-on-red.

| ID | Contract | Owner and gate |
|---|---|---|
| C01 | Identity | GitHub App selected-installation token; separate Google OAuth/WIF and Drive ACL |
| C02 | Snapshot lineage | Drive file ID/revision + actual SHA-256; Git exact commit/tree/blob IDs |
| C03 | Execution DAG | Kahn ready-set, explicit predecessors, bounded workers, exclusive resource locks |
| C04 | Proposal/patch | Existing GMI schema plus exactly ONE approved R2-W2 wire profile |
| C05 | QA/admission | Exact-HEAD native CI, independent review, required checks and last-push validity |
| C06 | Drive publication | Immutable snapshot and verified readback; no overwrite of unpublished edits |
| C07 | Binary QA | Native DOCX/PDF/HTML rendering/test owner, visual QA and hash receipts |
| C08 | Federation interface | Hub/CODEX/ABACUS/gg_MATH/QPS owner-native evidence, no authority transfer |

## R2-W2 incompatible proposal collision

- [PR #40](https://github.com/GBOGEB/GEMINI/pull/40) uses top-level profile/proposal sections with a git-object-reading offline broker and dedicated tests.
- [PR #41](https://github.com/GBOGEB/GEMINI/pull/41) uses a nested proposal_profile plus separate snapshot roots and expands the existing GMI test workflow.
- Both modified src/proposal_broker.py and docs/bridge/PROPOSAL_BROKER.md. **Current 2026-11-10 observation: both PR #40 and #41 are MERGED; historical collision cannot be treated as two still-open candidates. Audit the final merged implementation and post-merge compatibility rather than choosing an open PR.**
- Preserve original proposal lineage. Reconcile merged contract behavior with exact current-main source, tests and Hub admission records; do not declare IC3 or hosted round-trip from merge alone.

## Ordered BD queue

| ID | Rank | Next action | Admission proof |
|---|---|---|---|
| FED-BD-01 | P0 | Compare #40/#41 schema/paths/CI; choose one wire profile | Exact-head checks, negative controls, independent review, recorded disposition |
| FED-BD-02 | P0 | Isolate legacy ARGON direct-main push and demo token logic | Preserved source, safe adapter, no bypass primitive |
| FED-BD-03 | P0 | Register broker App initially selected-repo read-only | Observed installation/permission receipt |
| FED-BD-04 | P0 | Resolve existing IC3 Google WIF and Drive ACL (GEMINI #12) | Hosted read-only ingress >0, no stored credentials |
| FED-BD-05 | P1 | Integrate existing BridgeFlow scheduler via typed GMI adapter | No second Hub/CODEX/ABACUS task engine, native tests |
| FED-BD-06 | P1 | Add immutable Drive snapshot publisher and conflict holds | Separate write authorization, versioned readback |
| FED-BD-07 | P1 | Broker feature-branch/draft-PR execution | Exact-head green, approval policy, RED negative canary |
| FED-BD-08 | P1 | Mermaid source → SVG/HTML/PDF QA | Pinned renderer, source hashes, inspected pages |
| FED-BD-09 | P2 | Event-driven + periodic drift census | HMAC/replay guards, measured convergence |
| FED-BD-10 | P2 | Safe disjoint scaling and cross-repo release receipts | Repeated comparable passes and source-owner approvals |

## State machine

RECEIVED → SOURCE_VERIFIED → VALIDATED → PLAN_READY → DRAFT_PR → EXACT_HEAD_CI_PASS → INDEPENDENT_REVIEW → AUTHORIZED_MERGE → DRIVE_PUBLISHED.

Side states: STALE, CONFLICT, DENIED, CI_RED, AWAITING_AUTH, AWAITING_APPROVAL. Do not infer one gate from another. A new recursive wave is a new acyclic epoch and carries predecessor receipt hashes.

## Evidence limitation

A successful offline profile test is not a hosted GitHub App/Google Drive action, not an independently reviewed PR and not a formal engineering/contract approval.