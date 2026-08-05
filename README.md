# Docker homelab

A modular collection of Docker Compose stacks for a self-hosted homelab. Each
stack is independently deployable and documents its own configuration,
dependencies, storage, networking, and upgrade notes.

> [!IMPORTANT]
> This repository contains examples, not a ready-made production environment.
> Review a stack's README and example files before deploying it. Never commit
> generated secrets or local runtime configuration.

## Start here

| I want to… | Go to |
|---|---|
| Set up a new host and deploy a first stack | [Getting started](documents/GETTING-STARTED.md) |
| Find an application or service | [Stack catalog](documents/STACK-CATALOG.md) |
| Configure a particular stack | Its linked README in the [stack catalog](documents/STACK-CATALOG.md) |
| Understand how stacks connect | [Topology](documents/TOPOLOGY.md) |
| Create shared networks, storage, mail, or AI services | [Shared resources](documents/SHARED-RESOURCES.md) |
| Set up metrics, logs, probes, and alerts | [Monitoring and observability](documents/MONITORING.md) |
| Diagnose a failed deployment | [Troubleshooting](documents/TROUBLESHOOTING.md) |
| Browse all repository guides | [Documentation index](documents/README.md) |
| Contribute or add a stack | [Contributing](CONTRIBUTING.md) |

New here? Follow [Getting started](documents/GETTING-STARTED.md). It covers host
prerequisites, local configuration, shared resources, deployment, and
verification without assuming that every stack should be installed.

## How the repository is organized

```text
.
├── stacks/<name>/     # One independently documented application or service
├── portainer/         # Portainer CE, maintained outside the main stack catalog
├── documents/         # Cross-stack architecture and operations guides
├── scripts/           # Validation, preparation, and maintenance helpers
├── shared.env.example # Optional host-wide timezone and locale template
└── Makefile           # Common validation and maintenance commands
```

A typical stack contains:

| File | Purpose |
|---|---|
| `README.md` | Stack-specific setup, configuration, usage, and troubleshooting |
| `docker-compose.yml` | Compose definition |
| `stack.env.example` | Safe, committed configuration template |
| `stack.yaml` | Machine-readable catalog metadata |
| `prepare-stack.sh` | Optional preparation helper; preserves existing local files |

Some stacks need additional example configuration or generated upstream files.
The stack README is authoritative when its layout differs from this pattern.

## Choose and deploy a stack

1. Pick a service from the [stack catalog](documents/STACK-CATALOG.md).
2. Read that stack's README completely.
3. Run its `prepare-stack.sh` if present, or copy only the example files named
   by its README.
4. Replace placeholders and generate unique secrets in ignored local files.
5. Validate and deploy from the stack directory:

   ```bash
   docker compose config --quiet
   docker compose pull
   docker compose up -d
   docker compose ps
   ```

Do not assume one stack's environment variables, networks, or commands apply to
another. Stack-specific instructions deliberately live beside the Compose file
so they can evolve together.

## Shared architecture

Stacks remain separate but may opt into shared infrastructure:

- Caddy provides HTTP(S) ingress on trust-specific `ingress-*` networks.
- `telemetry` connects monitoring and logging services.
- Dedicated networks connect mail, AI, DNS, media, and download services.
- Named volumes and bind mounts persist application data outside containers.
- `shared.env` can provide common timezone and locale values.

Create only the resources required by the stacks you select. See
[Shared resources](documents/SHARED-RESOURCES.md) for the network model,
storage cautions, and one-time setup, or view the generated
[topology](documents/TOPOLOGY.md) for service relationships.

## Configuration and secrets

Committed `*.example` files are templates. Local files such as `stack.env`,
`.env`, live Caddy snippets, private keys, and application configuration are
ignored where appropriate and must not be committed.

Before deploying:

- inspect mounts and confirm remote storage is actually mounted;
- replace example domains, paths, credentials, and secret placeholders;
- use unique secrets for every application;
- check the stack README for required external networks and volumes;
- run `make doctor` and `make validate` from the repository root.

See [Environment variables](documents/ENV-VARS.md) for shared conventions and
secret-generation patterns. A stack's own README and `stack.env.example` remain
the source of truth for its variables.

## Repository maintenance

Useful read-only checks:

```bash
make doctor
make validate
```

Before contributing:

```bash
make hooks-install
make ci-local
```

The [scripts reference](scripts/README.md) explains the available helpers.
Contributor conventions, generated documentation, and validation requirements
are covered in [CONTRIBUTING.md](CONTRIBUTING.md).

## Security

These stacks can expose privileged services and personal data. Review published
ports, proxy routes, authentication, volume permissions, and image sources
before deployment. Back up persistent data before upgrades, and avoid
`docker compose down -v` during routine maintenance because it removes named
volumes.

To report a vulnerability in the repository, see the
[security policy](SECURITY.md).
