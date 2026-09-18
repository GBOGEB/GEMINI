# GMI batch ingestion and idempotency v1

This lane handles **many locally materialized `GMI-*` packages** after the
single-package contract has validated each package. It does not authenticate Google
Drive, download source content, or promote source claims.

## States

Per-package idempotency state:

- `NEW`: no prior ledger entry for the session.
- `UNCHANGED`: the canonical manifest digest matches the prior ledger.
- `CHANGED`: the same session ID now carries a different manifest digest.
- `INVALID`: package validation rejected the package or no stable identity exists.
- `DUPLICATE`: more than one package in the same batch declares the same session ID.

The deterministic idempotency key is the SHA-256 of
`session_id | canonical_manifest_digest`.

## Ledger safety

Rejected or duplicate packages do not overwrite a prior accepted/deferred ledger
entry. The ledger is an ingestion/idempotency memory, not a truth registry.
`NEW`, `UNCHANGED`, or `CHANGED` therefore says nothing about whether the
source-agent claims are verified.

## Batch verdict

`REJECT` if any package rejects or duplicate session IDs exist; otherwise
`DEFER` if at least one package defers; otherwise `ACCEPT`.

This verdict remains separate from IC3 transport/authentication evidence and from
QPS engineering/release authority.
