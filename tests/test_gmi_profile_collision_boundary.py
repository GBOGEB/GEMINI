"""Fail-closed wire-format boundary after GMI W2 #40/#41 converged.

This regression suite deliberately does not migrate historical #41 proposal_profile
into the canonical #40 `profile` + `proposal` structure. An explicit versioned
adapter and independent owner approval would be required to do so.
"""
from __future__ import annotations

import hashlib

import pytest
import yaml

from src.proposal_broker import (
    PROFILE,
    BrokerError,
    broker_workspace,
    evaluate_proposal,
    parse_profile,
)


def _manifest(tmp_path):
    content = b"one safe line\n"
    artifact = tmp_path / "CHANGES" / "report.txt"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_bytes(content)
    return {
        "schema_version": 1,
        "session_id": "GMI-BOUNDARY-CANARY",
        "profile": PROFILE,
        "proposal": {
            "repo": "GBOGEB/GEMINI",
            "base_sha": "a" * 40,
            "intent": "Test canonical proposal profile without dispatch",
            "changes": [{
                "path": "docs/report.txt",
                "base_blob": "b" * 40,
                "mode": "replace",
                "artifact_ref": "chg-0",
            }],
        },
        "artifact_refs": [{
            "id": "chg-0",
            "type": "local_file",
            "path": "CHANGES/report.txt",
            "required": True,
            "sha256": hashlib.sha256(content).hexdigest(),
        }],
    }, artifact


def _legacy():
    return {
        "schema": PROFILE,
        "repository": "GBOGEB/GEMINI",
        "base_sha": "a" * 40,
        "head_sha": "b" * 40,
        "changes": [{"op": "modify", "path": "docs/report.txt",
                     "artifact_path": "CHANGES/report.txt", "base_blob": "c" * 40}],
    }


def test_canonical_profile_is_still_accepted(tmp_path):
    manifest, artifact = _manifest(tmp_path)
    parsed = parse_profile(manifest, tmp_path)
    assert parsed["repo"] == "GBOGEB/GEMINI"
    assert parsed["changes"][0]["artifact"] == artifact.read_bytes()


def test_unrelated_top_level_metadata_is_not_forbidden(tmp_path):
    manifest, _ = _manifest(tmp_path)
    manifest["source_provenance"] = {"classification": "DECLARED"}
    assert parse_profile(manifest, tmp_path)["base_sha"] == "a" * 40


@pytest.mark.parametrize("coexist", [False, True])
def test_legacy_wire_shape_is_not_silently_adopted(tmp_path, coexist):
    manifest, artifact = _manifest(tmp_path)
    if not coexist:
        manifest.pop("profile")
        manifest.pop("proposal")
    manifest["proposal_profile"] = _legacy()
    original = artifact.read_bytes()
    with pytest.raises(BrokerError, match="legacy proposal_profile"):
        parse_profile(manifest, tmp_path)
    assert artifact.read_bytes() == original


@pytest.mark.parametrize("variant", [None, {}, {"schema": PROFILE}])
def test_ambiguous_legacy_marker_always_fails_closed(tmp_path, variant):
    manifest, _ = _manifest(tmp_path)
    manifest["proposal_profile"] = variant
    with pytest.raises(BrokerError, match="legacy proposal_profile"):
        parse_profile(manifest, tmp_path)


def test_canonical_marker_with_unknown_schema_is_still_rejected(tmp_path):
    manifest, _ = _manifest(tmp_path)
    manifest["profile"] = "gmi.proposal_profile.v2-undefined"
    with pytest.raises(BrokerError, match="manifest profile"):
        parse_profile(manifest, tmp_path)


