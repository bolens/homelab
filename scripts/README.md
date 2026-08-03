# Homelab scripts

Repository helpers are safe to run from any directory unless their help text
says otherwise. Start with:

```bash
make doctor
make validate
make help
```

The doctor and validation commands are read-only. Scripts that change live
containers or files require an explicit action or clearly describe the change.

## Onboarding and validation

| Helper | Purpose |
|---|---|
| `homelab-doctor.sh` | Checks prerequisites, Docker access, shared networks, sensitive-file tracking, Compose YAML, and known media mounts. Does not create or change anything. |
| `validate-repo.sh` | Compiles Python helpers, parses every top-level Compose file, and runs ShellCheck when available. |
| `ci-parse-composes.py` | PyYAML parser used by local validation and CI. |
| `scan-secrets-gitleaks.sh [git\|dir]` | Scans full Git history (default) or files on disk. The `dir` mode includes ignored runtime secrets, so output must be handled carefully. |

## Stack preparation

Most stacks provide `stacks/<name>/prepare-stack.sh`. Run it before editing
`stack.env`: it copies examples without overwriting existing runtime config,
creates required directories/networks where supported, and synchronizes
`stack.env` to Compose's `.env`. Re-run it after changing `stack.env`.

| Helper | Purpose |
|---|---|
| `prepare-stack-lib.sh` | Shared implementation used by stack preparation wrappers. Source it; do not execute it directly. |
| `prepare-stack.examples/` | Maintainer patterns for new preparation wrappers. |
| `upgrade-prepare-stack-verbose.py` | Maintainer utility that regenerates compatible wrappers after library changes. Review its diff before committing. |
| `sync-compose-shared-env.py` | Maintainer migration for adding optional root `shared.env` references to Compose files. Review its diff before committing. |

## Operations and troubleshooting

| Helper | Purpose |
|---|---|
| `apply-running-resource-limits.sh` | Previews fallback runtime limits. Applying requires both `--container NAME` and `--apply`; prefer persistent per-stack Compose limits. |
| `find_apache2_containers.sh` | Maps running host Apache processes to Docker containers. |
| `list-layout.sh` | Summarizes the repository layout. |
| `migrate-docker-volume-to-path.sh` | Copies a named volume to a bind path. Stop the affected stack first. |
| `sync-local-hosts.sh` | Maintains explicitly configured local hostname entries. Read its help before use. |
| `push-github-mirror.sh` | Pushes a branch to `origin` and optional `github` mirror. |

## Monitoring

| Helper | Purpose |
|---|---|
| `validate-monitoring-config.sh` | Validates Prometheus, Alertmanager, Loki, Promtail, Alloy, Blackbox Exporter, and related configuration. |
| `monitoring-smoke-check.sh` | Checks Prometheus jobs/rules, Alertmanager readiness, and important Loki queries. |
| `sync_blackbox_targets_from_monitoring.py` | Rebuilds non-alerting Blackbox target groups from the monitoring target inventory. |

Use `make help` for the supported validation and monitoring workflows. For the
end-to-end setup sequence, see
[Getting started](../documents/GETTING-STARTED.md).
