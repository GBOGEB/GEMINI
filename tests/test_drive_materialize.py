import copy
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest

from src.drive_materialize import (
    MaterializeError,
    check_lane_matrix,
    main,
    materialize,
    read_bundle_header,
    read_sidecar,
)

GIT_ID = [
    "-c",
    "user.name=Lane Test",
    "-c",
    "user.email=lane-test@example.invalid",
    "-c",
    "commit.gpgsign=false",
]


def _force_remove(func, path, _exc) -> None:
    os.chmod(path, stat.S_IWRITE)  # Git marks pack files read-only on Windows
    func(path)


@pytest.fixture
def workdir(monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """A temp folder that Git for Windows can use.

    pytest's tmp_path is created with mode 0o700. On Windows with Python 3.12.4+
    that becomes an owner-only ACL, and Git for Windows then fails with
    '.git: Permission denied'. A folder made with the default mode inherits the
    normal temp-folder ACL instead.

    On some managed Windows hosts new temp folders are owned by the
    Administrators group, which trips Git's safe.directory check. The override
    below applies only to Git processes started by these tests; the module
    under test never weakens that check itself.
    """

    monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
    monkeypatch.setenv("GIT_CONFIG_KEY_0", "safe.directory")
    monkeypatch.setenv("GIT_CONFIG_VALUE_0", "*")
    path = Path(tempfile.gettempdir()) / f"lane-test-{uuid.uuid4().hex}"
    path.mkdir()
    try:
        yield path
    finally:
        if sys.version_info >= (3, 12):
            shutil.rmtree(path, onexc=_force_remove)
        else:
            shutil.rmtree(path, onerror=_force_remove)


def _git(cwd: Path, *args: str) -> str:
    done = subprocess.run(
        ["git", *GIT_ID, *args], cwd=cwd, capture_output=True, text=True, check=True
    )
    return done.stdout.strip()


def _source_repo(root: Path) -> tuple[Path, str]:
    repo = root / "source"
    repo.mkdir()
    _git(repo, "init", "--quiet", "--initial-branch=main")
    (repo / "README.md").write_text("lane source\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "--quiet", "-m", "first")
    return repo, _git(repo, "rev-parse", "HEAD")


def _lane(root: Path, sidecar_style: str = "named") -> tuple[Path, str]:
    """A lane folder holding a full bundle and its sidecar; returns (bundle, commit)."""

    repo, commit = _source_repo(root)
    lane = root / "LANES" / "L-TEST-01"
    lane.mkdir(parents=True)
    bundle = lane / "TEST_lane.bundle"
    _git(repo, "bundle", "create", str(bundle), "HEAD", "main")
    digest = hashlib.sha256(bundle.read_bytes()).hexdigest()
    line = digest if sidecar_style == "bare" else f"{digest}  {bundle.name}"
    (lane / f"{bundle.name}.sha256").write_text(line + "\n", encoding="utf-8")
    return bundle, commit


def _run(bundle: Path, target: Path, commit: str, **extra) -> dict:
    return materialize(
        bundle=bundle,
        target=target,
        lane_id="L-TEST-01",
        expected_commit=commit,
        branch="lane/L-TEST-01-demo",
        **extra,
    )


@pytest.mark.parametrize("style", ["named", "bare"])
def test_full_bundle_materializes_on_lane_branch(workdir: Path, style: str) -> None:
    bundle, commit = _lane(workdir, style)
    target = workdir / "local" / "lane-wt"

    receipt = _run(
        bundle, target, commit, origin_url="https://github.com/GBOGEB/GEMINI.git"
    )

    assert receipt["result"] == "PASS"
    assert receipt["head"] == commit
    assert receipt["git_bundle_verify"] == "PASS"
    assert receipt["advertised_refs"]["refs/heads/main"] == commit
    assert receipt["origin_url"] == "https://github.com/GBOGEB/GEMINI.git"
    assert receipt["drive_mutated"] is False and receipt["pushed"] is False
    assert _git(target, "branch", "--show-current") == "lane/L-TEST-01-demo"
    assert (target / "README.md").read_text(encoding="utf-8") == "lane source\n"


def test_byte_mismatch_fails_before_git_and_creates_nothing(workdir: Path) -> None:
    bundle, commit = _lane(workdir)
    bundle.write_bytes(bundle.read_bytes() + b"tampered")
    target = workdir / "local" / "lane-wt"

    with pytest.raises(MaterializeError) as exc:
        _run(bundle, target, commit)

    assert exc.value.code == "SHA256_MISMATCH"
    assert not target.exists()


def test_sidecar_must_name_this_bundle(workdir: Path) -> None:
    sidecar = workdir / "x.bundle.sha256"
    sidecar.write_text(f"{'a' * 64}  other.bundle\n", encoding="utf-8")
    with pytest.raises(MaterializeError) as exc:
        read_sidecar(sidecar, "x.bundle")
    assert exc.value.code == "SIDECAR_NAME_MISMATCH"


@pytest.mark.parametrize(
    "content", ["", "not-a-hash\n", f"{'a' * 64}\n{'b' * 64}\n", f"{'a' * 64}  x  y\n"]
)
def test_malformed_sidecar_is_rejected(workdir: Path, content: str) -> None:
    sidecar = workdir / "x.bundle.sha256"
    sidecar.write_text(content, encoding="utf-8")
    with pytest.raises(MaterializeError) as exc:
        read_sidecar(sidecar, "x.bundle")
    assert exc.value.code == "SIDECAR_INVALID"


def test_expected_commit_must_be_advertised(workdir: Path) -> None:
    bundle, _ = _lane(workdir)
    target = workdir / "local" / "lane-wt"
    with pytest.raises(MaterializeError) as exc:
        _run(bundle, target, "0" * 40)
    assert exc.value.code == "EXPECTED_COMMIT_NOT_ADVERTISED"
    assert not target.exists()


def test_incremental_bundle_is_refused(workdir: Path) -> None:
    repo, first = _source_repo(workdir)
    (repo / "NEXT.md").write_text("next\n", encoding="utf-8")
    _git(repo, "add", "NEXT.md")
    _git(repo, "commit", "--quiet", "-m", "second")
    second = _git(repo, "rev-parse", "HEAD")
    lane = workdir / "lane"
    lane.mkdir()
    bundle = lane / "inc.bundle"
    _git(repo, "bundle", "create", str(bundle), f"{first}..main")
    (lane / "inc.bundle.sha256").write_text(
        hashlib.sha256(bundle.read_bytes()).hexdigest(), encoding="utf-8"
    )

    assert read_bundle_header(bundle)["prerequisites"] == [first]
    with pytest.raises(MaterializeError) as exc:
        _run(bundle, workdir / "local" / "wt", second)
    assert exc.value.code == "BUNDLE_HAS_PREREQUISITES"


def test_non_bundle_file_is_refused(workdir: Path) -> None:
    fake = workdir / "fake.bundle"
    fake.write_bytes(b"PK\x03\x04 a zip, not a bundle")
    with pytest.raises(MaterializeError) as exc:
        read_bundle_header(fake)
    assert exc.value.code == "BUNDLE_SIGNATURE_INVALID"


@pytest.mark.parametrize("where", ["lane", "my_drive", "mijn_drive"])
def test_target_inside_drive_is_refused(workdir: Path, where: str) -> None:
    bundle, commit = _lane(workdir)
    target = {
        "lane": bundle.parent / "checkout",
        "my_drive": workdir / "G" / "My Drive" / "checkout",
        "mijn_drive": workdir / "G" / "Mijn Drive" / "checkout",
    }[where]
    with pytest.raises(MaterializeError) as exc:
        _run(bundle, target, commit)
    assert exc.value.code == "TARGET_IN_DRIVE"
    assert not target.exists()


def test_non_empty_target_is_refused_and_kept(workdir: Path) -> None:
    bundle, commit = _lane(workdir)
    target = workdir / "local" / "busy"
    target.mkdir(parents=True)
    (target / "keep.txt").write_text("someone else's work\n", encoding="utf-8")
    with pytest.raises(MaterializeError) as exc:
        _run(bundle, target, commit)
    assert exc.value.code == "TARGET_NOT_EMPTY"
    assert (target / "keep.txt").exists()


def test_cli_writes_fail_receipt(workdir: Path) -> None:
    bundle, _ = _lane(workdir)
    receipt = workdir / "receipt.json"
    code = main(
        [
            "materialize",
            "--bundle",
            str(bundle),
            "--target",
            str(workdir / "local" / "wt"),
            "--lane-id",
            "L-TEST-01",
            "--expected-commit",
            "f" * 40,
            "--branch",
            "lane/L-TEST-01-demo",
            "--receipt",
            str(receipt),
        ]
    )
    assert code == 3
    payload = json.loads(receipt.read_text(encoding="utf-8"))
    assert payload["result"] == "FAIL"
    assert payload["classification"] == "EXPECTED_COMMIT_NOT_ADVERTISED"


VALID_MATRIX = {
    "schema": "gemini.lane_matrix.v1",
    "root_folder_id": "1FnbajqBiIjL6Y4-_7tE1D515fNWvHsu3",
    "as_of": "2026-11-08",
    "lanes": [
        {
            "id": "L-GEMINI-01",
            "repo": "GBOGEB/GEMINI",
            "branch": "lane/L-GEMINI-01-drive-materialize",
            "purpose": "Drive lane to local PyCharm worktree materializer",
            "files": [
                "src/drive_materialize.py",
                "tests/test_drive_materialize.py",
                "docs/bridge/LANES.md",
            ],
            "owner_session": "claude-code-2026-11-08",
            "state": "BUILDING",
        },
        {
            "id": "L-R3",
            "repo": "GBOGEB/cryoplant-project",
            "purpose": "R3 successor Git bundle return",
            "state": "BLOCKED_RETURN",
        },
    ],
}


def _matrix() -> dict:
    return copy.deepcopy(VALID_MATRIX)


def test_valid_matrix_has_no_errors() -> None:
    assert check_lane_matrix(_matrix()) == []


def test_overlapping_live_lanes_are_rejected() -> None:
    matrix = _matrix()
    matrix["lanes"].append(
        {
            "id": "L-GEMINI-02",
            "repo": "GBOGEB/GEMINI",
            "purpose": "docs refresh",
            "files": ["docs/bridge"],
            "state": "PROPOSED",
        }
    )
    errors = check_lane_matrix(matrix)
    assert errors == ["L-GEMINI-01 and L-GEMINI-02 both claim docs/bridge"]


def test_same_path_in_other_repo_or_finished_lane_is_allowed() -> None:
    matrix = _matrix()
    matrix["lanes"].append(
        {
            "id": "L-CODEX-01",
            "repo": "GBOGEB/CODEX",
            "purpose": "same filename, other repo",
            "files": ["src/drive_materialize.py"],
            "state": "PROPOSED",
        }
    )
    matrix["lanes"].append(
        {
            "id": "L-GEMINI-00",
            "repo": "GBOGEB/GEMINI",
            "purpose": "finished earlier",
            "files": ["src/drive_materialize.py"],
            "state": "MERGED",
        }
    )
    assert check_lane_matrix(matrix) == []


def test_live_lane_needs_owner_and_known_state() -> None:
    matrix = _matrix()
    matrix["lanes"][0]["owner_session"] = None
    matrix["lanes"][1]["state"] = "RUNNING"
    errors = check_lane_matrix(matrix)
    assert "L-GEMINI-01: a BUILDING lane must name its owner_session" in errors
    assert any(error.startswith("L-R3: state must be one of") for error in errors)


@pytest.mark.parametrize(
    "bad", ["../outside.py", "/abs/path.py", "C:/x.py", "src\\win.py", ""]
)
def test_unsafe_file_paths_are_rejected(bad: str) -> None:
    matrix = _matrix()
    matrix["lanes"][0]["files"] = [bad]
    assert any(
        "must be a relative POSIX path" in error for error in check_lane_matrix(matrix)
    )


def test_duplicate_ids_and_unquoted_dates_are_rejected(workdir: Path) -> None:
    matrix = _matrix()
    matrix["lanes"][1]["id"] = "L-GEMINI-01"
    assert "L-GEMINI-01: duplicate lane id" in check_lane_matrix(matrix)

    path = workdir / "LANE_MATRIX.yaml"
    path.write_text(
        "schema: gemini.lane_matrix.v1\nroot_folder_id: abc\nas_of: 2026-11-08\nlanes: []\n",
        encoding="utf-8",
    )
    assert main(["check-matrix", str(path)]) == 3


def test_cyclic_yaml_matrix_fails_closed(workdir: Path) -> None:
    path = workdir / "LANE_MATRIX.yaml"
    path.write_text("&a\nschema: gemini.lane_matrix.v1\nself: *a\n", encoding="utf-8")
    assert main(["check-matrix", str(path)]) == 3


def test_undecodable_sidecar_is_classified(workdir: Path) -> None:
    sidecar = workdir / "x.bundle.sha256"
    sidecar.write_bytes(b"\xff\xfe\x00 not utf-8\n")
    with pytest.raises(MaterializeError) as exc:
        read_sidecar(sidecar, "x.bundle")
    assert exc.value.code == "SIDECAR_INVALID"


def test_failed_branch_removes_a_target_this_run_created(workdir: Path) -> None:
    bundle, commit = _lane(workdir)
    target = workdir / "local" / "lane-wt"
    with pytest.raises(MaterializeError) as exc:
        materialize(bundle, target, "L-TEST-01", commit, "bad..branch")
    assert exc.value.code == "LANE_BRANCH_FAILED"
    assert not target.exists()


def test_failed_branch_empties_a_pre_existing_empty_target(workdir: Path) -> None:
    bundle, commit = _lane(workdir)
    target = workdir / "local" / "empty-wt"
    target.mkdir(parents=True)
    with pytest.raises(MaterializeError) as exc:
        materialize(bundle, target, "L-TEST-01", commit, "bad..branch")
    assert exc.value.code == "LANE_BRANCH_FAILED"
    assert target.is_dir() and list(target.iterdir()) == []
    receipt = _run(bundle, target, commit)  # the same target is usable again
    assert receipt["result"] == "PASS"


def test_repo_names_are_compared_case_insensitively() -> None:
    matrix = _matrix()
    matrix["lanes"].append(
        {
            "id": "L-GEMINI-02",
            "repo": "gbogeb/gemini",
            "purpose": "same repo, other casing",
            "files": ["src/drive_materialize.py"],
            "state": "PROPOSED",
        }
    )
    assert check_lane_matrix(matrix) == [
        "L-GEMINI-01 and L-GEMINI-02 both claim src/drive_materialize.py"
    ]
