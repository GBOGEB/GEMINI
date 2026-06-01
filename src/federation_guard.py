"""Federation guard: flag cross-concern artifacts that do not belong in GEMINI.

The federation ownership model (see FEDERATION.md) allows artifacts to be moved
*downward* into deeper folders freely, but requires *re-homing* across repos to
be a reviewed, semantic act. This guard enforces the mechanical half of that
rule: it scans the working tree for artifact *types* whose home domain is some
other federation member (declared in ``repo_manifest.yaml`` under
``federation.foreign_artifact_signatures``) and reports them so they can be
routed out.

Folder depth is never penalised; only foreign artifact types are flagged. Paths
under ``federation.guard_allowlist`` (for example the read-only mirror of
federation peers under ``docs/federation/``) are exempt.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "repo_manifest.yaml"
DOCS_DIR = ROOT / "docs"
REPORT_PATH = DOCS_DIR / "federation_guard.json"


def _load_manifest() -> dict[str, Any]:
    if not MANIFEST_PATH.exists():
        return {}
    try:
        data = yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return {}
    return data if isinstance(data, dict) else {}


def _federation_block(manifest: dict[str, Any]) -> dict[str, Any]:
    federation = manifest.get("federation", {})
    return federation if isinstance(federation, dict) else {}


def _allowlisted_paths(allowlist: list[str]) -> set[Path]:
    matched: set[Path] = set()
    for pattern in allowlist:
        if not isinstance(pattern, str) or not pattern:
            continue
        for path in ROOT.glob(pattern):
            matched.add(path.resolve())
    return matched


def _is_allowlisted(path: Path, allowlisted: set[Path]) -> bool:
    resolved = path.resolve()
    if resolved in allowlisted:
        return True
    return any(parent in allowlisted for parent in resolved.parents)


def find_foreign_artifacts(manifest: dict[str, Any]) -> list[dict[str, str]]:
    """Return foreign artifacts found in the working tree.

    Each entry records the offending file, its detected artifact ``type`` and
    the ``home`` domain it should be routed to.
    """
    federation = _federation_block(manifest)
    signatures = federation.get("foreign_artifact_signatures", {})
    if not isinstance(signatures, dict):
        return []

    allowlist = federation.get("guard_allowlist", [])
    allowlist = allowlist if isinstance(allowlist, list) else []
    allowlisted = _allowlisted_paths(allowlist)

    findings: dict[str, dict[str, str]] = {}
    for artifact_type, spec in signatures.items():
        if not isinstance(spec, dict):
            continue
        home = str(spec.get("home", "unknown"))
        patterns = spec.get("patterns", [])
        if not isinstance(patterns, list):
            continue
        for pattern in patterns:
            if not isinstance(pattern, str) or not pattern:
                continue
            for path in ROOT.glob(pattern):
                if not path.is_file():
                    continue
                if _is_allowlisted(path, allowlisted):
                    continue
                relative = path.resolve().relative_to(ROOT.resolve()).as_posix()
                findings[relative] = {
                    "file": relative,
                    "type": str(artifact_type),
                    "home": home,
                    "matched_pattern": pattern,
                }

    return sorted(findings.values(), key=lambda item: item["file"])


def _write_report(report: dict[str, Any]) -> None:
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")


def main() -> int:
    manifest = _load_manifest()
    findings = find_foreign_artifacts(manifest)

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "concern": _federation_block(manifest).get("concern", "unknown"),
        "foreign_artifact_count": len(findings),
        "foreign_artifacts": findings,
    }
    _write_report(report)

    if findings:
        print(
            f"Federation guard: {len(findings)} cross-concern artifact(s) "
            "detected in GEMINI.",
            file=sys.stderr,
        )
        for finding in findings:
            print(
                f"  - {finding['file']} looks like a '{finding['type']}' "
                f"artifact; route it to {finding['home']}.",
                file=sys.stderr,
            )
        return 1

    print("Federation guard: no cross-concern artifacts detected.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