def _package_on_disk(tmp_path, *, legacy=True, status="DEFERRED"):
    package_dir = tmp_path / "GMI-BOUNDARY-CANARY"
    manifest, artifact = _manifest(package_dir)
    manifest.update({
        "source_agent": "synthetic-owner-proof",
        "generated_at": "2026-11-09T00:00:00Z",
        "status": status,
        "scope": "source-bound negative test",
        "source_refs": [],
        "current_gate": "DRY_RUN_ONLY",
        "next_action": "independent owner review",
    })
    if legacy:
        manifest["proposal_profile"] = _legacy()
    folder = package_dir / "MANIFEST"
    folder.mkdir(parents=True)
    (folder / "manifest.yaml").write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    return package_dir, manifest, artifact


def test_legacy_deferred_package_rejected_before_defer_return(tmp_path):
    package, _, _ = _package_on_disk(tmp_path, legacy=True, status="DEFERRED")
    verdict = evaluate_proposal(package, tmp_path, "a" * 40, "GBOGEB/GEMINI")
    assert verdict["verdict"] == "REJECT"
    assert "AMBIGUOUS_LEGACY_PROFILE" in str(verdict["reasons"])
    assert verdict["patch"] == b""


def test_unrelated_deferred_package_remains_deferred(tmp_path):
    package, _, _ = _package_on_disk(tmp_path, legacy=False, status="DEFERRED")
    verdict = evaluate_proposal(package, tmp_path, "a" * 40, "GBOGEB/GEMINI")
    assert verdict["verdict"] == "DEFER"
    assert verdict["patch"] == b""


def test_same_digest_legacy_package_cannot_be_accepted_as_brokered(tmp_path, monkeypatch):
    import src.proposal_broker as broker

    package, manifest, _ = _package_on_disk(tmp_path, legacy=True, status="IMPLEMENTED")
    # Simulate a prior ledger digest match explicitly. The ordinary old path returned
    # SKIP/ACCEPT without evaluating or parsing the historical wire profile.
    record = {
        "package": package.name,
        "session_id": manifest["session_id"],
        "idempotency_state": "UNCHANGED",
        "package_verdict": "ACCEPT",
        "manifest_digest": "c" * 64,
        "errors": [],
    }
    prior = {"schema_version": 1, "sessions": {package.name: {"manifest_digest": "c" * 64}}}
    census = {
        "errors": [], "batch_digest": "d" * 64, "packages": [record],
        "updated_ledger": prior,
    }
    monkeypatch.setattr(broker, "_git", lambda *_args: b"a" * 40)
    monkeypatch.setattr(broker, "build_batch_census", lambda *_args: census)
    result = broker_workspace(tmp_path, tmp_path, "GBOGEB/GEMINI", prior_ledger=prior)
    assert result["broker_verdict"] == "REJECT"
    row = result["packages"][0]
    assert row["action"] == "REJECT"
    assert row["plan"] is None and row["patch"] == b""
    assert "AMBIGUOUS_LEGACY_PROFILE" in str(row["reasons"])
    assert result["updated_ledger"] == prior


def test_same_digest_deferred_canonical_package_cannot_be_accepted(tmp_path, monkeypatch):
    import src.proposal_broker as broker

    package, manifest, _ = _package_on_disk(tmp_path, legacy=False, status="DEFERRED")
    record = {
        "package": package.name, "session_id": manifest["session_id"],
        "idempotency_state": "UNCHANGED", "package_verdict": "DEFER",
        "manifest_digest": "c" * 64, "errors": [],
    }
    prior = {"schema_version": 1, "sessions": {package.name: {"manifest_digest": "c" * 64}}}
    census = {"errors": [], "batch_digest": "d" * 64, "packages": [record], "updated_ledger": prior}
    monkeypatch.setattr(broker, "_git", lambda *_args: b"a" * 40)
    monkeypatch.setattr(broker, "build_batch_census", lambda *_args: census)
    result = broker_workspace(tmp_path, tmp_path, "GBOGEB/GEMINI", prior_ledger=prior)
    assert result["broker_verdict"] == "DEFER"
    assert result["packages"][0]["action"] == "DEFER"
    assert result["packages"][0]["plan"] is None
