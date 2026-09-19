from pathlib import Path

import yaml

from src.handover_batch import build_batch_census, load_ledger


def _manifest(session_id: str, scope: str = "test") -> dict:
    return {
        "schema_version": 1,
        "session_id": session_id,
        "source_agent": "Gemini",
        "generated_at": "2026-09-18T00:00:00Z",
        "status": "DECLARED",
        "scope": scope,
        "source_refs": [],
        "artifact_refs": [],
        "current_gate": "BATCH_VALIDATION",
        "next_action": "review",
    }


def _package(workspace: Path, dirname: str, manifest: dict) -> Path:
    package = workspace / dirname
    target = package / "MANIFEST" / "manifest.yaml"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    return package


def test_new_then_unchanged_is_idempotent(tmp_path: Path) -> None:
    _package(tmp_path, "GMI-A", _manifest("GMI-A"))

    first = build_batch_census(tmp_path)
    assert first["batch_verdict"] == "ACCEPT"
    assert first["packages"][0]["idempotency_state"] == "NEW"

    second = build_batch_census(tmp_path, first["updated_ledger"])
    assert second["batch_verdict"] == "ACCEPT"
    assert second["packages"][0]["idempotency_state"] == "UNCHANGED"
    assert (
        second["packages"][0]["idempotency_key"]
        == first["packages"][0]["idempotency_key"]
    )


def test_manifest_change_is_classified_changed(tmp_path: Path) -> None:
    _package(tmp_path, "GMI-A", _manifest("GMI-A"))
    first = build_batch_census(tmp_path)

    _package(tmp_path, "GMI-A", _manifest("GMI-A", scope="changed"))
    second = build_batch_census(tmp_path, first["updated_ledger"])

    assert second["packages"][0]["idempotency_state"] == "CHANGED"
    assert (
        second["packages"][0]["manifest_digest"]
        != first["packages"][0]["manifest_digest"]
    )


def test_duplicate_session_id_rejects_batch(tmp_path: Path) -> None:
    _package(tmp_path, "GMI-A", _manifest("GMI-SAME"))
    _package(tmp_path, "GMI-B", _manifest("GMI-SAME"))

    census = build_batch_census(tmp_path)
    assert census["batch_verdict"] == "REJECT"
    assert census["duplicate_session_ids"] == ["GMI-SAME"]
    assert {entry["idempotency_state"] for entry in census["packages"]} == {
        "DUPLICATE"
    }


def test_invalid_package_does_not_overwrite_prior_ledger(tmp_path: Path) -> None:
    _package(tmp_path, "GMI-A", _manifest("GMI-A"))
    first = build_batch_census(tmp_path)
    prior = first["updated_ledger"]

    broken = _manifest("GMI-A", scope="broken")
    broken["artifact_refs"] = [
        {
            "type": "local_file",
            "path": "ARTIFACTS/missing.bin",
            "required": True,
        }
    ]
    _package(tmp_path, "GMI-A", broken)
    second = build_batch_census(tmp_path, prior)

    assert second["batch_verdict"] == "REJECT"
    assert second["packages"][0]["idempotency_state"] == "INVALID"
    assert second["updated_ledger"] == prior


def test_empty_workspace_is_deterministic_accept(tmp_path: Path) -> None:
    census = build_batch_census(tmp_path)
    assert census["package_count"] == 0
    assert census["batch_verdict"] == "ACCEPT"
    assert census["duplicate_session_ids"] == []


def test_missing_workspace_rejects_instead_of_empty_accept(tmp_path: Path) -> None:
    census = build_batch_census(tmp_path / "missing")
    assert census["batch_verdict"] == "REJECT"
    assert census["package_count"] == 0
    assert census["errors"] == ["workspace missing"]


def test_non_directory_workspace_rejects(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace.txt"
    workspace.write_text("not a directory", encoding="utf-8")
    census = build_batch_census(workspace)
    assert census["batch_verdict"] == "REJECT"
    assert census["errors"] == ["workspace is not a directory"]


def test_explicit_missing_ledger_fails_closed(tmp_path: Path) -> None:
    try:
        load_ledger(tmp_path / "missing-ledger.json")
    except FileNotFoundError as exc:
        assert "explicit ledger input missing" in str(exc)
    else:
        raise AssertionError("explicit missing ledger must not create a blank ledger")


def test_invalid_manifest_is_not_reread_outside_guarded_validation(tmp_path: Path) -> None:
    package = tmp_path / "GMI-BAD"
    target = package / "MANIFEST" / "manifest.yaml"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"schema_version: 1\nsource_agent: \xff\xfe\n")

    census = build_batch_census(tmp_path)
    assert census["batch_verdict"] == "REJECT"
    assert census["package_count"] == 1
    assert census["packages"][0]["idempotency_state"] == "INVALID"
    assert census["packages"][0]["manifest_digest"] is None
