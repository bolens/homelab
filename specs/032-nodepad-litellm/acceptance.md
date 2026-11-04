# Acceptance evidence

Date: 2026-11-04. Scope: optional Nodepad LiteLLM provider. Live rollout paused
for a separate host maintenance window before the new image was deployed.

## Source and build checks

- Pinned upstream `5a6bad286c7cd2d57ccc5a1011991f8795f5dc80` accepts the complete
  patch sequence `0001` through `0008` in order.
- `verify-litellm.sh`: 16 tests pass, zero skips. Focused TypeScript checks and
  JavaScript syntax checks pass after applying the patches.
- A host production build succeeds with empty existing first-visit build
  overrides. A server-key canary is absent from `.next/static`.
- The built production route passes an isolated HTTP upstream fixture:
  filtered discovery, JSON completion, rejected foreign origin and rejected
  management path. No real credentials or notes enter that fixture.
- Full-tree TypeScript checking reports the existing `GraphAreaProps.workspaces`
  mismatch in `app/page.tsx`. The same error reproduces from the unchanged
  seven-patch baseline. The changed client and route files pass focused checking.
- Client fixtures preserve all four existing provider selections and stored
  settings without writes. A stale browser key or custom URL cannot alter the
  LiteLLM destination or authorization.

- Generated catalog and Pages output were refreshed from source. `make validate`
  passes. Its locked Markdown linter is unavailable and was explicitly skipped.
  Metadata audit reports the existing Asking and Harbor layout warnings.
- `git diff --check` and shell syntax checks pass.

## Operations

The existing ingress application protects the complete Nodepad hostname. Its
sole Allow policy includes an owner group containing five explicit email
identities. No ingress policy was changed. This is a prerequisite check, not
application-level authentication added by this feature.

The previous image, runtime configuration and empty first-visit build overrides
were recorded privately. Nodepad has no server-side note volume. Its original
container remains deployed. The new Docker build was cancelled during dependency
installation for the maintenance pause. No scoped Nodepad key has been deployed.

Do not resume live work until the maintenance window is released. Recapture the
actual container, image and mount state after restart before building or deploying.
The deployed image, real provider discovery and synthetic completion, browser
selection, final preservation checks and temporary resource cleanup remain open.
Private backups for the broader app connection operation remain retained until
its acceptance checks finish.
