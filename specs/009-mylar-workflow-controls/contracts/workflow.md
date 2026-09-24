# Workflow interfaces

Existing application authentication protects Activity, Import problems and all
browser data. New mutations require POST plus a session-bound CSRF token. The
browser supplies identifiers and choices, never source paths or trusted labels.
Errors use fixed non-secret descriptions. Stale versions return a conflict.

- `activity`: linked page with status, settings, filtered history and handoff review.
- `workflowStatus`: bounded history, intake state, handoffs and scoped aliases.
- `workflowAction`: validated settings, request/reconcile handoff, confirm import
  selection, and disable alias. No action silently retries an uncertain dispatch.
- Existing `reportImportProblems` accepts optional `guidance` JSON with at most 50
  proposals. Existing problem rows may include a `source_token` and `version`.
- `workflowCommands`: primary-key API returns `commands` (at most 50 unresolved
  guided commands) and `aliases` (at most 200 enabled exact rules).
- `workflowAcknowledge`: primary-key API takes `command_id`, `phase` and optional
  fixed `reason`. Allowed phases: claimed, submitted, review, rejected, confirmed.
  Confirmed means verified source/library content equivalence, not merely Downloaded.
- Command fields: `id`, `source_token`, `version`, `issueid`, `comicid`, `save_alias`,
  `phase`. Alias fields: `id`, `series`, `year`, `comicid`, `enabled`.
- Proposal fields: `source_token`, `version`, `name`, `candidates`, `evidence`,
  optional `alias_scope` with `series` and `year`. Candidate fields: `issueid`,
  `comicid`, `title`, `year`, `number`, `status`, `agrees`, `conflicts`.

The updated Mylar image must precede the worker image. Unsupported guided API
capability must not erase existing maintenance state or claim import success.
