# GitHub App and Google Drive Authentication Runbook

**Proposed GitHub App:** gbogeb-federation-broker. **Status:** suggested registration settings, NOT evidence that an installation or external authorization exists.

## Registration values (initial READ-ONLY stage)

| Form field | Safe selection |
|---|---|
| GitHub App name | gbogeb-federation-broker |
| Homepage URL | https://github.com/GBOGEB/GEMINI |
| Description | Scoped GBOGEB/GEMINI source federation and review broker |
| Redirect URI / user OAuth during installation / Device Flow | Leave blank / unchecked / unchecked |
| OAuth wildcard matching | Unchecked |
| Expire user authorization tokens | Keep enabled if shown |
| Setup URL / redirect on update | Blank / unchecked |
| Webhook Active | **OFF** until a deployed HTTPS receiver is tested |
| Webhook URL / secret | Blank while inactive, never invent values |
| Installable on | **Only on this account** |
| Install repository selection | **Only selected repositories**, initially GEMINI |

**Initial repository permissions:** Metadata read (implicit), Contents read, Pull requests read, Checks read, Actions read. Issues, Workflows, Administration, Organization, Account and Enterprise: no access. No write scopes until reviewed need. Defer webhook event subscriptions until a receiving service is available.

## Later authenticated PR-write stage (new approval)

Approve Contents Read & write and Pull requests Read & write on selected repositories only. Enable other write scopes solely for separately evidenced capabilities. The broker may create feature refs/draft PRs but must not push default branches or auto-merge; repo branch protections remain independently enforced.

GitHub App ID and Installation ID are identifiers, not secrets. The App's PRIVATE KEY belongs in a secrets manager, not Google Drive, Git, chat or handover packages. Installation access tokens must be short-lived and scoped. Human passkey login does not issue a GitHub App installation token.

## Webhook stage

Deploy a real HTTPS endpoint first, with request-body HMAC SHA-256 validation, duplicate delivery rejection and current-ref re-read. Only then activate the webhook and select relevant push, pull_request, pull_request_review, workflow_run and installation/repository-selection events. The webhook event is only a wakeup signal, never a Git head authority.

## Google Drive trust boundary

GitHub App installation grants **zero Google Drive rights**. Google requires separately approved OAuth or GitHub OIDC → Google WIF / service account with verified folder ACL. The existing GEMINI src/drive_ingress.py identity remains read-only. Drive publishing requires a different scoped identity, immutable snapshot policy, version conflict checks and a documented consent record.

## Verification checklist

1. Check actual App installation identity and repository selection, never infer from a form screenshot.
2. Verify read-only GitHub and Drive census using observed SHAs and Drive revision identifiers.
3. Test absent/revoked token, wrong repo, stale ref, duplicate event, invalid HMAC and forbidden path.
4. Perform reviewed permission escalation only after native CI/negative controls and an authorized operator.
5. Record exact-head checks and independent review before any authorized merge. Never call synthetic receipts VERIFIED.