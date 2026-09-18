from pathlib import Path

import yaml

from src.handover_census import EVIDENCE_STATES, build_census, validate_receipt


def test_current_receipts_are_valid() -> None:
    census = build_census()
    assert census["receipt_count"] >= 1
    assert census["invalid_count"] == 0
    assert census["valid_count"] == census["receipt_count"]


def test_invalid_compound_status_fails_closed(tmp_path: Path) -> None:
    receipt = {
        "schema_version": 1,
        "receipt_type": "drive_ingress",
        "session_id": "GMI-TEST-001",
        "source_agent": "Gemini",
        "status": "VERIFIED_CONNECTOR_READ",
        "current_gate": "TEST",
        "next_action": "None",
    }
    path = tmp_path / "bad.yaml"
    path.write_text(yaml.safe_dump(receipt), encoding="utf-8")
    assert any("invalid status" in error for error in validate_receipt(path))


def test_evidence_state_contract_is_closed_set() -> None:
    assert EVIDENCE_STATES == {
        "VERIFIED",
        "IMPLEMENTED",
        "DECLARED",
        "INFERRED",
        "PARTIAL",
        "DEFERRED",
    }

def test_census_ignores_non_gmi_receipt_namespaces(tmp_path: Path) -> None:
    gmi = {
        "schema_version": 1,
        "receipt_type": "drive_ingress",
        "session_id": "GMI-TEST-001",
        "source_agent": "Gemini",
        "status": "DECLARED",
        "current_gate": "TEST",
        "next_action": "Review",
    }
    (tmp_path / "GMI-TEST-001.yaml").write_text(
        yaml.safe_dump(gmi), encoding="utf-8"
    )
    (tmp_path / "R3-FOREIGN-RECEIPT.yaml").write_text(
        yaml.safe_dump({"schema_version": 99, "status": "PASS"}), encoding="utf-8"
    )

    census = build_census(tmp_path)
    assert census["receipt_count"] == 1
    assert census["invalid_count"] == 0
    assert census["receipts"][0]["session_id"] == "GMI-TEST-001"

