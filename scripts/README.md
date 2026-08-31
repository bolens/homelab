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
Run `make hooks-install` to enable staged secret scanning, actionlint, zizmor,
Hadolint, dependency configuration, repository validation, and whitespace
checks. Run `make ci-local` for the all-files hooks plus a full-history
Gitleaks scan.

## Onboarding and validation

| Helper | Purpose |
|---|---|
| `homelab-doctor.sh` | Checks prerequisites, Docker access, sensitive-file tracking, and Compose YAML. Add repeatable `--network NAME` / `--mount PATH` checks, or set `HOMELAB_EXPECTED_NETWORKS` / `HOMELAB_MOUNT_PATHS`. Does not create or change anything. |
| `validate-repo.sh` | Compiles Python helpers; parses Compose; audits preparation, metadata, examples, links and anchors, generated docs, and tracked-file integrity; then runs YAML, Markdown, and shell lint when available. Pass `--strict` to require every lint tool. |
| `validate-dependency-config.py` | Parses Dependabot and Renovate configuration and catches unsupported ecosystem options before GitHub parses them. |
| `ci-parse-composes.py` | PyYAML parser used by local validation and CI. |
| `validate-compose-config.py` | Runs `docker compose config` against portable example environments and skips explicitly generated include bundles. |
| `audit-prepare-scripts.py` | Verifies every top-level Compose stack has an executable, verbose wrapper that prepares its examples and literal external networks/volumes. Maintainers may use `--fix`, then review the complete diff. |
| `audit-stack-metadata.py` | Validates `stack.yaml` coverage, schema shape, names, profile enums, and ports. Maintainers may use `--fix-missing`, then review inferred catalog fields. |
| `audit-repo-hygiene.py` | Checks README/example/metadata coverage, ignored runtime env files, portable examples, every tracked Markdown link, root CI/config syntax, and Caddy upstream basics. |
| `build-stack-catalog.py` | Regenerates `documents/STACK-CATALOG.md` from stack READMEs. |
| `build-topology.py` | Regenerates the topology inventory and architecture links in `documents/TOPOLOGY.md` from `documents/topology.yaml`. Requires PyYAML. The diagram source is `documents/topology.architecture.json`. |
| `validate-topology-artifacts.py` | Checks the Archify source graph, rendered HTML, dark PNG preview, topology links, and Mermaid removal. |
| `scan-secrets-gitleaks.sh [git\|dir]` | Scans full Git history (default) or files on disk. The `dir` mode includes ignored runtime secrets, so output must be handled carefully. |

## Stack preparation

Most stacks provide `stacks/<name>/prepare-stack.sh`. Run it before editing
`stack.env`: it copies examples without overwriting existing runtime config,
creates required directories/networks where supported, and synchronizes
`stack.env` to Compose's `.env`. It reports variable names and Caddy hostnames
that still look unfinished, but never prints secret values. Re-run it after
changing `stack.env`.

| Helper | Purpose |
|---|---|
| `prepare-stack-lib.sh` | Shared implementation used by stack preparation wrappers. Source it; do not execute it directly. |
| `prepare-stack.examples/` | Maintainer patterns for new preparation wrappers. |
| `upgrade-prepare-stack-verbose.py` | Maintainer utility that regenerates compatible wrappers after library changes, then applies the preparation audit fixer. Review its diff before committing. |
| `sync-compose-shared-env.py` | Maintainer migration for adding optional root `shared.env` references to Compose files. Review its diff before committing. |
| `sync-stack-env.py` | Previews or appends keys missing from private `stack.env`; preserves existing values and generates placeholder secrets without printing them. |

## Operations and troubleshooting

| Helper | Purpose |
|---|---|
| `apply-running-resource-limits.sh` | Previews fallback runtime limits. Applying requires both `--container NAME` and `--apply`; prefer persistent per-stack Compose limits. |
| `find-apache2-containers.sh` | Maps running host Apache processes to Docker containers. |
| `list-layout.sh` | Summarizes the repository layout. |
| `migrate-docker-volume-to-path.sh` | Copies a named volume to a bind path. Stop the affected stack first. |
| `sync-local-hosts.sh` | Maintains explicitly configured local hostname entries. Read its help before use. |
| `sync-gitea-from-github.sh` | Safely fast-forwards Gitea from authoritative GitHub and mirrors tags; refuses divergent history. |
| `sync-gitea-mirrors.sh` | Public template for the ignored, host-specific `sync-gitea-mirrors.local.sh` repository list. |
| `push-github-mirror.sh` | Compatibility wrapper for `sync-gitea-from-github.sh`. |
| `pre-commit-*.sh` | Focused wrappers for staged Gitleaks, Hadolint, and zizmor checks. |
| `sort-caddyfile.py` | Sorts generated Caddy hostname blocks while preserving the file preamble. |
| `patch-caddy-h1-transport.py` | Maintainer migration for adding HTTP/1.1 transport settings to selected Caddy proxies. |

## Monitoring

| Helper | Purpose |
|---|---|
| `validate-monitoring-config.sh` | Validates Prometheus, Alertmanager, Loki, Promtail, Alloy, Blackbox Exporter, and related configuration. |
| `monitoring-smoke-check.sh` | Checks Prometheus jobs/rules, Alertmanager readiness, and important Loki queries. |
| `sync-blackbox-targets-from-monitoring.py` | Rebuilds non-alerting Blackbox target groups from the monitoring target inventory. |

Use `make help` for the supported validation and monitoring workflows. For the
end-to-end setup sequence, see
[Getting started](../documents/GETTING-STARTED.md).
