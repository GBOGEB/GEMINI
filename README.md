# GEMINI — Governed SSOT, Analytics & Cross-Agent Handover Bridge

[![Manifest](https://img.shields.io/badge/manifest-1.0.0-blue)](repo_manifest.yaml)
[![Schema](https://img.shields.io/badge/schema-1-blueviolet)](repo_manifest.yaml)
[![BLSN CI](https://img.shields.io/github/actions/workflow/status/GBOGEB/GEMINI/generate_blsn_reports.yml?branch=main&label=BLSN%20CI)](https://github.com/GBOGEB/GEMINI/actions/workflows/generate_blsn_reports.yml)
[![GitHub Pages](https://img.shields.io/badge/docs-GitHub%20Pages-2ea44f?logo=github)](https://gbogeb.github.io/GEMINI/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

> **Purpose:** turn governed configuration and handover evidence into reproducible validation, analytics, review artifacts and machine-readable receipts without silently promoting source claims into verified engineering authority.

GEMINI began as a compact **Single Source of Truth (SSOT) baseline configuration engine**. The live repository is now broader: it combines the original BLSN configuration/rendering pipeline with statistical telemetry, GitHub Pages publication, CODEX/ABACUS federation, governed cross-agent handover validation, read-only Google Drive ingress, and exact-artifact handoff tooling.

The repository therefore has **two connected execution planes**:

1. **BLSN baseline plane** — YAML SSOT → validation → telemetry/statistics → rendered engineering views.
2. **Governed bridge plane** — Gemini/source session → handover package/Drive → evidence validation → Git branch/PR/CI → governed downstream consumption.

Neither plane automatically creates QPS engineering, release, procurement or formal authority. Evidence state and authority remain explicit.

---

## Quick launch

| Start here | Purpose | State |
|---|---|---|
| [`config/blsn_config.yaml`](config/blsn_config.yaml) | BLSN SSOT: simulation limits, system parameters, telemetry targets, presentation and publishing controls | **Source configuration** |
| [`src/pipeline.py`](src/pipeline.py) | Main idempotent BLSN render/orchestration engine | **Implemented** |
| [`GEMINI.md`](GEMINI.md) | Governed bridge authority model, evidence vocabulary and handover contract | **Governance contract** |
| [`docs/index.html`](docs/index.html) | Generated engineering/telemetry portal | **Generated view** |
| [`docs/IC3_EXTERNAL_AUTH_RUNBOOK.md`](docs/IC3_EXTERNAL_AUTH_RUNBOOK.md) | GitHub OIDC → Google WIF → Drive read-only hosted proof | **Runbook; external setup still gated** |
| [`docs/R3_SUCCESSOR_INGRESS_RUNBOOK.md`](docs/R3_SUCCESSOR_INGRESS_RUNBOOK.md) | Exact Git-object + portable-environment successor handoff | **Active handoff runbook** |
| [Issue #12](https://github.com/GBOGEB/GEMINI/issues/12) | IC3 real hosted Drive ingress / owner-side WIF configuration | **Open external gate** |
| [Issue #16](https://github.com/GBOGEB/GEMINI/issues/16) | R3 successor exact Git bundle + environment ingress | **Open producer gate** |
| [Actions](https://github.com/GBOGEB/GEMINI/actions) | CI, handover, Drive, CodeQL and exact-environment workflows | **Executable evidence** |

### Navigation rule

Use the following order when deciding what is authoritative:

```text
README / navigation
→ repo_manifest.yaml + GEMINI.md
→ source configuration / source package
→ executable validator / pipeline
→ machine-readable receipt
→ CI / hosted proof
→ generated HTML / PDF / dashboards
```

Generated pages and reports are **views of governed inputs and execution evidence**. They do not become a second SSOT simply because they are easier to browse.

---

## 1. System BIOS and intent

### Version control

- **Manifest version:** `1.0.0`
- **Schema version:** `1`
- **Primary SSOT:** `config/blsn_config.yaml`
- **Repository manifest:** `repo_manifest.yaml`
- **Bridge governance:** `GEMINI.md`

### Core purpose

GEMINI is a code-driven repository framework for:

- defining cryogenic/BLSN configuration limits and metadata as code;
- validating source configuration before publication;
- rendering repeatable HTML, Markdown, PDF and slide-style outputs;
- collecting CI/test telemetry and comparing claimed vs actual validation;
- building statistical/process-control evidence from historical runs;
- federating selected CODEX/ABACUS artifacts into a local review surface;
- packaging and validating cross-agent Gemini handovers;
- proving read-only external ingress without storing long-lived Google credentials;
- producing review-bound receipts that preserve lineage, hashes and evidence status;
- giving coding agents a decoupled, machine-readable handover surface instead of relying on chat/session memory.

### What GEMINI is not

GEMINI is **not**:

- an autonomous source of engineering truth beyond its governed inputs;
- a replacement for the QPS domain authority held elsewhere;
- a mechanism for promoting a Gemini-authored statement directly to `VERIFIED`;
- a write-capable Google Drive synchronization service;
- a substitute for Git review, CI or downstream acceptance;
- proof of runtime GOLD, release acceptance or formal authority merely because an artifact was transported or rendered.

---

## 2. Authority model

The bridge plane uses an explicit authority split:

| Surface | Responsibility |
|---|---|
| **Google Drive** | Persistent handover/source storage and native revision history |
| **Gemini CLI / source tooling** | Local agent execution and source-session packaging |
| **GitHub / GEMINI** | Governed code, schemas, hashes, receipts, CI and review-bound commit identity |
| **Chat/session memory** | Orchestration context only; never sole authority for completed work |
| **Downstream QPS / CODEX / ABACUS** | Independent domain, governance or runtime acceptance according to their own contracts |

Required evidence vocabulary:

```text
VERIFIED
IMPLEMENTED
DECLARED
INFERRED
PARTIAL
DEFERRED
```

A source-agent assertion shall not be promoted to `VERIFIED` unless it is independently corroborated by runtime evidence, repository evidence, connector evidence or another authoritative source.

---

## 3. Architecture at a glance

### 3.1 BLSN baseline and analytics plane

```text
config/blsn_config.yaml
        │
        ├── simulation/system limits
        ├── telemetry tuples
        ├── presentation controls
        └── publishing controls
        │
        ▼
src/validators.py + src/pipeline.py
        │
        ├── sanity checks
        ├── metric Markdown
        ├── HTML report
        ├── PDF report
        └── Reveal-style presentation
        │
        ▼
docs/
        │
        ├── telemetry_parser.py ── claimed-vs-actual KPI verification
        ├── stats_engine.py ────── historical ledger / DoE / PCA / drift
        ├── bt_ranking.py ─────── Bradley-Terry ranking from derived strengths
        ├── indexer.py ────────── artifact index + lineage metadata
        └── jekyll_bridge.py ──── Jekyll _data / _metrics projection
        │
        ▼
GitHub Pages + CI artifacts
```

### 3.2 Governed cross-agent handover plane

```text
Gemini/source session
        │
        ▼
GMI-<id>/ handover package
        │
        ├── RAW/
        ├── HANDOVER/
        ├── MANIFEST/
        └── ARTIFACTS/
        │
        ▼
Google Drive object / revision
        │
        ▼
read-only Drive ingress
        │
        ▼
package validation → batch census → evidence binding
        │
        ▼
Git branch / commit / PR
        │
        ▼
CI + independent review
        │
        ▼
merged governed state / downstream consumer
```

### 3.3 Federation plane

```text
GBOGEB/CODEX ─┐
              ├── src/federation_bridge.py
GBOGEB/ABACUS ┘            │
                           ▼
                 docs/federation/
                           │
                           ├── index/KPI evidence
                           ├── candidate SARIF evidence
                           └── federation_cherry_pick.json
                           │
                           ▼
                 local ranking / dashboard
```

The federation bridge assimilates selected artifacts for comparison and prioritization. It does not transfer the source repository's authority to GEMINI.

---

## 4. BLSN SSOT contract

The current SSOT is [`config/blsn_config.yaml`](config/blsn_config.yaml).

It presently carries five major groups:

| Group | Current role |
|---|---|
| `system_meta.presentation_layer` | Theme, density, audience and optional CSS framework controls |
| `simulation_parameters` | Nominal/min/max mass-flow values and baseline simulation identity |
| `system_parameters` | Nitrogen pre-cooling, turbine, helium-loop and cold-box engineering boundaries |
| `telemetry.tuple_execution_targets` | Target / warning / failure tuples for CI, pytest, pipeline and lint timing |
| `publishing` | PDF/slides switches and base URL |

### SSOT rule

Change the **source configuration first**, then regenerate governed outputs.

Do not manually edit a generated dashboard to make it disagree with `config/blsn_config.yaml`. If a generated result is wrong, repair the source data, validation logic or rendering logic and regenerate.

### Current minimum sanity gate

The public validator currently proves that:

```text
min_limit_g_s < nominal_mass_flow_g_s < max_limit_g_s
```

Additional system parameters are present in the SSOT and are exposed to tests/rendering, but their existence shall not be confused with comprehensive physical-model validation unless an explicit executable check exists.

---

## 5. Core implementation map

| Component | Responsibility |
|---|---|
| [`src/parameters.py`](src/parameters.py) | Load source configuration |
| [`src/validators.py`](src/validators.py) | Public sanity-check interface |
| [`src/pipeline.py`](src/pipeline.py) | Main report generation and orchestration |
| [`src/telemetry_parser.py`](src/telemetry_parser.py) | Build DMAIC KPI dashboard from pytest/runtime telemetry |
| [`src/stats_engine.py`](src/stats_engine.py) | Historical telemetry ledger, DoE foundation, PCA/process-control and drift analysis |
| [`src/bt_ranking.py`](src/bt_ranking.py) | Bradley-Terry ranking using derived/PCA strengths |
| [`src/indexer.py`](src/indexer.py) | Index `docs/` + `config/` artifacts with basic lineage metadata |
| [`src/jekyll_bridge.py`](src/jekyll_bridge.py) | Convert generated Python artifacts into Jekyll data/metric collections |
| [`src/federation_bridge.py`](src/federation_bridge.py) | Assimilate selected CODEX/ABACUS index/KPI/SARIF evidence |
| [`src/drive_ingress.py`](src/drive_ingress.py) | Fail-closed, read-only Google Drive census with classified failures |
| [`src/handover_package.py`](src/handover_package.py) | Validate one governed GMI package, canonical JSON shape and hashes |
| [`src/handover_batch.py`](src/handover_batch.py) | Batch-census packages and classify idempotency/duplicate state |
| [`src/handover_census.py`](src/handover_census.py) | Validate and census stored handover receipts |
| [`src/handover_binding.py`](src/handover_binding.py) | Bind content and transport evidence without compensation or source mutation |

---

## 6. Governed handover contract

A preferred source-session package has the following shape:

```text
GMI-<id>/
├── RAW/
├── HANDOVER/
├── MANIFEST/
└── ARTIFACTS/
```

The package validator expects a manifest that includes at least:

- schema version;
- `GMI-*` session identity;
- source agent;
- generation timestamp;
- evidence status;
- scope;
- source references;
- artifact references;
- current gate;
- next action.

Local files are hashable artifacts. Drive-native objects remain Drive-native evidence and shall not be given fabricated local hashes.

### Non-compensation rule

Transport evidence and content evidence remain independent.

A successful Drive authentication does not compensate for an invalid handover package.  
A valid handover package does not compensate for missing hosted transport proof.  
The binding output explicitly preserves:

```text
authority_transfer = false
formal_credit_delta = 0
source_claims_promoted = false
```

---

## 7. Google Drive ingress

[`src/drive_ingress.py`](src/drive_ingress.py) is intentionally **read only**.

The hosted trust chain is:

```text
GitHub Actions
→ GitHub OIDC
→ Google Workload Identity Federation
→ dedicated service account impersonation
→ short-lived OAuth access token
→ Google Drive API (drive.readonly)
→ configured handover root
```

Long-lived service-account JSON keys and OAuth refresh tokens are not part of the design.

The code classifies failures such as:

- `CONFIG_MISSING`
- `OIDC_WIF_AUTH_FAILED`
- `GOOGLE_ACCESS_TOKEN_REJECTED`
- `DRIVE_API_FORBIDDEN`
- `DRIVE_API_UNAVAILABLE`
- `ROOT_INACCESSIBLE_OR_MISSING`
- `ROOT_NOT_FOLDER`
- `ROOT_ID_MISMATCH`
- `CENSUS_ZERO_ITEMS`

A real IC3 pass requires the exact final classification:

```json
{
  "result": "PASS",
  "classification": "IC3_DRIVE_READONLY_GT0_STEP_PASS"
}
```

As of the 2026-10-02 documentation refresh, the implementation exists but the owner-side WIF/service-account/Drive ACL configuration remains tracked in [Issue #12](https://github.com/GBOGEB/GEMINI/issues/12). The workflow is deliberately manual-dispatch only so absent owner configuration does not repeatedly burn runners.

---

## 8. Exact successor ingress / R3 support

GEMINI also carries producer/reference tooling for an exact QPS successor handoff:

- [`scripts/build_qps_r3_successor_handoff.ps1`](scripts/build_qps_r3_successor_handoff.ps1)
- [`scripts/build_qps_r3_successor_handoff.sh`](scripts/build_qps_r3_successor_handoff.sh)
- [`scripts/validate_r3_exact_env_capsule.py`](scripts/validate_r3_exact_env_capsule.py)
- [`docs/R3_SUCCESSOR_INGRESS_RUNBOOK.md`](docs/R3_SUCCESSOR_INGRESS_RUNBOOK.md)

The runbook separates two prerequisites:

1. **Genuine successor Git-object bundle** from an authentic `GBOGEB/cryoplant-project` clone.
2. **Portable exact Python 3.12 environment capsule** with a machine-readable dependency lock and relocation proof.

The runbook records the capsule-v2 lineage as proven. The genuine successor Git-object handoff remains the open producer-side prerequisite tracked in [Issue #16](https://github.com/GBOGEB/GEMINI/issues/16).

Transport preparation does not imply QPS R3 acceptance, runtime GOLD, engineering authority or release credit.

---

## 9. Generated outputs

The main generated publication surface is `docs/`.

Current committed/generated artifacts include:

| Artifact | Purpose |
|---|---|
| `docs/index.html` | Main generated engineering/telemetry portal |
| `docs/blsn_report.pdf` | PDF projection of the BLSN report |
| `docs/presentation.html` | Reveal-style telemetry presentation |
| `docs/*-runtime-s.md` | Metric-specific Markdown pages |
| `docs/kpi_dashboard.json` | Claimed-vs-actual validation/runtime KPI payload |
| `docs/historical_telemetry_ledger.json` | Historical run ledger |
| `docs/experimental_design_matrix.json` | DoE/matrix telemetry surface |
| `docs/bt_ranking.json` | Bradley-Terry ranking output |
| `docs/index.json`, `docs/index.yaml` | Machine-readable repository artifact index |
| `docs/_data/` | Jekyll-ingestible generated data |
| `docs/_metrics/` | Jekyll metric collection |
| `docs/visuals/` | Plotly/chart payloads |
| `docs/federation/` | Assimilated CODEX/ABACUS bridge evidence |
| `handover/receipts/` | Governed cross-agent receipt store |

These outputs should be regenerated from their source and executable producers rather than hand-maintained as independent truth.

---

## 10. CI/CD and publication

The primary workflow is [`.github/workflows/generate_blsn_reports.yml`](.github/workflows/generate_blsn_reports.yml).

### Full-matrix validation

Configured lanes include:

- Ubuntu CPython **3.9, 3.10, 3.11, 3.12**
- Windows CPython **3.12**
- PyPy **3.9** telemetry lane
- Python **3.13-dev** telemetry lane
- Python **3.14-dev** telemetry lane

The Ubuntu Python 3.9 lane is the main lint/build/telemetry gate. Compatibility lanes provide additional execution evidence; several non-3.9 pytest steps are intentionally non-blocking.

The canonical build lane performs, in order:

```text
checkout
→ dependency install
→ YAML / JSON lint
→ Ruff lint
→ pytest + JSON telemetry
→ KPI dashboard parse
→ BLSN pipeline
→ repository indexes
→ federation bridge
→ statistical engine
→ Bradley-Terry ranking
→ Jekyll bridge
→ artifact upload
```

### GitHub Pages

On `main`, after the validation job succeeds, the Pages job rebuilds the publication assets, builds the Jekyll site and deploys `./_site`.

### Other workflows

The live workflow set also includes:

- `codeql.yml`
- `copilot-setup-steps.yml`
- `drive_ingress.yml`
- `drive_ingress_tests.yml`
- `gmi_handover_tests.yml`
- `r3_successor_exact_env_capsule.yml`

Workflow existence is not itself proof that an external gate has passed; use the run/receipt appropriate to that gate.

---

## 11. Testing surfaces

The repository currently contains focused tests for:

- the BLSN pipeline and SSOT structure;
- Drive ingress behavior;
- Gemini bridge hooks;
- single-package handover validation;
- batch handover census/idempotency;
- handover receipt census;
- content/transport evidence binding.

Test modules live under [`tests/`](tests/).

A useful local validation sequence is:

```bash
python -m pip install --upgrade pip
python -m pip install pyyaml pytest pytest-json-report ruff yamllint fpdf2 plotly pandas numpy scipy

ruff check .
pytest -q
python -m src.pipeline
python src/indexer.py
python src/stats_engine.py
python src/bt_ranking.py
python src/jekyll_bridge.py
```

> The repository currently has no root `requirements.txt` or pinned general-purpose lockfile. The GitHub Actions workflow is therefore the executable dependency reference until dependency locking is added as a separate governed change.

For contributor-side formatting, [`.pre-commit-config.yaml`](.pre-commit-config.yaml) configures trailing-whitespace/EOF checks, Ruff/Ruff-format and Prettier.

---

## 12. Repository structure

```text
GBOGEB/GEMINI/
├── .gemini/
│   ├── hooks/                         # Runtime bridge-hook implementation
│   └── settings.json                  # Project hook configuration
├── .github/
│   └── workflows/                     # CI, Drive, handover, CodeQL, R3 workflows
├── config/
│   └── blsn_config.yaml               # BLSN SSOT
├── docs/
│   ├── _data/                         # Generated Jekyll data
│   ├── _metrics/                      # Generated metric collection
│   ├── federation/                    # CODEX/ABACUS assimilation
│   ├── visuals/                       # Plot/chart payloads
│   ├── index.html                     # Main generated portal
│   ├── kpi_dashboard.json
│   ├── historical_telemetry_ledger.json
│   ├── experimental_design_matrix.json
│   ├── bt_ranking.json
│   ├── IC3_EXTERNAL_AUTH_RUNBOOK.md
│   └── R3_SUCCESSOR_INGRESS_RUNBOOK.md
├── handover/
│   ├── bridge_state.json
│   └── receipts/                      # Governed receipt lineage
├── scripts/
│   ├── build_qps_r3_successor_handoff.ps1
│   ├── build_qps_r3_successor_handoff.sh
│   └── validate_r3_exact_env_capsule.py
├── src/
│   ├── pipeline.py                    # Main BLSN engine
│   ├── validators.py
│   ├── telemetry_parser.py
│   ├── stats_engine.py
│   ├── bt_ranking.py
│   ├── indexer.py
│   ├── jekyll_bridge.py
│   ├── federation_bridge.py
│   ├── drive_ingress.py
│   ├── handover_package.py
│   ├── handover_batch.py
│   ├── handover_census.py
│   └── handover_binding.py
├── tests/                              # Pipeline, Drive and handover tests
├── GEMINI.md                           # Governed bridge context
├── notebook.md                         # Compact agent/source-edit instruction surface
├── repo_manifest.yaml                  # BIOS + manifest/schema identity
└── README.md                           # START HERE
```

The legacy `ASCII_repo_structure` file reflects the repository's earlier, smaller shape and should not be treated as the current structure authority.

---

## 13. Development and governance rules

### Source-first change discipline

1. Identify the authoritative source surface.
2. Change source/config/schema rather than only a generated view.
3. Run the narrowest relevant validation.
4. Regenerate dependent artifacts.
5. Preserve hashes, receipts and predecessor lineage where applicable.
6. Work on a feature/wave branch.
7. Open a PR; do not silently mutate `main` from an agentic shell.
8. Promote evidence status only when the required independent proof exists.

### Security rules

Do not commit:

- OAuth refresh tokens;
- service-account JSON;
- API keys;
- passwords;
- `.env` secrets;
- private Drive content merely to simplify CI.

### Generated-output rule

HTML/PDF/JSON/Jekyll outputs are controlled projections. A generated file may be committed for publication or review, but it remains traceable to its producer and source configuration.

### Evidence rule

A receipt shall say what was actually measured or computed. Do not invent hashes, timestamps, pass states or source identities.

---

## 14. Current execution state — 2026-10-02

This root documentation refresh was based on live `main` at commit `9e2be9c5e66d4e3a00e6f3dfd6c59319d2274049`.

### Implemented repository capabilities

- BLSN YAML SSOT and sanity validation.
- Multi-format report generation (HTML, Markdown, PDF, presentation).
- CI telemetry capture and claimed-vs-actual KPI dashboard generation.
- Historical telemetry ledger, DoE/PCA/drift-analysis engine and Plotly payload generation.
- Bradley-Terry ranking layer.
- Repository indexing and Jekyll data/metrics bridge.
- CODEX/ABACUS federation ingestion surface.
- GMI handover package, batch, census and evidence-binding code.
- Read-only Drive ingress implementation with classified fail-closed behavior.
- Exact successor handoff scripts and environment-capsule validator.
- Dedicated tests and workflows for the principal bridge surfaces.

### Open or deliberately withheld gates

| Gate | Current state |
|---|---|
| **IC3 real hosted Drive ingress** | **WITHHELD** pending owner-side Google WIF/service-account/Drive ACL configuration; tracked by #12 |
| **R3 genuine successor Git-object bundle** | **PENDING**; portable environment capsule lineage is recorded as proven, but genuine bundle production remains open in #16 |
| **Wave 16 causal-attribution delta** | **PLANNED**, not current implementation; `docs/wave_16_plan.md` is a plan, not completion evidence |
| **Manifest bump to 1.1.0** | **NOT DONE**; current manifest remains `1.0.0` |
| **Branch protection** | **NOT ENABLED** at the inspected 2026-10-02 main snapshot |
| **Pinned general dependency lock** | **NOT PRESENT**; workflow dependency declarations remain the current executable reference |

The repository should not be described as fully production-proven while these independent gates remain open.

---

## 15. Next execution order

The immediate bounded sequence is:

1. **Close the IC3 owner/config predicate** — configure the governed Google WIF provider, dedicated service account, Drive API/ACL and repository variables from [Issue #12](https://github.com/GBOGEB/GEMINI/issues/12).
2. **Run one real hosted Drive proof** — manually dispatch `drive_ingress.yml`; require >0 executed work and exact `IC3_DRIVE_READONLY_GT0_STEP_PASS`.
3. **Bind content + transport evidence without compensation** — only after IC3 PASS, advance the independent consumer/binding gate.
4. **Complete the genuine R3 successor Git-object handoff** — produce and verify the exact bundle/sidecar/receipt from an authentic QPS clone per [Issue #16](https://github.com/GBOGEB/GEMINI/issues/16).
5. **Reconcile Wave 16 against live code before implementation** — treat `docs/wave_16_plan.md` as a proposal; implement only measured deltas and then bump manifest/version metadata in the same governed change.
6. **Add dependency locking/reproducibility policy** — convert workflow-only dependency declarations into an explicit governed runtime/test dependency contract.
7. **Enable and prove branch protection/ruleset governance** — treat this as a separate repository-control gate, not as an implication of CI existence.
8. **Keep root README, runbooks, generated portal and machine-readable manifest synchronized** with each admitted capability/state change.

---

## 16. Design principles

GEMINI follows these operating principles:

1. **SSOT first** — one governed source, many reproducible views.
2. **Idempotency** — re-running a build or census should not silently change authority.
3. **Fail closed** — missing auth/config/evidence is classified, not waved through.
4. **Non-compensation** — one green gate does not erase a different red gate.
5. **Evidence before status** — pass/fail language follows executed proof.
6. **Lineage preservation** — predecessor states and hashes remain attributable.
7. **Generated views are not authority** — dashboards remain derivatives.
8. **Federation without authority transfer** — cross-repo evidence can be consumed without collapsing ownership boundaries.
9. **Agent portability** — handover artifacts should be useful to Gemini, Copilot, OpenAI models and other coding agents without depending on hidden chat memory.
10. **Human review remains explicit** — Git branches, PRs and downstream acceptance are part of the control system.

---

## 17. License

Licensed under the [MIT License](LICENSE).

---

**Repository role:** governed SSOT/rendering engine + analytics + cross-agent handover bridge  
**Manifest:** `1.0.0` / schema `1`  
**Root documentation refreshed:** 2026-10-02
