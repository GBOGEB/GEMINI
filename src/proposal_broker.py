"""GM-I-C R2-W2: dry-run proposal ingest broker for the Drive -> GitHub direction.

A Drive-only agent cannot push. It returns a change as a GMI handover package (see
``docs/bridge/PACKAGE_CONTRACT.md``) that carries the ``gmi.proposal_profile.v1``
profile: a ``proposal:`` section naming the commit it started from and, per file, the
git blob it last saw. This module turns such a package into a patch file and a draft
pull-request plan, or rejects it.

``gmi.proposal_profile.v1`` is a profile of the GMI package manifest, not a new schema.
The package is validated by ``handover_package.validate_package`` first, idempotency
comes from the ``handover_batch`` ledger, and path safety reuses ``repo_snapshot``.

The broker is offline and dry-run only. It never pushes, never calls GitHub, never
writes to Drive and never edits the target repository (it reads it with ``git ls-tree``
and ``git cat-file`` only). Proposal text is data: nothing in a manifest can change a
verdict, a branch name, the draft flag or the push behaviour.

Usage (from the repository root)::

    python -m src.proposal_broker ingest <workspace with GMI-* packages> \
        --repo . --repo-name GBOGEB/GEMINI --head origin/main \
        --ledger-in ledger.json --ledger-out ledger.json --out <empty dir outside Drive>
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path, PurePosixPath
from typing import Any

import yaml

from src.drive_ingress import DriveIngressError
from src.drive_materialize import check_target
from src.handover_batch import build_batch_census, load_ledger
from src.handover_package import (
    PACKAGE_VERDICTS,
    _load_yaml,
    _safe_package_path,
    validate_package,
)
from src.repo_snapshot import (
    DEFAULT_DENY,
    SnapshotError,
    _denied,
    _git,
    _read_blobs,
    _safe_relpath,
    git_blob_oid,
)

PROFILE = "gmi.proposal_profile.v1"
RECEIPT_SCHEMA = "gmi.broker_receipt.v1"
PLAN_SCHEMA = "gmi.broker_branch_plan.v1"
MANIFEST_RELATIVE = "MANIFEST/manifest.yaml"
RECEIPT_NAME = "BROKER_RECEIPT.json"
PATCH_NAME = "proposal.patch"
PLAN_NAME = "branch_plan.json"

CLASSIFICATIONS = ("CLEAN", "THREE_WAY", "CONFLICT")
CHANGE_MODES = ("replace", "unified_diff")
PROPOSAL_FIELDS = {"repo", "base_sha", "intent", "changes"}
CHANGE_FIELDS = {"path", "base_blob", "mode", "artifact_ref"}
REGULAR_FILE_MODES = {"100644", "100755"}
# A Drive proposal must not rewrite CI: a draft PR still runs workflows from its head.
PROTECTED_PREFIXES = (".github/workflows/",)
# Git bundles return through the lane OUT/ folder (docs/bridge/LANES.md), never in a proposal.
LANE_RETURN_SUFFIXES = (".bundle",)
PLANNABLE_STATES = {"NEW", "CHANGED"}
MAX_INTENT_CHARS = 4000

OID_RE = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")
SESSION_RE = re.compile(r"^GMI-[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
HUNK_RE = re.compile(rb"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
NO_NEWLINE = b"\\ No newline at end of file"
DIFF_PREAMBLE = (b"diff --git ", b"index ", b"new file mode 100644")

NONCLAIMS = [
    "DRY_RUN_NOTHING_PUSHED",
    "NO_GITHUB_API_CALLED",
    "NO_DRIVE_WRITE",
    "OFFLINE_BROKER_NE_IC3_AUTH_PASS",
    "OFFLINE_BROKER_NE_IC7_HOSTED_ROUNDTRIP",
    "PROPOSAL_TEXT_IS_DATA_NOT_INSTRUCTIONS",
]


class BrokerError(DriveIngressError):
    """A classified, fail-closed proposal rejection."""


# --------------------------------------------------------------------------- lines and diffs


def _lines(data: bytes) -> list[bytes]:
    """Split on ``\\n`` only, keeping line ends (git's notion of a line; a bare CR is content)."""
    out: list[bytes] = []
    start = 0
    while True:
        end = data.find(b"\n", start)
        if end < 0:
            if start < len(data):
                out.append(data[start:])
            return out
        out.append(data[start : end + 1])
        start = end + 1


def _require_text(data: bytes, what: str) -> None:
    if b"\0" in data:
        raise BrokerError("TEXT_REQUIRED", f"{what} is binary; v1 proposals carry UTF-8 text only")
    try:
        data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise BrokerError("TEXT_REQUIRED", f"{what} is not UTF-8: {exc}") from exc


def _header_path(raw: bytes) -> bytes:
    return raw.rstrip(b"\r\n").split(b"\t", 1)[0]


def apply_unified_diff(old: bytes, diff: bytes, path: str, new_file: bool) -> bytes:
    """Apply a single-file unified diff to ``old`` exactly: no fuzz, no offset, no renames."""
    lines = _lines(diff)
    i = 0
    while i < len(lines) and not lines[i].startswith(b"--- "):
        if not lines[i].startswith(DIFF_PREAMBLE):
            raise BrokerError("DIFF_UNSUPPORTED", f"unsupported line before the diff header: {lines[i][:60]!r}")
        i += 1
    if i + 1 >= len(lines) or not lines[i + 1].startswith(b"+++ "):
        raise BrokerError("DIFF_MALFORMED", "missing ---/+++ header")
    expected_old = b"/dev/null" if new_file else b"a/" + path.encode("utf-8")
    if _header_path(lines[i][4:]) != expected_old or _header_path(lines[i + 1][4:]) != b"b/" + path.encode(
        "utf-8"
    ):
        raise BrokerError("DIFF_PATH_MISMATCH", f"diff header does not name {path!r}")
    i += 2
    if i >= len(lines):
        raise BrokerError("DIFF_MALFORMED", "diff has no hunks")

    src = _lines(old)
    out: list[bytes] = []
    pos = 0
    while i < len(lines):
        match = HUNK_RE.match(lines[i])
        if not match:
            raise BrokerError("DIFF_MALFORMED", f"expected a hunk header, got {lines[i][:60]!r}")
        old_start = int(match.group(1))
        old_len = int(match.group(2)) if match.group(2) is not None else 1
        new_len = int(match.group(4)) if match.group(4) is not None else 1
        anchor = old_start - 1 if old_len > 0 else old_start
        if anchor < pos or anchor > len(src):
            raise BrokerError("DIFF_HUNK_MISMATCH", f"hunk at line {old_start} is out of order or range")
        out.extend(src[pos:anchor])
        pos = anchor
        i += 1
        seen_old = seen_new = 0
        while i < len(lines) and (seen_old < old_len or seen_new < new_len):
            line = lines[i]
            if line in (b"\n", b"\r\n"):
                tag, body = b" ", line
            else:
                tag, body = line[:1], line[1:]
            i += 1
            if i < len(lines) and lines[i].rstrip(b"\r\n") == NO_NEWLINE:
                body = body[:-1] if body.endswith(b"\n") else body
                i += 1
            if tag in (b" ", b"-"):
                if pos >= len(src) or src[pos] != body:
                    raise BrokerError("DIFF_HUNK_MISMATCH", f"context does not match base near line {pos + 1}")
                pos += 1
                seen_old += 1
                if tag == b" ":
                    out.append(body)
                    seen_new += 1
            elif tag == b"+":
                out.append(body)
                seen_new += 1
            else:
                raise BrokerError("DIFF_MALFORMED", f"bad hunk line {line[:60]!r}")
        if seen_old != old_len or seen_new != new_len:
            raise BrokerError("DIFF_MALFORMED", "hunk line counts do not match its header")
    out.extend(src[pos:])
    return b"".join(out)


def render_file_diff(path: str, old: bytes | None, new: bytes, old_oid: str | None, file_mode: str) -> bytes:
    """Render a git-style unified diff for one text file (``old is None`` means a new file)."""
    new_oid = git_blob_oid(new)
    head = [f"diff --git a/{path} b/{path}\n".encode()]
    if old is None:
        head.append(f"new file mode {file_mode}\n".encode())
        head.append(f"index {'0' * len(new_oid)}..{new_oid}\n".encode())
    else:
        head.append(f"index {old_oid}..{new_oid} {file_mode}\n".encode())
    body = difflib.diff_bytes(
        difflib.unified_diff,
        _lines(old or b""),
        _lines(new),
        fromfile=b"/dev/null" if old is None else b"a/" + path.encode("utf-8"),
        tofile=b"b/" + path.encode("utf-8"),
        lineterm=b"\n",
    )
    rendered: list[bytes] = []
    for line in body:
        rendered.append(line)
        if not line.endswith(b"\n"):
            rendered.append(b"\n" + NO_NEWLINE + b"\n")
    return b"".join(head + rendered)


# --------------------------------------------------------------------------- git (read only)


def _tree_entry(repo: Path, commit: str, path: str) -> tuple[str, str, str] | None:
    raw = _git(repo, "--literal-pathspecs", "ls-tree", "-z", "--full-tree", commit, "--", path)
    for record in raw.split(b"\0"):
        if not record:
            continue
        meta, name = record.split(b"\t", 1)
        if name.decode("utf-8") == path:
            mode, kind, oid = meta.decode().split(" ")
            return mode, kind, oid
    return None


def _blob(repo: Path, oid: str) -> bytes:
    data = _read_blobs(repo, [oid])[oid]
    if git_blob_oid(data) != oid:
        raise BrokerError("BLOB_OID_MISMATCH", f"object {oid} does not hash to itself")
    return data


def _is_ancestor(repo: Path, ancestor: str, head: str) -> bool:
    result = subprocess.run(
        ["git", "-C", str(repo), "merge-base", "--is-ancestor", ancestor, head],
        capture_output=True,
        check=False,
    )
    if result.returncode not in (0, 1):
        raise BrokerError("GIT_FAILED", result.stderr.decode(errors="replace").strip()[:300])
    return result.returncode == 0


def merge_file(head: bytes, base: bytes, proposal: bytes) -> tuple[bytes, bool]:
    """Three-way merge with ``git merge-file`` on temp copies; returns (result, clean)."""
    # Not tempfile.TemporaryDirectory: its 0o700 mode becomes an owner-only ACL on Windows
    # with Python 3.12.4+, and git for Windows is then refused (same cause as the test note).
    tmp = Path(tempfile.gettempdir()) / f"gmi-broker-{uuid.uuid4().hex[:12]}"
    os.makedirs(tmp)
    try:
        names = []
        for name, data in (("head", head), ("base", base), ("proposal", proposal)):
            target = tmp / name
            target.write_bytes(data)
            names.append(str(target))
        result = subprocess.run(
            ["git", "merge-file", "-p", "-L", "head", "-L", "base", "-L", "proposal", *names],
            capture_output=True,
            check=False,
        )
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    # Exit status is the conflict count (capped at 127); a negative status means an error.
    if result.returncode < 0 or result.returncode > 127:
        raise BrokerError("MERGE_FILE_FAILED", result.stderr.decode(errors="replace").strip()[:300])
    return result.stdout, result.returncode == 0


# --------------------------------------------------------------------------- profile checks


def check_path(raw: Any, deny: tuple[str, ...] = DEFAULT_DENY) -> str:
    """Return ``raw`` if it is a safe, plain repository path that a proposal may touch."""
    if not isinstance(raw, str) or not raw:
        raise BrokerError("UNSAFE_PATH", f"path must be a non-empty string: {raw!r}")
    parts = raw.split("/")
    if any(part.casefold().rstrip(". ") == ".git" for part in parts):
        raise BrokerError("GIT_METADATA_PATH", f"proposal may not touch git metadata: {raw!r}")
    if (
        raw != raw.strip()
        or any(ch in raw for ch in "\\:`")
        or any(ord(ch) < 32 or ord(ch) == 127 for ch in raw)
        or any(part in ("", ".") for part in parts)
    ):
        raise BrokerError("UNSAFE_PATH", f"unsafe path: {raw!r}")
    try:
        rel = _safe_relpath(raw)
    except SnapshotError as exc:
        raise BrokerError("UNSAFE_PATH", str(exc)) from exc
    if rel.as_posix() != raw:
        raise BrokerError("UNSAFE_PATH", f"path is not in normal form: {raw!r}")
    folded_deny = tuple(pattern.casefold() for pattern in deny)
    if _denied(raw, deny) or _denied(raw.casefold(), folded_deny):
        raise BrokerError("DENIED_PATH", f"deny-listed secret path: {raw!r}")
    if raw.casefold().startswith(PROTECTED_PREFIXES):
        raise BrokerError("PROTECTED_PATH", f"Drive proposals may not change CI workflows: {raw!r}")
    return raw


def _check_session_id(session_id: Any, package_dir: Path) -> str:
    if (
        not isinstance(session_id, str)
        or not SESSION_RE.match(session_id)
        or ".." in session_id
        or session_id.endswith((".", ".lock"))
    ):
        raise BrokerError("UNSAFE_SESSION_ID", f"session_id is not a safe branch component: {session_id!r}")
    if package_dir.name != session_id:
        raise BrokerError("PACKAGE_NAME_MISMATCH", f"package folder {package_dir.name!r} != {session_id!r}")
    return session_id


def _check_package_tree(package_dir: Path) -> None:
    """One return path per proposer type: bundles and git metadata belong to the lane OUT/ path."""
    for item in sorted(package_dir.rglob("*")):
        rel = item.relative_to(package_dir).as_posix()
        if any(part.casefold().rstrip(". ") == ".git" for part in PurePosixPath(rel).parts):
            raise BrokerError("GIT_METADATA_IN_PACKAGE", f"package contains git metadata: {rel}")
        if item.is_file() and item.name.casefold().endswith(LANE_RETURN_SUFFIXES):
            raise BrokerError(
                "LANE_BUNDLE_IN_PROPOSAL",
                f"{rel}: git bundles return through the lane OUT/ folder, not a GMI proposal",
            )


def _reject_legacy_profile_marker(manifest: dict[str, Any]) -> None:
    """Refuse old #41 wire marker before any package or idempotency early return."""
    if "proposal_profile" in manifest:
        raise BrokerError(
            "AMBIGUOUS_LEGACY_PROFILE",
            "legacy proposal_profile is incompatible with canonical profile + proposal; "
            "no implicit migration or merged wire contracts",
        )


def _preflight_legacy_package(package_dir: Path) -> None:
    """Inspect only the manifest, before reading or hashing any change artifacts.

    Malformed or vanished manifests are handled by the ordinary package validator,
    while a valid historical wire marker is a hard stop regardless of idempotency.
    """
    try:
        manifest = _load_yaml(package_dir / MANIFEST_RELATIVE)
    except (OSError, TypeError, ValueError, yaml.YAMLError):
        return  # Existing canonical package validation classifies bad manifests.
    _reject_legacy_profile_marker(manifest)


def parse_profile(manifest: dict[str, Any], package_dir: Path) -> dict[str, Any]:
    """Validate the ``gmi.proposal_profile.v1`` part of an already-valid GMI manifest."""
    _reject_legacy_profile_marker(manifest)
    if manifest.get("profile") != PROFILE:
        raise BrokerError("NOT_A_PROPOSAL", f"manifest profile must be {PROFILE!r}")
    proposal = manifest.get("proposal")
    if not isinstance(proposal, dict):
        raise BrokerError("PROPOSAL_MALFORMED", "proposal must be a mapping")
    unknown = sorted(set(proposal) - PROPOSAL_FIELDS)
    missing = sorted(PROPOSAL_FIELDS - set(proposal))
    if unknown or missing:
        raise BrokerError("PROPOSAL_MALFORMED", f"proposal fields: unknown={unknown} missing={missing}")
    repo_name = proposal["repo"]
    base_sha = proposal["base_sha"]
    intent = proposal["intent"]
    changes = proposal["changes"]
    if not isinstance(repo_name, str) or not repo_name:
        raise BrokerError("PROPOSAL_MALFORMED", "proposal.repo must be owner/name")
    if not isinstance(base_sha, str) or not OID_RE.match(base_sha):
        raise BrokerError("PROPOSAL_MALFORMED", "proposal.base_sha must be a full lowercase commit SHA")
    if not isinstance(intent, str) or not intent.strip():
        raise BrokerError("PROPOSAL_MALFORMED", "proposal.intent must be a non-empty string")
    if len(intent) > MAX_INTENT_CHARS:
        raise BrokerError("INTENT_TOO_LONG", f"proposal.intent exceeds {MAX_INTENT_CHARS} characters")
    if not isinstance(changes, list) or not changes:
        raise BrokerError("PROPOSAL_MALFORMED", "proposal.changes must be a non-empty list")

    artifacts = {
        ref.get("id"): ref
        for ref in manifest.get("artifact_refs", [])
        if isinstance(ref, dict) and isinstance(ref.get("id"), str)
    }
    parsed: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, change in enumerate(changes):
        where = f"proposal.changes[{index}]"
        if not isinstance(change, dict):
            raise BrokerError("PROPOSAL_MALFORMED", f"{where} must be a mapping")
        unknown = sorted(set(change) - CHANGE_FIELDS)
        missing = sorted(CHANGE_FIELDS - set(change))
        if unknown or missing:
            raise BrokerError("PROPOSAL_MALFORMED", f"{where} fields: unknown={unknown} missing={missing}")
        path = check_path(change["path"])
        if path.casefold() in seen:
            raise BrokerError("DUPLICATE_PATH", f"{where}: {path!r} appears twice")
        seen.add(path.casefold())
        base_blob = change["base_blob"]
        if base_blob is not None and (not isinstance(base_blob, str) or not OID_RE.match(base_blob)):
            raise BrokerError("PROPOSAL_MALFORMED", f"{where}.base_blob must be a blob OID or null")
        mode = change["mode"]
        if mode not in CHANGE_MODES:
            raise BrokerError("PROPOSAL_MALFORMED", f"{where}.mode must be one of {list(CHANGE_MODES)}")
        ref = artifacts.get(change["artifact_ref"])
        if ref is None:
            raise BrokerError("ARTIFACT_MISSING", f"{where}.artifact_ref names no artifact_refs[].id")
        if ref.get("type") != "local_file" or ref.get("required", True) is not True:
            raise BrokerError("ARTIFACT_NOT_LOCAL", f"{where}: change artifacts must be required local_file refs")
        if not isinstance(ref.get("sha256"), str):
            raise BrokerError("ARTIFACT_SHA256_REQUIRED", f"{where}: change artifacts must carry sha256")
        try:
            artifact_path = _safe_package_path(package_dir, ref["path"])
        except (KeyError, TypeError, ValueError) as exc:
            raise BrokerError("ARTIFACT_MISSING", f"{where}: {exc}") from exc
        if not artifact_path.is_file():
            raise BrokerError("ARTIFACT_MISSING", f"{where}: artifact file missing")
        parsed.append(
            {
                "path": path,
                "base_blob": base_blob,
                "mode": mode,
                "artifact_ref": change["artifact_ref"],
                "artifact": artifact_path.read_bytes(),
            }
        )
    return {"repo": repo_name, "base_sha": base_sha, "intent": intent, "changes": parsed}


# --------------------------------------------------------------------------- concurrency


def _conflict(row: dict[str, Any], reason: str) -> dict[str, Any]:
    return {**row, "classification": "CONFLICT", "reason": reason, "new_blob": None, "noop": False}


def evaluate_change(repo: Path, base_sha: str, head_sha: str, change: dict[str, Any]) -> dict[str, Any]:
    """Optimistic-concurrency check of one change against ``head_sha``; returns a row plus diff."""
    path = change["path"]
    base_entry = _tree_entry(repo, base_sha, path)
    head_entry = _tree_entry(repo, head_sha, path)
    for entry in (base_entry, head_entry):
        if entry is not None and (entry[1] != "blob" or entry[0] not in REGULAR_FILE_MODES):
            raise BrokerError("PATH_NOT_REGULAR_FILE", f"{path!r} is a {entry[1]} with mode {entry[0]}")
    head_blob = head_entry[2] if head_entry else None
    row: dict[str, Any] = {
        "path": path,
        "mode": change["mode"],
        "base_blob": change["base_blob"],
        "head_blob": head_blob,
        "diff": b"",
    }
    actual_base = base_entry[2] if base_entry else None
    if actual_base != change["base_blob"]:
        return _conflict(row, "BASE_BLOB_NOT_AT_BASE_SHA")

    base_bytes = _blob(repo, actual_base) if actual_base else b""
    if change["mode"] == "replace":
        proposed = change["artifact"]
    else:
        proposed = apply_unified_diff(base_bytes, change["artifact"], path, new_file=actual_base is None)
    _require_text(proposed, f"proposed content for {path}")

    if head_blob == actual_base:
        classification, final = "CLEAN", proposed
        head_bytes = base_bytes if head_blob else None
    elif actual_base is None:
        return _conflict(row, "PATH_CREATED_ON_HEAD")
    elif head_blob is None:
        return _conflict(row, "PATH_DELETED_ON_HEAD")
    else:
        head_bytes = _blob(repo, head_blob)
        _require_text(head_bytes, f"head content of {path}")
        _require_text(base_bytes, f"base content of {path}")
        merged, clean = merge_file(head_bytes, base_bytes, proposed)
        if not clean:
            return _conflict(row, "THREE_WAY_MERGE_CONFLICT")
        classification, final = "THREE_WAY", merged

    noop = head_bytes is not None and final == head_bytes
    file_mode = head_entry[0] if head_entry else "100644"
    diff = b"" if noop else render_file_diff(path, head_bytes, final, head_blob, file_mode)
    if diff and apply_unified_diff(head_bytes or b"", diff, path, new_file=head_bytes is None) != final:
        raise BrokerError("PATCH_SELF_CHECK_FAILED", f"rendered diff for {path} does not reproduce the result")
    return {
        **row,
        "classification": classification,
        "reason": None,
        "new_blob": git_blob_oid(final),
        "noop": noop,
        "diff": diff,
    }


def evaluate_proposal(
    package_dir: Path, repo: Path, head_sha: str, repo_name: str
) -> dict[str, Any]:
    """Validate one package, check it against ``head_sha`` and return a broker evaluation."""
    package_dir = package_dir.resolve()
    result: dict[str, Any] = {
        "base_sha": None,
        "concurrency": None,
        "changes": [],
        "patch": b"",
        "intent": None,
        "reasons": [],
    }
    try:
        _preflight_legacy_package(package_dir)
    except BrokerError as exc:
        return {**result, "verdict": "REJECT", "reasons": [f"{exc.code}: {exc}"]}
    validation = validate_package(package_dir, MANIFEST_RELATIVE)
    if validation["verdict"] == "REJECT":
        return {**result, "verdict": "REJECT", "reasons": [f"PACKAGE_INVALID: {e}" for e in validation["errors"]]}
    if validation["verdict"] == "DEFER":
        return {**result, "verdict": "DEFER", "reasons": [f"PACKAGE_DEFERRED: {d}" for d in validation["deferred"]]}
    try:
        manifest = _load_yaml(package_dir / MANIFEST_RELATIVE)
        _check_session_id(manifest.get("session_id"), package_dir)
        _check_package_tree(package_dir)
        profile = parse_profile(manifest, package_dir)
        if profile["repo"] != repo_name:
            raise BrokerError("REPO_MISMATCH", f"proposal targets {profile['repo']!r}, broker runs for {repo_name!r}")
        result["base_sha"] = profile["base_sha"]
        result["intent"] = profile["intent"]
        try:
            _git(repo, "cat-file", "-e", f"{profile['base_sha']}^{{commit}}")
        except SnapshotError as exc:
            raise BrokerError("BASE_SHA_UNKNOWN", f"base_sha {profile['base_sha']} is not in the target repo") from exc
        if not _is_ancestor(repo, profile["base_sha"], head_sha):
            raise BrokerError("BASE_NOT_ANCESTOR_OF_HEAD", "base_sha is not an ancestor of the target head")
        rows = [evaluate_change(repo, profile["base_sha"], head_sha, change) for change in profile["changes"]]
    except BrokerError as exc:
        return {**result, "verdict": "REJECT", "reasons": [f"{exc.code}: {exc}"]}
    except (SnapshotError, OSError, UnicodeError) as exc:
        return {**result, "verdict": "REJECT", "reasons": [f"BROKER_IO_FAILED: {type(exc).__name__}: {exc}"]}

    rows.sort(key=lambda row: row["path"])
    classes = {row["classification"] for row in rows}
    concurrency = next(name for name in reversed(CLASSIFICATIONS) if name in classes)
    reasons = [f"CONCURRENCY_CONFLICT: {row['path']}: {row['reason']}" for row in rows if row["reason"]]
    if concurrency != "CONFLICT" and all(row["noop"] for row in rows):
        reasons.append("NO_EFFECTIVE_CHANGE: every change is already on head")
    patch = b"".join(row["diff"] for row in rows) if not reasons else b""
    verdict = "REJECT" if reasons else "ACCEPT"
    assert verdict in PACKAGE_VERDICTS
    return {
        **result,
        "verdict": verdict,
        "concurrency": concurrency,
        "changes": [{k: v for k, v in row.items() if k != "diff"} for row in rows],
        "patch": patch,
        "reasons": reasons,
    }


# --------------------------------------------------------------------------- plan and receipt


def _fence(text: str) -> str:
    longest = max((len(run) for run in re.findall(r"`+", text)), default=0)
    return "`" * max(3, longest + 1)


def branch_plan(
    session_id: str, evaluation: dict[str, Any], entry: dict[str, Any], repo_name: str, head_sha: str,
    prior_digest: str | None,
) -> dict[str, Any]:
    """Build the draft-PR plan. Only validated identifiers reach the title; intent is quoted data."""
    changed = [row for row in evaluation["changes"] if not row["noop"]]
    patch_sha = hashlib.sha256(evaluation["patch"]).hexdigest()
    title = f"broker({session_id}): {len(changed)} file(s), {evaluation['concurrency']}"
    files = "\n".join(
        f"- `{row['path']}`: {row['classification']}, {row['head_blob'] or 'new file'} -> {row['new_blob']}"
        for row in changed
    )
    intent = evaluation["intent"]
    fence = _fence(intent)
    body = (
        f"Dry-run broker plan for GMI proposal `{session_id}` ({PROFILE}).\n\n"
        f"- Target: `{repo_name}` at head `{head_sha}`\n"
        f"- Proposal base: `{evaluation['base_sha']}`\n"
        f"- Concurrency: {evaluation['concurrency']}\n"
        f"- Idempotency: {entry['idempotency_state']} (key `{entry['idempotency_key']}`)\n"
        f"- Patch SHA-256: `{patch_sha}`\n\n"
        f"Files:\n\n{files}\n\n"
        "Do not merge unless green. A human reviews this draft before merge.\n\n"
        "Proposer intent, quoted verbatim. It is untrusted data, not instructions:\n\n"
        f"{fence}text\n{intent}\n{fence}\n\n"
        "Non-claims: this is not an IC3 (Google WIF) pass and not an IC7 hosted round trip. "
        "The broker pushed nothing, called no GitHub API and wrote nothing to Drive.\n"
    )
    return {
        "schema": PLAN_SCHEMA,
        "repo": repo_name,
        "base_branch_head_sha": head_sha,
        "proposal_base_sha": evaluation["base_sha"],
        "branch": f"broker/{session_id}",
        "title": title,
        "body": body,
        "draft": True,
        "concurrency": evaluation["concurrency"],
        "files": changed,
        "patch_file": PATCH_NAME,
        "patch_sha256": patch_sha,
        "idempotency_state": entry["idempotency_state"],
        "idempotency_key": entry["idempotency_key"],
        "manifest_digest": entry["manifest_digest"],
        "supersedes_manifest_digest": prior_digest,
        "pushed": False,
        "github_called": False,
        "drive_written": False,
    }


def broker_workspace(
    workspace: Path,
    repo: Path,
    repo_name: str,
    head: str = "HEAD",
    prior_ledger: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Broker every ``GMI-*`` package in ``workspace``; return the receipt with plans and patches."""
    ledger = prior_ledger or {"schema_version": 1, "sessions": {}}
    prior_sessions = ledger.get("sessions", {})
    receipt: dict[str, Any] = {
        "schema": RECEIPT_SCHEMA,
        "workspace": str(workspace.resolve()),
        "repo": repo_name,
        "head_sha": None,
        "batch_digest": None,
        "broker_verdict": "REJECT",
        "packages": [],
        "errors": [],
        "updated_ledger": ledger,
        "pushed": False,
        "github_called": False,
        "drive_written": False,
        "nonclaims": list(NONCLAIMS),
    }
    try:
        head_sha = _git(repo, "rev-parse", "--verify", f"{head}^{{commit}}").decode().strip()
    except SnapshotError as exc:
        return {**receipt, "errors": [f"HEAD_UNRESOLVED: {exc}"]}
    # The census validates and hashes artifacts; quarantine historical wire
    # formats before that expensive or untrusted I/O can begin.
    try:
        for package in sorted(workspace.glob("GMI-*")):
            if package.is_dir():
                _preflight_legacy_package(package)
    except BrokerError as exc:
        return {**receipt, "head_sha": head_sha, "errors": [f"{exc.code}: {exc}"]}
    census = build_batch_census(workspace, ledger)
    receipt["head_sha"] = head_sha
    receipt["batch_digest"] = census["batch_digest"]
    if census["errors"]:
        return {**receipt, "errors": list(census["errors"])}

    sessions = dict(prior_sessions)
    rows: list[dict[str, Any]] = []
    for entry in census["packages"]:
        state = entry["idempotency_state"]
        session_id = entry["session_id"]
        row: dict[str, Any] = {
            "package": entry["package"],
            "session_id": session_id,
            "idempotency_state": state,
            "package_verdict": entry["package_verdict"],
            "manifest_digest": entry["manifest_digest"],
            "action": "REJECT",
            "broker_verdict": "REJECT",
            "concurrency": None,
            "changes": [],
            "reasons": [],
            "plan": None,
            "patch": b"",
        }
        if state not in {"DUPLICATE", "INVALID"}:
            try:
                _reject_legacy_profile_marker(_load_yaml(workspace / entry["package"] / MANIFEST_RELATIVE))
            except (BrokerError, OSError, TypeError, ValueError, yaml.YAMLError) as exc:
                reason = f"{exc.code}: {exc}" if isinstance(exc, BrokerError) else (
                    f"BROKER_MANIFEST_RACE: {type(exc).__name__}"
                )
                row["reasons"] = [reason]
                rows.append(row)
                continue
        if state == "DUPLICATE":
            row["reasons"] = ["DUPLICATE_SESSION: more than one package in this batch declares this session_id"]
        elif state == "INVALID":
            row["reasons"] = [f"PACKAGE_INVALID: {e}" for e in entry["errors"]] or ["PACKAGE_INVALID"]
        elif state == "UNCHANGED":
            if entry["package_verdict"] == "DEFER":
                row.update(
                    action="DEFER", broker_verdict="DEFER",
                    reasons=["PACKAGE_DEFERRED: unchanged status remains deferred"],
                )
            else:
                row.update(action="SKIP", broker_verdict="ACCEPT", reasons=["ALREADY_BROKERED: same session and digest"])
        elif state in PLANNABLE_STATES:
            evaluation = evaluate_proposal(workspace / entry["package"], repo, head_sha, repo_name)
            row.update(
                broker_verdict=evaluation["verdict"],
                concurrency=evaluation["concurrency"],
                changes=evaluation["changes"],
                reasons=evaluation["reasons"],
            )
            if evaluation["verdict"] == "ACCEPT":
                prior = prior_sessions.get(session_id) if state == "CHANGED" else None
                prior_digest = prior.get("manifest_digest") if isinstance(prior, dict) else None
                row["action"] = "PLAN"
                row["patch"] = evaluation["patch"]
                row["plan"] = branch_plan(session_id, evaluation, entry, repo_name, head_sha, prior_digest)
                # Remember only brokered proposals, so a rejected one is evaluated again when resent.
                sessions[session_id] = census["updated_ledger"]["sessions"][session_id]
            elif evaluation["verdict"] == "DEFER":
                row["action"] = "DEFER"
        else:
            row["reasons"] = [f"UNKNOWN_IDEMPOTENCY_STATE: {state}"]
        rows.append(row)

    verdicts = {row["broker_verdict"] for row in rows}
    if "REJECT" in verdicts:
        verdict = "REJECT"
    elif "DEFER" in verdicts or not rows:
        verdict = "DEFER"
    else:
        verdict = "ACCEPT"
    assert verdict in PACKAGE_VERDICTS
    return {
        **receipt,
        "broker_verdict": verdict,
        "packages": rows,
        "updated_ledger": {"schema_version": 1, "sessions": sessions},
    }


def write_outputs(out_dir: Path, workspace: Path, receipt: dict[str, Any]) -> Path:
    """Write per-session patch and plan plus the receipt into an empty folder outside Drive."""
    check_target(out_dir, workspace)
    out_dir.mkdir(parents=True, exist_ok=True)
    serialisable = dict(receipt)
    serialisable["packages"] = []
    for row in receipt["packages"]:
        row = dict(row)
        patch = row.pop("patch")
        if row["plan"] is not None:
            session_dir = out_dir / row["session_id"]
            session_dir.mkdir()
            (session_dir / PATCH_NAME).write_bytes(patch)
            (session_dir / PLAN_NAME).write_text(
                json.dumps(row["plan"], indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
            row["plan"] = f"{row['session_id']}/{PLAN_NAME}"
        serialisable["packages"].append(row)
    receipt_path = out_dir / RECEIPT_NAME
    receipt_path.write_text(json.dumps(serialisable, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return receipt_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    ingest = sub.add_parser("ingest", help="broker every GMI-* proposal package in a workspace (dry run)")
    ingest.add_argument("workspace", type=Path)
    ingest.add_argument("--repo", type=Path, default=Path("."))
    ingest.add_argument("--repo-name", required=True)
    ingest.add_argument("--head", default="HEAD")
    ingest.add_argument("--ledger-in", type=Path)
    ingest.add_argument("--ledger-out", type=Path)
    ingest.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)

    try:
        prior = load_ledger(args.ledger_in)
        receipt = broker_workspace(args.workspace, args.repo, args.repo_name, args.head, prior)
        write_outputs(args.out, args.workspace, receipt)
    except DriveIngressError as exc:
        print(json.dumps({"result": "FAIL", "code": exc.code, "error": str(exc)}))
        return 2
    except (OSError, UnicodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
        print(json.dumps({"result": "FAIL", "code": "BROKER_INGRESS_FAILED", "error": f"{type(exc).__name__}: {exc}"}))
        return 2
    if args.ledger_out:
        args.ledger_out.parent.mkdir(parents=True, exist_ok=True)
        args.ledger_out.write_text(json.dumps(receipt["updated_ledger"], indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "broker_verdict": receipt["broker_verdict"],
        "head_sha": receipt["head_sha"],
        "packages": [
            {"session_id": row["session_id"], "action": row["action"], "concurrency": row["concurrency"]}
            for row in receipt["packages"]
        ],
        "errors": receipt["errors"],
    }
    print(json.dumps(summary, sort_keys=True))
    return 0 if receipt["broker_verdict"] != "REJECT" else 1


if __name__ == "__main__":
    sys.exit(main())
