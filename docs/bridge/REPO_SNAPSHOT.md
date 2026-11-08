# Repo snapshot contract: `gmi.repo_snapshot.v1`

Status: `GM-I-C R2-W1 / OFFLINE CONTRACT`. Mission brief: pipeline-automation-hub `mission-control/grand-missions/GM_I_C_R2_BIDIRECTIONAL_BRIDGE_BRIEF_v1.md`.

This is the **publish** direction of the bridge: GitHub to Drive, one way. A snapshot is a plain-file read copy of one exact commit for agents that can only reach Drive. GitHub stays the source of truth. Changes made in Drive come back only as GMI proposal packages (R2-W2), never by syncing the snapshot back.

## Layout

```text
<snapshot>/
  SNAPSHOT_MANIFEST.json   # gmi.repo_snapshot.v1
  files/                   # the commit's tree, raw bytes, no .git
```

## Manifest

| Field | Meaning |
|---|---|
| `commit_sha`, `tree_sha` | Exact identity; `commit_sha` is the only join key for census comparisons |
| `generated_at` | The commit's committer date (deterministic, not wall-clock time) |
| `files[]` | `path`, `mode`, `git_blob_oid`, `size`, sorted by path |
| `skipped[]` | Submodules and symlinks, recorded but not exported |
| `deny_patterns` | Secret-like paths that make the build fail instead of publishing |
| `manifest_sha256` | `canonical_manifest_digest` (from `src/handover_package.py`) of every other field |

## Commands

```bash
python -m src.repo_snapshot build --repo . --commit HEAD --repo-name GBOGEB/GEMINI --out <dir>
python -m src.repo_snapshot verify <dir>            # ACCEPT only if every blob OID matches the bytes
python -m src.repo_snapshot status <dir> --head <sha>  # FRESH or STALE
```

`verify` rejects missing, unexpected and edited files, an edited manifest, and any `.git` inside the snapshot. A snapshot whose `commit_sha` differs from the current head is `STALE`. It is labelled as stale, never compared as if it were current (REX-GMIC-R2-003).

## Non-claims

An offline `ACCEPT` is not IC2 Drive persistence and not an IC3 WIF pass. Nothing here uploads to Drive. The hosted upload is R2-W4, which is blocked on the owner-only IC3 setup in R2-W3.
