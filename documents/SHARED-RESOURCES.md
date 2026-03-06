# Shared resources and stack optimizations

This guide describes **what is already shared** across homelab stacks and **optional optimizations** you can apply to reduce duplication while keeping stacks modular and independently deployable.

---

## Design principle: modularity first

- Each stack remains **runnable on its own** (its own DB/cache when applicable).
- Shared resources are **opt-in**: you choose which stacks use a shared service.
- Stacks do not depend on other *application* stacks; they may depend on **infrastructure** (Caddy, networks, optional relay/minio/ollama).

---

## Already shared (no change needed)

### Networks

Stacks use **external** Docker networks so Caddy and apps can talk without binding host ports:

| Network   | Purpose | Created once |
|----------|---------|----------------|
| `monitor` | Caddy ↔ app backends, infra (MinIO, Postfix, Ollama, etc.) | `docker network create monitor` |
| `torrents` | qBittorrent / rtorrent-flood ↔ *arr stacks (Sonarr, Radarr, etc.) | `docker network create torrents` |
| `usenet`  | NZBGet ↔ *arr and NZBHydra2 | `docker network create usenet` |

Create these once (e.g. from the docker repo root or any host where you run stacks). Stacks that need them declare `external: true` and attach the relevant service(s).

### MinIO (S3-compatible storage)

The **minio** stack is the single object store for:

- **Outline** – uploads (bucket e.g. `outline`)
- **Restic** – backup repository (e.g. `s3:http://minio:9000/restic`)
- Other apps that support S3 (e.g. optional Firefly III file storage)

All run on the `monitor` network and use `http://minio:9000` (S3 API) or `minio:9001` (console). Create buckets per app in the MinIO console. See each stack’s README for `AWS_*` / `RESTIC_*` placeholders.

### Postfix (SMTP relay)

The **postfix** stack (folder `stacks/postfix`) is the shared outbound mail relay. Stacks that send email (e.g. n8n, Naisho, Password Pusher, SimpleLogin, Infisical) point to `smtp-relay:587` on the `monitor` network. Configure `RELAYHOST`, `ALLOWED_SENDER_DOMAINS`, etc. in the postfix stack; see [stacks/postfix/README.md](../stacks/postfix/README.md).

### Ollama (LLM runtime)

The **ollama** stack is the shared backend for:

- Open WebUI, LibreChat, Open Notebook, Perplexica

Set `OLLAMA_BASE_URL=http://ollama:11434` in each app’s `stack.env` when both stacks are on the `monitor` network. See [stacks/ollama/README.md](../stacks/ollama/README.md) and each AI stack’s README.

### External volumes (media / downloads)

Some stacks expect **external** named volumes so multiple stacks can share the same data:

| Volume(s) | Used by |
|-----------|---------|
| `torrents_downloads` | qbittorrent, *arr stacks (Sonarr, Radarr, Lidarr, Readarr), Mylar3 |
| `usenet_downloads`   | nzbget, *arr stacks |
| `media_movies`, `media_tv`, `media_music` | Jellyfin, Plex, Emby, *arr (paths may differ per stack) |

Create volumes once if your compose does not create them: e.g. `docker volume create torrents_downloads`. Stacks that use them declare `external: true`. This avoids duplicate download/layout and keeps modularity (each stack still has its own compose and config).

---

## Optional optimizations

### 1. Shared env file (TZ & locale)

Many stacks use the same `TZ`, `LANG`, `LC_ALL`, `LC_CTYPE`. You can set them in one place so you don’t repeat values in every `stack.env`.

**Setup:** From the `docker/` repo root, copy the template and edit:

```bash
cp shared.env.example shared.env
# Edit shared.env with your TZ and locale (e.g. Europe/London, en_GB.UTF-8). Do NOT commit shared.env.
```

**Do not commit real values** — `shared.env` is gitignored; only `shared.env.example` is in the repo.

#### Using the shared env file

**Docker Compose (CLI)**  
From any stack directory, pass both env files (later files override earlier ones for the same key, so `stack.env` overrides `shared.env` for any duplicate keys):

```bash
cd stacks/hedgedoc
docker compose --env-file ../shared.env --env-file stack.env up -d
```

You can use a shell alias or script if you prefer, e.g.:

```bash
alias compose-shared='docker compose --env-file ../shared.env --env-file stack.env'
compose-shared up -d
```

Stacks stay runnable without the shared file: if you use only `stack.env` (e.g. `docker compose up -d` with `env_file: stack.env` in the compose), existing behaviour is unchanged.

**Portainer**  
Portainer does not load a host path like `shared.env` when deploying from Git or the web editor, so use one of these:

