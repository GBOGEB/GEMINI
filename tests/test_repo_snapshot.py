import json
import os
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path

import pytest

from src.repo_snapshot import (
    MANIFEST_NAME,
    SnapshotError,
    build_manifest,
    freshness,
    git_blob_oid,
    main,
    verify_snapshot,
    write_snapshot,
)

GIT_ENV_ARGS = [
    "-c", "user.name=snapshot-test",
    "-c", "user.email=snapshot-test@example.invalid",
    "-c", "commit.gpgsign=false",
    "-c", "core.autocrlf=false",
]


@pytest.fixture()
def work():
    """Temp dir with default permissions.

    pytest's ``tmp_path`` is created with mode 0o700; on Windows with Python 3.12.4+ that
    becomes an owner-only ACL that a ``git`` child process may be refused (seen on the
    owner workstation). A default-mode directory avoids that and behaves the same on Linux.
    """
    path = Path(tempfile.gettempdir()) / f"repo-snapshot-{uuid.uuid4().hex[:12]}"
    os.makedirs(path)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *GIT_ENV_ARGS, *args], capture_output=True, text=True, check=True
    ).stdout.strip()


def _commit(repo: Path, files: dict[str, bytes], message: str = "c") -> str:
    for rel, data in files.items():
        path = repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", message)
    return _git(repo, "rev-parse", "HEAD")


@pytest.fixture()
def repo(work: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = work / "src_repo"
    root.mkdir()
    # Trust only this throwaway repo (command-scope config). On an admin Windows host the
    # directory owner can be BUILTIN\Administrators, which trips git's dubious-ownership check.
    monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
    monkeypatch.setenv("GIT_CONFIG_KEY_0", "safe.directory")
    monkeypatch.setenv("GIT_CONFIG_VALUE_0", root.as_posix())
    _git(root, "init", "-q")
    _commit(
        root,
        {
            "README.md": b"# demo\n",
            "docs/crlf.txt": b"line one\r\nline two\r\n",
            "data/blob.bin": bytes(range(256)),
            ".github/workflows/ci.yml": b"name: ci\n",
            ".env.example": b"TOKEN=\n",
        },
    )
    return root


def _build(repo: Path, out: Path, commit: str = "HEAD") -> dict:
    manifest, contents = build_manifest(repo, commit, "GBOGEB/demo")
    write_snapshot(out, manifest, contents)
    return manifest


def test_git_blob_oid_matches_git_hash_object(repo: Path) -> None:
    data = (repo / "docs/crlf.txt").read_bytes()
    assert git_blob_oid(data) == _git(repo, "hash-object", "docs/crlf.txt")


def test_build_binds_exact_commit_and_verifies(repo: Path, work: Path) -> None:
    out = work / "snap"
    manifest = _build(repo, out)
    assert manifest["commit_sha"] == _git(repo, "rev-parse", "HEAD")
    assert manifest["tree_sha"] == _git(repo, "rev-parse", "HEAD^{tree}")
    assert manifest["file_count"] == 5
    assert not (out / ".git").exists() and not (out / "files" / ".git").exists()
    # Bytes are exported raw: CRLF survives, so OIDs reproduce.
    assert (out / "files/docs/crlf.txt").read_bytes() == b"line one\r\nline two\r\n"
    assert verify_snapshot(out) == {"verdict": "ACCEPT", "reasons": [], "commit_sha": manifest["commit_sha"]}


def test_manifest_is_deterministic(repo: Path, work: Path) -> None:
    first = _build(repo, work / "a")
    second = _build(repo, work / "b")
    assert first["manifest_sha256"] == second["manifest_sha256"]
    assert (work / "a" / MANIFEST_NAME).read_bytes() == (work / "b" / MANIFEST_NAME).read_bytes()


@pytest.mark.parametrize(
    "tamper, reason",
    [
        (lambda out: (out / "files/README.md").write_bytes(b"# edited in Drive\n"), "OID_MISMATCH:README.md"),
        (lambda out: (out / "files/README.md").unlink(), "MISSING:README.md"),
        (lambda out: (out / "files/notes.md").write_bytes(b"added in Drive\n"), "UNEXPECTED:notes.md"),
        (lambda out: (out / "files/.git").mkdir(), "GIT_METADATA_PRESENT:.git"),
    ],
)
def test_verify_rejects_drift(repo: Path, work: Path, tamper, reason: str) -> None:
    out = work / "snap"
    _build(repo, out)
    tamper(out)
    result = verify_snapshot(out)
    assert result["verdict"] == "REJECT"
    assert reason in result["reasons"]


def test_verify_rejects_edited_manifest(repo: Path, work: Path) -> None:
    out = work / "snap"
    _build(repo, out)
    path = out / MANIFEST_NAME
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["commit_sha"] = "0" * 40
    path.write_text(json.dumps(manifest), encoding="utf-8")
    assert "MANIFEST_DIGEST_MISMATCH" in verify_snapshot(out)["reasons"]


def test_verify_rejects_missing_manifest(work: Path) -> None:
    assert verify_snapshot(work)["reasons"] == ["MANIFEST_MISSING"]


@pytest.mark.parametrize("secret", [".env", "config/prod.pem", "keys/id_rsa", "gha-creds-abc.json"])
def test_build_refuses_deny_listed_paths(repo: Path, secret: str) -> None:
    _commit(repo, {secret: b"secret\n"})
    with pytest.raises(SnapshotError, match="deny-listed"):
        build_manifest(repo)


def test_build_refuses_non_empty_output(repo: Path, work: Path) -> None:
    out = work / "snap"
    out.mkdir()
    (out / "stale.txt").write_text("old", encoding="utf-8")
    manifest, contents = build_manifest(repo)
    with pytest.raises(SnapshotError, match="not empty"):
        write_snapshot(out, manifest, contents)


def test_freshness_is_stale_after_new_commit(repo: Path, work: Path) -> None:
    manifest = _build(repo, work / "snap")
    assert freshness(manifest, manifest["commit_sha"])["freshness"] == "FRESH"
    head = _commit(repo, {"README.md": b"# demo v2\n"})
    assert freshness(manifest, head) == {"freshness": "STALE", "snapshot_sha": manifest["commit_sha"], "head_sha": head}


def test_older_commit_snapshot_is_exact(repo: Path, work: Path) -> None:
    old = _git(repo, "rev-parse", "HEAD")
    _commit(repo, {"README.md": b"# demo v2\n"})
    manifest = _build(repo, work / "snap", commit=old)
    assert manifest["commit_sha"] == old
    assert (work / "snap/files/README.md").read_bytes() == b"# demo\n"


def test_cli_round_trip(repo: Path, work: Path, capsys) -> None:
    out = work / "snap"
    assert main(["build", "--repo", str(repo), "--out", str(out), "--repo-name", "GBOGEB/demo"]) == 0
    built = json.loads(capsys.readouterr().out)
    assert built["result"] == "BUILT"
    assert main(["verify", str(out)]) == 0
    assert json.loads(capsys.readouterr().out)["verdict"] == "ACCEPT"
    (out / "files/README.md").write_bytes(b"drift\n")
    assert main(["verify", str(out)]) == 1
