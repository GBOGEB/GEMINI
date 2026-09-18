"""Bind GMI content and IC3 transport evidence without allowing compensation."""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any

BATCH_VERDICTS = {"ACCEPT", "REJECT", "DEFER"}
IC3_PASS_RESULT = "PASS"
IC3_PASS_CLASSIFICATION = "IC3_DRIVE_READONLY_GT0_STEP_PASS"


def _content_gate(batch_receipt: dict[str, Any]) -> dict[str, Any]:
    verdict = batch_receipt.get("batch_verdict")
    package_count = batch_receipt.get("package_count")

    if verdict not in BATCH_VERDICTS:
        return {
            "state": "REJECT",
            "classification": "BATCH_RECEIPT_INVALID",
            "source_verdict": verdict,
            "package_count": package_count,
        }

    if verdict == "REJECT":
        return {
            "state": "REJECT",
            "classification": "BATCH_REJECTED",
            "source_verdict": verdict,
            "package_count": package_count,
        }

    if verdict == "DEFER":
        return {
            "state": "DEFER",
            "classification": "BATCH_DEFERRED",
            "source_verdict": verdict,
            "package_count": package_count,
        }

    if not isinstance(package_count, int) or isinstance(package_count, bool) or package_count <= 0:
        return {
            "state": "DEFER",
            "classification": "BATCH_ZERO_OR_UNPROVEN_PACKAGES",
            "source_verdict": verdict,
            "package_count": package_count,
        }

    return {
        "state": "ACCEPT",
        "classification": "BATCH_ACCEPTED_GT0_PACKAGES",
        "source_verdict": verdict,
        "package_count": package_count,
    }


def _transport_gate(ic3_status: dict[str, Any]) -> dict[str, Any]:
    result = ic3_status.get("result")
    classification = ic3_status.get("classification")

    if result == IC3_PASS_RESULT and classification == IC3_PASS_CLASSIFICATION:
        return {
            "state": "PASS",
            "classification": IC3_PASS_CLASSIFICATION,
            "source_result": result,
        }

    if not isinstance(result, str) or not isinstance(classification, str):
        observed = "IC3_RECEIPT_INVALID"
    elif result == "FAIL":
        observed = classification
    else:
        observed = "IC3_NOT_PROVEN"

    return {
        "state": "WITHHELD",
        "classification": observed,
        "source_result": result,
        "source_classification": classification,
    }


def bind_evidence(
    batch_receipt: dict[str, Any],
    ic3_status: dict[str, Any],
) -> dict[str, Any]:
    """Return a control receipt while leaving both evidence inputs unchanged."""

    if not isinstance(batch_receipt, dict):
        raise TypeError("batch_receipt must be a mapping")
    if not isinstance(ic3_status, dict):
        raise TypeError("ic3_status must be a mapping")

    batch_before = copy.deepcopy(batch_receipt)
    ic3_before = copy.deepcopy(ic3_status)

    content = _content_gate(batch_receipt)
    transport = _transport_gate(ic3_status)

    ready = content["state"] == "ACCEPT" and transport["state"] == "PASS"
    blockers: list[str] = []
    if transport["state"] != "PASS":
        blockers.append(f"transport:{transport['classification']}")
    if content["state"] != "ACCEPT":
        blockers.append(f"content:{content['classification']}")

    if batch_receipt != batch_before or ic3_status != ic3_before:
        raise RuntimeError("evidence binding must not mutate source receipts")

    return {
        "schema_version": 1,
        "receipt_type": "gmi_evidence_binding",
        "transport_gate": transport,
        "content_gate": content,
        "control_readiness": "READY_FOR_REVIEW" if ready else "WITHHELD",
        "blockers": blockers,
        "non_compensation": True,
        "source_claims_promoted": False,
        "authority_transfer": False,
        "formal_credit_delta": 0,
    }


def _load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise TypeError(f"{path}: JSON root must be a mapping")
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch", type=Path, required=True)
    parser.add_argument("--ic3", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    binding = bind_evidence(_load_json(args.batch), _load_json(args.ic3))
    rendered = json.dumps(binding, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")

    return 0 if binding["control_readiness"] == "READY_FOR_REVIEW" else 1


if __name__ == "__main__":
    raise SystemExit(main())
