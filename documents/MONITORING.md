# Monitoring and observability

This guide explains how the repository's monitoring stacks fit together. Each
component remains optional and independently deployable. Read the linked stack
README before configuring or starting it.

## Pick the capabilities you need

| Capability | Primary stacks | Purpose |
|---|---|---|
| Dashboards | [Grafana](../stacks/grafana/README.md) | Visualize metrics and logs |
| Metrics storage | [Prometheus](../stacks/prometheus/README.md) | Scrape and query time-series metrics |
| Container metrics | [cAdvisor](../stacks/cadvisor/README.md) | Export container CPU, memory, network, and filesystem metrics |
| Host metrics | [Node Exporter](../stacks/node-exporter/README.md) | Export host operating-system metrics |
| Synthetic probes | [Blackbox Exporter](../stacks/blackbox-exporter/README.md) | Probe HTTP, TCP, DNS, and ICMP targets |
| Alert routing | [Alertmanager](../stacks/alertmanager/README.md) | Group and route Prometheus alerts |
| Notifications | [ntfy](../stacks/ntfy/README.md) | Deliver push notifications, including Alertmanager webhooks |
| Log storage | [Loki](../stacks/loki/README.md) | Store and query logs |
| Container log shipping | [Grafana Alloy](../stacks/grafana-alloy/README.md) | Discover Docker containers and send their logs to Loki |
| Host log shipping | [Promtail](../stacks/promtail/README.md) | Send host files and journald logs to Loki |
| Alternative log shipping | [Vector](../stacks/vector/README.md) | Replace the baseline shippers when Vector is preferred |
| Availability monitoring | [Uptime Kuma](../stacks/uptime-kuma/README.md) | Run active service checks and publish status pages |
| Disk health | [Scrutiny](../stacks/scrutiny/README.md) | Monitor SMART data for physical disks |

Do not run multiple agents against the same log source unless duplicate events
are intentional. In the repository's baseline, Alloy handles Docker container
logs and Promtail handles host files and journald. Vector is an alternative to
that arrangement.

## Shared networks

Monitoring traffic uses the internal `telemetry` network. Browser-facing
administration UIs normally use `ingress-admin` so Caddy can proxy them without
publishing their application ports directly.

Create these networks once if the selected stack READMEs require them:

```bash
docker network create --internal telemetry
docker network create ingress-admin
```

The internal flag prevents direct external access to `telemetry`. Caddy should
join `ingress-admin`, not `telemetry`.

## Recommended deployment order

1. Deploy [Caddy](../stacks/caddy/README.md) if dashboards will be accessed by
   hostname.
2. Deploy [Prometheus](../stacks/prometheus/README.md) for metrics storage.
3. Add metric exporters such as
   [cAdvisor](../stacks/cadvisor/README.md),
   [Node Exporter](../stacks/node-exporter/README.md), or
   [Blackbox Exporter](../stacks/blackbox-exporter/README.md).
4. Deploy [Grafana](../stacks/grafana/README.md) and install its example
   provisioning files.
5. Optionally add [Alertmanager](../stacks/alertmanager/README.md) and a
   notification receiver such as [ntfy](../stacks/ntfy/README.md).
6. For centralized logs, deploy [Loki](../stacks/loki/README.md), followed by
   the selected log shipper or shippers.
7. Add [Uptime Kuma](../stacks/uptime-kuma/README.md) when active endpoint
   checks or a status page are useful.

This is dependency order, not a requirement to install the entire suite.

## Metrics flow

```text
cAdvisor ───────┐
Node Exporter ──┼──> Prometheus ──> Grafana
Blackbox ───────┘         │
                          └──> Alertmanager ──> ntfy or another receiver
```

Prometheus must share `telemetry` with the exporters it scrapes. Grafana also
uses `telemetry` to query Prometheus, while its web UI is reached through
`ingress-admin`.

The Prometheus example configuration includes the repository's baseline scrape
and alerting structure. Follow the Prometheus README when copying it because
its host path may need to be supplied explicitly for Portainer deployments.

## Logging flow

```text
Docker containers ──> Alloy ─────┐
Host files/journald ─> Promtail ──┼──> Loki ──> Grafana
Alternative sources ─> Vector ────┘
```

Install Loki before its shippers, then verify Loki readiness before debugging a
shipper. Grafana's example datasource provisioning includes Loki. See
[Logging hardening](LOGGING-HARDENING.md) for Docker log rotation, Alloy
permissions, and Loki migration notes.

## Health and availability checks

Use a service's documented health or readiness endpoint when it has one.
Otherwise, use an HTTP check against its normal application URL or an
appropriate TCP check. The stack README is the source of truth because paths
and ports can change with application versions.

Common monitoring endpoints include:

| Stack | Endpoint |
|---|---|
| [Alertmanager](../stacks/alertmanager/README.md) | `/-/healthy` |
| [cAdvisor](../stacks/cadvisor/README.md) | `/healthz` |
| [Grafana](../stacks/grafana/README.md) | `/api/health` |
| [Headscale](../stacks/headscale/README.md) | `/health` |
| [Loki](../stacks/loki/README.md) | `/ready` on internal port `3100` |
| [n8n](../stacks/n8n/README.md) | `/healthz` |
| [Prometheus](../stacks/prometheus/README.md) | `/-/healthy` |
| [Promtail](../stacks/promtail/README.md) | `/ready` on internal port `9080` |
| [Umami](../stacks/umami/README.md) | `/api/heartbeat` |
| [Vaultwarden](../stacks/vaultwarden/README.md) | `/alive` |

When monitoring through Caddy, check the public or private application hostname
to exercise DNS, TLS, proxying, and the backend together. An internal endpoint
check is still useful for distinguishing an ingress failure from an application
failure.

## Validation and smoke checks

The repository includes targeted helpers:

```bash
./scripts/validate-monitoring-config.sh
./scripts/monitoring-smoke-check.sh
```

The validation helper checks configuration syntax and relationships. The smoke
check queries running services, so use it only after the relevant monitoring
stacks are deployed. See the [scripts reference](../scripts/README.md) for
details.

For container failures and restart behavior, continue with
[Troubleshooting](TROUBLESHOOTING.md).
