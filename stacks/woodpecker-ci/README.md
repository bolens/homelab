# Woodpecker CI – lightweight CI/CD

[Woodpecker CI](https://woodpecker-ci.org/) is a lightweight, Docker-native CI/CD system. This stack runs a Woodpecker server and agent with Postgres, designed to integrate with your `gitea` stack as the Git provider.

**Website:** https://woodpecker-ci.org/
**Docs:** https://woodpecker-ci.org/docs/
**Docker images:** `woodpeckerci/woodpecker-server`, `woodpeckerci/woodpecker-agent`

## Quick start

1. **Environment**
   - From this directory: copy `stack.env.example` → `stack.env`.
   - Set `POSTGRES_PASSWORD` and the same password inside `WOODPECKER_DATABASE_DATASOURCE` (see the `REPLACE_DB_PASSWORD` placeholder in the example).
   - Set `WOODPECKER_GITEA_URL`, `WOODPECKER_GITEA_CLIENT`, `WOODPECKER_GITEA_SECRET`, and `WOODPECKER_AGENT_SECRET`.
   - Optional: `WOODPECKER_HOST` (public Woodpecker URL for OAuth redirects).
2. **Deploy**

   ```bash
   docker compose up -d
   ```

3. **Migrating from the old layout** (`WOODPECKER_DB_PASSWORD` only)

   If your `stack.env` still has `WOODPECKER_DB_NAME` / `WOODPECKER_DB_USER` / `WOODPECKER_DB_PASSWORD` but not the Postgres-native variables, add:

   - `POSTGRES_DB` and `POSTGRES_USER` (usually `woodpecker` / `woodpecker`),
   - `POSTGRES_PASSWORD`, same value as the old `WOODPECKER_DB_PASSWORD`,
   - `WOODPECKER_DATABASE_DRIVER=postgres`,
   - `WOODPECKER_DATABASE_DATASOURCE=postgres://woodpecker:YOUR_PASSWORD@woodpecker-postgres:5432/woodpecker?sslmode=disable`.

   Then remove the obsolete `WOODPECKER_DB_*` lines if you like, and recreate the stack (`docker compose up -d --force-recreate`).

4. **If you see `pq: password authentication failed` (28P01)**

   Postgres only applies `POSTGRES_PASSWORD` on **first** volume init. If the role password no longer matches `stack.env`, fix it with:

   ```bash
   docker exec -i woodpecker-postgres psql -U woodpecker -d woodpecker -c "ALTER USER woodpecker WITH PASSWORD 'same-as-POSTGRES_PASSWORD-in-stack-env';"
   docker compose up -d --force-recreate server
   ```

   Also ensure the password inside `WOODPECKER_DATABASE_DATASOURCE` matches. Follow the verified backup and rollback workflow in [agent guidance](../../AGENTS.md#live-configuration-and-updates); do not delete persistent volumes as routine recovery.

5. **Access**
   - Woodpecker server listens on port `8000` (HTTP API/UI) and `9000` (gRPC) inside the container by default.
   - Put it behind Caddy on the `ingress-admin` network, e.g.:
     - `https://ci.yourdomain.com` → `woodpecker-server:8000`

## Configuration

| Item        | Details                                                                              |
| ----------- | ------------------------------------------------------------------------------------ |
| **Access**  | Via Caddy (reverse-proxy to `woodpecker-server:8000`)                                |
| **Network** | `ingress-admin` for Caddy + default internal network for Postgres and agent          |
| **Images**  | `woodpeckerci/woodpecker-server:v3`, `woodpeckerci/woodpecker-agent:v3`, `postgres:18-alpine` (`:latest` was removed upstream; pin `v3.x.y` if you want a fixed patch) |
| **Storage** | `woodpecker_pg18_data` (DB), `woodpecker_agent_data` (agent identity)                     |
| **Caddy**   | See [stacks/caddy/Caddyfile.example](../caddy/Caddyfile.example) for `woodpecker-ci.yourdomain.com` or `ci.yourdomain.com` → `woodpecker-server:8000` |

## Gitea integration

- In Gitea:
  - Create an OAuth2 application with redirect URL pointing at the Woodpecker server URL (see Woodpecker docs for exact path).
  - Copy the client ID/secret into `WOODPECKER_GITEA_CLIENT` / `WOODPECKER_GITEA_SECRET`.
- In Woodpecker:
  - Access the UI at `https://ci.yourdomain.com`, sign in via Gitea, and enable repositories for builds.

The `woodpecker-agent` runs builds on the same Docker host, using the Docker socket (`/var/run/docker.sock`) to launch build containers.

## Agent identity and backups

The named `woodpecker_agent_data` volume persists `/etc/woodpecker`, with
`WOODPECKER_AGENT_CONFIG_FILE=/etc/woodpecker/agent.conf` fixed in Compose. The
agent stores its server-assigned ID there and reuses it after container recreation.
Losing this state can register a replacement agent and leave an offline record.
Keep a separate state volume for each agent; never share or clone agent identities.

Preparation leaves this Docker-managed volume to Compose and does not create a
host directory or register an agent. Back up the agent state with the server
database and configuration before an update. Verify the restored file is readable
and retains the expected `agent_id`, then confirm that the same agent ID reconnects
and executes a build after recreation. Container health alone is insufficient.

For an existing installation without a persistent mount, preserve and verify its
current `/etc/woodpecker/agent.conf` before recreating the agent, and seed its own
state volume before the new mount hides the container's existing file. Follow the
[backup and restore workflow](../../AGENTS.md#live-configuration-and-updates).
If an existing override already mounts agent state at `/etc/woodpecker`, retain
that volume: Compose merges volume entries by their container target. Do not
replace it with an empty volume or copy a different agent's file.

## Shared-host resource policy

Compose enforces one workflow at a time on this agent. Each build container,
including service containers, is limited to 2 CPUs, 6 GiB RAM, no swap, CPU
shares 128, and 64 MiB shared memory. The agent itself has a separate 1-CPU,
512-MiB RAM, no-swap, 256-process budget. Its limits do not contain the build
containers, which are siblings created through the host Docker socket.

These non-secret settings are explicit in Compose and override duplicate keys
in `stack.env`. Review this policy before raising limits. The server defaults
new repositories to a 30-minute pipeline timeout and allows at most 60 minutes
in repository settings. Check existing repositories' timeout settings separately.

Keep steps sequential on this shared host and limit service containers: the
6-GiB budget applies per container, not per workflow. Additional agents multiply
concurrency. Privileged jobs or jobs given the host Docker socket can launch
other workloads outside these limits and should use a separate build host.
Browser and large shell-analysis workloads can exhaust a 4-GiB ceiling without
an OOM kill. Size the host for the aggregate workload; compare cgroup memory
usage and limit events when commands stop responding. Local reproduction must
match both Docker limits: `--memory=6g --memory-swap=6g` keeps swap disabled.
Omitting the swap limit can let a local run pass using memory unavailable in CI.

CPU and memory limits do not bound disk usage or disk I/O. Monitor free space,
image/build-cache growth, and host I/O pressure. Do not automatically prune
shared images or volumes used by other stacks.

Before changing an agent's build limits, disable scheduling on that agent and
wait until its active workflows reach zero. Recreate only the agent using the
locally installed image, then confirm its original identity reconnects before
reenabling scheduling. Other agents can continue processing the queue.

```bash
docker compose up -d --no-deps --pull never agent
```

A server timeout-policy change separately requires recreating the server.

Verify the next build container's Docker `HostConfig` resource fields. An
agent health check alone does not prove the build limits are applied. See the
[agent configuration](https://woodpecker-ci.org/docs/administration/configuration/agent)
and [Docker backend configuration](https://woodpecker-ci.org/docs/administration/configuration/backends/docker).

## Optional trusted publisher broker

The [publisher broker contract](publisher-broker/README.md) defines a separately
selected `docker-compose.publisher-broker.yml` override for native GitHub
publication. It authenticates exact Woodpecker 3.20.1 extension signatures and
returns short-lived, source-bound publication leases for the four configured
repositories. Publisher helpers redeem them immediately before use through the
existing HTTPS ingress; queueing does not consume the GitHub token lifetime.
No App key enters a build, no host port/socket is added, and the default stack
continues without the broker. Keep netrc transfer and local fallback publisher
secrets disabled. Preparation requires explicit opt-in and never deploys it.
