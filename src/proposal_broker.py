"""Offline GM-I-C R2-W2 proposal broker: report only, never pushes or merges.

Reuses GEMINI GMI handover validation and batch idempotency; local git snapshots
must be verified by their own owner before any branch is acted upon.
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import re
import subprocess
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any

from src.handover_package import _load_yaml, validate_package
from src.handover_batch import build_batch_census, load_ledger

PROFILE = "gmi.proposal_profile.v1"
RECEIPT = "gmi.broker_receipt"
SHA1 = re.compile(r"^[0-9a-f]{40}$")
SAFE_SEGMENT = re.compile(r"^[A-Za-z0-9_.-]+$")
DANGEROUS = {".git", ".env", ".ssh", ".npmrc", ".pypirc", "id_rsa", "id_ed25519", "gha-creds.json"}
SENSITIVE_SUFFIXES = (".pem", ".key", ".p12", ".pfx", ".kdbx")
MAX_TEXT_BYTES = 1_048_576
MAX_FILES = 20


class BrokerInputError(ValueError):
    """A proposal contract or local snapshot integrity violation."""


def _relative(raw: Any) -> str:
    if not isinstance(raw, str) or not raw or "\\" in raw or "\x00" in raw or raw.startswith("/"):
        raise BrokerInputError("UNSAFE_PATH")
    p = PurePosixPath(raw)
    if any(s in {"", ".", ".."} or not SAFE_SEGMENT.fullmatch(s) for s in raw.split("/")) or str(p) != raw:
        raise BrokerInputError("UNSAFE_PATH")
    parts = [s.lower() for s in p.parts]
    if any(s in DANGEROUS or s.endswith(SENSITIVE_SUFFIXES) for s in parts):
        raise BrokerInputError("SECRET_PATH_DENIED")
    if any(s.startswith("id_rsa") or s.startswith("id_ed25519") or s.startswith("gha-creds-") for s in parts):
        raise BrokerInputError("SECRET_PATH_DENIED")
    return raw


def _read(root: Path, raw: str) -> bytes:
    rel = _relative(raw)
    root = root.resolve()
    path = root.joinpath(*rel.split("/"))
    # Symlinks are refused even if they happen to resolve inside the root.
    if not path.resolve().is_relative_to(root) or any(p.is_symlink() for p in [path, *path.parents] if p != root and root in p.parents):
        raise BrokerInputError("SYMLINK_OR_PATH_ESCAPE")
    if not path.is_file():
        raise BrokerInputError("LOCAL_FILE_MISSING")
    if path.stat().st_size > MAX_TEXT_BYTES:
        raise BrokerInputError("TEXT_FILE_TOO_LARGE")
    data = path.read_bytes()
    if b"\x00" in data:
        raise BrokerInputError("BINARY_PROPOSAL_DENIED")
    try:
        data.decode("utf-8", "strict")
    except UnicodeError as exc:
        raise BrokerInputError("NON_UTF8_PROPOSAL_DENIED") from exc
    return data


def git_blob_oid(data: bytes) -> str:
    """Git SHA-1 blob object identifier (not SHA-256 and not a signature)."""
    return hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()


def _merge_text(head: bytes, base: bytes, proposed: bytes) -> tuple[str, bytes]:
    """Use local git merge-file (no network, no repository mutation) for 3-way analysis."""
    with tempfile.TemporaryDirectory(prefix="gmi-broker-") as temp:
        paths = [Path(temp) / n for n in ("head.txt", "base.txt", "proposal.txt")]
        for p, data in zip(paths, (head, base, proposed)):
            p.write_bytes(data)
        try:
            proc = subprocess.run(["git", "merge-file", "--stdout", *map(str, paths)],
                                  capture_output=True, timeout=10, check=False)
        except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
            raise BrokerInputError("THREE_WAY_TOOL_UNAVAILABLE") from exc
        if proc.returncode < 0 or proc.returncode > 127:
            raise BrokerInputError("THREE_WAY_TOOL_ERROR")
        return ("THREE_WAY" if proc.returncode == 0 else "CONFLICT"), proc.stdout


def _patch(before: bytes, after: bytes, rel: str) -> str:
    return "".join(difflib.unified_diff(before.decode("utf-8").splitlines(keepends=True),
            after.decode("utf-8").splitlines(keepends=True),
            fromfile=f"a/{rel}", tofile=f"b/{rel}"))


def evaluate_proposal(package_dir: Path, base_root: Path, head_root: Path,
                      *, repo: str, prior_ledger: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return a conservative dry-run receipt; never write the repo, ledger or Drive.

    base_root and head_root are untrusted local plain-file snapshots. The caller
    must independently prove each snapshot's declared Git commit identity.
    """
    package_dir = package_dir.resolve()
    validity = validate_package(package_dir)  # GEMINI's existing authority for GMI v1 package syntax.
    result: dict[str, Any] = {
        "schema_version": 1, "receipt_type": RECEIPT, "profile": PROFILE,
        "package_verdict": validity["verdict"], "manifest_digest": validity.get("manifest_digest"),
        "session_id": validity.get("session_id"), "repo": repo,
        "mode": "OFFLINE_DRY_RUN", "authority_transfer": False, "formal_credit_delta": 0,
        "github_mutated": False, "drive_mutated": False, "ledger_mutated": False,
        "source_identity_verified": False, "requires": ["verify_base_and_head_snapshot_at_exact_commits", "exact_head_ci", "independent_review"],
        "changes": [], "patch": "", "branch_plan": None, "disposition": "HOLD", "errors": list(validity["errors"]),
        "deferred": list(validity["deferred"]),
    }
    if validity["verdict"] != "ACCEPT":
        return result
    try:
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo):
            raise BrokerInputError("INVALID_REPOSITORY_ID")
        manifest = _load_yaml(package_dir / "MANIFEST" / "manifest.yaml")
        profile = manifest.get("proposal_profile")
        if not isinstance(profile, dict) or profile.get("schema") != PROFILE or profile.get("repository") != repo:
            raise BrokerInputError("PROPOSAL_PROFILE_MISSING_OR_WRONG_REPO")
        for field in ("base_sha", "head_sha"):
            if not isinstance(profile.get(field), str) or not SHA1.fullmatch(profile[field]):
                raise BrokerInputError(f"INVALID_{field.upper()}")
        result["declared_base_sha"] = profile["base_sha"]
        result["declared_head_sha"] = profile["head_sha"]
        changes = profile.get("changes")
        if not isinstance(changes, list) or not 1 <= len(changes) <= MAX_FILES:
            raise BrokerInputError("CHANGE_COUNT_OUT_OF_BOUNDS")
        artifact_paths = {ref.get("path") for ref in manifest["artifact_refs"]
                          if isinstance(ref, dict) and ref.get("type") == "local_file" and ref.get("required", True)}
        seen_paths: set[str] = set()
        for change in changes:
            if not isinstance(change, dict) or change.get("op") != "modify":
                raise BrokerInputError("ONLY_EXPLICIT_MODIFY_SUPPORTED")
            rel = _relative(change.get("path"))
            artifact = _relative(change.get("artifact_path"))
            if rel in seen_paths or artifact not in artifact_paths:
                raise BrokerInputError("DUPLICATE_TARGET_OR_UNDECLARED_ARTIFACT")
            seen_paths.add(rel)
            expected_base = change.get("base_blob")
            if not isinstance(expected_base, str) or not SHA1.fullmatch(expected_base):
                raise BrokerInputError("INVALID_BASE_BLOB")
            base = _read(base_root, rel)
            head = _read(head_root, rel)
            proposed = _read(package_dir, artifact)
            base_oid = git_blob_oid(base)
            if base_oid != expected_base:
                raise BrokerInputError(f"BASE_BLOB_MISMATCH:{rel}")
            head_oid, proposed_oid = git_blob_oid(head), git_blob_oid(proposed)
            if head_oid == proposed_oid:
                classification, merged = "NOOP", head
            elif head_oid == base_oid:
                classification, merged = "CLEAN", proposed
            else:
                classification, merged = _merge_text(head, base, proposed)
            result["changes"].append({"path": rel, "base_blob": base_oid,
                "head_blob": head_oid, "proposed_blob": proposed_oid,
                "classification": classification, "manual_resolution": classification == "CONFLICT"})
            if classification != "CONFLICT":
                result["patch"] += _patch(head, merged, rel)
        census = build_batch_census(package_dir.parent, prior_ledger)
        matching = [x for x in census["packages"] if x["package"] == package_dir.name]
        if len(matching) != 1 or census["duplicate_session_ids"] or census["batch_verdict"] != "ACCEPT":
            raise BrokerInputError("GMI_BATCH_LEDGER_REJECT_OR_DUPLICATE")
        item = matching[0]
        result["idempotency_state"] = item["idempotency_state"]
        result["idempotency_key"] = item["idempotency_key"]
        result["updated_ledger_candidate"] = census["updated_ledger"]
        if item["idempotency_state"] in {"INVALID", "DUPLICATE", "CHANGED"}:
            raise BrokerInputError("SESSION_REUSE_OR_INVALID_IDEMPOTENCY")
        if item["idempotency_state"] == "UNCHANGED":
            result["disposition"] = "NOOP_DUPLICATE"
            result["patch"] = ""
            return result
        states = {v["classification"] for v in result["changes"]}
        if "CONFLICT" in states:
            result["disposition"] = "CONFLICT"
            result["patch"] = ""  # Never silently emit an incomplete patch on conflict.
            return result
        result["disposition"] = "THREE_WAY" if "THREE_WAY" in states else ("NOOP" if states == {"NOOP"} else "CLEAN")
        safe_session = re.sub(r"[^a-z0-9-]", "-", validity["session_id"].lower())[:42]
        result["branch_plan"] = {
            "branch": f"broker/w2/{safe_session}-{item['idempotency_key'][:10]}",
            "base_sha": profile["base_sha"], "head_sha": profile["head_sha"],
            "draft_pr_only": True, "dispatch_disabled": True,
            "admission": "HOLD_PENDING_SNAPSHOT_VERIFICATION_AND_REVIEW",
        }
        return result
    except (BrokerInputError, KeyError, TypeError, ValueError, OSError) as exc:
        result["errors"].append(str(exc))
        result["patch"] = ""
        result["changes"] = []
        result["branch_plan"] = None
        result["disposition"] = "HOLD"
        return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--base-root", type=Path, required=True)
    parser.add_argument("--head-root", type=Path, required=True)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--ledger-in", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        prior = load_ledger(args.ledger_in)
        result = evaluate_proposal(args.package, args.base_root, args.head_root, repo=args.repo, prior_ledger=prior)
    except (OSError, UnicodeError, ValueError, TypeError, json.JSONDecodeError) as exc:
        result = {"receipt_type": RECEIPT, "disposition": "HOLD", "errors": [str(exc)], "github_mutated": False}
    rendered = json.dumps(result, sort_keys=True, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0 if result["disposition"] in {"CLEAN", "THREE_WAY", "NOOP", "NOOP_DUPLICATE"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
