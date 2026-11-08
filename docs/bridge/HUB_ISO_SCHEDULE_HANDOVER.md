# Hub ISO-schedule plan → GEMINI handover bridge (candidate, v0)

**Purpose:** reuse the existing GEMINI `src/handover_package.py` validator for a schedule receipt **without** copying Hub's Kahn implementation, BridgeFlow's worker runtime, or QPS's private bidder evidence.

- **Hub owner:** `GBOGEB/pipeline-automation-hub` `mission-control/jade_temple/tools/iso_schedule.py` (`jade.iso-schedule.v1`); the Hub owns date validation, topological layering, dependency waves, Gantt and DAG projection.
- **Integrity binding:** Hub `portable_receipt(plan)` emits a JSON-native `jade.iso-schedule.v1` object with `generation_method: JADE_ISO_SCHEDULE_PORTABLE_RECEIPT_V1` and a SHA-256 over canonical JSON excluding `receipt_sha256`. GEMINI recomputes it using the existing `handover_package.canonical_manifest_digest`; the transfer digest is not Git SHA, a signature or proof that the schedule ran.
- **Related non-overlapping work:** GEMINI #38 is the merged offline repo snapshot contract and GEMINI #41 is a separate offline proposal broker. Neither their files nor the generic BridgeFlow worktree are copied into this adapter. The existing `gmi_handover_tests.yml` is owned by #41 and not changed in this PR.
- **GEMINI owner:** `src/hub_schedule_handover.py` (thin candidate metadata map), `src/handover_package.py` (canonical schema and v1 native ACCEPT/REJECT/DEFER verdict), existing `src/drive_ingress.py` (read-only scoped Drive transport).
- **Existing Drive worktree:** generic BridgeFlow and ARGON candidate assets remain independently governed in Google Drive. They are NOT copied into this public repository.
- **Future consumers:** ABACUS runner, CODEX governance, gg_MATH kernels, QPS/private engineering, DOCX_RTM_Automation builder. Only use source-digest-bound receipt APIs; no unchecked authority transfer.

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
