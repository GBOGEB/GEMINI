"""Batch-census GMI handover packages with deterministic idempotency classification."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import yaml

from src.handover_package import validate_package


def _load_manifest(package_dir: Path) -> dict[str, Any] | None:
    path = package_dir / "MANIFEST" / "manifest.yaml"
    if not path.is_file():
        return None
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError):
        return None
    return data if isinstance(data, dict) else None


def _manifest_digest(manifest: dict[str, Any]) -> str:
    # Handover manifests are accepted for idempotency only if they can be
    # represented canonically in JSON. YAML-only objects such as sets, mixed
    # key types, and non-finite floats must never acquire process-dependent
    # string representations.
    rendered = json.dumps(
        manifest,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(rendered).hexdigest()


def _idempotency_key(session_id: str, manifest_digest: str) -> str:
    return hashlib.sha256(f"{session_id}|{manifest_digest}".encode()).hexdigest()


def load_ledger(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {"schema_version": 1, "sessions": {}}
    if not path.is_file():
        raise FileNotFoundError(f"explicit ledger missing: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("sessions"), dict):
        raise TypeError("ledger root must be a mapping with a sessions mapping")
    return data


def _rejected_census(
    workspace: Path,
    prior_ledger: dict[str, Any],
    error: str,
) -> dict[str, Any]:
    sessions = prior_ledger.get("sessions", {})
    if not isinstance(sessions, dict):
        sessions = {}
    return {
        "schema_version": 1,
        "workspace": str(workspace),
        "package_count": 0,
        "batch_verdict": "REJECT",
        "duplicate_session_ids": [],
        "batch_digest": hashlib.sha256(b"").hexdigest(),
        "packages": [],
        "errors": [error],
        "updated_ledger": {
            "schema_version": 1,
            "sessions": dict(sessions),
        },
    }


def build_batch_census(
    workspace: Path,
    prior_ledger: dict[str, Any] | None = None,
) -> dict[str, Any]:
    workspace = workspace.resolve()
    ledger = prior_ledger or {"schema_version": 1, "sessions": {}}
    prior_sessions = ledger.get("sessions", {})
    if not isinstance(prior_sessions, dict):
        raise TypeError("ledger sessions must be a mapping")

    if not workspace.is_dir():
        return _rejected_census(
            workspace,
            ledger,
            "workspace missing or not a directory",
        )

    package_dirs = sorted(
        (
            path
            for path in workspace.iterdir()
            if path.is_dir() and path.name.startswith("GMI-")
        ),
        key=lambda path: path.name,
    )

    entries: list[dict[str, Any]] = []
    session_occurrences: dict[str, int] = {}

    for package_dir in package_dirs:
        validation = validate_package(package_dir)
        # Do not re-read a manifest that has already failed validation. This
        # keeps malformed/unreadable packages on the structured REJECT path.
        manifest = (
            _load_manifest(package_dir)
            if validation["verdict"] != "REJECT"
            else None
        )
        session_id = validation.get("session_id")
        digest = None
        digest_error = None
        if manifest is not None:
            try:
                digest = _manifest_digest(manifest)
            except (TypeError, ValueError) as exc:
                digest_error = (
                    "manifest must be JSON-compatible for deterministic hashing: "
                    f"{type(exc).__name__}"
                )

        key = (
            _idempotency_key(str(session_id), digest)
            if isinstance(session_id, str) and digest is not None
            else None
        )
        if isinstance(session_id, str):
            session_occurrences[session_id] = (
                session_occurrences.get(session_id, 0) + 1
            )

        errors = list(validation["errors"])
        if digest_error:
            errors.append(digest_error)

        prior = (
            prior_sessions.get(session_id)
            if isinstance(session_id, str)
            else None
        )
        prior_digest = (
            prior.get("manifest_digest")
            if isinstance(prior, dict)
            else None
        )
        effective_reject = validation["verdict"] == "REJECT" or digest_error is not None
        if effective_reject or key is None:
            state = "INVALID"
            package_verdict = "REJECT"
        elif prior_digest is None:
            state = "NEW"
            package_verdict = validation["verdict"]
        elif prior_digest == digest:
            state = "UNCHANGED"
            package_verdict = validation["verdict"]
        else:
            state = "CHANGED"
            package_verdict = validation["verdict"]

        entries.append(
            {
                "package": package_dir.name,
                "session_id": session_id,
                "package_verdict": package_verdict,
                "idempotency_state": state,
                "manifest_digest": digest,
                "idempotency_key": key,
                "errors": errors,
                "deferred": validation["deferred"],
            }
        )

    duplicates = sorted(
        session_id
        for session_id, count in session_occurrences.items()
        if count > 1
    )
    if duplicates:
        for entry in entries:
            if entry["session_id"] in duplicates:
                entry["idempotency_state"] = "DUPLICATE"

    package_verdicts = {entry["package_verdict"] for entry in entries}
    if duplicates or "REJECT" in package_verdicts:
        verdict = "REJECT"
    elif "DEFER" in package_verdicts:
        verdict = "DEFER"
    else:
        verdict = "ACCEPT"

    updated_sessions = dict(prior_sessions)
    for entry in entries:
        if (
            entry["package_verdict"] != "REJECT"
            and entry["idempotency_state"] != "DUPLICATE"
            and isinstance(entry["session_id"], str)
            and isinstance(entry["manifest_digest"], str)
            and isinstance(entry["idempotency_key"], str)
        ):
            updated_sessions[entry["session_id"]] = {
                "manifest_digest": entry["manifest_digest"],
                "idempotency_key": entry["idempotency_key"],
                "package_verdict": entry["package_verdict"],
            }

    identity_material = [
        entry["idempotency_key"]
        for entry in entries
        if isinstance(entry["idempotency_key"], str)
    ]
    batch_digest = hashlib.sha256(
        "\n".join(sorted(identity_material)).encode("utf-8")
    ).hexdigest()

    return {
        "schema_version": 1,
        "workspace": str(workspace),
        "package_count": len(entries),
        "batch_verdict": verdict,
        "duplicate_session_ids": duplicates,
        "batch_digest": batch_digest,
        "packages": entries,
        "errors": [],
        "updated_ledger": {
            "schema_version": 1,
            "sessions": updated_sessions,
        },
    }


def _cli_reject(workspace: Path, error: Exception) -> dict[str, Any]:
    return _rejected_census(
        workspace.resolve(),
        {"schema_version": 1, "sessions": {}},
        f"batch input failed closed: {type(error).__name__}: {error}",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workspace", type=Path)
    parser.add_argument("--ledger-in", type=Path)
    parser.add_argument("--ledger-out", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    try:
        prior = load_ledger(args.ledger_in)
        census = build_batch_census(args.workspace, prior)
    except (OSError, UnicodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
        census = _cli_reject(args.workspace, exc)

    ledger = census["updated_ledger"]

    if args.ledger_out:
        args.ledger_out.parent.mkdir(parents=True, exist_ok=True)
        args.ledger_out.write_text(
            json.dumps(ledger, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    rendered = json.dumps(census, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")

    return 1 if census["batch_verdict"] == "REJECT" else 0


if __name__ == "__main__":
    raise SystemExit(main())
