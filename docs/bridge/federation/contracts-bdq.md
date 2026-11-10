# Federation contracts and cumulative BD ledger

**Source snapshot:** GEMINI main d3a885ab8593cbf9af22e6fce6c64d589ad80575 (merged #49 public reader and #52 legacy receipt repair). F05 PR #48 source reconciliation merge 803532158ea4ed1bff51506f6e5d7d86238d2bc5 has parents d44a52295bb411e8a8eb1a390f0039026a576fbe and d3a885ab8593cbf9af22e6fce6c64d589ad80575. Newer F05 probe commits require their own exact-head CI.
**Review surfaces:** [F02 #48](https://github.com/GBOGEB/GEMINI/pull/48) and [public reader #49](https://github.com/GBOGEB/GEMINI/pull/49). PR #49 is now MERGED, while PR #48 remains open and requires current-head admission.
**Classification:** F06_PROBE_FALSE_COMPLETE_REPAIRED / PREDECESSOR_NATIVE_QA_COMPLETE / NEW_HEAD_CI_PENDING / G1_OWNER_HOLD / IC3_OWNER_HOLD / NO_MERGE.

## Latest F06 pulse — scoped evidence repair

Predecessor PR head `d377dc67c4aed780dca3394e0c361699d362c681` is now fully native source-qualified: [F02/F05](https://github.com/GBOGEB/GEMINI/actions/runs/42904553809) and [BLSN](https://github.com/GBOGEB/GEMINI/actions/runs/42904554187) completed, including PyPy; **12 successful checks and one intentionally skipped PR Pages deploy**. This completes FED-BD-14's original first-red requalification at that head. It does not grant independent review or apply main protection.

Four new concrete false-complete reproductions in the existing offline admission probe are repaired under added **FED-BD-25**: an explicit default-branch exclusion, missing required provider binding, missing PR-author identity, and a later change-request decision failing to revoke an earlier approval. Conservative HOLD now also covers unreadable exclusions, malformed providers, case-variant self-review, duplicate-reviewer quorum, dismissals and ambiguous/out-of-order review histories. Fifteen new test methods bring the probe suite to 36; F02's 14 inert-policy and six canonical-DAG cases remain unchanged. [Operator contract and proposed native context/provider mapping](ADMISSION_READINESS_PROBE_F05.md) record the evidence boundaries.

F06 changes require their own native qualification and eligible independent review; FED-BD-18/FED-BD-22 remain open and consume the current PR head. The former head's completed QA is preserved rather than repeatedly reclassified as unfinished. No policy, broker wire, WIF/Drive ACL, default-branch or merge authority changes.

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

**TOTAL 31 | DONE_SOURCE 15 | OPEN 16 (ACTIVE 3, HOLD/SCHEDULED 13).**

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
| FED-BD-14 | P0 | DONE_SOURCE | Original first-red requalification completed at d377dc67: F02/F05 and full BLSN/PyPy native workflows SUCCESS; newer-head qualification remains BD-18/BD-22 |
| FED-BD-15 | P0 | OWNER_HOLD | Issue #50: effective main required checks, independent review, last-push/RED canaries |
| FED-BD-16 | P1 | SOURCE_HOLD | Issue #16: genuine R3 successor Git bundle and exact Python environment |
| FED-BD-17 | P0 | DONE_SOURCE | Verify #48 source/PR #49/#52 lineage, disjoint 10-path F02 overlay vs 8-path main delta, two-parent commit 80353215 and intact main tree |
| FED-BD-18 | P0 | ACTIVE | Requalify PR #48 on exact latest head against merged #49 main ancestry; prevent stale-base or stale-review admission |
| FED-BD-19 | P0 | GOVERNANCE_HOLD | Reconcile #49 historical integration with #50 Main_Protect ruleset; independent-review/required-CI negative-canary proof not retroactively granted |
| FED-BD-20 | P0 | DONE_SOURCE | [PR #52](https://github.com/GBOGEB/GEMINI/pull/52) merged into main d3a885ab; R2-W2 per-package legacy REJECT receipts restored, exact-main broker/negative/BLSN 16/16 checks SUCCESS. Historical independent review deficit remains NEW BD-23; no retroactive acceptance |
| FED-BD-21 | P0 | DONE_SOURCE | Implement F05 offline admission evidence probe and 21 positive/adversarial unit tests; historical source readback correctly produces HOLD, never executes or merges |
| FED-BD-22 | P0 | ACTIVE | Qualify F05 probe source with exact-head Python 3.12/3.13 policy CI, Python 3.9 BLSN, PyPy, Windows and negative-case results; require independent final-head review |
| FED-BD-23 | P0 | GOVERNANCE_HOLD | Address historical PR #52 merge with no completed independent review through owner-audited admission discrepancy, #44 protocol decision and #50 effective rules; no retrospective approval |
| FED-BD-24 | P1 | DONE_SOURCE | Document scope difference: PR #49 canonical 20-node, 24-edge federation DAG is DECLARED, F02 six-node microplan is INERT subset, Hub owns real scheduler; no false ready-set equivalence |
| FED-BD-25 | P0 | DONE_SOURCE | F06 repair of reproduced false-complete default exclusion/provider/PR-author/review-history evidence; 36 probe tests including 15 new methods. Current-head native/independent qualification stays BD-22; never emits merge authority |

## Historical F04 pulse reconciliation (10 November 2026)

The then-current failures below are preserved as dated lineage. F05 source convergence and the F06 predecessor native receipt above supersede the old main-red/reconciliation action statuses.

- Public-reader [PR #49](https://github.com/GBOGEB/GEMINI/pull/49) is **MERGED** at `e991d55d40b0f624f2df4539829e8d6e409d7cbf`; its historical admission is not proof that the active ruleset had required independent review.
- PR #48 currently includes an exact-source, GitHub-native [five-diagram Mermaid preview](diagrams/rendered.md) and [F03 QA/readback receipt](diagrams/QA_READBACK_F03_20261110.md). Vector PDF, HTML, and 21-entry ZIP are stored inside the existing [ARGON/BridgeFlow Drive artifact folder](https://drive.google.com/drive/folders/1F6tq6QeM4EMfHrCtd1NbkoS_2lV27YTA); archive byte-for-byte Drive readback and SHA-256 **PASS**.
- PR #48's Codex-bot review attempt failed due review-usage limits and is **not** an independent completed review; an owner-authored COMMENTED submission is also not independent approval.
- **Independent inherited first-red:** current main `e991d55d40b0f624f2df4539829e8d6e409d7cbf` native Ubuntu Python 3.9 [job 129977729760](https://github.com/GBOGEB/GEMINI/actions/runs/42858438906/job/129977729760) reports 187 PASS / 1 FAIL in `test_same_digest_legacy_package_cannot_be_accepted_as_brokered`: `IndexError` at `tests/test_gmi_profile_collision_boundary.py:163` because `broker_workspace(...)["packages"]` is empty. PR #48 later recorded the same first-red with 201 PASS / 1 FAIL; its 14 inert-policy tests passed. This is a W2 broker source/receipt regression, **not** an F02 configuration failure. Dedicated draft [PR #52](https://github.com/GBOGEB/GEMINI/pull/52) owns the disjoint repair; current main remains RED until genuinely qualified.
- **Do not merge #48 on full-red baseline or silently cherry-pick #52**; rebase/qualification must follow the owner-reviewed #52 repair (or an explicitly governed equivalent) and independent exact-head review.
- The Ubuntu Python 3.9 Ruff I001 defect required two source edits: import spacing followed by correct standard-library/first-party grouping. Each new commit invalidates older-head CI evidence; no RED waiver.
- Render source and Git blob checks passed. Native pinned Mermaid CLI parity remains **NOT RUN**. The F03 Graphviz semantic render is a legitimate review view, not a claim of Mermaid layout equivalence.

## F05 — source-to-admission convergence (10 November 2026)

- Reconciled existing PR #48 by an expected-head, non-force **two-parent merge** of current main into its feature branch: `803532158ea4ed1bff51506f6e5d7d86238d2bc5`. The 10 F02 paths and eight intervening main paths were **disjoint**. Main branch unchanged; branch is zero commits behind main at that reconciliation.
- Fresh native tests on the reconciliation head: [F02 policy QA](https://github.com/GBOGEB/GEMINI/actions/runs/42903253413) **2/2 SUCCESS**. Its full [BLSN matrix](https://github.com/GBOGEB/GEMINI/actions/runs/42903254382) was 11 successful and PyPy 3.9 running at the first observation; these checks do not qualify the newer F05 code head.
- [PR #52](https://github.com/GBOGEB/GEMINI/pull/52) is already merged, no duplicate broker fix or third broker. [Mainline check evidence](https://github.com/GBOGEB/GEMINI/actions/runs/42893744721) and broker/legacy negative workflows show **16/16 SUCCESS** on exact main `d3a885...`; its historical independent review gap remains for #50 owner disposition.
- New [F05 advisory admission probe](../../../src/federation_admission_probe.py) and [21 adversarial tests](../../../tests/test_federation_admission_probe.py) check stale SHA, required status contexts, nonzero steps, provider identity, last-push review freshness, bypass actors and RED/stale negative canaries. It **never grants** merge or execution rights even for synthetic complete evidence.
- The pinned [historical source snapshot](../../../config/federation/admission_observation_20261110.json) records the active [Main_Protect](https://github.com/GBOGEB/GEMINI/rules/26381197) ruleset's two existing rules and intentionally incomplete review/check data. Its expected diagnostic is **HOLD**, not a green admission receipt.
- [Probe operator notes](ADMISSION_READINESS_PROBE_F05.md) distinguish the PR #49 20-node canonical declared architecture DAG from F02's six-node **inert micro-example** and prevent promotion of either into the actual Hub/BridgeFlow production scheduler.
- Current F05 source commits and this ledger update invalidate earlier review/CI qualifications; re-read exact latest PR head before attempting admission. Owner #44, G1 #50, IC3 #12 and R3 #16 stay open.

## Critical prerequisite DAG

Source verification => F02 repair/README disjointness => new-head exact CI => independent review => #50 effective protection + negative canaries => owner PR admission.
Separately: canonical #40 source guard => issue #44 explicit owner wire disposition => W2 P2/P3 admission; and issue #12 WIF/ACL => scoped Drive publisher.
Only after those joins may the hosted Drive-to-GitHub-to-Drive trial be classified as proven. Recursion must create a new bounded epoch; no backward edge in one Kahn DAG.

## Safety and accounting

Do not merge on red, waive required controls, claim review from self or simulated agents, share the Drive folder broadly, reuse a GitHub token as Google OAuth, or push main directly.
The original Drive ARGON worktree and generic BridgeFlow package remain their respective portable source repositories; no replacement worktree or hosted dispatch was created in this pulse.
