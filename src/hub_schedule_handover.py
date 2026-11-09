"""Non-authoritative Hub ISO schedule -> native GEMINI handover manifest adapter.

This is a *candidate metadata projection*, not a Drive transport, a GitHub
dispatcher, schedule proof, or engineering approval. Use the existing
handover_package.validate_manifest for the GEMINI schema and verdict.
"""
from __future__ import annotations

import re

from src.handover_package import canonical_manifest_digest

SOURCE_REPO = "GBOGEB/pipeline-automation-hub"
SCHEDULE_SCHEMA = "jade.iso-schedule.v1"
SCHEDULE_METHOD = "JADE_ISO_SCHEDULE_PORTABLE_RECEIPT_V1"
HUB_UTF8_WIRE = "JADE_CANONICAL_UTF8_JSON_V1"
SOURCE_PREFIX = "mission-control/jade_temple/"
_SHA = re.compile(r"[0-9a-f]{40}")
_GMI = re.compile(r"GMI-[A-Za-z0-9_-]+")


def hub_schedule_manifest(*, session_id: str, generated_at: str,
                          source_sha: str, source_path: str,
                          receipt: dict) -> dict:
    """Map a pinned plan-only Hub receipt into GEMINI's existing v1 manifest.

    Raw schedule/task bodies, Drive objects, user tokens and private project
    evidence are intentionally not embedded in the public GitHub manifest.
    Neither this projection nor native manifest schema ACCEPT makes a
    schedule a verified execution result.
    """
    if not isinstance(session_id, str) or not _GMI.fullmatch(session_id):
        raise ValueError("session_id must be a GMI-* identifier")
    if not isinstance(generated_at, str) or not generated_at.strip():
        raise ValueError("generated_at is required")
    if not isinstance(source_sha, str) or not _SHA.fullmatch(source_sha):
        raise ValueError("source_sha must be an exact 40-digit lowercase hex Git commit")
    if not isinstance(source_path, str) or not source_path.startswith(SOURCE_PREFIX):
        raise ValueError("source_path must be a JADE Hub path")
    if ".." in source_path.split("/") or source_path.endswith("/"):
        raise ValueError("unsafe source path")
    if not isinstance(receipt, dict):
        raise TypeError("receipt must be a mapping")
    if (receipt.get("schema") != SCHEDULE_SCHEMA or
            receipt.get("status") != "DECLARED_PLAN_ONLY" or
            receipt.get("authority_transfer") is not False):
        raise ValueError("only unpromoted Hub schedule plan receipts are accepted")
    year = receipt.get("iso_year")
    if type(year) is not int or not (1 <= year <= 9999):
        raise ValueError("schedule iso_year must be explicit")
    if receipt.get("generation_method") != SCHEDULE_METHOD:
        raise ValueError("unsupported Hub generation method")
    if not isinstance(receipt.get("tasks"), dict) or not receipt["tasks"]:
        raise ValueError("a non-empty task map must have been validated by Hub")
    if not isinstance(receipt.get("waves"), list) or not receipt["waves"]:
        raise ValueError("Hub schedule waves are missing")
    digest = receipt.get("receipt_sha256")
    if not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
        raise ValueError("receipt_sha256 must be an actual lowercase SHA-256 digest")
    payload = {key: value for key, value in receipt.items() if key != "receipt_sha256"}
    wire_format = receipt.get("canonicalization")
    if "canonicalization" in receipt and wire_format != HUB_UTF8_WIRE:
        raise ValueError("unsupported Hub canonicalization profile")

    if wire_format == HUB_UTF8_WIRE:
        # Strict profile, without implementing a second digest/canonicalizer.
        # ASCII keys and integer-only JSON values allow cross-runtime stable sorting.
        def validate_wire(value):
            if type(value) is dict:
                for key, item in value.items():
                    if type(key) is not str or not key.isascii():
                        raise ValueError("Hub UTF-8 receipt object keys must be ASCII")
                    validate_wire(item)
            elif type(value) is list:
                for item in value:
                    validate_wire(item)
            elif type(value) not in (str, int, bool, type(None)):
                raise ValueError("unsupported Hub UTF-8 receipt value type")

        validate_wire(payload)
        try:
            calculated = canonical_manifest_digest(payload, ensure_ascii=False)
        except UnicodeEncodeError as exc:
            raise ValueError("Hub UTF-8 receipt contains a lone surrogate") from exc
    else:
        # Backwards compatibility for existing unversioned GMI/Hub candidates.
        calculated = canonical_manifest_digest(payload)
    if calculated != digest:
        raise ValueError("Hub schedule receipt digest mismatch")
    # The digest is a payload-integrity check, not Git source authentication.
    # GEMINI stores a reference, not a second copy of the Hub DAG, and cannot
    # verify its semantics without source-pinned Hub native tests.
    return {
        "schema_version": 1,
        "session_id": session_id,
        "source_agent": "GBOGEB/pipeline-automation-hub:iso_schedule",
        "generated_at": generated_at,
        "status": "DECLARED",
        "scope": "Source-pinned read-only ISO week schedule proposal; no execution or owner approval",
        "source_refs": [{
            "repository_full_name": SOURCE_REPO,
            "source_path": source_path,
            "source_sha": source_sha,
            "schema_version": SCHEDULE_SCHEMA,
            "generation_method": SCHEDULE_METHOD,
            "receipt_sha256": digest,
            "source_visibility": "PUBLIC",
            "validation_status": "EXTERNAL_NATIVE_QA_PENDING",
            "owner_disposition": "NOT_APPROVED",
        }],
        "artifact_refs": [],
        "current_gate": "HUB_EXACT_HEAD_NATIVE_QA_AND_OWNER_REVIEW_PENDING",
        "next_action": "Validate source SHA and native Hub QA; reconcile with existing Drive package; do not auto-merge",
    }
