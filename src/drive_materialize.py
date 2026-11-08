"""Materialize one Drive lane (Git bundle + SHA-256 sidecar) into a local worktree.

Google Drive carries lanes; a live repository never sits inside a synced Drive
folder. A lane folder holds ``<name>.bundle`` and ``<name>.bundle.sha256``. This
module checks the bundle bytes against the sidecar before Git touches them,
refuses a target inside Drive or inside the lane folder, clones the bundle,
runs ``git bundle verify``, checks out the expected commit on the lane branch
and emits a machine-readable receipt.

It also validates the lane registry ``00_CONTROL/LANE_MATRIX.yaml``: lanes in
the same repository may run concurrently only when their file sets are disjoint.

The module never writes to Drive, never pushes and never contacts GitHub.
Setting ``--origin-url`` only rewrites the clone's local remote configuration.

Usage (from the repository root)::

    python -m src.drive_materialize materialize --bundle LANE/GEMINI_6136b9eb.bundle \
        --target C:/repos/_wt/gemini-L-GEMINI-01 --lane-id L-GEMINI-01 \
        --expected-commit 6136b9ebd976b994afefc57cc7d3497060e45a3e \
        --branch lane/L-GEMINI-01-drive-materialize \
        --origin-url https://github.com/GBOGEB/GEMINI.git --receipt materialize_receipt.json
    python -m src.drive_materialize check-matrix 00_CONTROL/LANE_MATRIX.yaml
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

import yaml

from src.drive_ingress import DriveIngressError, write_status
from src.handover_package import _load_yaml, _sha256, _validate_json_value

RECEIPT_SCHEMA = "gemini.lane_materialize_receipt.v1"
MATRIX_SCHEMA = "gemini.lane_matrix.v1"
BUNDLE_SIGNATURES = (b"# v2 git bundle", b"# v3 git bundle")
MAX_BUNDLE_HEADER_BYTES = 1024 * 1024
SHA_RE = re.compile(r"^[0-9a-f]{40}$|^[0-9a-f]{64}$")
SHA256_HEX_RE = re.compile(r"^[0-9a-f]{64}$")
LANE_ID_RE = re.compile(r"^L-[A-Z0-9][A-Z0-9-]*$")
REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
# Folder names that Google Drive for desktop uses for its synced roots (English and Dutch UI).
DRIVE_PATH_MARKERS = {
    "my drive",
    "mijn drive",
    "shared drives",
    "gedeelde drives",
    "google drive",
}
LANE_STATES = {
    "PROPOSED",
    "CLAIMED",
    "BUILDING",
    "PR_OPEN",
    "MERGED",
    "HISTORICAL",
    "BLOCKED_RETURN",
}
LIVE_STATES = {"CLAIMED", "BUILDING", "PR_OPEN"}
INACTIVE_STATES = {"MERGED", "HISTORICAL"}


class MaterializeError(DriveIngressError):
    """A classified, fail-closed lane materialization failure."""


def read_sidecar(sidecar: Path, bundle_name: str) -> str:
    """Return the SHA-256 from a ``sha256sum``-style sidecar (``<hex>`` or ``<hex>  <name>``)."""

    if not sidecar.is_file():
        raise MaterializeError(
            "SIDECAR_MISSING", f"SHA-256 sidecar not found: {sidecar}"
        )
    lines = [
        line.strip()
        for line in sidecar.read_text(encoding="utf-8-sig").splitlines()
        if line.strip()
    ]
    if len(lines) != 1:
        raise MaterializeError(
            "SIDECAR_INVALID", "sidecar must hold exactly one non-empty line"
        )
    parts = lines[0].split()
    digest = parts[0].lower()
    if not SHA256_HEX_RE.match(digest) or len(parts) > 2:
        raise MaterializeError(
            "SIDECAR_INVALID",
            "sidecar line must be '<64 hex>' or '<64 hex>  <filename>'",
        )
    if len(parts) == 2 and parts[1].lstrip("*") != bundle_name:
        raise MaterializeError(
            "SIDECAR_NAME_MISMATCH",
            f"sidecar names {parts[1]!r}, but the bundle is {bundle_name!r}",
        )
    return digest


def read_bundle_header(bundle: Path) -> dict[str, Any]:
    """Parse the plain-text bundle header: version, capabilities, prerequisites and refs."""

    refs: dict[str, str] = {}
    prerequisites: list[str] = []
    capabilities: list[str] = []
    consumed = 0
    with bundle.open("rb") as handle:
        signature = handle.readline().rstrip(b"\n")
        consumed += len(signature) + 1
        if signature not in BUNDLE_SIGNATURES:
            raise MaterializeError(
                "BUNDLE_SIGNATURE_INVALID", "file is not a v2 or v3 Git bundle"
            )
        while True:
            raw = handle.readline()
            consumed += len(raw)
            if not raw or consumed > MAX_BUNDLE_HEADER_BYTES:
                raise MaterializeError(
                    "BUNDLE_HEADER_INVALID",
                    "bundle header has no terminating blank line",
                )
            try:
                line = raw.rstrip(b"\n").decode("utf-8")
            except UnicodeDecodeError as exc:
                raise MaterializeError(
                    "BUNDLE_HEADER_INVALID", "bundle header is not UTF-8"
                ) from exc
            if line == "":
                break
            if line.startswith("@"):
                capabilities.append(line[1:])
            elif line.startswith("-"):
                prerequisites.append(line[1:].split(" ", 1)[0])
            else:
                sha, _, ref = line.partition(" ")
                if not SHA_RE.match(sha) or not ref:
                    raise MaterializeError(
                        "BUNDLE_HEADER_INVALID", f"unreadable bundle ref line: {line!r}"
                    )
                refs[ref] = sha
    return {
        "version": signature.decode("ascii").split()[1],
        "capabilities": capabilities,
        "prerequisites": prerequisites,
        "refs": refs,
    }


def _is_within(child: Path, parent: Path) -> bool:
    return child == parent or parent in child.parents


def check_target(target: Path, lane_dir: Path) -> None:
    """Refuse a clone target inside Drive or the lane folder, or one that already holds files."""

    resolved = target.resolve()
    if _is_within(resolved, lane_dir.resolve()):
        raise MaterializeError(
            "TARGET_IN_DRIVE", "target is inside the lane folder; clone outside Drive"
        )
    if any(part.casefold() in DRIVE_PATH_MARKERS for part in resolved.parts):
        raise MaterializeError(
            "TARGET_IN_DRIVE", "target is inside a Google Drive synced folder"
        )
    if resolved.exists() and (not resolved.is_dir() or any(resolved.iterdir())):
        raise MaterializeError(
            "TARGET_NOT_EMPTY", f"target already exists and is not empty: {resolved}"
        )


def _git(args: list[str], code: str, cwd: Path | None = None) -> str:
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except OSError as exc:
        raise MaterializeError(
            "GIT_UNAVAILABLE", f"git could not be started: {exc}"
        ) from exc
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()[:500]
        raise MaterializeError(code, f"git {args[0]} failed: {detail}")
    return (completed.stdout + completed.stderr).strip()


def materialize(
    bundle: Path,
    target: Path,
    lane_id: str,
    expected_commit: str,
    branch: str,
    sidecar: Path | None = None,
    origin_url: str | None = None,
) -> dict[str, Any]:
    """Verify then clone one lane bundle. Returns a PASS receipt or raises MaterializeError."""

    if not LANE_ID_RE.match(lane_id):
        raise MaterializeError(
            "LANE_ID_INVALID", f"lane id must look like L-NAME-01, got {lane_id!r}"
        )
    expected = expected_commit.lower()
    if not SHA_RE.match(expected):
        raise MaterializeError(
            "EXPECTED_COMMIT_INVALID",
            "expected commit must be a full 40 or 64 hex object ID",
        )
    if not bundle.is_file():
        raise MaterializeError("BUNDLE_MISSING", f"bundle not found: {bundle}")
    bundle = bundle.resolve()
    sidecar = (sidecar or bundle.with_name(bundle.name + ".sha256")).resolve()

    want = read_sidecar(sidecar, bundle.name)
    actual = _sha256(bundle)
    if actual != want:
        raise MaterializeError(
            "SHA256_MISMATCH", f"bundle SHA-256 {actual} does not match sidecar {want}"
        )

    header = read_bundle_header(bundle)
    if header["prerequisites"]:
        raise MaterializeError(
            "BUNDLE_HAS_PREREQUISITES",
            "incremental bundle needs commits that a fresh clone lacks; ship a full bundle",
        )
    if expected not in header["refs"].values():
        raise MaterializeError(
            "EXPECTED_COMMIT_NOT_ADVERTISED",
            "no bundle ref points at the expected commit",
        )

    check_target(target, bundle.parent)
    target = target.resolve()
    created = not target.exists()
    try:
        _git(
            ["clone", "--quiet", "--no-checkout", str(bundle), str(target)],
            "BUNDLE_CLONE_FAILED",
        )
        verify_output = _git(
            ["bundle", "verify", str(bundle)], "BUNDLE_VERIFY_FAILED", cwd=target
        )
        _git(
            ["switch", "--quiet", "-c", branch, expected],
            "LANE_BRANCH_FAILED",
            cwd=target,
        )
        head = _git(["rev-parse", "HEAD"], "HEAD_UNREADABLE", cwd=target)
        if head != expected:
            raise MaterializeError(
                "HEAD_MISMATCH", f"HEAD is {head}, expected {expected}"
            )
        if origin_url:
            _git(
                ["remote", "set-url", "origin", origin_url],
                "ORIGIN_SET_FAILED",
                cwd=target,
            )
        origin = _git(["remote", "get-url", "origin"], "ORIGIN_UNREADABLE", cwd=target)
    except MaterializeError:
        if created and target.exists():
            shutil.rmtree(target, ignore_errors=True)
        raise

    return {
        "schema": RECEIPT_SCHEMA,
        "result": "PASS",
        "classification": "LANE_MATERIALIZED",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "lane_id": lane_id,
        "bundle_filename": bundle.name,
        "bundle_sha256": actual,
        "bundle_bytes": bundle.stat().st_size,
        "bundle_version": header["version"],
        "advertised_refs": header["refs"],
        "git_bundle_verify": "PASS",
        "verify_output": verify_output.splitlines(),
        "expected_commit": expected,
        "head": head,
        "branch": branch,
        "target": str(target),
        "origin_url": origin,
        "drive_mutated": False,
        "pushed": False,
        "authority_transfer": False,
        "formal_credit_delta": 0,
    }


def _safe_repo_path(raw: Any) -> str | None:
    if not isinstance(raw, str) or not raw or "\\" in raw:
        return None
    path = PurePosixPath(raw)
    if (
        not path.parts
        or path.is_absolute()
        or ".." in path.parts
        or ":" in path.parts[0]
    ):
        return None
    return str(path)


def _overlaps(left: str, right: str) -> bool:
    return left == right or left.startswith(right + "/") or right.startswith(left + "/")


def check_lane_matrix(matrix: Any) -> list[str]:
    """Return every rule the lane registry breaks; an empty list means it is valid."""

    try:
        _validate_json_value(matrix)
    except (TypeError, ValueError) as exc:
        return [
            f"not canonical JSON-compatible YAML ({exc}); quote dates such as as_of"
        ]
    if not isinstance(matrix, dict):
        return ["root must be a mapping"]
    errors: list[str] = []
    if matrix.get("schema") != MATRIX_SCHEMA:
        errors.append(f"schema must be {MATRIX_SCHEMA!r}")
    if not isinstance(matrix.get("root_folder_id"), str) or not matrix.get(
        "root_folder_id"
    ):
        errors.append("root_folder_id must be a non-empty string")
    lanes = matrix.get("lanes")
    if not isinstance(lanes, list) or not lanes:
        return [*errors, "lanes must be a non-empty list"]

    seen: set[str] = set()
    claims: list[
        tuple[str, str, str]
    ] = []  # (repo, path, lane id) for lanes that are not finished
    for index, lane in enumerate(lanes):
        where = f"lanes[{index}]"
        if not isinstance(lane, dict):
            errors.append(f"{where}: must be a mapping")
            continue
        lane_id = lane.get("id")
        if not isinstance(lane_id, str) or not LANE_ID_RE.match(lane_id):
            errors.append(f"{where}: id must look like L-NAME-01")
            lane_id = where
        elif lane_id in seen:
            errors.append(f"{lane_id}: duplicate lane id")
        seen.add(lane_id)
        repo = lane.get("repo")
        if not isinstance(repo, str) or not REPO_RE.match(repo):
            errors.append(f"{lane_id}: repo must be owner/name")
        if not isinstance(lane.get("purpose"), str) or not lane.get("purpose"):
            errors.append(f"{lane_id}: purpose must be a non-empty string")
        state = lane.get("state")
        if state not in LANE_STATES:
            errors.append(f"{lane_id}: state must be one of {sorted(LANE_STATES)}")
        owner = lane.get("owner_session")
        if state in LIVE_STATES and (not isinstance(owner, str) or not owner):
            errors.append(f"{lane_id}: a {state} lane must name its owner_session")
        files = lane.get("files", [])
        if not isinstance(files, list):
            errors.append(f"{lane_id}: files must be a list")
            continue
        for raw in files:
            path = _safe_repo_path(raw)
            if path is None:
                errors.append(
                    f"{lane_id}: file {raw!r} must be a relative POSIX path inside the repo"
                )
            elif state not in INACTIVE_STATES and isinstance(repo, str):
                claims.append((repo, path, lane_id))

    for i, (repo_a, path_a, lane_a) in enumerate(claims):
        for repo_b, path_b, lane_b in claims[i + 1 :]:
            if lane_a != lane_b and repo_a == repo_b and _overlaps(path_a, path_b):
                errors.append(
                    f"{lane_a} and {lane_b} both claim {path_a if len(path_a) <= len(path_b) else path_b}"
                )
    return errors


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="command", required=True)
    mat = sub.add_parser(
        "materialize", help="verify a lane bundle and clone it outside Drive"
    )
    mat.add_argument("--bundle", required=True, type=Path)
    mat.add_argument("--sidecar", type=Path, help="default: <bundle>.sha256")
    mat.add_argument("--target", required=True, type=Path)
    mat.add_argument("--lane-id", required=True)
    mat.add_argument("--expected-commit", required=True)
    mat.add_argument("--branch", required=True)
    mat.add_argument("--origin-url")
    mat.add_argument("--receipt", help="write the PASS or FAIL receipt here as JSON")
    chk = sub.add_parser("check-matrix", help="validate 00_CONTROL/LANE_MATRIX.yaml")
    chk.add_argument("matrix", type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.command == "check-matrix":
        try:
            errors = check_lane_matrix(_load_yaml(args.matrix))
        except (OSError, TypeError, ValueError, yaml.YAMLError) as exc:
            errors = [str(exc)]
        for error in errors:
            print(f"LANE_MATRIX_INVALID: {error}", file=sys.stderr)
        if not errors:
            print(f"LANE_MATRIX_VALID: {args.matrix}", file=sys.stderr)
        return 3 if errors else 0

    try:
        receipt = materialize(
            bundle=args.bundle,
            target=args.target,
            lane_id=args.lane_id,
            expected_commit=args.expected_commit,
            branch=args.branch,
            sidecar=args.sidecar,
            origin_url=args.origin_url,
        )
    except MaterializeError as exc:
        write_status(
            args.receipt,
            {
                "schema": RECEIPT_SCHEMA,
                "result": "FAIL",
                "classification": exc.code,
                "message": str(exc),
                "lane_id": args.lane_id,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        print(f"{exc.code}: {exc}", file=sys.stderr)
        return 3
    write_status(args.receipt, receipt)
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
