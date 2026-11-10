# GBOGEB/GEMINI — Federation Core

**Release:** F01/F02 review candidate, 2026-11-09. **State:** architecture DECLARED; external authorization and hosted synchronization UNVERIFIED.

GEMINI is the **governed cross-agent contract and handover surface** in the GBOGEB federation. Keep existing BLSN and bridge modules, and do not create a duplicate orchestration platform.

## Readable assets and navigation

- [Architecture and authority boundaries](architecture.md)
- [GitHub App, OAuth and webhook setup](github-app-auth.md)
- [Contract registry and recursive BD queue](contracts-bdq.md)
- [All five diagrams — GitHub Mermaid preview](diagrams/rendered.md)
- [Topology diagram](diagrams/topology.mmd)
- [SIPOC](diagrams/sipoc.mmd)
- [Kahn dependency/worker lanes](diagrams/kahn-lanes.mmd)
- [Bidirectional synchronization sequence](diagrams/roundtrip-sequence.mmd)
- [Review/merge admission state machine](diagrams/admission-state.mmd)

## Proven reuse and source ownership

- Existing GEMINI: src/drive_ingress.py (read-only), src/drive_materialize.py (bundle worktrees), src/repo_snapshot.py (exact Git snapshot), src/handover_package.py, src/handover_batch.py, src/federation_bridge.py.
- [Drive portable worktree](https://drive.google.com/drive/folders/1GMMHGux7x_xgZplqRk0_xEUix7gPJuo-) and [BridgeFlow generic package](https://drive.google.com/drive/folders/1dw2Zy1I-cylXYqGThLRaPJ4HSRhJZV7p) are the already-preserved source assets; no replacement worktree is created by this documentation.
- Hub owns portfolio DAG/CI observability (default branch master); CODEX owns code-agent runtime; ABACUS owns QA and first reds; gg_MATH owns numerical methods; DOCX_RTM_Automation owns document/binary QA; cryoplant-project owns engineering authority.

## Non-negotiable boundaries

Google Drive is persistent source/handover storage, NOT a Git remote. GitHub protected branches are authoritative for reviewed Git history. SHA-256 files, Git object IDs, Drive-native revisions and CI/review approvals are different proof types.

No universal AI token, credentials in Drive, direct default-branch push, automatic merge on red, or overwrite of unpublished Drive edits. A local synthetic PASS does not prove native CI, hosted Google WIF, user consent, PR review or merge.

The legacy Drive shell script has a direct push-to-main mode and the legacy broker has hard-coded demonstration signing material and simulated peer states: classify both LEGACY_ADAPTER_HOLD, preserve originals, do not run as production sync.

Historical GEMINI R2-W2 broker PRs [#40](https://github.com/GBOGEB/GEMINI/pull/40) and [#41](https://github.com/GBOGEB/GEMINI/pull/41) are now **MERGED**, as observed on 2026-11-10. Their source-contract compatibility and hosted IC3/round-trip proof remain separate reconciliation gates. See [F02 operating procedure](operations.md) and [inert policy](../../../config/federation/governed_broker.v1.json).
