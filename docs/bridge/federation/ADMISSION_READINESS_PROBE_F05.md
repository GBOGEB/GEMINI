# F05 — non-authorizing exact-head admission evidence probe

**Role:** optional offline QA helper, not a GitHub policy controller, reviewer, broker or merging service.
**State:** implementation candidate under [PR #48](https://github.com/GBOGEB/GEMINI/pull/48). Owner decisions and live admission remain separate.

## Reuse and source priority

- Source: [src/federation_admission_probe.py](../../../src/federation_admission_probe.py). Adversarial tests: [test_federation_admission_probe.py](../../../tests/test_federation_admission_probe.py).
- Historical, deliberately incomplete GitHub readback: [admission_observation_20261110.json](../../../config/federation/admission_observation_20261110.json). This is not a signed connector log.
- Broad, declared 20-node federation DAG: [precedence_contract_v1.json](precedence_contract_v1.json) on main from merged PR #49. The F02 six-node example remains a reduced inert plan only; it does NOT replace the canonical join or Hub/BridgeFlow scheduling.
- GMI profile and broker remain owned by merged #40/#46/#51/#52 code. This probe cannot replace the broker, infer a #44 owner decision or grant Drive access.

## Inputs and interpretation

The JSON uses schema gmi.federation_admission_observation.v1 and classification READ_ONLY_UNATTESTED. It identifies repository, PR and exact source/default SHA, one observed ruleset, candidate head checks, review decisions, last push, unresolved threads and RED/stale-review canary outcomes. Evidence typed manually is still only a claim; this validator cannot authenticate it.

The observed example is pinned to GEMINI PR #48 head 803532158ea4ed1bff51506f6e5d7d86238d2bc5 and main d3a885ab8593cbf9af22e6fce6c64d589ad80575. Its active Main_Protect ruleset #26381197 contains only deletion and non_fast_forward. It intentionally does not invent executed check-step counts, independent review, or negative-canary attestations. The correct output is HOLD.

## Fail-closed predicates

1. Validate exact PR/default identities and current observed SHA equality; malformed/different refs, wrong repo or stale default are HOLD.
2. Verify one active branch ruleset for the default ref, no unapproved bypass actors, and effective pull_request and required_status_checks rules. Scope requires an explicit empty `exclude` list; any nonempty, missing or malformed exclusion remains HOLD. The helper does not implement GitHub's pattern matching and conservatively withholds a verdict even for exclusions that might affect another branch.
3. Require positive independent approval count, last-push approval, stale-dismissal and resolved thread policy. The PR author's identity must be present. Reviewer identities are compared and deduplicated case-insensitively; a differently cased author name is still self-review. Evaluate the latest decisive review per identity by submitted time, independently of input order: a later CHANGES_REQUESTED or DISMISSED revokes an earlier approval. An outstanding change request by any reviewer, an unknown decisive timestamp, or contradictory decisions tied at the latest timestamp holds the verdict. COMMENTED and PENDING are non-decisive; malformed or unknown review entries/states withhold completeness. Blank or padded identities, an author COMMENTED review or an approval for an old SHA never count.
4. Each required status context must be uniquely observed at the exact PR HEAD, completed with success, with a recorded nonzero job step count. Required and observed provider IDs must both be explicit positive integers and agree; an absent/null/any-source provider binding remains HOLD. This is a conservative evidence requirement, not a claim that GitHub disallows unbound contexts. Skipped, RED, unknown provider or duplicate context is HOLD.
5. Independently observe a required-check RED rejection canary and stale-approval rejection canary. Green CI does not compensate for these tests.
6. The result can be HOLD or STRUCTURAL_EVIDENCE_COMPLETE_UNATTESTED. Both return execution_authorized=false, merge_authorized=false and authority_transfer=false. Neither grants release admission.

## Repeatable commands

```bash
python -m unittest discover -s tests -p 'test_federation_admission_probe.py' -v
python -m src.federation_admission_probe --expect hold config/federation/admission_observation_20261110.json
```

The --expect hold option exits with process status 0 only when the historical restricted ruleset correctly classifies HOLD. It is a regression assertion, NOT a green merge gate. A synthetic complete fixture only proves that the checker is internally consistent.

## F06 — bounded scope/provider/author repair

At predecessor `d377dc67c4aed780dca3394e0c361699d362c681`, three mutations of the otherwise complete test fixture incorrectly returned `STRUCTURAL_EVIDENCE_COMPLETE_UNATTESTED`: excluding `refs/heads/main`, removing the required provider ID, and removing the PR author. Independent advisory source review then reproduced a fourth case: a later CHANGES_REQUESTED decision did not revoke an earlier approval. No mutation granted merge authority, but the structural verdict overstated the evidence. The existing probe now returns HOLD for all four, including case-variant self-review, duplicate-reviewer quorum, dismissal and ambiguous/out-of-order review cases. Fifteen added test methods bring the probe suite to 36; F02's 14 inert-policy cases and the six canonical precedence cases remain separate. Advisory source review does not constitute eligible GitHub approval.

The prior head's [BLSN matrix](https://github.com/GBOGEB/GEMINI/actions/runs/42904554187) completed with 10 successful jobs and one intentionally skipped PR deploy. Together with the two F05 jobs, this is 12 successful candidate checks and one skipped deploy at `d377dc67...`. That completed qualification is retained as predecessor evidence; the F06 source head requires new native checks and independent review.

### Concrete required-context proposal for issue #50

The existing [BLSN workflow](https://github.com/GBOGEB/GEMINI/blob/d377dc67c4aed780dca3394e0c361699d362c681/.github/workflows/generate_blsn_reports.yml) runs on every PR targeting main with no path filter. Its three existing strict candidate contexts are below; observed GitHub Actions provider/integration ID is **15368**. This is an enumerated proposal, not an applied ruleset or owner acceptance.

| Exact context | Producer and observed qualifying job | Evidence boundary |
|---|---|---|
| `Run (ubuntu-latest - Py 3.9)` | `full-matrix-validation`, [job 130139020666](https://github.com/GBOGEB/GEMINI/actions/runs/42904554187/job/130139020666) | Strict Ruff/pytest/BLSN leg; PR checkout uses GitHub's synthetic merge ref, so record tested checkout separately from the PR check head |
| `JADE CI (tests, build once, hash) / Tests (zero-test guard + coverage floor)` | Pinned Hub reusable CI, [job 130139021326](https://github.com/GBOGEB/GEMINI/actions/runs/42904554187/job/130139021326) | Explicit exact-PR-head checkout/assertion, fail-closed pytest and minimum 50-test guard; numeric coverage floor currently defaults to 0 (measurement, not a positive percentage threshold) |
| `JADE CI (tests, build once, hash) / Build once and hash the artefact` | Same pinned owner, [job 130139268249](https://github.com/GBOGEB/GEMINI/actions/runs/42904554187/job/130139268249) | Depends on strict tests; caller always supplies `_site`, so build is produced; records exact-head artifact manifest |

The reusable owner is pinned to [Hub `77bac410...`](https://github.com/GBOGEB/pipeline-automation-hub/blob/77bac410de6b34afa5df665608611ad9e8db5c84/.github/workflows/jade-reusable-ci.yml). Its test/build checkout explicitly uses `github.event.pull_request.head.sha || github.sha`.

Do not select PR-skipped `Deploy GitHub Pages`, path-filtered `inert-contract (...)`, or telemetry legs as universal mandatory controls. Non-3.9 matrix pytest steps tolerate test failures and cannot be substituted for the strict Py3.9/JADE test gates. Owner/admin still decides the exact required set, approval count, stale/last-push review policy, and executes real RED/stale/positive canaries before issue #50 closes. No new aggregate workflow or policy writer is needed to enumerate these existing producers.

## Next eligible owner/implementation frontier

- [Issue #50](https://github.com/GBOGEB/GEMINI/issues/50) must select safe always-produced CI context identities and real independent review policy before an authorized administrator changes main protection.
- Re-read the live ruleset and verify actual GitHub job IDs, executed steps, exact PR SHA and reviewer identities through an authenticated source, then apply this offline probe as a second opinion, not as the authority.
- Prove native negative canaries: RED required CI prevents admission, and last-push stale approval prevents admission. Record independent reviewer signoff and source hashes.
- Keep [#44](https://github.com/GBOGEB/GEMINI/issues/44) protocol decisions, [#12](https://github.com/GBOGEB/GEMINI/issues/12) hosted Google WIF and [#16](https://github.com/GBOGEB/GEMINI/issues/16) authentic Git-bundle constraints as independent gates.

**Non-compensation:** a structurally complete probe result, a merged PR, an offline synthetic worker, a Drive mirror, or a code review from the PR author cannot substitute for effective GitHub protection and actual owner authorization.
