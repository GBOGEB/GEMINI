# GM-I-C R2-W2 post-merge legacy preflight hardening — 10 November 2026

**Owner:** GBOGEB/GEMINI, canonical `src/proposal_broker.py` · **Tracked:** issue #44 · **Predecessor:** merged PR #46.

CODEX post-merge review identified two independent exposure paths in the negative legacy-profile boundary. A historical `proposal_profile` could be loaded and hashed by `validate_package` or `build_batch_census` **before** it was rejected, and a manifest replaced/deleted after census could throw instead of classifying a rejected package.

This repair does **not** add an alternative broker or legacy converter. `_preflight_legacy_package` reads the manifest **without** opening change artifacts and invokes the existing `_reject_legacy_profile_marker`. It runs ahead of validation in one-package evaluation and ahead of batch census. The existing generic package validator still classifies malformed manifests. A second manifest read after census catches `BrokerError`, `OSError`, `TypeError`, `ValueError`, and `yaml.YAMLError` as an explicit rejected row; the accepted ledger is not advanced.

The new test cases assert: no artifact validation on a historical marker; no census on a historical marker; malformed YAML still rejected through the canonical contract; manifest disappearance after census yields `BROKER_MANIFEST_RACE` rather than aborting ingestion. Original collision tests, canonical/DEFER/UNCHANGED semantics, and repo integration checks must all remain green.

The source remains **offline dry-run only**. No GitHub push by broker, no Drive authentication, no IC3 success, no engineering authority, and no automatic merge. Exact-head independent security/code review and native CI are necessary for admission.
