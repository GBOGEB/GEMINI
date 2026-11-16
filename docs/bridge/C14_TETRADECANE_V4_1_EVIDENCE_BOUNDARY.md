# C14 Tetradecane — v4.1 source accounting and B42 reconciliation (2026-11-16)

**Intent owner:** [GEMINI #56](https://github.com/GBOGEB/GEMINI/issues/56). This is a **public-safe, metadata-only proposed contract**. The private Drive worktree remains a projection, not engineering/source authority.

## Current observed repository evidence

- [document-organization-system #85](https://github.com/GBOGEB/document-organization-system/pull/85): MERGED. Reuse satellite renderer and guarded hydrator; do not create another HMI engine.
- [document-organization-system #87](https://github.com/GBOGEB/document-organization-system/pull/87): MERGED. Reuse RFC 3986 URI resolver; AD13-specific meaning still requires source interpretation.
- [gg_MATH #139](https://github.com/GBOGEB/gg_MATH/pull/139): MERGED.
- [gg_MATH #140](https://github.com/GBOGEB/gg_MATH/pull/140): OPEN, no eligible APPROVED review observed in the reconciliation. Exact head can drift; reread before any admission.

## B42 routing

| Node | Repo receiver | Disposition |
|---|---|---|
| C9_Nonane | document-organization-system | Reuse existing #87 URI resolver; proposed AD13 mappings require target-scoped tests |
| C6_Hexane | cryoplant-project (candidate) | `HOLD_ENGINEERING`; the proposed cryogenic-project name did not resolve; controlled source/owner pending |
| C4_Butane | ABACUS | `SOURCE_PATH_HOLD`; two named files absent on observed default branch |
| C14_Tetradecane | GEMINI | This metadata-only gate; private source proofs remain outside this public repo |
| C15_Pentadecane | pipeline-automation-hub | Reuse [#1230](https://github.com/GBOGEB/pipeline-automation-hub/issues/1230) session owner; no duplicate DAG or extractor |

## Evidence and DoV

The private v4.0 set contains three raw file snapshots with computed local SHA-256 and two native Google Docs whose *exported text* has been hashed. Original raw HTML/TXT byte equivalence remains **unverified**. Declared A–H arithmetic reconciles 141 rows minus three overlaps to 138 declared unique entries (114 proposed safe candidates / 19 local checks / five hold); no immutable chat-ID crosswalk is independently proved. The **deletion-eligible count is zero**.

This PR changes **only the public, fail-closed metadata gate and its regression tests**. It must not include private Drive IDs, chat titles, controlled QPS technical requirements, raw archive bytes or user paths.

## Admission controls

- [x] Public-safe source accounting contract
- [x] Defined conservative 3 raw / 2 derived source fidelity classes
- [ ] Native exact-head CI and independent human review
- [ ] Verify 19 local source objects with owner-authorized physical hashes, then original chat identity
- [ ] Engineering source disposition for helium/SIL/LOPA/RTM/5G requirements under [cryoplant-project #2334](https://github.com/GBOGEB/cryoplant-project/issues/2334)
- [ ] Source-owner G0–G5 acceptance and release decision

**Disposition:** `SOURCE_ACCOUNTING_HOLD / LOSSLESS_NOT_VERIFIED / DELETION_AUTHORIZED_FALSE / MERGE_AUTHORIZED_FALSE`.
