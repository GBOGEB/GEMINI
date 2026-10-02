---
layout: default
title: "Wave 16 – Governance Plan"
---

# Wave 16 – Governance Plan

> **LIVE RECONCILIATION — 2026-10-02**
>
> Reconciled against `main@b9a89705ac0ba00b60c5841211e7cd17115ce66c`.
> This document remains a **proposal/control plan**, not completion evidence.
> `authority_transfer=false` and `formal_credit_delta=0`.

## 0 – Live-code reconciliation

The original Wave 16 plan pre-dates the current GEMINI implementation and generated-artifact rules. The following deltas are measured on the bound main snapshot and govern any implementation PR:

| Surface | Live state on b9a89705 | Wave 16 delta |
|---|---|---|
| `src/stats_engine.py` | Wave 15 drift/regression engine exists; no `attribute_drift_cause()` | Add only if deterministic insufficient-data behavior and tests are included |
| `build_drift_alerts_payload()` | Emits `"wave": "15"`; no `cause` key | Add `cause` as an additive field and advance wave identity only with implementation evidence |
| `src/pipeline.py` | Imports detect/regression/payload helpers; Wave 15 banner; no causal callout | Wire causal result through the producer, not by hand-editing generated HTML |
| `tests/test_pipeline.py` | Current file has five pipeline/SSOT tests; no causal-attribution test | Add focused unit coverage plus producer/render assertion; do not assume repository-wide test count is 5 |
| `docs/_data/drift_alerts.json` | Generated artifact is Wave 15 and has no `cause` | Regenerate from code; do not edit as independent truth |
| `src/federation_bridge.py` | Snapshot has no causal field | Extend producer only if downstream use is still required; regenerate the JSON projection |
| `repo_manifest.yaml` | `manifest_version: "1.0.0"` | Bump only in the same admitted implementation change, not in this reconciliation-only PR |
| telemetry evidence | Historical ledger currently contains 2 runs, both `unknown-python`, runtime `0.0` | Current stored evidence is insufficient for empirical cause attribution across Python/OS strata |

### Admission rule

Wave 16 implementation is admitted only if it preserves fail-closed/statistically honest behavior:

1. `cause` MUST be `null` or an explicit `insufficient_data` result when minimum per-stratum evidence is not met.
2. No synthetic confidence value may be emitted as if measured from the current two-run ledger.
3. Generated surfaces (`docs/index.html`, `docs/_data/drift_alerts.json`, federation JSON) must be produced by their source code and regenerated in CI.
4. The manifest/version bump occurs only with the code + tests + regenerated outputs in the same governed implementation PR.
5. Existing IC3 #12 and R3 #16 RETURN gates remain independent and non-compensating.

---

> **Recommendation: `TEMPLATE_DUPLICATION_WITH_DELTA`**
>
> The Wave 15 architecture is sound (CI matrix, stats engine, Jekyll portal, DMAIC ledger).
> Do **not** rewrite the strategy. Duplicate the Wave 15 template and apply a controlled
> delta for the new capability scope.

---

## 1 – Wave Recommendation

| Option | Verdict |
|--------|---------|
| `TEMPLATE_DUPLICATION` | ❌ Too rigid – wave scope has earned new capabilities. |
| **`TEMPLATE_DUPLICATION_WITH_DELTA`** | ✅ **Recommended** – re-use proven scaffolding; layer in new delta only. |
| `NEW_PLAN_REQUIRED` | ❌ No evidence of architectural failure requiring a clean slate. |

---

## 2 – Template Duplication Guide

### Files / folders to copy from Wave 15

| Source (Wave 15) | Target (Wave 16) | Action |
|------------------|-----------------|--------|
| `docs/wave_16_plan.md` ← this file | `docs/wave_17_plan.md` | Copy + update wave number |
| `docs/_data/drift_alerts.json` | Preserve as runtime artifact | Reset `wave` key to `"16"` |
| `docs/historical_telemetry_ledger.json` | Keep in place | Append new wave row |
| `src/stats_engine.py` | Extend in-place | Add Wave 16 functions below existing |
| `src/pipeline.py` | Extend in-place | Add new guard-gated calls |
| `.github/workflows/generate_blsn_reports.yml` | Extend in-place | Add any new CI steps |

### Placeholders to replace

| Token | Old value | New value |
|-------|-----------|-----------|
| `"wave": "15"` | `docs/_data/drift_alerts.json` | `"wave": "16"` |
| `Wave 12/15` (module docstring) | `src/stats_engine.py:1` | `Wave 12/15/16` |
| `wave_15_plan.md` link refs | portal HTML | `wave_16_plan.md` |

### Checklist before opening Wave 16 PR

- [ ] Bump `wave` field in `docs/_data/drift_alerts.json` to `"16"`
- [ ] Preserve the historical telemetry ledger as runtime evidence; do not hand-insert a synthetic Wave 16 row
- [ ] Update `repo_manifest.yaml` `manifest_version` (minor bump: `1.0.0` → `1.1.0`)
- [ ] Update the HTML producer (`src/pipeline.py`) and regenerate `docs/index.html`; do not hand-maintain generated HTML
- [ ] Re-run: `pytest -v --durations=0`, `ruff check .`, `python -m src.pipeline`, then regenerate the governed derived surfaces
- [ ] Confirm `docs/_data/drift_alerts.json` regenerates cleanly with `any_alert: false`

---

## 3 – Wave 16 Planning Template

### Executive intent

Extend the drift-detection runtime with **causal attribution**: when `any_alert` is `True`,
surface the *root factor* (Python version, OS, dependency version) driving the anomaly.
Deliver this as a new `cause` key in `drift_alerts.json` and a human-readable callout in
the Jekyll portal dashboard.

### Previous-wave carryover

