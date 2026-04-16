# Backup & restore runbook 💾

Operational guide for `asking-ng` Postgres data protection in homelab/self-hosted setups.

## Scope

- Primary data: Postgres volume used by `asking-ng` API (`polls`, `votes`, users, audit logs).
- This runbook assumes Docker Compose deployment from this repository.

## Recovery objectives (recommended defaults)

- **RPO target**: <= 24h for basic setups (daily dump); <= 1h for tighter setups (hourly dump).
- **RTO target**: <= 60 min for single-node restores.

Adjust to your risk tolerance and storage budget.

## Backup methods

### A) Volume-level snapshot (fast full restore)

- Stop write traffic if possible (maintenance window preferred).
- Snapshot the Docker volume/filesystem containing Postgres data.
- Label snapshots with UTC timestamp and stack name.

### B) Logical dump (portable, easiest off-site copy)

Use `pg_dump` from host or container:

`docker exec <postgres-container> pg_dump -U <user> -d <db> -Fc > backup-asking-ng-$(date -u +%Y%m%dT%H%M%SZ).dump`

Recommended cadence:

- Daily for low-churn environments.
- Hourly for active/community-facing streams.

## Retention policy (example)

- Keep last 7 daily backups.
- Keep last 4 weekly backups.
- Keep last 3 monthly backups.
- Store at least one copy off-host/off-site.

## Restore drill (test regularly)

1. Create isolated restore environment (separate compose project/network).
2. Restore latest backup into a fresh Postgres instance:
   - Logical: `pg_restore -U <user> -d <db> --clean --if-exists backup.dump`
   - Snapshot: mount restored volume.
3. Start API against restored DB.
4. Validate:
   - `GET /ready` returns healthy.
   - Poll list loads.
   - New vote can be cast.
   - Admin audit logs still query.
5. Record elapsed restore time and issues.

Run at least monthly.

## Verification checks after production restore

- Confirm expected row counts for `polls`, `votes`, `audit_logs`.
- Spot-check newest polls and moderation actions.
- Confirm WebSocket updates and exports still function.
- Rotate sensitive credentials if compromise is suspected.

## Automation hooks (optional)

- Add cron/systemd timer invoking `pg_dump`.
- Upload encrypted backups to object storage/NAS.
- Emit backup success/failure into your monitoring stack.

## Incident notes template

- Incident start (UTC):
- Backup used (timestamp + type):
- Restore completed (UTC):
- RPO achieved:
- RTO achieved:
- Follow-up actions:
