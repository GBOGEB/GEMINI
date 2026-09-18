# GMI handover package contract v1

This contract governs **content/package validation** only. It does not prove Google
Drive authentication, GitHub runner admission, source-agent truth, QPS engineering
acceptance, or authority transfer.

## Required manifest

Each package uses `MANIFEST/manifest.yaml` and declares:

- `schema_version`
- `session_id` beginning with `GMI-`
- `source_agent`, `generated_at`, and `scope`
- evidence `status` from the closed evidence-state set
- `source_refs` and `artifact_refs`
- `current_gate` and `next_action`

Package verdicts are a separate closed set:

`ACCEPT | REJECT | DEFER`

Evidence status and package verdict are deliberately not aliases.

## Artifact references

`local_file` references must remain inside the package root. A supplied SHA-256 is
verified against the actual bytes. No hash is required merely to make a package
valid; hashes are only asserted when genuinely available.

`drive_native` references identify a Drive object with `drive_file_id` and an
optional native `drive_revision_id`. A native revision ID is **not** a SHA-256.
The validator rejects a non-null SHA-256 claim on a Drive-native reference because
no exported bytes were supplied for hashing.

Missing required local artifacts are `REJECT`. Missing optional local artifacts and
a manifest whose evidence status is `DEFERRED` yield package verdict `DEFER`.

## Non-compensation

A package `ACCEPT` means only that the declared package is structurally valid and
its locally checkable integrity claims hold. It does not burn GM-I-C/IC3 and does
not promote `DECLARED`, `INFERRED`, or other source claims to `VERIFIED`.
