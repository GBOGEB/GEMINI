# Gemini -> Google Drive -> External Agent -> GitHub Bridge

Status: `V0 / HUMAN-TRIGGERED / CONNECTOR-ENABLED`

## Purpose

Use Google Drive as the persistent, model-neutral handover surface between Gemini and successor agents such as ChatGPT or Claude, while GitHub records the governed, reviewable implementation state.

## Current executable path

```text
Gemini session
  -> human asks Gemini to create/export a lossless handover
  -> Google Drive handover folder
  -> successor agent authenticates through its own Drive connector
  -> successor reads manifest first, then handover/artifacts
  -> successor reconciles source-declared vs independently verified claims
  -> successor writes governed receipt / code / documentation to GitHub branch
  -> pull request provides human review and merge gate
```

Google Drive placement does not itself grant an external AI client access. The successor must have a separately authorized Google Drive connector with permission to the target files.

## Workspace model for tens of Gemini sessions

Treat one Drive folder as an inbox/workspace. Each session is an immutable-ish package, not a chat-memory dependency:

```text
GEMINI_QPS_HANDOVER_YYYY-MM-DD/
  GMI-001/
    RAW/
    HANDOVER/
    MANIFEST/
    ARTIFACTS/
  GMI-002/
  ...
  GMI-0NN/
```

The successor can enumerate the folder, read each manifest, then process packages independently or as a batch. The folder is a source inbox; GitHub remains the governed development/audit surface.

## Handover contract

Every session package SHOULD expose:

- `source_agent`
- `session_id`
- `generated_at`
- `drive_file_id` and/or Drive URL
- `drive_revision_id` when native Drive revision identity is available
- `scope`
- `source_refs`
- `artifact_refs`
- `status`
- `current_gate`
- `next_action`
- `open_items`
- hashes for concrete exported files when actually computed

Do not invent hashes. Native Google Docs revision identity is not equivalent to a SHA-256 digest.

## Evidence states

Use: `VERIFIED`, `IMPLEMENTED`, `DECLARED`, `INFERRED`, `PARTIAL`, `DEFERRED`.

A source-agent statement is not promoted to `VERIFIED` merely because it appears in the handover. Verification requires runtime, repository, connector, or authoritative-source evidence.

## A -> B state transition

### A. Current position

- Gemini owns conversational state.
- Drive persistence is manually triggered.
- successor connector reads are manually triggered.
- GitHub publication is manually triggered.
- no watcher/event bridge is active.

### B. Desired state

```text
Gemini completion
 -> deterministic handover package
 -> Drive object + revision/digest receipt
 -> ingestion event
 -> manifest/schema validation
 -> semantic/root reconciliation
 -> ACCEPT | REJECT | DEFER
 -> Git commit/PR binding
 -> updated handover receipt
 -> REBUILD-AS-OF / replay proof
```

## Automation boundary

This repository can validate handover receipts and host bridge code/workflows. A real unattended Drive sync still requires an authorized Google API identity (OAuth or service account, depending environment), secret management, change detection/polling or events, and conflict/idempotency rules. Do not put Drive credentials in the repository.

## Current Drive source proven through ChatGPT connector

The first governed read used Google Doc ID `1Suf0HhnozsCVXdvCzjeReQkOfinXY2m59paNQHrrQR4`, revision ID recorded in the companion receipt under `handover/receipts/`. The document itself defines the cross-agent bridge contract, Golden Thread sequence, and the gate `BASELINE MATERIALIZATION + PARITY TESTING`.

## Authority split

- **Drive**: persistent source package / native revision history / collaboration ACL.
- **Connector**: authenticated transport available to a specific AI client.
- **GitHub**: code, schemas, receipts, reviewed changes, CI, immutable commit identity.
- **Chat**: orchestration surface only; never the sole authority for a completed handover.
