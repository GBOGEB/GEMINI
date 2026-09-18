"""Validate and census governed cross-agent handover receipts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RECEIPTS = ROOT / "handover" / "receipts"
EVIDENCE_STATES = {"VERIFIED", "IMPLEMENTED", "DECLARED", "INFERRED", "PARTIAL", "DEFERRED"}
REQUIRED_RECEIPT_FIELDS = {
    "schema_version",
    "receipt_type",
    "session_id",
    "source_agent",
    "status",
    "current_gate",
    "next_action",
}


def _load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise TypeError(f"{path}: YAML root must be a mapping")
    return data


def validate_receipt(path: Path) -> list[str]:
    data = _load_yaml(path)
    errors: list[str] = []
    missing = sorted(REQUIRED_RECEIPT_FIELDS - data.keys())
    if missing:
        errors.append(f"missing required fields: {', '.join(missing)}")
    status = data.get("status")
    if status not in EVIDENCE_STATES:
        errors.append(f"invalid status {status!r}; expected one of {sorted(EVIDENCE_STATES)}")
    session_id = data.get("session_id")
    if not isinstance(session_id, str) or not session_id.startswith("GMI-"):
        errors.append("session_id must be a GMI-* string")
    return errors


def build_census(receipts_dir: Path = DEFAULT_RECEIPTS) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    invalid = 0
    for path in sorted(receipts_dir.glob("GMI-*.yaml")):
        data = _load_yaml(path)
        errors = validate_receipt(path)
        if errors:
            invalid += 1
        entries.append(
            {
                "path": str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path),
                "session_id": data.get("session_id"),
                "receipt_type": data.get("receipt_type"),
                "status": data.get("status"),
                "event": data.get("event"),
                "current_gate": data.get("current_gate"),
                "valid": not errors,
                "errors": errors,
            }
        )
    return {
        "schema_version": 1,
        "receipt_count": len(entries),
        "valid_count": len(entries) - invalid,
        "invalid_count": invalid,
        "evidence_states": sorted(EVIDENCE_STATES),
        "receipts": entries,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipts", type=Path, default=DEFAULT_RECEIPTS)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    census = build_census(args.receipts)
    rendered = json.dumps(census, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 1 if census["invalid_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
