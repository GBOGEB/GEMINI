# Drive ingress via GitHub OIDC -> Google Workload Identity Federation

This repository uses a read-only trust path for unattended Google Drive census jobs.

## Trust chain

```text
GitHub Actions run
  -> GitHub OIDC token
  -> Google Workload Identity Provider
  -> Google service account impersonation
  -> short-lived OAuth access token
  -> Google Drive API (drive.readonly)
```

The GitHub `GITHUB_TOKEN` is not a Google credential. GitHub only supplies the OIDC assertion used by Google to mint a separate short-lived Google token.

## Repository variables

Configure these GitHub Actions repository variables:

- `GCP_WORKLOAD_IDENTITY_PROVIDER`
  - Full provider name, for example:
    `projects/123456789/locations/global/workloadIdentityPools/github/providers/gemini-repo`
- `GCP_DRIVE_SERVICE_ACCOUNT`
  - Service account email used by the workflow, for example:
    `gemini-drive-reader@example-project.iam.gserviceaccount.com`

No long-lived Google service-account key is required or expected.

## Google-side requirements

1. Create or select a Google Cloud project.
2. Enable the IAM Credentials API and Google Drive API.
3. Create a Workload Identity Pool and OIDC provider for GitHub.
4. Restrict provider admission at minimum to repository `GBOGEB/GEMINI`.
5. Grant the GitHub principal permission to impersonate the dedicated Drive-reader service account (`roles/iam.workloadIdentityUser`).
6. Share the Drive handover folder directly with the service-account email as Viewer, unless a Workspace-approved impersonation model is intentionally used.

The current configured Drive handover folder is:

- title: `GEMINI_QPS_HANDOVER_2026-09-17`
- folder ID: `1FnbajqBiIjL6Y4-_7tE1D515fNWvHsu3`

Sharing the folder is essential: Google Cloud IAM permission does not itself grant a service account visibility into a user's My Drive content.

## Workflow behavior

`.github/workflows/drive_ingress.yml`:

- runs manually and every 6 hours;
- requests only `https://www.googleapis.com/auth/drive.readonly`;
- recursively lists metadata under the handover folder;
- downloads no document contents;
- writes no Drive objects;
- generates `output/drive_ingress/drive_census.json`;
- uploads that JSON as a GitHub Actions artifact;
- does not commit generated state back into the repository.

## Receipt semantics

The census digest is a SHA-256 of canonical Drive identity metadata. It detects changes in file membership, IDs, paths, MIME types, versions, timestamps, sizes, and available checksums.

For native Google Docs/Sheets/Slides, Drive does not expose a byte SHA-256 for the live native object. Their Drive `version` and modification identity are therefore recorded explicitly instead of pretending they are content hashes.

## Next gate

After a successful hosted census with a real Google identity and shared folder, the next governed slice is:

```text
CENSUS PASS
 -> package classifier (GMI-* / RAW / HANDOVER / MANIFEST / ARTIFACTS)
 -> selective content export/download
 -> byte SHA-256 where export bytes exist
 -> previous-census comparison
 -> NEW | CHANGED | UNCHANGED | MISSING
 -> ACCEPT | REJECT | DEFER reconciliation receipt
```

Do not add automatic Drive writes or automatic commits before this read-only hosted proof is observed.
