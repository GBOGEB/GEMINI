import hashlib
from pathlib import Path

import yaml

from src.handover_package import validate_package


def _manifest() -> dict:
    return {
        "schema_version": 1,
        "session_id": "GMI-TEST-001",
        "source_agent": "Gemini",
        "generated_at": "2026-09-18T00:00:00Z",
        "status": "DECLARED",
        "scope": "test package",
        "source_refs": [],
        "artifact_refs": [],
        "current_gate": "PACKAGE_VALIDATION",
        "next_action": "review",
    }


def _write_manifest(package: Path, manifest: dict) -> None:
    target = package / "MANIFEST" / "manifest.yaml"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")


def test_valid_local_file_and_real_hash_accept(tmp_path: Path) -> None:
    package = tmp_path / "GMI-TEST-001"
    artifact = package / "ARTIFACTS" / "payload.txt"
    artifact.parent.mkdir(parents=True)
    artifact.write_bytes(b"payload\n")
    manifest = _manifest()
    manifest["artifact_refs"] = [
        {
            "id": "payload",
            "type": "local_file",
            "path": "ARTIFACTS/payload.txt",
            "sha256": hashlib.sha256(b"payload\n").hexdigest(),
        }
    ]
    _write_manifest(package, manifest)

    receipt = validate_package(package)
    assert receipt["verdict"] == "ACCEPT"
    assert receipt["errors"] == []


def test_missing_manifest_rejects(tmp_path: Path) -> None:
    receipt = validate_package(tmp_path / "GMI-TEST-001")
    assert receipt["verdict"] == "REJECT"
    assert "manifest missing" in receipt["errors"]


def test_path_escape_rejects(tmp_path: Path) -> None:
    package = tmp_path / "GMI-TEST-001"
    manifest = _manifest()
    manifest["artifact_refs"] = [
        {"type": "local_file", "path": "../outside.txt", "required": True}
    ]
    _write_manifest(package, manifest)

    receipt = validate_package(package)
    assert receipt["verdict"] == "REJECT"
    assert any("escapes the package root" in error for error in receipt["errors"])


def test_hash_mismatch_rejects(tmp_path: Path) -> None:
    package = tmp_path / "GMI-TEST-001"
    artifact = package / "ARTIFACTS" / "payload.txt"
    artifact.parent.mkdir(parents=True)
    artifact.write_text("real", encoding="utf-8")
    manifest = _manifest()
    manifest["artifact_refs"] = [
        {
            "type": "local_file",
            "path": "ARTIFACTS/payload.txt",
            "sha256": "0" * 64,
        }
    ]
    _write_manifest(package, manifest)

    receipt = validate_package(package)
    assert receipt["verdict"] == "REJECT"
    assert any("SHA-256 mismatch" in error for error in receipt["errors"])


def test_drive_native_revision_without_sha_is_valid(tmp_path: Path) -> None:
    package = tmp_path / "GMI-TEST-001"
    manifest = _manifest()
    manifest["artifact_refs"] = [
        {
            "id": "native-doc",
            "type": "drive_native",
            "drive_file_id": "1abc",
            "drive_revision_id": "rev-7",
            "sha256": None,
        }
    ]
    _write_manifest(package, manifest)

    receipt = validate_package(package)
    assert receipt["verdict"] == "ACCEPT"


def test_drive_native_revision_cannot_claim_sha(tmp_path: Path) -> None:
    package = tmp_path / "GMI-TEST-001"
    manifest = _manifest()
    manifest["artifact_refs"] = [
        {
            "type": "drive_native",
            "drive_file_id": "1abc",
            "drive_revision_id": "rev-7",
            "sha256": "a" * 64,
        }
    ]
    _write_manifest(package, manifest)

    receipt = validate_package(package)
    assert receipt["verdict"] == "REJECT"
    assert any("not a SHA-256" in error for error in receipt["errors"])


def test_optional_missing_artifact_defers(tmp_path: Path) -> None:
    package = tmp_path / "GMI-TEST-001"
    manifest = _manifest()
    manifest["artifact_refs"] = [
        {
            "type": "local_file",
            "path": "ARTIFACTS/not-yet-present.bin",
            "required": False,
        }
    ]
    _write_manifest(package, manifest)

    receipt = validate_package(package)
    assert receipt["verdict"] == "DEFER"
    assert receipt["errors"] == []
    assert receipt["deferred"]


def test_unsupported_schema_and_empty_governance_values_reject(tmp_path: Path) -> None:
    package = tmp_path / "GMI-TEST-001"
    manifest = _manifest()
    manifest["schema_version"] = 999
    manifest["source_agent"] = None
    manifest["scope"] = ""
    _write_manifest(package, manifest)

    receipt = validate_package(package)
    assert receipt["verdict"] == "REJECT"
    assert any("schema_version" in error for error in receipt["errors"])
    assert any("source_agent" in error for error in receipt["errors"])
    assert any("scope" in error for error in receipt["errors"])


def test_non_scalar_status_returns_structured_reject(tmp_path: Path) -> None:
    package = tmp_path / "GMI-TEST-001"
    manifest = _manifest()
    manifest["status"] = []
    _write_manifest(package, manifest)

    receipt = validate_package(package)
    assert receipt["verdict"] == "REJECT"
    assert "status must be a string" in receipt["errors"]


def test_invalid_utf8_manifest_returns_structured_reject(tmp_path: Path) -> None:
    package = tmp_path / "GMI-TEST-001"
    target = package / "MANIFEST" / "manifest.yaml"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"schema_version: 1\nsource_agent: \xff\xfe\n")

    receipt = validate_package(package)
    assert receipt["verdict"] == "REJECT"
    assert any("manifest load failed" in error for error in receipt["errors"])
