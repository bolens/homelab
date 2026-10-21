# Maintenance state

- Configuration: selected profile, protected channel UUIDs/groups, quarantine age fourteen days, minimum three distinct failed days, recording filesystem identity, backup destination identity, monitoring integration.
- Health observations keyed by stable UUID: failed UTC dates, first failure, original group/profile membership, latest successful check. Duplicate same-day observations do not advance eligibility. Recovery clears failure state.
- Backup generation: timestamp, source image IDs, PostgreSQL dump, native Plex DB snapshots, file manifest, restore verification receipt. State is owner-only and outside Git.
- Health report: generated timestamp, mount/free-byte checks, stale source counts, failed-recording counts, backup verification age and maintenance outcome. No personal metadata.
