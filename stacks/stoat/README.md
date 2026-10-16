# Stoat

Self-hosted, user-first chat platform (channels, DMs, threads, media, voice) compatible with the official Stoat clients. This stack embeds the upstream `stoatchat/self-hosted` services but **does not expose any host ports** – all access goes through the main `caddy` reverse proxy in this homelab.

**Website:** https://stoat.chat  
**Docs:** https://docs.stoat.dev/docs/installation  
**GitHub:** https://github.com/stoatchat/self-hosted  
**Docker image:** https://github.com/stoatchat/api/pkgs/container/api  
**Releases:** https://github.com/stoatchat/self-hosted/releases  

## Release updates

Keep the backend services on a release intended for self-hosting. Upstream marks
[v0.15.6](https://github.com/stoatchat/stoatchat/releases/tag/v0.15.6) as gateway
testing unsuitable for self-hosters and
[v0.15.7](https://github.com/stoatchat/stoatchat/releases/tag/v0.15.7) as an internal
shield update. Dependabot excludes those two backend releases while continuing
to monitor subsequent versions. Upgrade the coupled backend services together
only after reviewing the selected release and verifying application state.

## Quick start

1. **Generate configuration for a new installation**

   Use a reviewed checkout of [stoatchat/self-hosted](https://github.com/stoatchat/self-hosted), not the generator script on its own: it also needs `secrets.env.example` and the matching Caddy/configuration files. Review the selected revision, then run `./generate_config.sh stoat.yourdomain.com` inside that checkout. Do not use `--overwrite` to perform an image upgrade.

   After verifying the destination filesystem, copy the generated `Revolt.toml`, `.env.web`, `livekit.yml`, `stoat.json`, matching `Caddyfile` and private `secrets.env` into a new private config directory, for example `/home/youruser/.config/stoat`. Preserve every existing file. Restrict the directory to its owner and the private secrets file to mode `600`.

   Set `STOAT_CONFIG_DIR` in `stack.env` and set `STOAT_SECRETS_FILE` to the generated private `secrets.env` path. All eight backend services load that selected file. A missing selected file stops deployment; the image's public development keys are not suitable for a fresh deployment. `stoat.json` contains the public API URL and is mounted read-only for the inner Caddy discovery route; it contains no credentials.

2. **(Recommended) Adjust for running behind this Caddy**

   Because this homelab already has a global `caddy` reverse proxy that terminates TLS, Stoat's own Caddy runs **HTTP-only** on the internal `stoat` network. After running `generate_config.sh`, edit `.env.web`:

   - Change `HOSTNAME=...` to:

     ```env
     HOSTNAME=:80
     ```

  - Leave `REVOLT_PUBLIC_URL`, `VITE_API_URL`, `VITE_WS_URL`, etc. pointing at your actual public hostname (e.g. `https://stoat.yourdomain.com`).

3. **Data volumes**

   The compose file uses Docker-managed named volumes for persistent storage:

   - `stoat_db_data` – MongoDB data
   - `stoat_rabbit_data` – RabbitMQ data
   - `stoat_minio_data` – MinIO object storage
   - `stoat_caddy_data`, `stoat_caddy_config` – Stoat Caddy state
   - The complete `STOAT_CONFIG_DIR`, selected `STOAT_SECRETS_FILE`, and private `stack.env` – configuration and keys; keep these with the database/object-store backup.

   These volumes are managed by Docker (not stored under the stack directory).

4. **Deploy**

   ```bash
   docker compose up -d
   ```

   Or add the stack in Portainer, ensure `ingress-public` exists, and deploy.

5. **Access**

  - Local: `https://stoat.home` (via Caddy internal TLS, if you add the Caddy blocks below).
  - Public: `https://stoat.yourdomain.com` (via Cloudflare DNS + Tunnel or port-forward + Caddy).

## Configuration

| Item | Details |
|------|---------|
| **Access** | Via main Caddy only (no host ports in this stack) |
| **Network** | `stoat` private for all services; `ingress-public` only for Stoat Caddy |
| **Images** | From `ghcr.io/stoatchat/*`, `mongo`, `valkey/valkey`, `rabbitmq`, `minio` |
| **Env** | `Revolt.toml` plus the selected `STOAT_SECRETS_FILE` configure the backends; `.env.web` configures inner Caddy. Keep RabbitMQ/MinIO credentials consistent across their services and backend configuration. |
| **Storage** | Named state volumes plus operator-owned `STOAT_CONFIG_DIR` and `STOAT_SECRETS_FILE` (see above) |

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

Ensure Stoat Caddy is on `ingress-public` so the main Caddy can resolve `stoat-caddy`.

## Voice / LiveKit notes

This stack **does not** publish LiveKit ports (`7881`, `50000-50100/udp`) on the host. For full voice/video support from the public internet you will need additional routing (e.g. publishing those ports, using a VPN, or Cloudflare-compatible UDP tunnelling). For local/LAN-only testing, you can selectively expose them in a `compose.override.yml` based on the upstream docs.

## Existing configuration and release upgrades

Back up the complete configuration, selected secrets file and all persistent volumes, and verify an isolated restore before upgrading. Record the current image IDs, accounts/messages, files and their checksums. Do not regenerate encryption, VAPID or LiveKit keys during an image update.

Existing `stack.env` files without `STOAT_SECRETS_FILE` use the tracked empty `legacy-backend.env.example`, preserving their previous `Revolt.toml` settings. Before selecting a generated `secrets.env`, verify privately that its keys match the effective keys used by the old deployment. A previously generated but unused file is not proof of the active key. Changing the effective encryption key can make existing files unreadable. Preparation preserves existing runtime files and never enables a new secrets file automatically.

Before recreation, provide `stoat.json` under `STOAT_CONFIG_DIR` with the existing public API URL, for example `{"api":"https://stoat.yourdomain.com/api"}`. This public discovery file can be added without regenerating private configuration. The bind refuses to create a missing source as a directory. Keep the existing Caddy routing and public hostname choices when reviewing an upstream template.

The 0.16.1 backend retains `/Revolt.toml` and `REVOLT__...` environment overrides; its added settings have embedded defaults. The default Shield host is empty. If a custom Shield service is configured, review the [0.16 protocol change](https://github.com/stoatchat/stoatchat/pull/1018): the client now uses `/v1/validate`, bearer authentication and a changed JSON response. This requires checking that configured service, not replacing all self-hosted configuration.

Upgrade the eight backend services together. Verify login, sending/receiving messages and events, old and new media, the existing client, push configuration, voice and API discovery before acceptance. The official self-hosted example still selects 0.15.5; source/configuration compatibility alone does not establish these runtime checks for 0.16.1. If acceptance fails, stop the updated backend and restore the verified state and effective keys with all prior matching images; reverting one service tag is insufficient.
