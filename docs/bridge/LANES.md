# Drive lanes: from a Drive lane folder to a local worktree

Status: `IMPLEMENTED` locally for lane `L-GEMINI-01`. Hosted Drive ingress (#12)
and the R3 bundle return (#16) are separate gates and remain open.

A **lane** is one unit of work with one home repository, one future branch and
its own file set. Google Drive carries the lane. A live repository never sits
inside a synced Drive folder, because sync conflicts and file locks can damage
`.git`. The work is built in a local worktree and returns to GitHub by pull
request.

```text
Drive lane folder (bundle + .sha256)
  -> src/drive_materialize.py materialize      (bytes, header, git bundle verify, HEAD)
  -> local worktree under C:\repos\_wt\        (PyCharm, .venv on Python 3.12)
  -> lane branch -> pull request -> CI -> main
  -> RECEIPT.json back into the Drive lane folder
```

This "lane matrix" is the Drive lane registry. It is not the CI lane matrix in
`pipeline-automation-hub/docs/ci-spine/LANE_MATRIX_TOP_VIEW_20261030.md`.

## Drive layout

The one Drive root stays `GEMINI_QPS_HANDOVER_2026-09-17`
(`1FnbajqBiIjL6Y4-_7tE1D515fNWvHsu3`), which `drive_ingress.yml` already
scans. Lanes go under it; no second root is created.

```text
GEMINI_QPS_HANDOVER_2026-09-17/
  00_CONTROL/
    LANE_MATRIX.yaml
    HISTORICAL/
  LANES/
    L-GEMINI-01/
      GEMINI_6136b9eb.bundle
      GEMINI_6136b9eb.bundle.sha256
      RECEIPT.json              (written after the PR exists)
      OUT/                      (bundle return from agents without GitHub access)
  GMI-NNN/                      (handover packages, see PACKAGE_CONTRACT.md)
```

## Lane registry: `00_CONTROL/LANE_MATRIX.yaml`

```yaml
schema: gemini.lane_matrix.v1
root_folder_id: 1FnbajqBiIjL6Y4-_7tE1D515fNWvHsu3
as_of: "2026-11-08" # quote dates: the registry must be JSON-compatible
lanes:
  - id: L-GEMINI-01
    repo: GBOGEB/GEMINI
    base_sha: 6136b9ebd976b994afefc57cc7d3497060e45a3e
    branch: lane/L-GEMINI-01-drive-materialize
    purpose: Drive lane to local PyCharm worktree materializer
    files: [src/drive_materialize.py, tests/test_drive_materialize.py, docs/bridge/LANES.md]
    owner_session: null # set before any edit; required while CLAIMED, BUILDING or PR_OPEN
    state: PROPOSED # PROPOSED | CLAIMED | BUILDING | PR_OPEN | MERGED | HISTORICAL | BLOCKED_RETURN
  - id: L-R3
    repo: GBOGEB/cryoplant-project
    purpose: R3 successor Git bundle return
    state: BLOCKED_RETURN
```

Check it before claiming a lane:

```powershell
Set-Location "C:\repos\_wt\gemini-L-GEMINI-01"
.\.venv\Scripts\python -m src.drive_materialize check-matrix "<path to>\LANE_MATRIX.yaml"
```

The check fails when two unfinished lanes in the same repository claim the same
file or a folder that contains it, when a live lane has no `owner_session`, when
an ID repeats, when a path is absolute or leaves the repository, or when the
YAML is not JSON-compatible (for example an unquoted date or a cyclic alias).

## Produce a lane bundle

Use a full bundle that advertises `HEAD`, and a `sha256sum`-style sidecar. This
is the same triplet contract as the R3 successor bundle.

```powershell
Set-Location "C:\repos\_wt\gemini-bundle-src"
git bundle create "C:\repos\_wt\GEMINI_6136b9eb.bundle" HEAD main
$h = (Get-FileHash "C:\repos\_wt\GEMINI_6136b9eb.bundle" -Algorithm SHA256).Hash.ToLower()
"$h  GEMINI_6136b9eb.bundle" | Set-Content -Encoding ascii "C:\repos\_wt\GEMINI_6136b9eb.bundle.sha256"
```

Upload both files to the lane folder on drive.google.com.

## Materialize a lane

Download the lane folder (or use Google Drive for desktop), then:

```powershell
Set-Location "C:\repos\_wt\gemini-L-GEMINI-01"
.\.venv\Scripts\python -m src.drive_materialize materialize `
  --bundle "$env:USERPROFILE\Downloads\L-GEMINI-01\GEMINI_6136b9eb.bundle" `
  --target "C:\repos\_wt\gemini-L-GEMINI-01-work" `
  --lane-id L-GEMINI-01 `
  --expected-commit 6136b9ebd976b994afefc57cc7d3497060e45a3e `
  --branch lane/L-GEMINI-01-drive-materialize `
  --origin-url https://github.com/GBOGEB/GEMINI.git `
  --receipt "C:\repos\_wt\L-GEMINI-01_materialize_receipt.json"
```

Checks run in this order and stop at the first failure:

| Check | Failure code |
| --- | --- |
| Sidecar has one line, `<64 hex>` or `<64 hex>  <bundle name>` | `SIDECAR_MISSING`, `SIDECAR_INVALID`, `SIDECAR_NAME_MISMATCH` |
| Bundle bytes match the sidecar, before Git reads them | `SHA256_MISMATCH` |
| File is a v2/v3 bundle with no prerequisites | `BUNDLE_SIGNATURE_INVALID`, `BUNDLE_HEADER_INVALID`, `BUNDLE_HAS_PREREQUISITES` |
| A bundle ref points at the expected commit | `EXPECTED_COMMIT_NOT_ADVERTISED` |
| Target is outside Drive and outside the lane folder, and empty | `TARGET_IN_DRIVE`, `TARGET_NOT_EMPTY` |
| `git clone`, `git bundle verify`, lane branch at the expected commit | `BUNDLE_CLONE_FAILED`, `BUNDLE_VERIFY_FAILED`, `LANE_BRANCH_FAILED`, `HEAD_MISMATCH` |

A failure after the clone started removes only the folder the tool created.
The receipt (`gemini.lane_materialize_receipt.v1`) records the bundle SHA-256,
advertised refs, verify output, HEAD and branch. It always states
`drive_mutated: false`, `pushed: false` and `authority_transfer: false`.

## Open the worktree in PyCharm

```powershell
Set-Location "C:\repos\_wt\gemini-L-GEMINI-01-work"
py -3.12 -m venv .venv
.\.venv\Scripts\python -m pip install --disable-pip-version-check pytest PyYAML
Add-Content ".git\info\exclude" ".idea/"
& "$env:LOCALAPPDATA\Programs\PyCharm 2025.2.4\bin\pycharm64.exe" "C:\repos\_wt\gemini-L-GEMINI-01-work"
```

Choose `.venv\Scripts\python.exe` as the interpreter, mark the repository root
as Sources Root (`pythonpath = ["."]`), and set pytest as the test runner.

## Return the work

1. Commit on the lane branch, then `git push -u origin HEAD` straight away.
2. Open the pull request. Write "Do not merge unless green" in its body until CI
   on Python 3.12 passes.
3. Write `RECEIPT.json` (lane ID, branch, head SHA, PR number, CI run ID) into
   the Drive lane folder. The lane counts as returned only when that receipt
   exists.

An agent with Drive access but no GitHub access writes a bundle, its `.sha256`
and a receipt into the lane's `OUT/` folder instead.

## Windows test note

`tests/test_drive_materialize.py` does not use pytest's `tmp_path`. On Windows
with Python 3.12.4 or later, `tmp_path` folders get an owner-only ACL that Git
for Windows cannot use. The tests make an ordinary temp folder instead, and
allow Git's `safe.directory` check for their own Git processes only.
