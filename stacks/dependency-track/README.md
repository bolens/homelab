# OWASP Dependency-Track

Software Composition Analysis (SCA) platform: upload SBOMs (CycloneDX, SPDX), track components, and get vulnerability alerts from NVD, OSS Index, GitHub Advisories, and more. [Dependency-Track](https://dependencytrack.org/) provides a web UI and REST API—no host ports; access via Caddy.

**Project:** https://owasp.org/www-project-dependency-track/  
**Docs:** https://docs.dependencytrack.org/  
**Docker:** https://docs.dependencytrack.org/getting-started/deploy-docker/

## Quick start

1. **Copy env and set required values**

   ```bash
   cp stack.env.example stack.env
   ```

   Edit `stack.env` and set at least:
   - `POSTGRES_PASSWORD` – strong password for the Postgres DB. For example:

     ```bash
     openssl rand -hex 32
     ```

   - `API_BASE_URL` – full URL the **browser** will use to reach the API (see below).

2. **Start the stack**

   ```bash
   docker compose up -d
   ```

   Wait for the API to be healthy (first start can take 1–2 minutes).

3. **Access the UI**

   Open your Caddy hostname (e.g. `https://dtrack.home`). On first visit you will create the admin account.

4. **Upload SBOMs**

   Use the UI (Projects → Create → Upload BOM) or the REST API. Supported formats: CycloneDX (JSON/XML), SPDX (JSON). You can generate SBOMs with `syft`, `docker scout`, or CI integrations.

## API_BASE_URL (required)

The frontend only serves static files; all API calls are made **from the user’s browser** to `API_BASE_URL`. You must set this to the URL where Caddy exposes the Dependency-Track API.

**Option A – Path-based (one hostname)**  
Caddy serves frontend at `/` and API at `/api`:

- Frontend: `https://dtrack.home/` → `dtrack-frontend:8080`
- API: `https://dtrack.home/api` → `dtrack-apiserver:8080`

Then set:

```env
API_BASE_URL=https://dtrack.home/api
```

**Option B – Subdomain**  
Caddy serves API at e.g. `https://api.dtrack.home`:

- Set `API_BASE_URL=https://api.dtrack.home`

## Configuration

| Item | Details |
|------|---------|
| **Access** | Via Caddy only. No host ports. |
| **Network** | `dtrack` (internal); `dtrack-apiserver` and `dtrack-frontend` also on `monitor` for Caddy. |
| **Images** | `dependencytrack/apiserver`, `dependencytrack/frontend`, `postgres:17-alpine`. |
| **Resources** | API server is limited to 4GB RAM; minimum recommended 2GB. See [Dependency-Track docs](https://docs.dependencytrack.org/getting-started/deploy-docker/) for tuning. |

## Caddy reverse proxy

**Path-based (one hostname)** – add to your Caddyfile:

```caddyfile
dtrack.home, dtrack.local {
	tls internal
	handle /api/* {
		uri strip_prefix /api
		reverse_proxy dtrack-apiserver:8080
	}
	handle {
		reverse_proxy dtrack-frontend:8080
	}
}
```

**Subdomain** – separate server blocks for `dtrack.home` (frontend) and `api.dtrack.home` (reverse_proxy dtrack-apiserver:8080), and set `API_BASE_URL=https://api.dtrack.home`.

## Rebuild / update

```bash
docker compose pull
docker compose up -d
```
