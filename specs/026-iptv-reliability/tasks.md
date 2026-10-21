# Tasks: IPTV reliability and recovery

## Setup and preservation

- [x] T001 Record scope and source contracts in specs/026-iptv-reliability/spec.md and plan.md.
- [x] T002 Restore-verify native application snapshots in private operational state before live mutation.

## US1 - Viewing and guide data

- [x] T003 [US1] Change Plex to matching profile XMLTV while preserving DVR/device/rules; document in stacks/dispatcharr/README.md.
- [x] T004 [US1] Add verified exact local FAST guide matches; record source evidence in specs/026-iptv-reliability/validation.md.
- [x] T005 [US1] Link tested equivalent backup streams and demonstrate isolated failover; record bounded evidence in specs/026-iptv-reliability/validation.md.

## US2 - Maintenance and recording defaults

- [x] T006 [US2] Implement and fixture-test dated quarantine/recovery policy in stacks/dispatcharr/maintenance/.
- [x] T007 [US2] Disable immediate deletion and deploy protected maintenance schedule; document in stacks/dispatcharr/README.md.
- [x] T008 [US2] Configure future Plex recording defaults with markers, padding and bounded retention; document preserved rules in specs/026-iptv-reliability/validation.md.

## US3 - Recovery and health

- [x] T009 [US3] Implement verified recurring backups and health checks in stacks/dispatcharr/maintenance/.
- [x] T010 [US3] Verify existing Restic coverage, restore a new generation and activate timers/monitoring; record evidence in specs/026-iptv-reliability/validation.md.

## Validation and delivery

- [x] T011 Update affected public contracts and regenerate catalog from stacks/dispatcharr/README.md and stack.yaml.
- [x] T012 Run focused fixtures and make validate; verify original live records and clean operation-created temporary copies; record specs/026-iptv-reliability/validation.md.

## Dependencies and execution

T001 → T002 → T003/T004/T005/T006/T008/T009 → T007/T010 → T011 → T012. Public guide and backup-stream research can run independently against upstream sources. Live writes remain serialized. Deliver the matching guide first, then maintenance and recovery controls.

## Supplemental guide and organization follow-up

- [x] T013 Check additional free guide sources, apply reviewed current matches and report remaining gaps.
- [x] T014 Correct channel categories/names and configure browsing order while preserving numbers, profiles and rules.
- [x] T015 Repair Plex blank channel labels by verifying export names and client-reachable logo addresses, preserving DVR identities and mappings.

## Authorized Multiview follow-up

- [x] T016 Install official Multiview, configure a bounded news mosaic, verify audio/video and resource use, then expose the tested channel through Plex without new public listeners.
- [x] T017 Install Clapparr and configure metadata sidecars for Dispatcharr DVR without touching unrelated media; install Twitcharr for the operator to configure.

## City and network matrix expansion

- [x] T018 Verify a current recovery generation and preservation baseline; research and decode the six-city/four-network feed matrix.
- [x] T019 Add missing verified standalone stations, per-city mosaics in NBC/ABC/CBS/FOX order, and per-network mosaics; preserve the existing four-city layout and standalone channels.
- [x] T020 Verify every admitted mosaic, resource use, original records/mappings, complete Plex activation and final recovery generation; document real gaps and clean only temporary operation copies.

- [x] T021 Research local PBS member stations for all six markets, add verified available feeds to standalone and city/network layouts, and retest changed mosaics without relabeling other markets or bypassing geographic restrictions.

- [x] T022 Apply and document a version-guarded Multiview 0.5.0 clock-discontinuity fix after source tracing found that forward timestamp jumps can leave decoded video queued in the future; verify real mosaic output before accepting it.

- [x] T023 Add an opt-in public-HLS remux bridge after a directly decoded Streamlink source failed the proxy's TS input contract; verify actual MPEG-TS output and child-process cleanup through the existing profile.

## Explicit channel-number organization follow-up

- [x] T024 Back up and restore-verify current Dispatcharr/Plex state, coordinate concurrent lineup writers, then order Library TV first, mosaics second, local news by city/network preference, national news and remaining genres. Preserve station identities, source numbers, streams, EPG bindings, memberships and recording rules. Verify the full tuner/XMLTV/Plex mapping and record acceptance evidence.

## Library overlap follow-up

- [x] T025 Compare active IPTV with existing scheduled ErsatzTV coverage and available library series, restore-verify affected state, disable reviewed duplicate memberships in the Plex export, preserve recoverable alternatives and multiview inputs, and verify the complete tuner/XMLTV/Plex set and existing records.

- [x] T026 Coordinate the artwork writer, restore-verify ErsatzTV state, add dedicated library-backed Portlandia and Teenage Mutant Ninja Turtles replacement stations without changing existing stations, then verify schedules, Dispatcharr/Plex mapping, playback and preservation.

- [x] T027 Restore-verify current Dispatcharr/Plex state, hide four explicitly approved genre-overlap feeds while retaining protected alternatives, preserve the full remaining Plex mapping and report specific gaps from current listings against the library.

- [x] T028 Diagnose blank custom-program cards in Plex hubs, add an opt-in private guide and public image bridge with guarded startup configuration and strict ingress paths, restore-verify state before deployment, preserve lineup identities and recording rules, and verify movie/episode poster bytes and visible cards without speculative classification changes.
