# Documentation

- [Custom container images](CUSTOM-IMAGES.md)

Cross-stack guides for operating and maintaining this Docker homelab.
Application-specific setup belongs in each stack's README; find one through the
[stack catalog](STACK-CATALOG.md).

For plain-language service discovery and architecture guidance, use the
[Homelab Atlas](https://bolens.github.io/homelab/). This directory remains the
technical reference for deployment and operation.

## New deployment

1. Follow [Getting started](GETTING-STARTED.md) for prerequisites, preparation,
   deployment, and verification.
2. Use the [stack catalog](STACK-CATALOG.md) to choose a service.
3. Read that stack's linked README before copying examples or starting
   containers.
4. Refer to [Shared resources](SHARED-RESOURCES.md) only for the networks,
   storage, and shared services your selected stack needs.

## Architecture and shared configuration

| Guide | Use it for |
|---|---|
| [Topology](TOPOLOGY.md) | Generated overview of ingress, VPN, application, and monitoring relationships |
| [Shared resources](SHARED-RESOURCES.md) | Networks, storage, MinIO, Postfix, Ollama, DNS, and host-wide settings |
| [Environment variables](ENV-VARS.md) | Shared variable conventions, secret generation, and the per-stack variable index |
| [Cloudflare Access SSO](ACCESS-SSO.md) | Protecting tunnel hostnames with an identity provider or one-time PIN |
| [CrowdSec Cloudflare Worker](CROWDSEC-CLOUDFLARE-WORKER.md) | Enforcing CrowdSec decisions at Cloudflare's edge |
| [Monitoring and observability](MONITORING.md) | Choosing and connecting metrics, logs, probes, dashboards, and alerts |
| [Logging hardening](LOGGING-HARDENING.md) | Docker log rotation, Alloy access, and Loki migration |

## Operations

| Guide | Use it for |
|---|---|
| [Troubleshooting](TROUBLESHOOTING.md) | Health checks, exited containers, restart behavior, and common failures |
| [Portainer](../portainer/README.md) | Deploying and proxying the Portainer management UI |
| [Scripts reference](../scripts/README.md) | Validation, preparation, maintenance, and monitoring helpers |

For an application-specific failure, start with its stack README before using
the cross-stack troubleshooting guide.

## Maintainer reference

| Guide | Use it for |
|---|---|
| [Development workflow](DEVELOPMENT-WORKFLOW.md) | Local validation, secret scanning, CI, commits, and mirror pushes |
| [Preparation standards](PREPARATION-STANDARDS.md) | Contract and audit workflow for stack preparation scripts |
| [Stack metadata](STACK-METADATA.md) | `stack.yaml` schema, validation, and reviewed inference |
| [Stack catalog](STACK-CATALOG.md) | Generated index of every stack and its purpose |

Each `stacks/<name>/README.md` should describe the application, link to its
upstream project and image, and document its own prerequisites, configuration,
deployment, verification, upgrade, and troubleshooting details. Omit upstream
link fields that do not apply.
