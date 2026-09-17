# GEMINI Bridge Census — Current

Authority baseline for this wave: `main` at `cd68e0c68d882d4fe37417f7a1c1ca45dff0a3ab` (merged PR #11, GM-I-C IC3 Drive auth proof hardening).

## Repository census

- Repository: `GBOGEB/GEMINI`
- Default branch: `main`
- Open issues observed: 2 (`#6`, `#12`)
- Bridge contract: `docs/bridge/DRIVE_HANDOVER_BRIDGE.md`
- Governed manual Drive receipt: `handover/receipts/GMI-DOCENG-20260917-001.drive-receipt.yaml`
- Hosted Drive auth lane: GM-I-C / IC3, with external identity/configuration still owned by issue `#12`
- Manual connector read and hosted OIDC/WIF Drive proof remain distinct evidence lanes and do not compensate for each other.

## Wave topology

```text
PR #8  manual Gemini -> Drive -> external-agent bridge contract
  |
  +--> PR #11  hosted Drive ingress proof hardening (IC3 lane)
  |
  `--> PR #13  receipt normalization + local handover census (this wave)
                 |
                 +--> next: full GMI-* package/manifest validation
                 +--> next: batch ingestion + idempotency receipts
                 `--> later: bind package census to hosted IC3 evidence
```

## Receipt contract

Evidence state is a closed set:

`VERIFIED | IMPLEMENTED | DECLARED | INFERRED | PARTIAL | DEFERRED`

Transport actions such as `CONNECTOR_READ` are recorded separately from evidence state. `src/handover_census.py` fails closed when a receipt omits required fields, uses a non-`GMI-*` session identifier, or introduces an undeclared status.

## Non-compensation

A manual ChatGPT Drive connector read does not burn IC3. A hosted IC3 workflow does not by itself validate every semantic claim inside a Gemini handover. Package validation, connector transport evidence, hosted identity proof, and GitHub review remain separate receipts until explicitly bound.
