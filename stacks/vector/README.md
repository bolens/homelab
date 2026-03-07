# Vector (log shipper)

Vector is a log collection and routing agent. This stack ships host and container logs to the existing Loki stack for centralized search and dashboards in Grafana.

**Website:** https://vector.dev/  
**Docs:** https://vector.dev/docs/  
**Docker image:** https://hub.docker.com/r/timberio/vector  

## Quick start

1. Ensure the **Loki** stack is running and reachable as `http://loki:3100` on the `monitor` network.
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
| **Access**  | Internal only; Vector reads host logs and sends to `loki:3100` on the `monitor` network |
| **Config**  | `vector.toml` (sources, transforms, sinks; safe to commit)                             |
| **Network** | `monitor` — shared with Loki and other observability stacks                            |
| **Env**     | See `stack.env.example` and `documents/ENV-VARS.md` for TZ/locale via `shared.env`.    |

The example `vector.toml` includes:

- A **journald** source (`host_journal`) for host logs.
- A **docker_logs** source (`docker_containers`) for container logs.
- A small **remap** transform to add a `host` label.
- A **Loki sink** that sends logs to `http://loki:3100` with basic labels.

Adjust these to match your environment (e.g. additional labels, different Loki URL, or extra sinks).

