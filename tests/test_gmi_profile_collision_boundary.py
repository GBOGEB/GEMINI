"""Fail-closed wire-format boundary after GMI W2 #40/#41 converged.

This regression suite deliberately does not migrate historical #41 proposal_profile
into the canonical #40 `profile` + `proposal` structure. An explicit versioned
adapter and independent owner approval would be required to do so.
"""
from __future__ import annotations

import hashlib

import pytest

from src.proposal_broker import BrokerError, PROFILE, parse_profile


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
