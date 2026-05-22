# Docker Scripts

This directory contains utility scripts for managing and troubleshooting Docker containers and services in this homelab setup.

## Scripts

- **prepare-stack-lib.sh**: Shared verbose helpers for `stacks/*/prepare-stack.sh` (env and Caddy snippet copies). On `prepare_stack_end`, copies `stack.env` → `.env` so Docker Compose’s default `.env` loading handles `${VAR}` interpolation without `--env-file stack.env` (re-run prepare after editing `stack.env`). See **prepare-stack.examples/** for copy-paste patterns (`standard-self-contained.sh`, `standard-with-lib.sh`, `with-custom-middle.sh`).
- **upgrade-prepare-stack-verbose.py**: Regenerates stack `prepare-stack.sh` wrappers from the shared lib after you change the library (advanced; re-run only if you know you need it).
- **sync-compose-shared-env.py**: Adds optional repo-root `shared.env` to compose `env_file` (before `stack.env`) and strips duplicate `TZ`/`LANG`/`LC_*` from service `environment` blocks. See [documents/SHARED-RESOURCES.md](../documents/SHARED-RESOURCES.md). Only touches top-level `stacks/<name>/docker-compose.yml` and `portainer/docker-compose.yml` (not nested vendor trees).
- **find_apache2_containers.sh**: Lists all running apache2 processes on the host and shows which (if any) Docker container they belong to. Useful for debugging web server deployments and container isolation.
- **scan-secrets-gitleaks.sh**: Runs [Gitleaks](https://github.com/gitleaks/gitleaks) on the whole repo (default: full git history). Uses `--redact` and `--verbose`; pass flags such as `--no-git` for a quick working-tree-only scan. Requires `gitleaks` on your `PATH`. Optional repo-root `.gitleaks.toml` / `.gitleaksignore` for allowlists.
- **ci-parse-composes.py**: Loads each top-level stack `docker-compose.yml` (plus `portainer/`) with PyYAML; used by **`.woodpecker.yml`** in CI. Run locally: `python3 scripts/ci-parse-composes.py` (needs PyYAML).
- **push-github-mirror.sh**: Pushes the given branch (default: current) to `origin` and then to remote `github` if it exists. See [documents/DEVELOPMENT-WORKFLOW.md](../documents/DEVELOPMENT-WORKFLOW.md) for Gitea + GitHub mirror setup.
- **migrate-docker-volume-to-path.sh**: Copies a named Docker volume to a host directory (`cp -a` via Alpine) when switching stacks from named volumes to `stack.env`-controlled bind mounts. Optional `--chown UID:GID`. Stop the stack first; see stack READMEs for volume names and paths.
- **monitoring-smoke-check.sh**: Verifies monitoring baseline health (Prometheus jobs/rules + Alertmanager readiness) and now validates key Loki LogQL alert queries. Optional env vars: `LOKI_CONTAINER` (default `loki`), `LOKI_QUERY_WINDOW` (default `15m`), and threshold enforcement toggles (`LOKI_ENFORCE_THRESHOLDS=1`, `LOKI_FALLBACK_THRESHOLD`, `LOKI_RECONCILE_THRESHOLD`, `LOKI_HTTP_5XX_THRESHOLD`, `LOKI_LLM_UPSTREAM_THRESHOLD`).

## Usage

Run scripts from this directory with:

```bash
./<script_name>.sh
```

Some scripts may require root privileges or Docker group membership.
