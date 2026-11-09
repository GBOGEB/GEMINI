# R2-W2 merge lineage and legacy profile collision guard

**Owner:** GEMINI broker (`src/proposal_broker.py`) · **Issue:** GBOGEB/GEMINI#44 · **Classification:** negative compatibility contract, not a version migration.

Two implementations were merged into `main`: #41 (merge `5abe214ee343af457bf9dc32aa4a915f2298036a`) and then #40 (merge `3ee30f9364c2f45687b83ad2f2b642ccf6a9b4b4`). #41 accepted `proposal_profile: {schema,repository,base_sha,head_sha,changes}`. #40 owns the later canonical wire shape: `profile: gmi.proposal_profile.v1` plus `proposal: {repo,base_sha,intent,changes}`.

The shapes are incompatible but used the same `gmi.proposal_profile.v1` identity. Normal package validation allows unrelated top-level metadata; the broker therefore needs a narrow **fail-closed boundary** for `proposal_profile` specifically. If the legacy key is present, with or without the canonical fields, reject with `AMBIGUOUS_LEGACY_PROFILE` before reading change artifacts, building a patch, dispatching, or mutating the ledger. Other unrelated top-level provenance fields remain permitted.

This guard is not an automatic converter. The original legacy package bytes remain evidence and should be quarantined, not silently treated as a new proposal. Any future conversion needs a distinct versioned adapter, explicit owner approval, sha-bound original and converted artifact receipts, idempotency semantics, and positive/negative round-trip fixtures.

**DoD/DoV:** dedicated 8-case boundary suite; existing broker suite remains green; current exact-head workflow successful; independent review of the implementation and governance admission. A green local suite or exact-head CI is not an IC3 hosted authentication pass or engineering authority transfer.
