# Stacks documentation

Shared and cross-stack docs for the homelab Docker setup.

**Stack README convention:** Each stack under `stacks/<name>/` should include a standardized **upstream links** block near the top of its `README.md` (after the one-line description), with real URLs where applicable: **Website:**, **Docs:** (omit if no separate docs site), **GitHub:** (or other source host), **Docker image:** (Docker Hub / GHCR / registry for the image used in that stack), **Releases:** (project releases or changelog page). Omit any row that does not apply (e.g. no **Docs** if the project has no separate docs site).

| Doc | Description |
|-----|-------------|
| [ACCESS-SSO.md](ACCESS-SSO.md) | Cloudflare Access SSO for tunnel subdomains (replace basic auth with Google/GitHub/etc.) |
| [CROWDSEC-CLOUDFLARE-WORKER.md](CROWDSEC-CLOUDFLARE-WORKER.md) | Use CrowdSec decisions to block or challenge traffic at Cloudflare’s edge via the Cloudflare Workers bouncer |
| [ENV-VARS.md](ENV-VARS.md) | Common environment variables (TZ, locale, per-app) and which stacks use them |
| [SHARED-RESOURCES.md](SHARED-RESOURCES.md) | Shared resources (networks, MinIO, Postfix, Ollama), one-time setup, and optional optimizations (Redis, TZ/locale) |

Other guides (backup, monitoring, security) can live here as they’re added.