- **Recommended:** Add the same four variables to each stack’s **Environment variables** in Portainer. When creating or editing a stack, in the "Environment variables" section add:
  - `TZ` = your timezone (e.g. `America/Denver`)
  - `LANG` = `en_US.UTF-8` (or your locale)
  - `LC_ALL` = `en_US.UTF-8`
  - `LC_CTYPE` = `en_US.UTF-8`
  You can copy them from your local `shared.env` (or from `shared.env.example`) and paste name/value pairs into Portainer. Stacks that already define these in their compose will use the values you set in Portainer (compose typically uses `${TZ:-default}` so the Portainer env wins when provided).

- **If you deploy from the host (e.g. Portainer with a bind-mounted compose path):** Some setups let you specify an env file path for the stack. If your Portainer has access to the host filesystem and supports an env file path, you can point it at `shared.env` in the `docker/` directory; otherwise use the manual variables above.

- **Optional:** Keep a single "reference" note (e.g. in your runbook or a Portainer stack description) listing the four variable names and your chosen values so you can paste them into new stacks quickly.

Result: one place to edit (either `shared.env` on disk or your Portainer reference); stacks remain independent and work with or without the shared file.

### 2. Optional shared Redis

Several stacks run their own Redis (Outline, Nextcloud, Immich, LibreChat, SearXNG, Paperless-ngx, Authentik, Infisical, etc.). Redis supports **multiple logical databases** (DB 0, 1, 2, …) in one instance.

- **Benefit:** One Redis container to run and patch; slightly lower total memory if you have many small Redis users.
- **Tradeoff:** All stacks using it depend on the same container and version; you must start the shared Redis stack before those apps.

**If you want a shared Redis:**

1. Add a small **redis** stack (or reuse an existing one that you’re comfortable sharing), on the `monitor` network, with a single Redis container and a volume for persistence.
2. In each app stack that currently has its own Redis:
   - Remove the Redis service and its volume from that stack’s compose.
   - Point the app to the shared Redis host (e.g. `redis-shared:6379`) and set the **DB index** (e.g. `redis://redis-shared:6379/0` for app A, `/1` for app B). Use different DB numbers per app to avoid key collisions.
3. Document which app uses which DB index (e.g. in this file or in ENV-VARS.md).

Stacks that don’t opt in keep their bundled Redis; modularity is preserved.

### 3. Optional shared Postgres (advanced)

Many stacks run their own Postgres (Gitea, Firefly III, Hedgedoc, Outline, Nextcloud, Keycloak, etc.). You *can* run a **single Postgres** server with **multiple databases** (one per app) and point each stack at that server with a different `POSTGRES_DB` (or equivalent).

- **Benefits:** One Postgres to backup, patch, and tune.
- **Tradeoffs:**  
  - All participating stacks depend on one Postgres version and availability.  
  - You must create databases and users (and optionally extensions) by hand or via an init script.  
  - Removing a stack is less “delete this compose” and more “drop this DB and stop the app.”

Recommendation: only consider this if you explicitly want to centralize DB management. Otherwise, per-stack Postgres keeps stacks independent and is the default in this repo.

---

## One-time setup checklist

To avoid “network/volume does not exist” when bringing up stacks:

1. **Networks** (if not already created):
   - `docker network create monitor`
   - `docker network create torrents`   (if you use qbittorrent / *arr)
   - `docker network create usenet`    (if you use NZBGet / *arr)

2. **External volumes** (if your stacks declare them as `external: true` and you haven’t created them yet):
   - e.g. `docker volume create torrents_downloads`
   - e.g. `docker volume create usenet_downloads`
   - Media volumes (`media_movies`, etc.) as needed by your media stacks.

3. **MinIO:** Deploy the minio stack and create buckets (e.g. `outline`, `restic`) and access keys; set the corresponding env in Outline, Restic, etc.

4. **Postfix:** Deploy once; configure relay and allowed domains; then set SMTP host to `smtp-relay` (and port `587`) in any stack that sends mail.

5. **Ollama:** Deploy once on `monitor`; set `OLLAMA_BASE_URL=http://ollama:11434` in Open WebUI, LibreChat, etc.

---

## Summary

| Resource      | Status        | Action |
|---------------|---------------|--------|
| Networks      | Shared        | Create once (`monitor`, `torrents`, `usenet`) |
| MinIO         | Shared        | Deploy minio stack; create buckets; set env in Outline, Restic, etc. |
| Postfix       | Shared        | Deploy postfix stack; set SMTP in apps that send mail |
| Ollama        | Shared        | Deploy ollama stack; set `OLLAMA_BASE_URL` in AI UIs |
| External vols | Shared        | Create named volumes once when required by stacks |
| TZ/locale     | Optional share| Copy `shared.env.example` → `shared.env`; use with `--env-file` (CLI) or add the four vars in Portainer (see above) |
| Redis         | Optional share| One Redis + different DB indices per app (opt-in per stack) |
| Postgres      | Optional share| Single Postgres with multiple DBs (advanced; not recommended by default) |

Keeping each stack self-contained (with its own DB/Redis in the repo) preserves modularity; the options above let you **optionally** consolidate where it makes sense for your environment.
