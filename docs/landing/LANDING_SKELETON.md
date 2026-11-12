# Core-repository landing skeleton — R2 (pilot: GEMINI)

**Status:** pilot. GEMINI is the first repository on this structure ([R1 #49](https://github.com/GBOGEB/GEMINI/pull/49), R2 this page). GEMINI is **not** part of JADE OG 5; the JADE OG 5 repositories are the next target.

**Purpose:** every core repository's root `README.md` should feel like the same building: the same doors in the same places, so a visitor who knows one landing can find their way in the next. What is *inside* each room — domain, EPICs, owner, diagrams, gates — is personal to the repository.

## 1. Fixed structure (same in every repository)

The order and the meaning of each part are fixed. Heading wording may name the repository (for example "Why GEMINI exists — BIOS").

| # | Part | Must answer | Done when |
|---|---|---|---|
| 0 | Title, badges, one-sentence promise | What is this, in one breath? | Badges point at real files/workflows; licence badge matches `LICENSE` |
| 0a | **At a glance** card | Domain, EPICs, owner and decision authority, federation role, owns / does not own, status snapshot | Every slot in §2 is filled from a source, or explicitly says `not yet declared` |
| 0b | "I want to…" router | Where does *my* question start? | Every row links to a heading on the page or a file that exists |
| 1 | Why it exists — BIOS | Baseline, Identity, Orchestration, Safety; who uses it; where authority lives | Authority files named and linked |
| 2 | From source to decision | The repo's journey from input to accepted result | Steps name the real gate at each hand-off |
| 3 | What is inside | Block → native source → input/output → boundary | Every `src/` module that does work appears once; boundary column says what it does *not* prove |
| 4 | Where it sits in the federation | Neighbours, what they keep, the interface | Links only; no copied capability of another owner |
| 5 | Process diagrams | Flow, SIPOC, Kahn/DAG as needed | Labelled as declared architecture unless a receipt backs it |
| 6 | Status and open gates | What is open, its status, what would close it | Cut at one exact `main` SHA and date; each row links its live issue/PR |
| 7 | Run it locally | Commands on the **declared** runtime | Runtime matches the gating CI leg / `.python-version` |
| 8 | Evidence rules | Vocabulary and non-compensation | Points at the repo's own governance file |
| 9 | Repository map and next actions | Which folder to open, ordered next actions | Next actions match §6 |
| — | Footer | BIOS line, release authority, licence, landing version + SHA | Landing version and SHA match §6 |

## 2. Personal slots (different in every repository)

These fill the **At a glance** card. Take each value from a source in the repository or its live tracker; never invent one.

| Slot | Meaning | GEMINI (R2) source |
|---|---|---|
| Domain | The problem area the repo is accountable for | `repo_manifest.yaml` `bios`, `GEMINI.md` purpose |
| EPICs carried here | Issue families the repo owns, with their open anchors | Issue title prefixes `[GM-I-C]`, `[P0-G1]`; BLSN |
| Owner and decision authority | Who admits to the default branch and grants external access | Repository owner account; no agent or bot holds it |
| Role in the federation | One line: what this repo *is* to its neighbours | Federation README |
| Owns / does not own | The boundary, both sides | §3 capability map; federation ownership list |
| Status snapshot | `main@<sha>`, date, open issue/PR counts | `git rev-parse origin/main`, `gh issue list`, `gh pr list` at the same moment |

**Nuance, not template-filling.** The BIOS letters, the journey, the chosen diagrams and the operating routes are written for the repo's domain. A QA repo's journey ends at a first-red diagnosis; a methods repo's at a validated kernel; GEMINI's at an admitted, read-back merge. Keep the *parts*; rewrite the *content*.

## 3. Rules carried from the GEMINI pilot

1. **One pulse per snapshot.** Read every status row at the same `main` SHA and record that SHA in §6 and in the footer.
2. **Status rows point, they do not certify.** A row says where the live truth is and what would close it; it is never a closure badge.
3. **Merged is not live.** A merged workflow or adapter that has never run, lacks its secret or watches missing paths is reported as *merged, not live* (R2 found this for GEMINI #53).
4. **Link neighbours, never copy them.** §4 links the owner; it does not restate their capability as the repo's own.
5. **Declared runtime.** §7 uses the gating CI leg, not the workstation's interpreter.
6. **Readable first screen.** The At-a-glance card and router fit on one screen; long method text goes in a `<details>` block.
7. **Guard the structure.** [`tests/test_readme_landing.py`](../../tests/test_readme_landing.py) checks the part order, the card slots, the snapshot SHA and that every relative link and in-page anchor resolves.

## 4. Rolling out to the next repository (JADE OG 5)

- [ ] Fetch, then cut the snapshot at the current default-branch SHA (`master` for the Hub).
- [ ] Fill §2 slots from that repo's sources; mark any that are missing as `not yet declared` and raise them with the owner.
- [ ] Rewrite BIOS, journey and routes for the domain; keep the part order.
- [ ] Before the second copy exists, move the structure check into the Hub as its single owner and have each repo import it from a pinned Hub commit — do not copy `test_readme_landing.py` repo to repo.
- [ ] Record the landing version (R*n*) and SHA in the footer.

## 5. Changes R1 → R2 (GEMINI)

| R1 (#49, 10 Nov) | R2 (13 Nov) |
|---|---|
| Purpose paragraph, then router | **At a glance** card with domain, EPICs, owner/decision authority, owns / does not own, snapshot |
| Status at 10 Nov; #50 absent | Snapshot at `main@737537b`; #50 protection gap, #44 decision packet, #53 dispatch *merged, not live* |
| Capability map without F02/F05 | Adds F02 policy, F05 probe, ecosystem dispatch |
| Drive folder labelled "portable BridgeFlow worktree" | Two folders separated as in the federation README: portable worktree vs BridgeFlow generic package |
| Kahn method text inline | Method text folded into `<details>`; numbers (20 nodes / 24 edges / 11 layers) stated |
| Quick start without runtime | Gating runtime Python 3.9 stated; landing test added |
| No structure guard | `tests/test_readme_landing.py` |
