# Proposal ingest broker: `gmi.proposal_profile.v1` (dry run)

Status: `GM-I-C R2-W2 / OFFLINE DRY RUN`. Mission brief: pipeline-automation-hub
`mission-control/grand-missions/GM_I_C_R2_BIDIRECTIONAL_BRIDGE_BRIEF_v1.md`.

This is the **return** direction of the bridge: Drive back to GitHub. The publish
direction (`REPO_SNAPSHOT.md`) gives Drive-only agents an exact-SHA read copy. Those
agents cannot push, so they return a change as a GMI proposal package. The broker turns
that package into a patch file and a draft pull-request plan, or rejects it.

GitHub stays the source of truth. A proposal is never synced back into a branch. It
becomes a review-gated draft PR or nothing.

## One return path per proposer type

GBOGEB/GEMINI#37 added a second return path, the lane `OUT/` bundle. The two paths do
not overlap, and each proposer type uses exactly one:

| Proposer | Has local git? | Returns through | Checked by |
|---|---|---|---|
| Drive-only agent (Gemini in Drive or Docs, connector consumers reading a repo snapshot) | No | A `GMI-*` package with `profile: gmi.proposal_profile.v1`, at the handover root | `src/proposal_broker.py` (this document) |
| Agent with git but no GitHub access (works in a lane worktree) | Yes | A full git bundle, its `.sha256` and a receipt in `LANES/<lane>/OUT/` | `src/drive_materialize.py` (`LANES.md`) |
| Agent with GitHub access | Yes | A branch and a PR directly | CI |

The broker enforces the split. It rejects a proposal package that contains a `*.bundle`
file (`LANE_BUNDLE_IN_PROPOSAL`) or any `.git` metadata (`GIT_METADATA_IN_PACKAGE`). It
only scans `GMI-*` folders, so it never reads `LANES/`. A git-capable agent that has a
commit should send a bundle, not flatten the commit into a proposal.

## The profile

`gmi.proposal_profile.v1` is a profile of the GMI package contract v1
(`PACKAGE_CONTRACT.md`), not a new schema. The package must first pass
`handover_package.validate_package`. The profile then adds a top-level marker and one
section:

```yaml
schema_version: 1
session_id: GMI-PROP-0001          # must equal the package folder name; becomes broker/<session_id>
source_agent: gemini-in-drive
generated_at: "2026-11-09T10:00:00Z"
status: DECLARED
scope: README wording fix
source_refs: []
artifact_refs:
  - id: chg-0
    type: local_file               # required, not optional
    path: CHANGES/README.md
    sha256: "<64 hex>"             # required for change artifacts
current_gate: BROKER_DRY_RUN
next_action: broker
profile: gmi.proposal_profile.v1
proposal:
  repo: GBOGEB/GEMINI              # must match the broker's --repo-name
  base_sha: "<40 hex>"             # the snapshot commit_sha the agent read
  intent: Fix the README wording.  # free text, treated as data
  changes:
    - path: README.md
      base_blob: "<40 hex>"        # git blob OID at base_sha, or null for a new file
      mode: replace                # replace | unified_diff
      artifact_ref: chg-0
```

`base_blob` comes straight from the snapshot manifest (`files[].git_blob_oid`), so a
Drive-only agent can fill it without git.

- `replace`: the artifact holds the full new file content.
- `unified_diff`: the artifact holds a single-file unified diff against the base blob,
  with `--- a/<path>` (or `--- /dev/null` for a new file) and `+++ b/<path>`. The diff
  is applied exactly: no fuzz, no offset, no renames, deletes or mode changes.

Unknown fields in `proposal:` or in a change are rejected. Unknown top-level manifest
fields are allowed by the package contract and have no effect on the broker. v1 carries
UTF-8 text only. File deletion is out of scope for v1.

## Checks, in order

