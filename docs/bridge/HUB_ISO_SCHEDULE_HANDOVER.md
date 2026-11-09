# Hub ISO-schedule plan → GEMINI handover bridge (candidate, v0)

**Purpose:** reuse the existing GEMINI `src/handover_package.py` validator for a schedule receipt **without** copying Hub's Kahn implementation, BridgeFlow's worker runtime, or QPS's private bidder evidence.

- **Hub owner:** `GBOGEB/pipeline-automation-hub` `mission-control/jade_temple/tools/iso_schedule.py` (`jade.iso-schedule.v1`); the Hub owns date validation, topological layering, dependency waves, Gantt and DAG projection.
- **Integrity binding:** Hub `portable_receipt(plan)` now emits `canonicalization: JADE_CANONICAL_UTF8_JSON_V1` and a SHA-256 of exactly the unsigned, sorted-ASCII-key, compact JSON payload encoded with raw UTF-8 Unicode scalar values (no BOM/newline; array order preserved). GEMINI recomputes it using the **existing** `handover_package.canonical_manifest_digest(..., ensure_ascii=False)` owner. The default `ensure_ascii=True` is unchanged for all legacy GMI callers. Unversioned old Hub candidates retain the original ASCII-escaped digest until retired with a separate governed decision. This checksum is not Git SHA, a signature or proof that the schedule ran.
- **Related non-overlapping work:** GEMINI #38 is the merged offline repo snapshot contract and GEMINI #41 is a separate offline proposal broker. Neither their files nor the generic BridgeFlow worktree are copied into this adapter. The existing `gmi_handover_tests.yml` is owned by #41 and not changed in this PR.
- **GEMINI owner:** `src/hub_schedule_handover.py` (thin candidate metadata map), `src/handover_package.py` (canonical schema and v1 native ACCEPT/REJECT/DEFER verdict), existing `src/drive_ingress.py` (read-only scoped Drive transport).
- **Existing Drive worktree:** generic BridgeFlow and ARGON candidate assets remain independently governed in Google Drive. They are NOT copied into this public repository.
- **Future consumers:** ABACUS runner, CODEX governance, gg_MATH kernels, QPS/private engineering, DOCX_RTM_Automation builder. Only use source-digest-bound receipt APIs; no unchecked authority transfer.

## Compatibility DoD / DoV (source-bound)

This bridge has **two noninterchangeable wire profiles**. Never guess the profile from the title contents or silently try both hashes. An absent `canonicalization` means the historical escaped-ASCII GMI digest; an explicit `JADE_CANONICAL_UTF8_JSON_V1` means raw UTF-8 with recursively sorted ASCII object keys, JSON compact separators and no Unicode normalization. Unsupported profile identifiers, non-ASCII keys, floats and lone surrogates fail closed for the versioned mode. Do not change or duplicate the GMI manifest schema or its digest owner.

**Cross-language vector:** Synthetic Hub plan `CAFE`, title `Café 🔬/∆`, `2026-w46MON` through the same date, no predecessors. The versioned unsigned payload hashes to:

```text
bb7d5953a763eed0e7b9d0cd7741f7ae2c128d5305677884d44fbd8038b80c17
```

Python's legacy `ensure_ascii=True` hashes the *same* versioned record to `ddbb0ba85716d73267ca18d1cafe2fb9a3af0e378fa0ff3b6c3679704cce976b`, deliberately **not** accepted for the new profile. Independent Node.js `JSON.stringify` of recursively ASCII-sorted fields yields the UTF-8 digest above. Hub owns wire generation at [Hub #1138](https://github.com/GBOGEB/pipeline-automation-hub/pull/1138); GEMINI owns candidate transport at this adapter. Neither may claim that a matching digest certifies authenticated source, Drive ACL, executed jobs or owner approval.

**Minimum DoD:** one version-selected verification branch; backwards compatibility for legacy GMI digests; positive vector; negative stale/tampered/unknown-profile/type/Unicode cases; no new Drive API, no branch push, no engineering or contract authority.

**Minimum DoV:** native GEMINI tests collect >0 cases on this PR's **exact head**, verify the fixture bytes/digest against Hub's pinned source, retain existing GMI regressions, pass relevant required checks, receive independent code review after last push, and obtain owner merge admission. Until all pass, `DRAFT / NOT_APPROVED / EXTERNAL_NATIVE_QA_PENDING`. [IC3 external auth](https://github.com/GBOGEB/GEMINI/issues/12) remains separately blocked; no manual connector access substitutes for hosted WIF proof.

## Minimal use

```python
from pathlib import Path
from src.hub_schedule_handover import hub_schedule_manifest
from src.handover_package import validate_manifest

# For illustration only; the real value must come from exact-commit Hub validation.
verified_hub_source_sha = "a" * 40  # synthetic; do NOT use for a real receipt
hub_plan = {
    "schema": "jade.iso-schedule.v1", "iso_year": 2026,
    "status": "DECLARED_PLAN_ONLY", "authority_transfer": False,
    "generation_method": "JADE_ISO_SCHEDULE_PORTABLE_RECEIPT_V1",
    "tasks": {"SAMPLE": {"id": "SAMPLE"}}, "waves": [["SAMPLE"]],
}
from src.handover_package import canonical_manifest_digest
hub_plan["receipt_sha256"] = canonical_manifest_digest(hub_plan)
manifest = hub_schedule_manifest(
    session_id="GMI-synthetic-hub", generated_at="2026-11-09T00:00:00Z",
    source_sha=verified_hub_source_sha,
    source_path="mission-control/jade_temple/tools/iso_schedule.py",
    receipt=hub_plan,
)
assert not validate_manifest(manifest, Path(".").resolve())["errors"]
assert manifest["status"] == "DECLARED"
assert manifest["source_refs"][0]["receipt_sha256"] == hub_plan["receipt_sha256"]
```

**Schema acceptance and a matching transport digest only prove that the declared candidate is structurally valid and its JSON payload is intact.** It does not certify its Hub commit SHA, Hub's source content, the release/CI head, signed runner evidence, owner approval, project schedule commitment, execution, or Drive-file revision. Source/digest authentication and independent review remain outstanding.

## Noncompensating admission gates

1. Read the **existing** Drive/GMI package through an independently authorized connector and preserve native Drive revision identity, not a fabricated SHA.
2. Resolve the exact `GBOGEB/pipeline-automation-hub` commit and run native Hub schedule tests and Kahn dependency checks. Reject cycles, missing parents, unknown ISO week-years, invalid w53, and serial-edge violations.
3. Bind an immutable `source_sha`, source file path, schema, provenance, source visibility, validation status and owner disposition into the candidate manifest.
4. Validate against `handover_package.validate_manifest`. A native schema `ACCEPT` does **not** promote `DECLARED` to `VERIFIED`.
5. Request an independent review and read effective GitHub required checks/last-push rules at exact head before any downstream consumption. No unreviewed branch or credential bypass.
6. Keep the owner QPS Addendum II / RTM / OFFER / commercial decision controls and any 93% confidence challenge completely independent of schedule/transport success.

Test:

```bash
python -m unittest discover -s tests -p test_hub_schedule_handover.py -v
```

**Status:** `CANDIDATE_METADATA_ADAPTER / NATIVE_GEMINI_SCHEMA_TEST_EXPECTED / REAL_DRIVE_INGRESS_DEFERRED / HUB_HEAD_QA_DEFERRED / NO_AUTO_MERGE`.
