# Vector (log shipper)

Vector is a log collection and routing agent. This stack ships host and container logs to the existing Loki stack for centralized search and dashboards in Grafana. It is an alternative to Grafana Alloy; do not enable both Docker collectors at the same time or Loki will receive duplicate container logs.

**Website:** https://vector.dev/
**Docs:** https://vector.dev/docs/
**Docker image:** https://hub.docker.com/r/timberio/vector

## Quick start

1. Ensure the **Loki** and **Grafana Alloy** stacks are running on the `ingress-admin` network. Vector reuses Alloy's read-only Docker socket proxy at `http://alloy-docker-socket-proxy:2375`.
2. From this directory, copy `stack.env.example` → `stack.env`.
3. Review `vector.toml` and adjust sources and labels if needed.
4. Start the stack:

   ```bash
   docker compose up -d
   ```

5. In Grafana, add Loki as a data source (if not already) and explore logs from the new `vector` pipeline.

## Configuration

| Item        | Details                                                                                 |
| ----------- | --------------------------------------------------------------------------------------- |
| **Access**  | Internal only; Vector reads Docker logs through Alloy's read-only socket proxy and sends to `loki:3100` |
| **Config**  | `vector.toml` (sources, transforms, sinks; safe to commit)                             |
| **Network** | `ingress-admin`, shared with Loki and other observability stacks                            |
| **Env**     | See `stack.env.example` and `documents/ENV-VARS.md` for TZ/locale via `shared.env`.    |

The example `vector.toml` includes:

- A **journald** source (`host_journal`) for host logs.
- A **docker_logs** source (`docker_containers`) using Docker's API through `alloy-docker-socket-proxy`; this works with Docker's `local` logging driver.
- A small **remap** transform to add a `host` label.
- A **Loki sink** that sends logs to `http://loki:3100` with basic labels.

Adjust these to match your environment (e.g. additional labels, different Loki URL, or extra sinks).
