# Implementation plan

## Ownership
Maintain stacks/ersatztv contracts. Reuse existing Dispatcharr/Plex contracts without overwriting unrelated checkout changes. Generate catalog and site output through owning generators.

## Constitution checks
Portable placeholder examples; explicit public authentication; read-only media; no host-published ports by default; version and digest pin; complete persistent configuration backup; idempotent preparation; bounded resource and log limits.

## Design
Use maintained ErsatzTV Legacy release with private ingress-admin connectivity to Dispatcharr and Caddy. Validate upstream authentication and image runtime before selecting healthcheck. Restrict public management origin to the connector and configure Access before publishing DNS. Keep playlist/guide URLs private. Capture application baselines and verified restores before integration writes.

## Acceptance evidence
Record runtime and private receipts outside Git. Verify mount source, health, anonymous denial, library scan, channel schedule, guide mapping and playback. Validate public examples in isolated fixtures, regenerate output, and run make validate. Report unavailable client playback separately.

## Programming and presentation additions

Use native classic scheduling features for balanced show batches, filler presets,
intermittent channel-logo watermarks and alternate calendar schedules. Keep
Morning Cartoons episodes-only and keep both nighttime stations free of IDs and
overlays. Generate short silent IDs from existing artwork in the configuration
volume and scan them as a separate local Other Videos path; do not write to the
media library. Reuse the reviewed seasonal Smart Collections for Movie Night
weekends, adding an outer movie-only boundary where necessary. Preserve existing
channel numbers, source rules, collection identities and downstream DVR mappings.
Verify the changed schedule on a disconnected application restore before live
installation, then compare native guide entries, downstream programmes, source
identities and actual video/audio playback. Calendar fixtures must cover active
and inactive dates and transitions; retain the configured UTC schedule timezone.

## Integration reliability additions

Extend the existing opt-in Dispatcharr host runner with an optional ErsatzTV
module. Store deployment-specific recipes and credentials outside Git; public
examples contain placeholders. Routine checks compare current programme fields
across native XMLTV, Dispatcharr and Plex without mutation. Export fixed numeric
metrics for correctness, content restrictions, recipe drift and guide coverage.
Filter reconciliation is a separate explicit command with expected-source checks,
dry-run default, active-viewer/recording guards and no automatic full reset.
Generate seasonal derived rules from their owning recipes.

Back up SQLite through its online backup API and capture required stable assets
with before/after hash checks. Exclude rebuildable index, guide/Next caches and
logs; verify the isolated application can rebuild the omitted index. Existing
backup generations remain protected on any failure. Enable Next loudness and
forced English subtitle burn-in after representative isolated playback tests.
Use a rolling seven-day horizon and remove daily reset times; append through the
native scheduler and prove every prior future programme is unchanged. Preserve
all station identities, media, mappings, recording rules and runtime deployment
settings. Run transition/concurrency probes without stopping user sessions.


### Network and library-only rollout

Capture definitions and complete row/mapping baselines, then verify a fresh
application-consistent backup through isolated restores. Evaluate proposed
filters against a stable copy of the native index and exercise the native SQL
change on a disposable database. Preserve source station identities and apply
only reviewed output-number, grouping, curation and artwork changes. Build only
new or deliberately changed playouts. Use native show-group rotation for series.

Retain IPTV records with hidden output and disabled memberships/source polling.
Store their exact prior flags and mappings privately under normal backup
coverage. Add a boolean host-maintenance quarantine pause with regression proof
that it neither calls the mutation adapter nor rewrites history. Submit the
complete Plex mapping with the intended custom-only enabled set. If Plex drops
bindings absent from the tuner, compare the remaining custom bindings exactly
and verify every prior IPTV binding in the backed-up restoration manifest. Prove
actual guide, logo, playback and persistence behavior.
