# Data model

- Activity event: sequence, timestamp, issue/comic identifiers, display name,
  stage, provider category, fixed outcome/reason, optional next-retry timestamp.
  Maximum 5,000 events / 30 days. Paginated reads return at most 100.
- Handoff: opaque request ID, one issue and DDL record, created timestamp,
  queued/searching/dispatching/accepted/no-result/review phase. An unresolved issue
  reservation blocks competing dispatch. Unknown external outcomes remain review.
- Proposal: worker token (32 lowercase hex), version (64 lowercase hex), filename,
  up to eight candidate issues, up to six evidence labels, optional exact source
  series/year alias scope. Private source paths/digests stay worker-side.
- Import command: ID, proposal token/version, issue/comic IDs, save-alias flag and
  queued/claimed/submitted/review/rejected/confirmed phase. Replays are idempotent.
- Alias: ID, exact normalized source series and series-start year, target comic,
  enabled flag and originating confirmed command. No wildcard or yearless rules.
- Policy: validated automatic-handoff age, intake enabled/high/low watermarks and
  free-space stop/resume thresholds. Persist separately from native provider settings.
