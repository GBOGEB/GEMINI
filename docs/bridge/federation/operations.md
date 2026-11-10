# F02 operating procedure — read-only and guarded

## Validation

From the GEMINI repository root on Python 3.12+:

```bash
python -m src.federation_config
python -m unittest discover -s tests -p 'test_federation_config.py' -v
```

These verify inert config and Kahn DAG ordering only. No GitHub/Google tokens, Drive writes, branch pushes or PR admissions are performed.

## Source paths

- `config/federation/governed_broker.v1.json`: immutable demo policy, no live installation assertion.
- `src/federation_config.py`: fail-closed verifier, not a second scheduler.
- `tests/test_federation_config.py`: positive and negative tests.
- `.github/workflows/federation_config_tests.yml`: native Python 3.12/3.13 exact-head check.

## Recent reconciliation

As of 2026-11-10, R2-W2 PRs [#40](https://github.com/GBOGEB/GEMINI/pull/40) and [#41](https://github.com/GBOGEB/GEMINI/pull/41) were both observed MERGED. Do not rely on the 9 November open-draft overlap text as current state. Their source-level contract reconciliation, post-merge regression and the Hub admissions ledger require a separate audited comparison. This F02 policy branch deliberately does **not** rewrite `src/proposal_broker.py`.

The earlier F01 source-only branch was no longer present on 10 November. Its Markdown and Mermaid sources were found on main, but this does not by itself demonstrate all requested visual artifacts were rendered, regression-checked or merged through a reviewed PR.

## Still gated

Owner GitHub App installation and selected-repo grants; external WIF/Drive ACL, hosted HTTPS webhook and Drive writer; same-HEAD independent code review; hosted Drive-to-GitHub-to-Drive positive and negative end-to-end cases. No direct default-branch push or merge-on-red.
