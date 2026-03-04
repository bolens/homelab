# Stoat

Self-hosted, user-first chat platform (channels, DMs, threads, media, voice) compatible with the official Stoat clients. This stack embeds the upstream `stoatchat/self-hosted` services but **does not expose any host ports** – all access goes through the main `caddy` reverse proxy in this homelab.

**Website:** https://stoat.chat  
**Docs:** https://docs.stoat.dev/docs/installation  
**GitHub:** https://github.com/stoatchat/self-hosted  
**Docker image:** https://github.com/stoatchat/api/pkgs/container/api  
**Releases:** https://github.com/stoatchat/self-hosted/releases  

## Quick start

1. **Generate Stoat config in this folder**

   From `docker/stacks/stoat`:

   ```bash
   curl -O https://raw.githubusercontent.com/stoatchat/self-hosted/main/generate_config.sh
   chmod +x generate_config.sh
   ./generate_config.sh stoat.home   # or stoat.yourdomain.com
   ```

   This creates:

   - `.env.web` – host/URL config for Stoat's internal Caddy and web app.
   - `Revolt.toml` – core Stoat configuration.
   - `livekit.yml` – LiveKit (voice/video) configuration.

2. **(Recommended) Adjust for running behind this Caddy**

   Because this homelab already has a global `caddy` reverse proxy that terminates TLS, Stoat's own Caddy runs **HTTP-only** on the internal `stoat` network. After running `generate_config.sh`, edit `.env.web`:

   - Change `HOSTNAME=...` to:

     ```env
     HOSTNAME=:80
     ```

  - Leave `REVOLT_PUBLIC_URL`, `VITE_API_URL`, `VITE_WS_URL`, etc. pointing at your actual public hostname (e.g. `https://stoat.yourdomain.com`).

3. **Data directories**

   The compose file uses `./data` for persistent storage:

   - `./data/db` – MongoDB data
   - `./data/rabbit` – RabbitMQ data
   - `./data/minio` – MinIO object storage
   - `./data/caddy-data`, `./data/caddy-config` – Stoat Caddy state

   These paths live next to `docker-compose.yml` (and are gitignored).

4. **Deploy**

   ```bash
   docker compose up -d
   ```

   Or add the stack in Portainer (Git or Web editor), ensure the `monitor` network exists, and deploy.

5. **Access**

  - Local: `https://stoat.home` (via Caddy internal TLS, if you add the Caddy blocks below).
  - Public: `https://stoat.yourdomain.com` (via Cloudflare DNS + Tunnel or port-forward + Caddy).

## Configuration

| Item | Details |
|------|---------|
| **Access** | Via main Caddy only (no host ports in this stack) |
| **Network** | `stoat` (internal for all Stoat services); `monitor` (Stoat Caddy only, for main Caddy) |
| **Images** | From `ghcr.io/stoatchat/*`, `mongo`, `eqalpha/keydb`, `rabbitmq`, `minio` |
| **Env** | `.env.web` (generated) and `Revolt.toml` control URLs and features; compose uses `${RABBITMQ_DEFAULT_*}` and `${MINIO_ROOT_*}` overrides if set |
| **Storage** | Host-mapped `./data/*` directories (see above) |

For advanced options (invite-only, S3, email, captcha, mobile push), see the upstream README and `Revolt.toml` reference.

## Caddy reverse proxy

Example Caddy vhosts for this homelab (main `stacks/caddy` Caddyfile):

```caddyfile
stoat.home, stoat.local {
	tls internal
	reverse_proxy stoat-caddy:80
}
```

Cloudflare Tunnel `:80` block (HTTP host routing):

```caddyfile
	@stoat host stoat.yourdomain.com
	handle @stoat {
		reverse_proxy stoat-caddy:80 {
			header_up X-Forwarded-Proto https
		}
	}
```

Public HTTPS (Cloudflare DNS-01):

```caddyfile
stoat.yourdomain.com {
	tls {
		dns cloudflare {env.CLOUDFLARE_API_TOKEN}
	}
	reverse_proxy stoat-caddy:80 {
		header_up X-Forwarded-Proto https
	}
}
```

Ensure the stack is on the `monitor` network (already configured in `docker-compose.yml`) so Caddy can resolve `stoat-caddy`.

## Voice / LiveKit notes

This stack **does not** publish LiveKit ports (`7881`, `50000-50100/udp`) on the host. For full voice/video support from the public internet you will need additional routing (e.g. publishing those ports, using a VPN, or Cloudflare-compatible UDP tunnelling). For local/LAN-only testing, you can selectively expose them in a `compose.override.yml` based on the upstream docs.

