# Federation Architecture — GMI-FED-ARCH-v1

**Owner:** GEMINI handover and contract plane. **Snapshot:** 2026-11-09. **Authority:** design proposal, not hosted release evidence.

## Mission

Keep Gemini (without local GitHub credentials), Claude and ChatGPT/Codex collaborating through authenticated Google Drive work packages and a separately permissioned broker. Reuse existing GBOGEB source owners, GitHub protected integration, native CI and Kahn-style disjoint work execution.

### Independent control planes

| Plane | Service | Authority |
|---|---|---|
| Transport | Google Drive OAuth/WIF, immutable snapshots, GMI source packages | Files + Drive revision, not Git refs |
| Contracts | GEMINI package/snapshot validators + BridgeFlow adapter | Verified proposal identity, typed receipts |
| Execution | Isolated Git runners + CODEX/ABACUS/gg_MATH/DOCX/QPS workers | Code changes, tests, owner-specific proof |
| Admission | GitHub feature PR, exact HEAD, required checks, independent review | Governs commits on protected branches |
| Observability | pipeline-automation-hub (master) | Portfolio ledger and DAG/CI evidence |

[Topology](diagrams/topology.mmd) · [SIPOC](diagrams/sipoc.mmd) · [Kahn lanes](diagrams/kahn-lanes.mmd) · [sequence](diagrams/roundtrip-sequence.mmd) · [states](diagrams/admission-state.mmd)

## Direction A — Drive to GitHub

1. Acquire the authorized Drive object and revision; compute real byte SHA-256 where bytes are available.
2. Validate GMI manifest, artifact refs, evidence class, path safety and idempotency using existing GEMINI modules.
3. Pin Git repository/default branch, exact base/head SHAs and blob identities; stale or ungrounded refs HOLD.
4. Build deterministic Kahn DAG. A successor is eligible only after all predecessor receipts are committed and verified. Unrelated workers may run concurrently only with disjoint exclusive resources.
5. Produce a bounded patch plan; classify CLEAN / THREE_WAY / CONFLICT. Do not auto-fix unreviewed conflicts or accept simulated approvals.
6. On a separately authorized runner, apply changes to an isolated feature branch and create a draft PR. Require native exact-head checks, negative controls, independent review, effective branch protection and last-push review freshness.
7. Observe the authorized merge SHA; publish a **new versioned Drive snapshot** with manifest and readback receipt. Do not overwrite unpublished agent edits.

No step in this document grants broker rights or bypasses reviewer admission. Existing PR #40 and #41 are competing OFFLINE dry-run candidates, not a production step 6.

## Direction B — GitHub to Drive

Receive a verified merge event or manual refresh request; query GitHub's current protected HEAD and exact commit; use existing src/repo_snapshot.py to export a plain-file immutable snapshot and per-blob manifest without .git; verify the complete snapshot; upload as a new Drive revision/snapshot with a separately approved Drive writer; update a pointer only after readback. A Drive proposal based on an older commit becomes STALE/RECONCILE, never last-writer-wins.

Webhooks trigger re-census; their event bodies are not source authority. Enable only after a real public HTTPS receiver checks X-Hub-Signature-256, delivery idempotency, repo allowlist and current ref.

## Kahn and recursive epochs

Edges represent finish-to-commit dependencies. The graph must be acyclic. Independent branches can be scheduled in parallel with exclusive write-resource locks; the critical path is the longest dependency-weighted path. Synthetic estimates must not be presented as observed runtime. A repeat/recursion creates a new bounded epoch with parent/source receipts, never a cycle in the same graph.

## Repository authority map

- GBOGEB/GEMINI (main): cross-agent GMI contract, ingress and snapshot publication specification.
- GBOGEB/pipeline-automation-hub (master): global CI/DAG observability and merge governance.
- GBOGEB/CODEX (main): coding agents, governance and orchestration interfaces.
- GBOGEB/ABACUS (main): native runtime/QA, first-red and adversarial tests.
- GBOGEB/gg_MATH (main): numerical algorithms and confidence evidence.
- GBOGEB/DOCX_RTM_Automation (main): binary generation/render/format QA.
- GBOGEB/cryoplant-project (main): contract/engineering/QPS domain acceptance.

## BridgeFlow and legacy ARGON migration

The Drive generic package already provides a tested *synthetic* Kahn scheduler and offline outputs. Integrate via typed adapter only after native GEMINI validator and owner test parity; do not duplicate it. Legacy argon_bidirectional_git_drive_sync.sh contains a direct push-to-main and references a default remote not established as a governed canonical repository. Its broker's static demonstration HMAC seed and simulated COMMITTED states are **not** production authentication/provenance. Preserve these assets, disable their production use, and replace direct pushes with draft-PR admission.

Historical R2-W2 PRs #40 and #41 proposed different wire profiles and are now both merged (verified 2026-11-10). Audit the final mainline contract, negative tests and lineage; do not assume that merge proves profile parity, IC3 or hosted transport.