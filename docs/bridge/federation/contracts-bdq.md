# Federation contracts and cumulative BD ledger

**Source snapshot:** F02 branch based on GEMINI main cf72ec33ff85017c997d51bc563e5708453212a1; main has since advanced to e991d55d40b0f624f2df4539829e8d6e409d7cbf through PR #49 (2026-11-10).
**Review surfaces:** [F02 #48](https://github.com/GBOGEB/GEMINI/pull/48) and [public reader #49](https://github.com/GBOGEB/GEMINI/pull/49). PR #49 is now MERGED, while PR #48 remains open and requires current-head admission.
**Classification:** SOURCE_RECONCILED / NEW_HEAD_CI_REQUIRED / G1_OWNER_HOLD / IC3_OWNER_HOLD / NO_MERGE.

## What the source actually proves

- The live GEMINI broker uses canonical #40 profile plus proposal wire. #41 proposal_profile is legacy input, rejected with AMBIGUOUS_LEGACY_PROFILE by merged PR #46. See [issue #44](https://github.com/GBOGEB/GEMINI/issues/44) and [boundary contract](../PROPOSAL_PROFILE_BOUNDARY_20261109.md). Owner P2/P3 acceptance remains open.
- PR #47 changed Windows CRLF git apply --cached guidance. Historical #40/#41 merges must not be retrospectively credited with newer governance.
- Original PR #48 head b60f798a5f499d22334c2c6d91315f30d35d11f2: dedicated Python 3.12 and 3.13 inert-contract checks PASSED, while Ubuntu Python 3.9 baseline failed Ruff I001, at tests/test_federation_config.py line 6. The source repair does not equal new-head CI proof.
- PR #49 MERGED on 2026-11-10 at e991d55d40b0f624f2df4539829e8d6e409d7cbf and owns the public GEMINI README/BIOS/SIPOC/Kahn narrative. PR #48 did not change README relative to its original merge-base; review its merge against latest main without reverting #49.
- The active [Main_Protect ruleset #26381197](https://github.com/GBOGEB/GEMINI/rules/26381197) was read back with only deletion and non_fast_forward; there are no required PR-review/CI contexts in that ruleset. [Issue #50](https://github.com/GBOGEB/GEMINI/issues/50) tracks the distinct owner/admin governance gate.

## Contract register

| Contract | Owner and proof |
|---|---|
| C01 identity | GitHub App selected repos, separately approved Google OAuth/WIF and Drive ACL; no token reuse |
| C02 provenance | Drive file ID/revision and true byte SHA-256 vs Git exact commit/tree/blob identities |
| C03 dependency | Kahn acyclic finish-to-commit DAG; exclusive resources; no parallel conflicting writers |
| C04 proposal | One canonical #40 profile; #41 fail-closed legacy; versioned conversion only with owner permission |
| C05 merge admission | Exact-head CI, independent review, current approval, positive and RED negative canaries |
| C06 publisher | Immutable new Drive snapshot and authenticated readback; never overwrite unmerged edits |
| C07 visual QA | Mermaid source hashes, explicitly named renderer, SVG/PDF/HTML inspect |
| C08 federation | Hub/CODEX/ABACUS/gg_MATH/DOCX/QPS native owner receipts, no authority transfer |

## Cumulative checklist

**TOTAL 25 | DONE_SOURCE 9 | OPEN 16 (ACTIVE 4, HOLD/SCHEDULED 12).**

Each completed item means its narrowly scoped source/checklist step is done, not that an issue or entire integration has passed DoD/DoV.

| ID | Priority | State | Task and exit proof |
|---|---|---|---|
| F01-01 | P0 | DONE_SOURCE | Verify original ARGON and BridgeFlow Drive worktree IDs and lineage |
| F01-02 | P0 | DONE_SOURCE | Inventory seven existing core repositories, including Hub default master |
| F01-03 | P1 | DONE_SOURCE | Five editable Mermaid sources plus federation Markdown merged through PR #43 |
| F01-04 | P0 | DONE_SOURCE | Record unsafe legacy direct-main push and simulated broker approval; preserve originals |
| F02-01 | P0 | DONE_SOURCE | Create controlled F02 draft PR #48, no merge |
| F02-02 | P0 | DONE_SOURCE | Implement inert policy validator, 14 negative/positive source tests and workflow |
| FED-BD-01 | P0 | OWNER_HOLD | Issue #44: owner accepts canonical #40 wire and fail-closed #41, or approves separately versioned migration |
| FED-BD-02 | P0 | HOLD | Keep ARGON legacy direct-main push undeployable; replace via reviewed adapter only |
| FED-BD-03 | P0 | AUTH_HOLD | Verify selected-repo broker GitHub App installation and real permission scopes |
| FED-BD-04 | P0 | AUTH_HOLD | Issue #12: GitHub OIDC to Google WIF, hosted Drive readonly >0-step proof |
| FED-BD-05 | P1 | SCHEDULED | Typed BridgeFlow-to-GMI adapter, without duplicating Hub scheduler |
| FED-BD-06 | P1 | AUTH_HOLD | Scoped Drive writer, immutable snapshots, readback and stale/divergence negative cases |
| FED-BD-07 | P1 | GOVERNANCE_HOLD | Feature branch and draft PR execution with required independent admission |
| FED-BD-08 | P1 | ACTIVE | Source-pinned Mermaid diagrams to SVG/HTML/PDF, manifest and visual inspection |
| FED-BD-09 | P2 | SCHEDULED | Webhooks, replay protection, periodic drift census and measured convergence |
| FED-BD-10 | P2 | SCHEDULED | Cross-repo load scaling and comparable repeated QA pulses |
| FED-BD-11 | P0 | DONE_SOURCE | Current main broker canonical #40; PR #46 rejects legacy #41; PR #47 CRLF fix |
| FED-BD-12 | P0 | DONE_SOURCE | Repair PR #48 Ruff I001 first-red on tests/test_federation_config.py |
| FED-BD-13 | P0 | DONE_SOURCE | Restore PR #48 README to main byte parity; reserve public BIOS ownership for PR #49 |
| FED-BD-14 | P0 | ACTIVE | Requalify NEW PR #48 exact-head CI after fixing original-head Ubuntu 3.9 red |
| FED-BD-15 | P0 | OWNER_HOLD | Issue #50: effective main required checks, independent review, last-push/RED canaries |
| FED-BD-16 | P1 | SOURCE_HOLD | Issue #16: genuine R3 successor Git bundle and exact Python environment |
| FED-BD-17 | P0 | ACTIVE | Reconcile current-main ancestry and native #48/#49 evidence, cumulative ledger and scope |
| FED-BD-18 | P0 | ACTIVE | Requalify PR #48 on exact latest head against merged #49 main ancestry; prevent stale-base or stale-review admission |
| FED-BD-19 | P0 | GOVERNANCE_HOLD | Reconcile #49 historical integration with #50 Main_Protect ruleset; independent-review/required-CI negative-canary proof not retroactively granted |

## Latest F04 pulse reconciliation (10 November 2026)

- Public-reader [PR #49](https://github.com/GBOGEB/GEMINI/pull/49) is **MERGED** at `e991d55d40b0f624f2df4539829e8d6e409d7cbf`; its historical admission is not proof that the active ruleset had required independent review.
- PR #48 currently includes an exact-source, GitHub-native [five-diagram Mermaid preview](diagrams/rendered.md) and [F03 QA/readback receipt](diagrams/QA_READBACK_F03_20261110.md). Vector PDF, HTML, and 21-entry ZIP are stored inside the existing [ARGON/BridgeFlow Drive artifact folder](https://drive.google.com/drive/folders/1F6tq6QeM4EMfHrCtd1NbkoS_2lV27YTA); archive byte-for-byte Drive readback and SHA-256 **PASS**.
- PR #48's Codex-bot review attempt failed due review-usage limits and is **not** an independent completed review; an owner-authored COMMENTED submission is also not independent approval.
- The Ubuntu Python 3.9 Ruff I001 defect required two source edits: import spacing followed by correct standard-library/first-party grouping. Each new commit invalidates older-head CI evidence; no RED waiver.
- Render source and Git blob checks passed. Native pinned Mermaid CLI parity remains **NOT RUN**. The F03 Graphviz semantic render is a legitimate review view, not a claim of Mermaid layout equivalence.

## Critical prerequisite DAG

Source verification => F02 repair/README disjointness => new-head exact CI => independent review => #50 effective protection + negative canaries => owner PR admission.
Separately: canonical #40 source guard => issue #44 explicit owner wire disposition => W2 P2/P3 admission; and issue #12 WIF/ACL => scoped Drive publisher.
Only after those joins may the hosted Drive-to-GitHub-to-Drive trial be classified as proven. Recursion must create a new bounded epoch; no backward edge in one Kahn DAG.

## Safety and accounting

Do not merge on red, waive required controls, claim review from self or simulated agents, share the Drive folder broadly, reuse a GitHub token as Google OAuth, or push main directly.
The original Drive ARGON worktree and generic BridgeFlow package remain their respective portable source repositories; no replacement worktree or hosted dispatch was created in this pulse.
