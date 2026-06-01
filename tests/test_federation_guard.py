from pathlib import Path

import yaml

from src.federation_guard import (
    _federation_block,
    _load_manifest,
    find_foreign_artifacts,
)

MANIFEST_PATH = "repo_manifest.yaml"


def _manifest() -> dict:
    return yaml.safe_load(Path(MANIFEST_PATH).read_text(encoding="utf-8"))


def test_manifest_declares_federation_handshake() -> None:
    federation = _federation_block(_manifest())

    assert federation["concern"] == "review-reasoning-notebook"
    assert federation["upstream_dependencies"]["codex"]["pinned_version"]
    assert federation["upstream_dependencies"]["abacus"]["pinned_version"] is None
    assert "artstyle" in federation["contracts"]


def test_clean_repository_has_no_foreign_artifacts() -> None:
    findings = find_foreign_artifacts(_load_manifest())

    assert findings == []


def test_guard_flags_foreign_schema_artifact(tmp_path: Path) -> None:
    manifest = {
        "federation": {
            "foreign_artifact_signatures": {
                "schema": {
                    "home": "CODEX",
                    "patterns": ["**/*.schema.json"],
                }
            },
            "guard_allowlist": ["docs/federation/**"],
        }
    }

    # Point the guard's glob root at a scratch tree by monkeypatching ROOT.
    from src import federation_guard

    original_root = federation_guard.ROOT
    federation_guard.ROOT = tmp_path
    try:
        offending = tmp_path / "blocks" / "user.schema.json"
        offending.parent.mkdir(parents=True)
        offending.write_text("{}", encoding="utf-8")

        findings = federation_guard.find_foreign_artifacts(manifest)
    finally:
        federation_guard.ROOT = original_root

    assert len(findings) == 1
    assert findings[0]["type"] == "schema"
    assert findings[0]["home"] == "CODEX"
    assert findings[0]["file"] == "blocks/user.schema.json"


def test_guard_allowlist_exempts_federation_mirror(tmp_path: Path) -> None:
    manifest = {
        "federation": {
            "foreign_artifact_signatures": {
                "schema": {
                    "home": "CODEX",
                    "patterns": ["**/*.schema.json"],
                }
            },
            "guard_allowlist": ["docs/federation/**"],
        }
    }

    from src import federation_guard

    original_root = federation_guard.ROOT
    federation_guard.ROOT = tmp_path
    try:
        mirrored = tmp_path / "docs" / "federation" / "codex" / "a.schema.json"
        mirrored.parent.mkdir(parents=True)
        mirrored.write_text("{}", encoding="utf-8")

        findings = federation_guard.find_foreign_artifacts(manifest)
    finally:
        federation_guard.ROOT = original_root

    assert findings == []
