# Authentication and API model

The bridge has three independent trust domains. Do not conflate their credentials.

## 1. Gemini model/CLI authentication

Gemini CLI supports Google account sign-in, `GEMINI_API_KEY`, and Vertex AI authentication. These credentials authorize Gemini model usage; they do not automatically grant Google Drive access or GitHub repository access.

## 2. Google Drive API authentication

Programmatic Drive access requires Google OAuth/IAM authorization with Drive scopes appropriate to the operation. For local interactive use this is commonly a user OAuth flow; for CI, prefer a short-lived federated identity where feasible.

### GitHub Actions -> Google

Preferred pattern: GitHub Actions OIDC -> Google Workload Identity Federation (WIF) -> optionally impersonated Google service account -> short-lived OAuth access token -> Google API.

This uses GitHub as the external identity issuer, but **GitHub authentication itself is not a Google Drive credential**. Google Cloud must explicitly trust the GitHub OIDC identity through a Workload Identity Provider and IAM binding.

For Drive operations on a user's My Drive, a service account cannot magically see user files. The file/folder must be shared with the service-account principal, or an approved user-delegation/domain-wide-delegation design must be used in a Workspace domain. Use least privilege.

Avoid long-lived service-account JSON keys when WIF is available.

## 3. GitHub authentication

Inside GitHub Actions, `GITHUB_TOKEN` authorizes repository/API actions according to workflow permissions. It does not authorize Google APIs.

For local Gemini CLI -> GitHub operations, use a separately authenticated GitHub mechanism such as GitHub CLI/OAuth or another approved GitHub token/credential provider. Do not commit tokens.

## Cross-API flow

```text
GitHub Actions job
  -> GitHub OIDC assertion (short-lived)
  -> Google Workload Identity Provider validates repository/ref/actor claims
  -> Google federated credential / service-account impersonation
  -> OAuth 2.0 access token with explicit Google API scopes
  -> Google Drive API
```

This is a trust federation, not token reuse. A GitHub token is never sent as a Drive bearer token.

## Recommended bridge controls

- Restrict WIF provider admission by `repository` and preferably branch/environment.
- Grant only the Google IAM permissions needed to mint the intended access token.
- Request the narrowest Drive OAuth scope compatible with the bridge operation.
- Share only the dedicated handover folder with the automation principal when possible.
- Keep GitHub `id-token: write` limited to the job that needs Google federation.
- Keep `contents: read` for ingestion jobs; use separate review-bound jobs for repository writes.
- Never persist access tokens in receipts; store only issuer, subject/audience metadata, operation IDs, and non-secret hashes.
