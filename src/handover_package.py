"""Validate one governed Gemini handover package without promoting source claims."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import yaml

EVIDENCE_STATES = {"VERIFIED", "IMPLEMENTED", "DECLARED", "INFERRED", "PARTIAL", "DEFERRED"}
PACKAGE_VERDICTS = {"ACCEPT", "REJECT", "DEFER"}
ARTIFACT_TYPES = {"local_file", "drive_native"}
SUPPORTED_SCHEMA_VERSIONS = {1}
REQUIRED_MANIFEST_FIELDS = {
    "schema_version",
    "session_id",
    "source_agent",
    "generated_at",
    "status",
    "scope",
    "source_refs",
    "artifact_refs",
    "current_gate",
    "next_action",
}
REQUIRED_NONEMPTY_STRING_FIELDS = {
    "source_agent",
    "generated_at",
    "scope",
    "current_gate",
    "next_action",
}


def _load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise TypeError(f"{path}: YAML root must be a mapping")
    return data


def _safe_package_path(package_dir: Path, raw: str) -> Path:
    rel = Path(raw)
    if rel.is_absolute():
        raise ValueError("artifact path must be relative to the package")
    root = package_dir.resolve()
    candidate = (package_dir / rel).resolve()
    if candidate != root and root not in candidate.parents:
        raise ValueError("artifact path escapes the package root")
    return candidate


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_json_value(
    value: Any,
    path: str = "$",
    active_container_ids: set[int] | None = None,
) -> None:
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"{path}: non-finite float is not canonical JSON")
        return
    if isinstance(value, (list, dict)):
        if active_container_ids is None:
            active_container_ids = set()
        identity = id(value)
        if identity in active_container_ids:
            raise ValueError(f"{path}: cyclic container is not canonical JSON")
        active_container_ids.add(identity)
        try:
            if isinstance(value, list):
                for index, item in enumerate(value):
                    _validate_json_value(
                        item,
                        f"{path}[{index}]",
                        active_container_ids,
                    )
            else:
                for key, item in value.items():
                    if not isinstance(key, str):
                        raise TypeError(f"{path}: mapping key {key!r} is not a string")
                    _validate_json_value(
                        item,
                        f"{path}.{key}",
                        active_container_ids,
                    )
        finally:
            active_container_ids.remove(identity)
        return
    raise TypeError(f"{path}: non-JSON value type {type(value).__name__}")


def canonical_manifest_digest(manifest: dict[str, Any]) -> str:
    _validate_json_value(manifest)
    rendered = json.dumps(
        manifest,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(rendered).hexdigest()


def validate_manifest(manifest: dict[str, Any], package_dir: Path) -> dict[str, list[str]]:
    errors: list[str] = []
    deferred: list[str] = []

    missing = sorted(REQUIRED_MANIFEST_FIELDS - manifest.keys())
    if missing:
        errors.append(f"missing required fields: {', '.join(missing)}")

    schema_version = manifest.get("schema_version")
    if (
        not isinstance(schema_version, int)
        or isinstance(schema_version, bool)
        or schema_version not in SUPPORTED_SCHEMA_VERSIONS
    ):
        errors.append(
            f"schema_version must be one of {sorted(SUPPORTED_SCHEMA_VERSIONS)}, got {schema_version!r}"
        )

    session_id = manifest.get("session_id")
    if not isinstance(session_id, str) or not session_id.strip() or not session_id.startswith("GMI-"):
        errors.append("session_id must be a non-empty GMI-* string")

    for field in REQUIRED_NONEMPTY_STRING_FIELDS:
        value = manifest.get(field)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{field} must be a non-empty string")

    status = manifest.get("status")
    if not isinstance(status, str):
        errors.append("status must be a string")
    elif status not in EVIDENCE_STATES:
        errors.append(f"invalid status {status!r}; expected one of {sorted(EVIDENCE_STATES)}")
    elif status == "DEFERRED":
        deferred.append("manifest evidence status is DEFERRED")

    for field in ("source_refs", "artifact_refs"):
        if field in manifest and not isinstance(manifest[field], list):
            errors.append(f"{field} must be a list")

    artifact_refs = manifest.get("artifact_refs")
    if isinstance(artifact_refs, list):
        seen_ids: set[str] = set()
        for index, ref in enumerate(artifact_refs):
            prefix = f"artifact_refs[{index}]"
            if not isinstance(ref, dict):
                errors.append(f"{prefix} must be a mapping")
                continue

            artifact_id = ref.get("id")
            if artifact_id is not None:
                if not isinstance(artifact_id, str) or not artifact_id:
                    errors.append(f"{prefix}.id must be a non-empty string when present")
                elif artifact_id in seen_ids:
                    errors.append(f"{prefix}.id duplicates {artifact_id!r}")
                else:
                    seen_ids.add(artifact_id)

            artifact_type = ref.get("type")
            if not isinstance(artifact_type, str) or artifact_type not in ARTIFACT_TYPES:
                errors.append(
                    f"{prefix}.type must be one of {sorted(ARTIFACT_TYPES)}, got {artifact_type!r}"
                )
                continue

            required = ref.get("required", True)
            if not isinstance(required, bool):
                errors.append(f"{prefix}.required must be boolean")
                continue

            if artifact_type == "local_file":
                raw_path = ref.get("path")
                if not isinstance(raw_path, str) or not raw_path:
                    errors.append(f"{prefix}.path is required for local_file")
                    continue
                try:
                    candidate = _safe_package_path(package_dir, raw_path)
                except ValueError as exc:
                    errors.append(f"{prefix}: {exc}")
                    continue

                if not candidate.is_file():
                    message = f"{prefix}: local artifact missing: {raw_path}"
                    if required:
                        errors.append(message)
                    else:
                        deferred.append(message)
                    continue

                claimed_sha = ref.get("sha256")
                if claimed_sha is not None:
                    if (
                        not isinstance(claimed_sha, str)
                        or len(claimed_sha) != 64
                        or any(ch not in "0123456789abcdefABCDEF" for ch in claimed_sha)
                    ):
                        errors.append(f"{prefix}.sha256 must be a 64-character hexadecimal digest")
                    elif _sha256(candidate) != claimed_sha.lower():
                        errors.append(f"{prefix}: SHA-256 mismatch for {raw_path}")

            if artifact_type == "drive_native":
                drive_file_id = ref.get("drive_file_id")
                revision_id = ref.get("drive_revision_id")
                if not isinstance(drive_file_id, str) or not drive_file_id:
                    errors.append(f"{prefix}.drive_file_id is required for drive_native")
                if revision_id is not None and (not isinstance(revision_id, str) or not revision_id):
                    errors.append(f"{prefix}.drive_revision_id must be a non-empty string when present")
                if ref.get("sha256") not in (None, ""):
                    errors.append(
                        f"{prefix}: Drive-native revision identity is not a SHA-256; "
                        "exported-byte hash must not be invented"
                    )

    return {"errors": errors, "deferred": deferred}


def validate_package(
    package_dir: Path, manifest_relative: str = "MANIFEST/manifest.yaml"
) -> dict[str, Any]:
    package_dir = package_dir.resolve()
    manifest_path = package_dir / manifest_relative
    base_receipt = {
        "schema_version": 1,
        "package_dir": str(package_dir),
        "manifest_path": str(manifest_path),
        "session_id": None,
        "evidence_status": None,
        "manifest_digest": None,
        "verdict": "REJECT",
        "errors": [],
        "deferred": [],
    }

    if not manifest_path.is_file():
        return {**base_receipt, "errors": ["manifest missing"]}

    try:
        manifest = _load_yaml(manifest_path)
    except (OSError, UnicodeError, TypeError, yaml.YAMLError) as exc:
        return {**base_receipt, "errors": [f"manifest load failed: {exc}"]}

    result = validate_manifest(manifest, package_dir)
    digest: str | None = None
    try:
        digest = canonical_manifest_digest(manifest)
    except (TypeError, ValueError) as exc:
        result["errors"].append(f"manifest canonicalization failed: {exc}")

    if result["errors"]:
        verdict = "REJECT"
    elif result["deferred"]:
        verdict = "DEFER"
    else:
        verdict = "ACCEPT"

    assert verdict in PACKAGE_VERDICTS
    return {
        **base_receipt,
        "session_id": manifest.get("session_id"),
        "evidence_status": manifest.get("status"),
        "manifest_digest": digest,
        "verdict": verdict,
        "errors": result["errors"],
        "deferred": result["deferred"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package_dir", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    receipt = validate_package(args.package_dir)
    rendered = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0 if receipt["verdict"] != "REJECT" else 1


if __name__ == "__main__":
    raise SystemExit(main())
