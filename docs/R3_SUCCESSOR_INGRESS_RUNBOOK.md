# GM-I-C R3 successor ingress runbook

Active production source: `1248290ca0a9d55ec83d0efa0235ed1a45a88eeb`.

Historical predecessor `70964e5f...` remains immutable provenance and must not be relabelled.

## A. Genuine Git-object handoff

Run on a machine with an authentic clean private `GBOGEB/cryoplant-project` clone:

```bash
bash scripts/build_qps_r3_successor_handoff.sh /path/to/cryoplant-project ./output/r3_successor_handoff
```

The operator emits:
- `QPS_R3_1248290c.bundle`
- `QPS_R3_1248290c.bundle.sha256`
- `QPS_R3_1248290c.bundle.receipt.json`

Upload these to Drive folder `Handover_Bundle_QPLANT` / `1B0i2T7hUsSFhHiyw35PPGaeQ_40E2nNr`.

## B. Portable exact environment

The workflow `R3 Successor Portable Exact Environment` builds a Linux x86_64 CPython 3.12 capsule with exact dependencies:

- PyYAML 6.0.1
- openpyxl 3.1.5
- python-docx 1.2.0
- python-pptx 1.0.2
- reportlab 5.0.1
- pypdf 6.0.0

It performs a relocated self-test before upload. The artifact contains the runtime tarball, SHA-256 sidecar, and machine-readable manifest.

## Downstream gate

Both A and B are prerequisites for QPS `R3_SUCCESSOR_EXACT_ENVIRONMENT_REPROOF_ON_ADMITTED_QUALIFIED_EXECUTOR`.

Transport preparation does not imply R3 acceptance, runtime GOLD, engineering authority, GT gate burn, or R4 permission.