| Item | Status | Disposition |
|------|--------|-------------|
| `isinstance(int \| float)` Py 3.9 fix | ✅ Resolved – Wave 15 commit `84a235b` | Closed |
| pypy-3.9 telemetry lane stability | ⚠️ Still flaky on slow runners | Monitor; keep `telemetry: true` flag |
| `matplotlib` removal from CI | ✅ Done | Closed |
| `continue-on-error` at job level | ✅ Done | Closed |
| `docs/_data/blsn_config.yml` YAML-lint indent | ✅ Done | Closed |

### New delta for Wave 16

1. **`src/stats_engine.py`** – add `attribute_drift_cause(drift_payload, matrix_rows)` function
   - Stratifies `runtime_seconds` by `python_version` and `os`
   - Returns `{"cause_factor": "python_version", "cause_value": "3.9", "confidence": 0.92}`
   - Falls back gracefully when fewer than 4 samples per stratum
2. **`docs/_data/drift_alerts.json`** – add optional `cause` key written by `pipeline.main()`
3. **`docs/index.html`** (portal) – add `cause` callout line inside the existing drift-alert banner
4. **Tests** – add `test_attribute_drift_cause_returns_expected_shape` in `tests/test_pipeline.py`

### Runtime evidence required

| Artefact | Source | Acceptance gate |
|----------|--------|----------------|
| `docs/_data/drift_alerts.json` | `python src/pipeline.py` | `cause` key present when `any_alert: true` |
| `docs/pytest_telemetry.json` | CI pytest step | 0 failures on Py 3.9/3.10/3.11/3.12/3.13-dev |
| `output/report.html` | CI pipeline run | Drift banner renders `cause` line |

### CI/CD checks

```yaml
# No structural changes to the matrix needed.
# Add one new validation step after the existing pytest step:
- name: Drift-Cause Shape Validation
  if: matrix.python-version == '3.9' && matrix.os == 'ubuntu-latest'
  run: |
    python -c "
    import json, pathlib
    d = json.loads(pathlib.Path('docs/_data/drift_alerts.json').read_text())
    print('Wave:', d['wave'])
    print('any_alert:', d['any_alert'])
    print('drift keys:', list(d['drift'].keys()))
    "
```

### DMAIC loop

| Phase | Owner | Action |
|-------|-------|--------|
| **Define** | @GBOGEB | Confirm `cause` key schema matches Jekyll template needs |
| **Measure** | CI | `drift_alerts.json` regenerated on every push |
| **Analyse** | `stats_engine.attribute_drift_cause()` | Stratified ANOVA or Kruskal-Wallis |
| **Improve** | `pipeline.main()` | Write `cause` to JSON; render in HTML |
| **Control** | pytest gate | `test_attribute_drift_cause_returns_expected_shape` blocks regression |

### Federation / bridge impact

- `src/federation_bridge.py` – add `cause` field to the cherry-pick JSON emitted to `docs/federation/`
- `docs/federation/federation_cherry_pick.json` – generated projection; change its producer first, then regenerate with an additive `"cause": null` default if the bridge consumer still requires it
- No breaking changes to existing consumers (additive key only)

### Portal / HTML output

- `docs/index.html` drift-alert banner gains one additional line:
  ```html
  {% if site.data.drift_alerts.cause %}
  <p class="mt-1 text-sm">Root factor: <strong>{{ site.data.drift_alerts.cause.cause_factor }}</strong>
  = <code>{{ site.data.drift_alerts.cause.cause_value }}</code>
  (confidence {{ site.data.drift_alerts.cause.confidence | times: 100 | round }}%)</p>
  {% endif %}
  ```
- No changes to CSS tokens or density/audience system.

### Acceptance criteria

- [ ] All collected tests pass on blocking lanes (Py 3.9 – 3.12 and Windows 3.12); do not encode a stale fixed test count
- [ ] `ruff check .` clean (zero errors)
- [ ] `yamllint` clean on `config/blsn_config.yaml`
- [ ] `docs/_data/drift_alerts.json` contains `"wave": "16"` after pipeline run
- [ ] `cause` key present in JSON (value may be `null` when `any_alert: false`)
- [ ] Jekyll portal renders without build errors (`jekyll build` clean)
- [ ] No new `continue-on-error: false` step failures in telemetry lanes

### Copilot next actions

1. Open new PR: `feat(wave-16): Causal Drift Attribution`
2. Add `attribute_drift_cause()` to `src/stats_engine.py`
3. Wire into `pipeline.main()` under `_STATS_ENGINE_AVAILABLE` guard
4. Add test in `tests/test_pipeline.py`
5. Update `docs/_data/drift_alerts.json` schema (add `"cause": null` default)
6. Update `repo_manifest.yaml` version → `1.1.0`
7. Run full local validation; push; monitor CI matrix

---

## 4 – Open TODO items carried from Wave 15

> These were noted as non-blocking in Wave 15 and deferred to Wave 16+.

| # | File | Description | Priority |
|---|------|-------------|----------|
| T-01 | `tests/test_pipeline.py:20-22` | Mass-flow limit key assertions aligned to current SSOT schema | Low (passing) |
| T-02 | `.github/workflows/…:64-67` | Review `continue-on-error` scope after pypy-3.9 stabilises | Medium |
| T-03 | `.github/workflows/*.yml` | Reconcile GitHub Action major versions/runtime compatibility as a separate CI-governance change; this does not belong in `src/pipeline.py` | High |
| T-04 | `docs/index.html` | Audience toggle UX: persist `data-audience` across page navigations via `localStorage` | Low |
| T-05 | `src/stats_engine.py` | Increase `historical_ledger` rolling window from 10 to 20 runs once telemetry backlog reaches 20 entries | Low |
