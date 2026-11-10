# GM-I-C post-merge P4 native failure — classified preflight rows

**Date:** 10 November 2026. **Source branch:** GEMINI `main@e991d55d40b0f624f2df4539829e8d6e409d7cbf`. **Owner:** `src/proposal_broker.py`. **Issue:** #44.

After the concurrent merge of #51 (merge `ea3f55d502d5b3499fabe95db1437cb186bd51b0`), native negative workflow `42858449023` reported **56 passed, 1 failed**: `test_same_digest_legacy_package_cannot_be_accepted_as_brokered` expected a package-level rejected row, but early pre-census quarantine returned an empty `packages` list. This is an output/receipt contract regression, not proof that legacy content passed.

The repair keeps the important pre-hash quarantine and returns a **minimal, explicitly rejected package-level row** for every legacy manifest observed before census. Each row preserves `package`, a folder-derived unverified `session_id`, `REJECT` action/verdict, `AMBIGUOUS_LEGACY_PROFILE` reason, no patch and no branch plan. The prior ledger remains unchanged. This ensures consumers can display/deduplicate rejected packages without reading their artifact bytes. Multiple legacy packages are tested; no GitHub or Drive dispatch is performed by the broker.

DOV: negative workflow, canonical broker suite and BLSN matrix must all pass at the exact new head; independently review quarantine semantics and required merge protections. **Historical #51 was merged despite the subsequently failing negative workflow; retain that discrepancy in the governance ledger.** No automatic merge or IC3 authority transfer.
