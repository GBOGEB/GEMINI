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
2. Verify one active branch ruleset for the default ref, no unapproved bypass actors, and effective pull_request and required_status_checks rules.
3. Require positive independent approval count, last-push approval, stale-dismissal and resolved thread policy. An author COMMENTED review or an approval for an old SHA never counts.
4. Each required status context must be uniquely observed at the exact PR HEAD, completed with success, with a recorded nonzero job step count; skipped, RED, unknown provider or duplicate context is HOLD.
5. Independently observe a required-check RED rejection canary and stale-approval rejection canary. Green CI does not compensate for these tests.
6. The result can be HOLD or STRUCTURAL_EVIDENCE_COMPLETE_UNATTESTED. Both return execution_authorized=false, merge_authorized=false and authority_transfer=false. Neither grants release admission.

## Repeatable commands

```bash
python -m unittest discover -s tests -p 'test_federation_admission_probe.py' -v
python -m src.federation_admission_probe --expect hold config/federation/admission_observation_20261110.json
```

The --expect hold option exits with process status 0 only when the historical restricted ruleset correctly classifies HOLD. It is a regression assertion, NOT a green merge gate. A synthetic complete fixture only proves that the checker is internally consistent.

## Next eligible owner/implementation frontier

- [Issue #50](https://github.com/GBOGEB/GEMINI/issues/50) must select safe always-produced CI context identities and real independent review policy before an authorized administrator changes main protection.
- Re-read the live ruleset and verify actual GitHub job IDs, executed steps, exact PR SHA and reviewer identities through an authenticated source, then apply this offline probe as a second opinion, not as the authority.
- Prove native negative canaries: RED required CI prevents admission, and last-push stale approval prevents admission. Record independent reviewer signoff and source hashes.
- Keep [#44](https://github.com/GBOGEB/GEMINI/issues/44) protocol decisions, [#12](https://github.com/GBOGEB/GEMINI/issues/12) hosted Google WIF and [#16](https://github.com/GBOGEB/GEMINI/issues/16) authentic Git-bundle constraints as independent gates.

**Non-compensation:** a structurally complete probe result, a merged PR, an offline synthetic worker, a Drive mirror, or a code review from the PR author cannot substitute for effective GitHub protection and actual owner authorization.
