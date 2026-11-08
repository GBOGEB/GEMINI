"""GM-I-C R2-W1: exact-SHA repository snapshot for the GitHub -> Drive publish direction.

Builds a plain-file export of one commit (no git metadata) plus a ``gmi.repo_snapshot.v1``
manifest that binds every file to its git blob OID, then verifies a snapshot directory
against that manifest by recomputing the OIDs from the bytes on disk.

This module is offline. It does not authenticate to Google, upload to Drive, or prove IC2
or IC3. A snapshot is a read copy: GitHub stays the source of truth, and the manifest's
``commit_sha`` is the only key a snapshot census may be compared on.
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import subprocess
import sys
from pathlib import Path, PurePosixPath
from typing import Any

from src.handover_package import PACKAGE_VERDICTS, canonical_manifest_digest

SCHEMA = "gmi.repo_snapshot.v1"
MANIFEST_NAME = "SNAPSHOT_MANIFEST.json"
FILES_DIR = "files"
# Paths that must never be published to a shared Drive folder, even if committed.
DEFAULT_DENY = (
    ".env",
    ".env.local",
    ".env.*.local",
    "*.pem",
    "*.p12",
    "*.pfx",
    "*.key",
    "id_rsa*",
    "id_ed25519*",
    "gha-creds-*.json",
    "*service-account*.json",
    "credentials*.json",
)
FRESHNESS = {"FRESH", "STALE"}


class SnapshotError(RuntimeError):
    """Raised when a snapshot cannot be built without breaking the contract."""


def git_blob_oid(data: bytes) -> str:
    """Return the SHA-1 git blob OID for ``data`` (same value as ``git hash-object``)."""
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def _git(repo: Path, *args: str, data: bytes | None = None) -> bytes:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        input=data,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise SnapshotError(f"git {' '.join(args)} failed: {result.stderr.decode(errors='replace').strip()}")
    return result.stdout


def _denied(path: str, deny: tuple[str, ...]) -> bool:
    name = PurePosixPath(path).name
    return any(fnmatch.fnmatchcase(name, pattern) or fnmatch.fnmatchcase(path, pattern) for pattern in deny)


def _safe_relpath(raw: str) -> PurePosixPath:
    rel = PurePosixPath(raw)
    if rel.is_absolute() or ".." in rel.parts or ".git" in rel.parts or not rel.parts:
        raise SnapshotError(f"unsafe path in tree: {raw!r}")
    return rel


def _list_tree(repo: Path, commit: str) -> list[tuple[str, str, str, str]]:
    raw = _git(repo, "ls-tree", "-r", "-z", "--full-tree", commit)
    entries = []
    for record in raw.split(b"\0"):
        if not record:
            continue
        meta, path = record.split(b"\t", 1)
        mode, kind, oid = meta.decode().split(" ")
        entries.append((mode, kind, oid, path.decode("utf-8")))
    return entries


def _read_blobs(repo: Path, oids: list[str]) -> dict[str, bytes]:
    if not oids:
        return {}
    out = _git(repo, "cat-file", "--batch", data=("\n".join(oids) + "\n").encode())
    blobs: dict[str, bytes] = {}
    pos = 0
    for oid in oids:
        header_end = out.index(b"\n", pos)
        got_oid, kind, size = out[pos:header_end].decode().split(" ")
        if got_oid != oid or kind != "blob":
            raise SnapshotError(f"unexpected cat-file record for {oid}: {kind}")
        start = header_end + 1
        end = start + int(size)
        blobs[oid] = out[start:end]
        pos = end + 1
    return blobs


def build_manifest(
    repo: Path,
    commit: str = "HEAD",
    repo_name: str | None = None,
    generated_at: str | None = None,
    deny: tuple[str, ...] = DEFAULT_DENY,
) -> tuple[dict[str, Any], dict[str, bytes]]:
    """Return the manifest and ``{path: bytes}`` for one commit without touching the filesystem."""
    commit_sha = _git(repo, "rev-parse", "--verify", f"{commit}^{{commit}}").decode().strip()
    tree_sha = _git(repo, "rev-parse", f"{commit_sha}^{{tree}}").decode().strip()
    if generated_at is None:
        # Deterministic default: the commit's own committer date, not wall-clock time.
        generated_at = _git(repo, "show", "-s", "--format=%cI", commit_sha).decode().strip()

    files: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    denied: list[str] = []
    wanted: list[tuple[str, str, str]] = []
    for mode, kind, oid, path in _list_tree(repo, commit_sha):
        _safe_relpath(path)
        if kind == "commit":
            skipped.append({"path": path, "kind": "submodule", "oid": oid})
        elif mode == "120000":
            skipped.append({"path": path, "kind": "symlink", "oid": oid})
        elif _denied(path, deny):
            denied.append(path)
        else:
            wanted.append((mode, oid, path))
    if denied:
        raise SnapshotError(f"refusing to publish deny-listed paths: {sorted(denied)}")

    blobs = _read_blobs(repo, sorted({oid for _, oid, _ in wanted}))
    contents: dict[str, bytes] = {}
    for mode, oid, path in sorted(wanted, key=lambda item: item[2]):
        data = blobs[oid]
        if git_blob_oid(data) != oid:
            raise SnapshotError(f"blob OID mismatch for {path}")
        contents[path] = data
        files.append({"path": path, "mode": mode, "git_blob_oid": oid, "size": len(data)})

    manifest: dict[str, Any] = {
        "schema": SCHEMA,
        "repo": repo_name or "",
        "commit_sha": commit_sha,
        "tree_sha": tree_sha,
        "generated_at": generated_at,
        "file_count": len(files),
        "files": files,
        "skipped": sorted(skipped, key=lambda item: item["path"]),
        "deny_patterns": list(deny),
        "nonclaims": [
            "SNAPSHOT_NE_SOURCE_OF_TRUTH",
            "OFFLINE_SNAPSHOT_NE_IC2_OR_IC3_PASS",
            "NO_GIT_METADATA_PUBLISHED",
        ],
    }
    manifest["manifest_sha256"] = canonical_manifest_digest(manifest)
    return manifest, contents


def write_snapshot(out_dir: Path, manifest: dict[str, Any], contents: dict[str, bytes]) -> Path:
    """Write ``files/`` and the manifest. Refuses a non-empty target so nothing stale survives."""
    if out_dir.exists() and any(out_dir.iterdir()):
        raise SnapshotError(f"output directory is not empty: {out_dir}")
    files_root = out_dir / FILES_DIR
    for path, data in contents.items():
        target = files_root.joinpath(*_safe_relpath(path).parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    manifest_path = out_dir / MANIFEST_NAME
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest_path


def verify_snapshot(snapshot_dir: Path) -> dict[str, Any]:
    """Recompute every blob OID from disk; return ``ACCEPT`` only on an exact match."""
    reasons: list[str] = []
    manifest_path = snapshot_dir / MANIFEST_NAME
    if not manifest_path.is_file():
        return {"verdict": "REJECT", "reasons": ["MANIFEST_MISSING"], "commit_sha": None}
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema") != SCHEMA:
        reasons.append("SCHEMA_MISMATCH")
    claimed = manifest.get("manifest_sha256")
    body = {key: value for key, value in manifest.items() if key != "manifest_sha256"}
    if claimed != canonical_manifest_digest(body):
        reasons.append("MANIFEST_DIGEST_MISMATCH")

    files_root = snapshot_dir / FILES_DIR
    expected = {row["path"]: row for row in manifest.get("files", [])}
    if manifest.get("file_count") != len(expected):
        reasons.append("FILE_COUNT_MISMATCH")
    on_disk: set[str] = set()
    if files_root.is_dir():
        for item in files_root.rglob("*"):
            rel = item.relative_to(files_root).as_posix()
            if ".git" in PurePosixPath(rel).parts:
                reasons.append(f"GIT_METADATA_PRESENT:{rel}")
            elif item.is_file():
                on_disk.add(rel)
    for path in sorted(set(expected) - on_disk):
        reasons.append(f"MISSING:{path}")
    for path in sorted(on_disk - set(expected)):
        reasons.append(f"UNEXPECTED:{path}")
    for path in sorted(set(expected) & on_disk):
        data = files_root.joinpath(*PurePosixPath(path).parts).read_bytes()
        if git_blob_oid(data) != expected[path]["git_blob_oid"]:
            reasons.append(f"OID_MISMATCH:{path}")

    verdict = "REJECT" if reasons else "ACCEPT"
    assert verdict in PACKAGE_VERDICTS
    return {"verdict": verdict, "reasons": reasons, "commit_sha": manifest.get("commit_sha")}


def freshness(manifest: dict[str, Any], head_sha: str) -> dict[str, str]:
    """Label a snapshot against the current default-branch head (disjointed-census rule)."""
    state = "FRESH" if manifest.get("commit_sha") == head_sha else "STALE"
    assert state in FRESHNESS
    return {"freshness": state, "snapshot_sha": manifest.get("commit_sha", ""), "head_sha": head_sha}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build", help="export one commit and write the manifest")
    build.add_argument("--repo", type=Path, default=Path("."))
    build.add_argument("--commit", default="HEAD")
    build.add_argument("--repo-name", default="")
    build.add_argument("--out", type=Path, required=True)
    verify = sub.add_parser("verify", help="verify a snapshot directory against its manifest")
    verify.add_argument("snapshot", type=Path)
    status = sub.add_parser("status", help="label a snapshot FRESH or STALE against a head SHA")
    status.add_argument("snapshot", type=Path)
    status.add_argument("--head", required=True)
    args = parser.parse_args(argv)

    try:
        if args.command == "build":
            manifest, contents = build_manifest(args.repo, args.commit, args.repo_name or None)
            write_snapshot(args.out, manifest, contents)
            result: dict[str, Any] = {
                "result": "BUILT",
                "commit_sha": manifest["commit_sha"],
                "file_count": manifest["file_count"],
                "manifest_sha256": manifest["manifest_sha256"],
            }
        elif args.command == "verify":
            result = verify_snapshot(args.snapshot)
        else:
            manifest = json.loads((args.snapshot / MANIFEST_NAME).read_text(encoding="utf-8"))
            result = freshness(manifest, args.head)
    except SnapshotError as exc:
        print(json.dumps({"result": "FAIL", "error": str(exc)}))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0 if result.get("verdict", "ACCEPT") == "ACCEPT" else 1


if __name__ == "__main__":
    sys.exit(main())
