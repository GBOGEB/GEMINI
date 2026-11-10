# GM-I-C W2 historical wire corpus (P0007)

**Purpose:** an independent, reproducible synthetic fixture corpus derived from the source shape in [merged PR #41](https://github.com/GBOGEB/GEMINI/pull/41) versus [merged PR #40](https://github.com/GBOGEB/GEMINI/pull/40), without introducing a second broker or migrating historical inputs. The exact fixture bytes in `tests/fixtures/gmi_wire/` are **test-generated representations**, not recovered owner-signed historical packages. The source head SHAs are retained in `SOURCE_RECEIPT.json`.

- `historical_41.json` uses `proposal_profile: {schema,repository,base_sha,head_sha,changes}` and a `modify` action. The canonical broker rejects it via `AMBIGUOUS_LEGACY_PROFILE` *before reading an artifact*.
- `canonical_40.json` uses `profile: gmi.proposal_profile.v1` plus `proposal: {repo,base_sha,intent,changes}` with `replace` + `artifact_ref`. Production `parse_profile` accepts this fixture and opens the bounded fixture artifact.
- A mixed manifest carrying both markers must fail closed. Manifest digest identity remains stable under map-key reorder, but historical and canonical shapes have **different digests**.
- Two manifest contents that reuse one `session_id` with changed intent have different digests; this **does not** determine whether `CHANGED` replay/supersession is authorized or safe.

## Owner decisions necessary for B09/B26

1. Explicitly accept canonical #40 v1 + permanent fail-closed historical #41 input, **or** authorize an independently versioned and reviewed conversion. Never silently convert the v1 marker in place.
2. Decide whether changed digest under identical session is `CHANGED` with bounded supersession or REJECT pending a distinct session ID, including replay, stale-head and ledger-locking semantics. The tests above show identity differences, **not permission**.
3. Bind one owner-approved wire/version contract to the observed exact-source native W1 snapshot, W2 corpus, GEMINI main protection and independent review. Record the source evidence in issue #44 and the Hub B09/B26 ledger.

The fixture set is intentionally standalone and must not alter `src/proposal_broker.py`, `src/handover_batch.py`, Google Drive ACL, GitHub protection or any default branch. `formal_credit_delta=0`, `authority_transfer=false`, `hosted_IC3=false`, `merge_admission=HOLD`.