# Federation Pattern — Governance Reference

This is the single governance document for the **CODEX / ABACUS / ARTSTYLE**
federation. Every member repository may reference it; `GBOGEB/GEMINI` declares
its conformance machine-readably in [`repo_manifest.yaml`](repo_manifest.yaml)
under the `federation` key, and enforces it mechanically via
[`src/federation_guard.py`](src/federation_guard.py).

## The governing law

```
Move artifacts downward into deeper folders.
Move ownership upward into clearer domains.
Avoid moving repositories unless duplication is overwhelming.
```

This invariant separates two operations people usually conflate:

- **Refactoring** — mechanical, history-preserving, reversible → change *folder
  depth*.
- **Re-homing** — semantic, lossy, requires review → change *ownership domain*.

Keeping these orthogonal is what makes the system safe to evolve.

## Federation topology

ARTSTYLE is **not** a layer above CODEX and ABACUS; it is a bidirectional
bridge that owns *no artifacts of its own domain* — only the interfaces between
them.

```
CODEX  ↔  ARTSTYLE  ↔  ABACUS
```

- **CODEX** — *knowledge of how*. Declarative and **versioned** (schemas,
  blocks, templates). Consumers pin to a semver.
- **ABACUS** — *knowledge in action*. Stateful and **ephemeral** (runs,
  experiments, deployments). References CODEX versions but is never depended
  upon.
- **ARTSTYLE** — the federation bridge. Owns agent contracts, ports, and
  handshakes.

**Dependency rule:** *ABACUS may import CODEX; CODEX must never import ABACUS.*
This one-directional dependency keeps the federation from degenerating back
into a tangle.

**ARTSTYLE membership test:** *would both CODEX and ABACUS break if this
changed?* If yes → ARTSTYLE. If only one breaks → it belongs in that one.

## The decision procedure

Don't ask "which repo should own this?" Ask "what *is* this artifact?"

1. **Classify by type** → Schema / Block / Parser / RTM logic / Taxonomy /
   Runtime / Contract / Policy / Knowledge / Dashboard / Calculation.
2. **Route by type** → each type has exactly one home domain (table below).

Anything that resists classification is a signal it is actually *two* artifacts
entangled — split it first, then route each half.

| Artifact type           | Home domain                       |
| ----------------------- | --------------------------------- |
| Schema                  | CODEX                             |
| MCP block               | CODEX                             |
| Template                | CODEX                             |
| Parser                  | CODESPACES_jyperter               |
| RTM logic               | DOCX_RTM_Automation               |
| Taxonomy                | document-organization-system     |
| Agent runtime           | ABACUS                            |
| Federation contract     | ARTSTYLE                          |
| Governance policy       | anthropic                        |
| Domain knowledge        | cryogenic-accelerator-workspace  |
| Dashboard               | cryo_leak_rate_dashboard         |
| Engineering calculation | Q_engineering_tools              |
| Review / reasoning      | GEMINI                           |
| Notebook                | GEMINI                           |

## Allowed vs forbidden operations

| Operation                                   | Allowed? | Why                              |
| ------------------------------------------- | -------- | -------------------------------- |
| Deepen a folder (`x.py` → `x/x.py`)         | ✅ auto   | History-preserving, reversible   |
| Group siblings into a subfolder             | ✅ auto   | History-preserving, reversible   |
| Move artifact across repos                  | ⚠️ review | Semantic, breaks imports         |
| Move/splice README, ADR, CHANGELOG          | ❌ never  | Provenance-bearing               |
| Move a *concept* (e.g. "move RTM")          | ❌ never  | Only modules/schemas/libs move   |

The auto-allowed rows are encoded as a CI guard. The review rows require a
human PR with a stated ownership justification.

## Frozen (provenance-bearing) artifacts

The general rule: *any artifact whose value is its provenance stays put; any
artifact whose value is its content can move.* A parser's value is its content
→ movable. A `CHANGELOG`'s value is that it belongs to *this* repo's timeline →
frozen.

Frozen in GEMINI: `README.md`, `CHANGELOG.md`, `LICENSE`, and any ADR
(`docs/adr/**`, `**/ADR*.md`).

## GEMINI's place in the federation

GEMINI owns the **review-reasoning-notebook** concern. To remain a good
federation citizen:

- Keep GEMINI's artifacts classified as *review / reasoning / notebook*. Do not
  let CODEX-type (schemas, reusable blocks) or ABACUS-type (runtime, agents)
  artifacts accumulate here — route them out when they appear. The federation
  guard flags such foreign artifacts automatically.
- Treat `repo_manifest.yaml#federation` as GEMINI's federation handshake: it
  declares the concern, the pinned upstream CODEX version, and the contract
  ARTSTYLE expects.
- Federation peers' artifacts are mirrored read-only under
  `docs/federation/`; that path is allow-listed for the guard.
