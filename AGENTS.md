# Repository guidance for coding agents

## Scope and intent

This repository is a public, example-driven collection of independently
deployable Docker Compose stacks. Favor portable examples, explicit operator
choices, and safe defaults over assumptions about one homelab host.

Before changing a stack, read its `README.md` and inspect all files in that
stack directory. Do not copy conventions blindly from another stack; local
documentation is authoritative when layouts differ.

## Repository map

- `stacks/<name>/`: independently deployable stacks and their documentation.
- `portainer/`: Portainer CE, maintained outside the main stack catalog.
- `documents/`: cross-stack architecture, operations, and generated guides.
- `scripts/`: validation, generation, preparation, and maintenance tooling.
- `Makefile`: supported repository-wide workflows.

A normal stack contract includes:

- `docker-compose.yml`: service, storage, network, health, and resource config.
- `stack.env.example`: committed, portable variable template without secrets.
- `stack.yaml`: machine-readable catalog metadata.
- `README.md`: setup, dependencies, deployment, and troubleshooting.
- `prepare-stack.sh`: idempotent preparation using the shared helper library.
- `caddy_snippet.conf.example`: ingress template when the stack uses Caddy.

## Working rules

1. Inspect `git status --short` before editing. Preserve all unrelated and
   pre-existing work; never revert or reformat it.
2. Make the smallest coherent change. Keep stack-specific details beside the
   stack and cross-stack concepts in `documents/`.
3. Treat committed files as public examples. Use placeholder domains,
   credentials, private addresses, and machine paths.
4. When a stack's public contract changes, update all affected surfaces
   together: Compose, `stack.env.example`, `stack.yaml`, `prepare-stack.sh`,
   Caddy example, and README.
5. Preserve the established YAML, shell, and Markdown style in nearby files.
   Shell scripts use Bash, `set -euo pipefail`, and must pass ShellCheck at
   warning severity.
6. Pin or follow the dependency convention already used by the surrounding
   stack. Do not introduce floating image tags without explicitly documenting
   and representing that choice in metadata.

## Safety boundaries

- Never read, print, edit, stage, or commit runtime secrets merely to complete
  a repository task. Sensitive local files include `stack.env`, `.env`,
  non-example Caddy/config files, keys, credentials, tokens, and backups.
- Modify committed `*.example` templates, not ignored live configuration.
- Do not run `make secrets-files` unless the user explicitly requests a scan of
  local files; its output can expose ignored runtime values.
- Repository validation should be read-only. Do not start, stop, restart,
  recreate, pull, or deploy containers unless the user explicitly requests an
  operational action.
- Never use `docker compose down -v` for routine work. It removes named volumes.
- Do not create bind-mount directories automatically when a missing remote
  mount may be the cause; this can redirect writes onto the host filesystem.
- Treat published ports, privileged mode, host networking, Docker socket
  access, GPU access, and public ingress as security-relevant changes. Explain
  them in the stack README and keep `stack.yaml` runtime security metadata
  accurate.

## Stack preparation

Every top-level stack has an executable `prepare-stack.sh`. Follow
`documents/PREPARATION-STANDARDS.md` and start new wrappers from
`scripts/prepare-stack.examples/standard-with-lib.sh`.

Preparation must be idempotent and may create only missing local files,
directories, and explicitly declared external Docker resources. It must:

- source `scripts/prepare-stack-lib.sh`;
- preserve existing runtime configuration;
- avoid printing environment values;
- avoid starting or modifying containers; and
- report optional or unfinished setup without silently enabling it.

Run `make prepare-audit` after preparation changes. Automated `--fix` modes are
maintainer tools: review their complete diff before accepting any result.

## Generated documentation

- `documents/STACK-CATALOG.md` is generated from stack metadata and READMEs.
- The generated section of `documents/TOPOLOGY.md` comes from
  `documents/topology.yaml`.

Do not hand-edit generated content. After adding, removing, renaming, or
changing catalog/topology inputs, run:

```bash
make docs-generate
make docs-check
```

Review generated diffs and include them with the source change.

## Validation

Use the narrowest relevant checks during iteration, then repository validation
before handoff.

```bash
# Safe host/repository diagnostics
make doctor

# Standard repository validation; optional linters may be skipped if absent
make validate

# Generated documentation only
make docs-check

# Stack preparation or metadata changes
make prepare-audit
make metadata-audit

# CI-equivalent strict validation for changed stacks
make validate-changed BASE=<git-revision>

# Full local CI; requires all hook tools and scans Git history
make ci-local
```

For a focused Compose edit, also render the affected stack using its portable
example inputs. Prefer the repository validator because it handles example
environment files and known generated/include exceptions:

```bash
python3 scripts/validate-compose-config.py
```

Report exactly which checks ran, passed, failed, or were skipped. Do not claim
strict or CI-equivalent validation when optional tools were unavailable.

## Change-specific checklist

### Compose or environment variables

- Keep examples deployable without real credentials.
- Update the README variable table/instructions and `stack.env.example`.
- Keep external networks and volumes aligned with `prepare-stack.sh`.
- Maintain health checks, restart policy, resource limits, and persistence
  unless the change intentionally revises them.

### New or renamed stack

- Provide the complete stack contract described above.
- Regenerate catalog and topology documentation.
- Run preparation, metadata, hygiene, and full repository validation.

### GitHub workflows or dependency automation

- Preserve least-privilege permissions and immutable action pins.
- Validate `.github/dependabot.yml` and `renovate.json` ownership boundaries.
- Run the relevant actionlint, zizmor, Hadolint, and dependency checks through
  pre-commit or `make ci-local`.

### Documentation

- Keep the root README short and navigational.
- Put application-specific guidance in the stack README.
- Put shared architecture and operational guidance in `documents/`.
- Use relative links and ensure headings/anchors pass repository hygiene checks.

## Completion standard

A change is complete when the requested behavior is implemented, related stack
contract files agree, generated artifacts are current, relevant checks pass,
and unrelated working-tree changes remain untouched. Summarize changed files,
validation performed, and any operational migration or remaining risk.
