# GM-I-C R3 successor ingress runbook

Active production source: `1248290ca0a9d55ec83d0efa0235ed1a45a88eeb`.

Historical predecessor `70964e5f...` remains immutable provenance and must not be relabelled.

## QPS-native consumer synchronization

QPS has now materialized the governed Windows producer in the actual execution repository:

- QPS #1491 / merge `5f325217c6ff5381e77be36a7aae5203c26e7546`: local producer materialization;
- QPS #1492 / merge `43e23f40976279088018fcf6365be99e9888526c`: self-locating QPS-native invocation;
- QPS #1495: restart/perpetuation rebind to the QPS-local entrypoint.

Therefore the preferred operator path for the admitted real clone is now **from the QPS clone itself**:

```powershell
cd C:\Users\gbonthuy\cryoplant-project
powershell -ExecutionPolicy Bypass -File .\scripts\build_qps_r3_successor_handoff.ps1
```

The GEMINI copy remains the upstream producer lineage/reference implementation. QPS-local
materialization removes cross-repository path ambiguity; it does not transfer release or
engineering authority.

## A. Genuine Git-object handoff

### Windows / PowerShell — preferred for the admitted real clone

The known real private Windows clone may be on a historical branch and may contain
untracked files. That does **not** invalidate Git-object handoff production: this
operator fetches objects, creates a temporary namespaced ref, builds/verifies the bundle,
and removes the temporary ref. It does not checkout, reset, stage, clean or modify the
working tree.

From a checkout of this GEMINI repository:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_qps_r3_successor_handoff.ps1 `
  -QpsClone "C:\Users\gbonthuy\cryoplant-project" `
  -OutDir ".\output\r3_successor_handoff"
```

The operator:

1. verifies the path is a genuine Git worktree;
2. verifies `origin` resolves to `GBOGEB/cryoplant-project`;
3. records the current branch, HEAD and dirty-state count;
4. runs `git fetch origin main --prune` without checkout/reset;
5. proves the exact successor object with `git cat-file -e` and
   `git rev-parse --verify '<sha>^{commit}'`;
6. asserts the current checkout HEAD did not move;
7. creates and verifies the exact Git bundle;
8. emits SHA-256 sidecar and a machine-readable v2 receipt;
9. deletes the temporary ref.

A dirty/untracked worktree is recorded in the receipt but is not a failure because the
bundle is created from verified Git objects only and the checkout is left unchanged.

### Bash / POSIX

On a machine with an authentic clean private `GBOGEB/cryoplant-project` clone:

```bash
bash scripts/build_qps_r3_successor_handoff.sh /path/to/cryoplant-project ./output/r3_successor_handoff
```

The Bash operator retains its original clean-worktree requirement.

### Required outputs

Both operators emit:

- `QPS_R3_1248290c.bundle`
- `QPS_R3_1248290c.bundle.sha256`
- `QPS_R3_1248290c.bundle.receipt.json`

Upload these to Drive folder `Handover_Bundle_QPLANT` /
`1B0i2T7hUsSFhHiyw35PPGaeQ_40E2nNr`.

## B. Portable exact environment

Prerequisite B is already proven by the relocation-safe capsule-v2 lineage:

- GEMINI #18 merge `8b8e72400bb6860789b11b1fca3b809fc8ca6524`
- exact-head run `35339129647`
- artifact `10544103232`
- artifact ZIP SHA-256
  `64c363cfeaded7fc6b156b28fe344166e3c560aac3ea43f50b2695220cffd912`
- inner archive SHA-256
  `c77566e6c6aa261034f86303ef1be7b033622f357333e3d474d3bde8fb3ec44e`
- clean-`LD_LIBRARY_PATH` relocation PASS
- Python 3.12.14 + exact dependency lock PASS
- GEMINI #19 validator-hygiene repair merged at
  `9faeb10cd57395538eb163791c7c56ba90be711b`.

Do not rebuild capsule v1 or treat its earlier hosted PASS as current portability proof.

## Downstream gate

The only remaining producer-side physical prerequisite is **A**: the genuine successor
Git-object handoff for exact commit
`1248290ca0a9d55ec83d0efa0235ed1a45a88eeb`.

After verified arrival, QPS consumes the bundle together with the already-proven capsule-v2
bytes through the existing successor consumer/acceptance chain. Transport preparation does
not imply R3 acceptance, runtime GOLD, engineering authority, GT gate burn, or R4 permission.
