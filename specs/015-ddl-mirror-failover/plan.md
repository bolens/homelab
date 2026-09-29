# Implementation plan

Keep the native parser and configured mirror preference. Add `ddl_failover.py` and a checked, idempotent native adapter after existing discovery/queue adapters. Distinguish Main and Mirror labels. Persist retry history in existing DDL control state and priority/probe observations in the existing workflow journal.

Guard retry publication with the original record identity and existing workflow ownership locks. Use a conditional update, never an upsert, for retries. Reject changing a retry into multiple child records. Preserve existing catalog and pack identity. Replace only pending queue copies of the same release.

Extend scheduler priority and its displayed projection together. When selection has no eligible transfer, inspect one cooling release in projected order. Persist pacing before network I/O. Network lookups hold no global workflow lock. Cooldown-only misses retain the original record.

Tests cover native HTML parsing with synthetic content, concurrent removal/handoff, ordering, pause, budgets, restart, queue accounting and pacing. Run the isolated installed-image gate and repository validation. Independently review behavior/ownership and persistence/failure paths before merging. Publish GHCR and deploy only Mylar after downloads/imports drain and a verified application backup and isolated restore. Compare catalog and library baseline, verify protected service uptime, then remove operation backups. A verified concurrent normalizer conversion requires its own receipt/content proof; do not exempt arbitrary missing data.

Constitution: existing volume and authentication are sufficient. Compose, environment, preparation and ingress behavior are unchanged. README and module ownership describe behavior. No library file mutation is introduced by this feature.
