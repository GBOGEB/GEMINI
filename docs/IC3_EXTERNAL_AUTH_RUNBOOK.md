# GM-I-C IC3 External Auth Runbook

## Purpose

This runbook closes the external configuration boundary for `GM-I-C / IC3_AUTH` without introducing a long-lived Google credential into GitHub.

The implemented runtime chain is:

```text
GitHub Actions job
  -> GitHub OIDC identity token
  -> Google Workload Identity Federation provider
  -> dedicated Google service account impersonation
  -> short-lived Google OAuth access token
  -> Google Drive API with drive.readonly
  -> configured handover root
```

GitHub authentication is **not** Google Drive authorization. The GitHub runner obtains an OIDC assertion from GitHub; Google WIF decides whether to trust that assertion and mint a short-lived Google access token for the configured service account. Google Drive then authorizes that service account against the folder ACL.

No service-account JSON key, OAuth refresh token, or other long-lived Google credential is required or permitted in the repository.

## Frozen implementation identity

- repository: `GBOGEB/GEMINI`
- hardened implementation merge: `cd68e0c68d882d4fe37417f7a1c1ca45dff0a3ab`
- workflow: `.github/workflows/drive_ingress.yml`
- Drive root ID: `1FnbajqBiIjL6Y4-_7tE1D515fNWvHsu3`
- Drive root title: `GEMINI_QPS_HANDOVER_2026-09-17`
- positive-enumeration control child currently present: `00_CONTROL`
- issue owner for external setup: `GBOGEB/GEMINI#12`

## External configuration

### 1. Google Cloud project

Use a governed Google Cloud project and enable the Google Drive API.

### 2. Workload Identity Pool and provider

Create or select a Workload Identity Pool and GitHub OIDC provider.

Restrict the provider to the intended repository and workflow/ref claims. The trust boundary should admit `GBOGEB/GEMINI`, not the entire GitHub organization by default.

The resulting provider resource name is stored in the GitHub repository variable:

`GCP_WORKLOAD_IDENTITY_PROVIDER`

Use the full provider resource name expected by `google-github-actions/auth@v3`.

### 3. Dedicated service account

Create or select a dedicated service account for Drive ingress. It is an authentication/resource principal, not a mission crew member and not a QPS authority.

Grant the federated GitHub principal `roles/iam.workloadIdentityUser` on this service account. Add only any extra token-creation permission that the selected WIF impersonation flow actually requires.

Store the service-account email in the GitHub repository variable:

`GCP_DRIVE_SERVICE_ACCOUNT`

### 4. Google Drive folder ACL

Share only the target handover folder with the dedicated service-account email as **Viewer**:

`1FnbajqBiIjL6Y4-_7tE1D515fNWvHsu3`

Do not widen the ACL to My Drive root or unrelated QPS material merely to make IC3 pass.

### 5. GitHub Actions permissions

The workflow already requests:

```yaml
permissions:
  contents: read
  id-token: write
```

`id-token: write` permits GitHub Actions to request its OIDC assertion. It does not itself grant Google or Drive access.

## Runtime proof

Dispatch `.github/workflows/drive_ingress.yml` from the governed post-merge implementation or a separately governed successor.

The workflow must execute more than zero steps and traverse all six proof layers:

1. `L0_CONFIG` — required repository variables are present.
2. `L1_IDENTITY` — GitHub OIDC -> Google WIF succeeds.
3. `L2_RESOURCE_AUTH` — a short-lived Google token with `drive.readonly` is minted for the dedicated service account.
4. `L3_RESOURCE_IDENTITY` — the configured Drive root resolves to the exact non-trashed folder identity.
5. `L4_GT0_WORK` — recursive census returns `total_items > 0`.
6. `L5_RECEIPT` — one artifact family binds run/job/SHA, census digest and PASS classification.

Required final status:

```json
{
  "result": "PASS",
  "classification": "IC3_DRIVE_READONLY_GT0_STEP_PASS"
}
```

The artifact family must include `drive_census.json` and `ic3_status.json`.

## Failure classification

Do not repair application code merely because the hosted proof is red. Use the emitted classification:

- `CONFIG_MISSING` — GitHub repository variables are absent.
- `OIDC_WIF_AUTH_FAILED` — GitHub OIDC/WIF trust or service-account impersonation failed.
- `GOOGLE_ACCESS_TOKEN_REJECTED` — a token was produced but rejected for the Google request.
- `DRIVE_API_FORBIDDEN` — Google Drive/API returned a forbidden response; inspect API enablement, token scope and ACL without assuming one cause.
- `DRIVE_API_UNAVAILABLE` — Drive API unavailable/transient class.
- `ROOT_INACCESSIBLE_OR_MISSING` — configured root cannot be resolved.
- `ROOT_TRASHED` / `ROOT_TRASHED_STATE_UNPROVEN` — root lifecycle state is unacceptable or not proven.
- `ROOT_NOT_FOLDER` — configured object is not the expected folder type.
- `ROOT_ID_MISMATCH` — returned object identity differs from the configured root.
- `CENSUS_ZERO_ITEMS` — root is readable but no positive child enumeration was proven.
- zero-step / `steps=null` — infrastructure or runner-admission evidence, not an application defect.

## Non-compensation

The following are not IC3 PASS:

- merge of the hardened implementation;
- unit-test PASS;
- a manual ChatGPT Google Drive connector read;
- a readable but empty Drive root;
- a GitHub token by itself;
- a successful Google authentication that never performs a positive Drive census.

`authority_transfer=false`. No engineering, release, procurement, QPS or runtime-GOLD credit is created by IC3.

## Next gate after IC3

Only after the real hosted IC3 PASS is bound should GM-I-C advance to the independent consumer receipt for `IC4_CONSUMER_A`.
