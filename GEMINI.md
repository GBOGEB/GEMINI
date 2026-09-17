# GBOGEB/GEMINI — Governed Bridge Context

## Purpose

This repository is the governed GitHub side of the Gemini -> Google Drive -> external agent -> GitHub handover bridge.

## Authority model

- Google Drive: persistent source/handover storage and native revision history.
- Gemini CLI connector/tooling: local agent execution and source-session packaging.
- GitHub: governed code, schema, receipts, CI and review-bound commit identity.
- Chat/session memory: orchestration only; never sole authority for completed work.

## Required evidence vocabulary

Use `VERIFIED`, `IMPLEMENTED`, `DECLARED`, `INFERRED`, `PARTIAL`, `DEFERRED`.

Never promote a Gemini-authored claim to `VERIFIED` unless independently corroborated by runtime, repository, connector, or authoritative external evidence.

## Handover package contract

For each source session prefer:

```text
GMI-<id>/
  RAW/
  HANDOVER/
  MANIFEST/
  ARTIFACTS/
```

A manifest should carry at least source agent/session identity, timestamps, Drive object/revision identifiers where available, source refs, artifact refs, current gate, next action, open items, and only actually-computed hashes.

## Git governance

- Work on a feature/wave branch.
- Do not push directly to `main`/`master` from an agentic shell action.
- Open a pull request for governed mutation.
- Preserve predecessor state as lineage; do not silently overwrite historical handovers.
- Do not store credentials, API keys, OAuth tokens, service-account JSON, or `.env` secrets in the repository.

## Hook contract

Project hooks are configured in `.gemini/settings.json` and implemented by `.gemini/hooks/bridge_hook.py`.

The hook records metadata/hash-only runtime receipts under `handover/runtime_receipts/`. It intentionally does not persist prompt bodies, model responses, or full tool payloads.

## Current bridge sequence

```text
Gemini source/session
 -> package/handover
 -> Google Drive object/revision
 -> external-agent authenticated read
 -> evidence reconciliation
 -> Git branch/commit/PR
 -> CI/review
 -> merged governed state
```

Unattended Google Drive access from GitHub Actions requires separate Google authentication and authorization. GitHub repository authentication alone does not grant Google Drive API access.