1. **Package contract**: `validate_package`. `REJECT` or `DEFER` stops here.
2. **Identity**: `session_id` is a safe ref component and equals the folder name.
3. **Return path**: no `*.bundle` and no `.git` inside the package.
4. **Profile**: fields, modes, artifact refs (required `local_file` with `sha256`).
5. **Paths**: relative, normal form, no `..`, `\`, `:`, backtick or control
   characters. No `.git` component in any letter case. Not deny-listed
   (`repo_snapshot.DEFAULT_DENY`, matched case-sensitively and case-insensitively).
   Not under `.github/workflows/`, because a draft PR still runs workflows from its head.
6. **Repository**: `proposal.repo` equals `--repo-name`. `base_sha` exists in the
   target and is an ancestor of the head.
7. **Optimistic concurrency**, per change:

| Class | Condition | Result |
|---|---|---|
| `CLEAN` | `base_blob` is the blob at `base_sha` and also at head | Proposal applied as is |
| `THREE_WAY` | `base_blob` is the blob at `base_sha`, head moved, `git merge-file` merges cleanly | Merged result |
| `CONFLICT` | `base_blob` is not the blob at `base_sha` (`BASE_BLOB_NOT_AT_BASE_SHA`), the merge conflicts, or head created or deleted the path | No patch |

The proposal takes its worst class (`CONFLICT` > `THREE_WAY` > `CLEAN`). Any
`CONFLICT` makes the broker verdict `REJECT`. A proposal whose every change is
already on head is rejected as `NO_EFFECTIVE_CHANGE`.

## Idempotency: the existing batch ledger

The broker runs `handover_batch.build_batch_census` on the workspace and uses its
states. There is no second ledger.

| Batch state | Broker action |
|---|---|
| `NEW` | Evaluate and plan |
| `CHANGED` | Evaluate and plan; the plan records `supersedes_manifest_digest` |
| `UNCHANGED` | `SKIP` (already brokered); no new plan |
| `DUPLICATE` | `REJECT` every package with that session ID |
| `INVALID` | `REJECT` |

The updated ledger keeps the batch ledger's format, but it records **only** proposals
that were planned. A rejected proposal is therefore evaluated again when it is resent,
for example after the proposer rebases it on a fresh snapshot.

## Outputs

```bash
python -m src.proposal_broker ingest <workspace> --repo . --repo-name GBOGEB/GEMINI \
  --head origin/main --ledger-in ledger.json --ledger-out ledger.json --out <dir>
```

`--out` must be empty and outside the workspace and outside any Google Drive synced
folder (`drive_materialize.check_target`). It receives:

```text
<out>/
  BROKER_RECEIPT.json          # gmi.broker_receipt.v1: every package, verdict, reasons, ledger
  <session_id>/proposal.patch  # git-style diff against head; `git apply` applies it
  <session_id>/branch_plan.json  # gmi.broker_branch_plan.v1
```

The branch plan names branch `broker/<session_id>`, a title, a body and `draft: true`.
It states `pushed: false`, `github_called: false` and `drive_written: false`. Exit
codes: `0` when no package is rejected, `1` when any package is rejected (accepted
packages still get their plan), `2` when the run itself fails.

## Proposal text is data

Nothing in a manifest can change a verdict, the branch name, the draft flag or the push
behaviour. The title contains only the validated session ID, a file count and the
class. `intent` appears once, in the body, inside a fence that is longer than any
backtick run it contains, so it cannot close the fence, and `@mentions` inside it do not
notify anyone. Intent longer than 4000 characters is rejected. The tests check that a
hostile intent plus a `broker_override` block produce the same plan as a benign one.

## Non-claims

An offline broker `ACCEPT` is not an IC3 (Google WIF) pass and not an IC7 hosted round
trip. The broker does not download from Drive, push, open PRs or write receipts back to
Drive. The hosted ingest workflow and the broker GitHub App are R2-W4, blocked on the
owner-only IC3 setup in R2-W3.
