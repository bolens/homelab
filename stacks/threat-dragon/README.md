# OWASP Threat Dragon

Threat modeling tool: create diagrams, document threats (STRIDE, etc.), and optionally save models to GitHub, Bitbucket, or GitLab. [OWASP Threat Dragon](https://owasp.org/www-project-threat-dragon/) runs as a web app—no host ports; access via Caddy.

**Website:** https://owasp.org/www-project-threat-dragon/  
**Docs:** https://www.threatdragon.com/docs/  
**GitHub:** https://github.com/OWASP/threat-dragon  
**Docker image:** https://hub.docker.com/r/owasp/threat-dragon  
**Releases:** https://github.com/OWASP/threat-dragon/releases  

## Quick start

1. **Copy env and set required values**

   ```bash
   cp stack.env.example stack.env
   ```

   Edit `stack.env` and set at least:
   - `SESSION_SIGNING_KEY` – 32-character hex string (e.g. `openssl rand -hex 16`).
   - For saving models to **GitHub**: create an OAuth App and set `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET`, and `NODE_ENV=production`. Callback URL: `https://threatdragon.home/oauth/github` (use your Caddy hostname).
   - For **Bitbucket** or **GitLab**, see [Threat Dragon configure docs](https://www.threatdragon.com/docs/configure/configure.html).

2. **Start the stack**

   ```bash
   docker compose up -d
   ```

3. **Access the UI**

   Open your Caddy hostname (e.g. `https://threatdragon.home`). Sign in with GitHub (or your provider) to save and load models from repos.

## Configuration

| Item | Details |
|------|---------|
| **Access** | Via Caddy only (reverse proxy to `threatdragon:3000`). No host ports. |
| **Network** | `monitor` (external). |
| **Image** | `owasp/threat-dragon:stable` (OWASP Docker Hub). |
| **Env** | `.env` is mounted read-only; change values on host and restart container. |

## Caddy reverse proxy

Example Caddy vhost (main `stacks/caddy` Caddyfile):

```caddyfile
threatdragon.home, threatdragon.local {
	tls internal
	reverse_proxy threatdragon:3000
}
```

For OAuth callbacks (e.g. GitHub), use the same hostname in your OAuth app’s callback URL (e.g. `https://threatdragon.home/oauth/github`).

## Rebuild / update

```bash
docker compose pull threatdragon
docker compose up -d
```
