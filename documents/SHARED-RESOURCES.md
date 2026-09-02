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
| `ingress-public` | Caddy ingress for ordinary user-facing applications | `docker network create ingress-public` |
| `ingress-admin` | Caddy ingress for infrastructure and administrative interfaces | `docker network create ingress-admin` |
| `ingress-sensitive` | Caddy ingress for identity, secrets, finance, and other sensitive applications | `docker network create ingress-sensitive` |
| `edge-services` | Cloudflare Tunnel to Caddy | `docker network create edge-services` |
| `telemetry` | Prometheus, exporters, Grafana, Loki, and alerting | `docker network create --internal telemetry` |
| `mail-clients` | Internal SMTP plane for Postfix, Mailpit, and explicitly configured mail clients | `docker network create --internal mail-clients` |
| `mail-egress` | Outbound-capable network used only by the SMTP relay | `docker network create mail-egress` |
| `ai-backend` | Internal plane for Ollama and trusted AI/search clients | `docker network create --internal ai-backend` |
| `document-services` | Paperless-ngx and trusted API clients | `docker network create --internal document-services` |
| `media-services` | Playback/library plane: media servers and trusted playback, metadata, and statistics clients | `docker network create media-services` |
| `media-automation` | Control/download plane: *arr apps, indexers, downloaders, subtitle tools, and related dashboards | `docker network create media-automation` |
| `dns-services` | Pi-hole and AdGuard Home to Unbound | `docker network create dns-services` |
| `backup` | MinIO and trusted backup clients | `docker network create --internal backup` |
| `monitoring-push` | Dead-man callbacks from scheduled jobs to Uptime Kuma | `docker network create --internal monitoring-push` |
| `security-research` | OSINT, recon, scanning, and trusted research-tool APIs | `docker network create security-research` |
| `torrents` | qBittorrent / rtorrent-flood ↔ *arr stacks (Sonarr, Radarr, etc.) | `docker network create torrents` |
| `usenet`  | NZBGet ↔ *arr and NZBHydra2 | `docker network create usenet` |

Create these once (e.g. from the docker repo root or any host where you run stacks). Stacks that need them declare `external: true` and attach the relevant service(s).

**Address pool exhaustion:** shared external networks are created once and reused by
services with the same role. Multi-service stacks still use a private per-stack
network for databases and caches. If pool limits are reached, adjust Docker's
default address pools in `daemon.json`.

### MinIO (S3-compatible storage)

The **minio** stack is the single object store for:

- **Outline** – uploads (bucket e.g. `outline`)
- **Restic** – backup repository (e.g. `s3:http://minio:9000/restic`)
- **Kasm** – S3-based persistent profiles (bucket e.g. `kasm`; see [stacks/kasm/README.md](../stacks/kasm/README.md#optional-minio-s3-persistent-profiles))
- Other apps that support S3 (e.g. optional Firefly III file storage)

Trusted S3 clients reach `http://minio:9000` on `backup`; Caddy reaches the
console through `ingress-admin`. Create buckets per app in the MinIO console.

### Postfix (SMTP relay)

The **postfix** stack (folder `stacks/postfix`) is the shared outbound mail relay. Stacks that send email explicitly join `mail-clients` and point to `smtp-relay:587`. Configure `RELAYHOST`, `ALLOWED_SENDER_DOMAINS`, etc. in the postfix stack; see [stacks/postfix/README.md](../stacks/postfix/README.md).

**Stacks with SMTP relay support:** Alertmanager, Authentik, Diun, Firefly III, Gitea, Hedgedoc, Infisical, Joplin Server, Keycloak, Linkwarden, n8n, Naisho, Nextcloud, Outline, Password Pusher, Romm, Scrutiny, SimpleLogin, Snipe-IT, Uptime Kuma. See each stack's README for configuration (env vars or admin UI).

For **internal-only mailing** (no external delivery), deploy the **mailpit** stack and set Postfix `RELAYHOST=mailpit:1025`. Mailpit catches all mail and displays it in a web UI at `https://mailpit.yourdomain.com`; see [stacks/mailpit/README.md](../stacks/mailpit/README.md).

### Ollama (LLM runtime)

The **ollama** stack is the shared backend for:

- Open WebUI, LibreChat, Open Notebook, Perplexica, AnythingLLM, Paperless-GPT, Paperless-AI-Next, Nodepad (and optional backends behind **LiteLLM**)

Set `OLLAMA_BASE_URL=http://ollama:11434` (or the provider-specific equivalent)
when both services join `ai-backend`. Web UIs separately use their assigned `ingress-*` zone.

**LiteLLM** ([stacks/litellm](../stacks/litellm/README.md)) is an optional **OpenAI-compatible proxy** in front of Ollama and cloud APIs. Point clients at `http://litellm:4000/v1` with `LITELLM_MASTER_KEY` (or virtual keys) instead of calling Ollama directly when you want unified keys and routing.

**Whisper ASR** ([stacks/whisper-asr](../stacks/whisper-asr/README.md)) is an optional **speech-to-text** HTTP service (`whisper-asr:9000`) for Open WebUI, AnythingLLM, or workflows, protect it with Caddy / Access like any other AI endpoint.

**Kokoro TTS** ([stacks/kokoro-tts](../stacks/kokoro-tts/README.md)) is an optional **text-to-speech** service (`kokoro-tts:8880`): browser UI at `/web`, OpenAI-compatible API at `/v1`, useful with Open WebUI or scripts; protect the hostname the same way as other AI endpoints.

### External volumes (downloads) and media bind mounts

Media libraries and downloads are bind-mounted from one host tree (default
`/mnt/unraid/media`) to `/data` in download clients and *arr apps:

| Host path | Container path | Used by |
|-----------|----------------|---------|
| `/mnt/unraid/media/tv` | `/data/tv` | Sonarr |
| `/mnt/unraid/media/movies` | `/data/movies` | Radarr |
| `/mnt/unraid/media/adult` | `/data/adult` | Whisparr |
| `/mnt/unraid/media/music` | `/data/music` | Lidarr |
| `/mnt/unraid/media/books` | `/data/books` | Readarr |
| `/mnt/unraid/media/comics` | `/data/comics` | Mylar3 |
| `/mnt/unraid/media/downloads/usenet` | `/data/downloads/usenet` | *arr apps (NZBGet reports `/downloads`) |
| `/mnt/unraid/media/downloads/torrents` | `/data/downloads/torrents` | qBittorrent and *arr apps |

Mounting the tree once is important: Usenet imports can use an atomic rename,
and active torrents can be hardlinked into a library without consuming space
twice. For NZBGet, add a remote path mapping in each *arr app from remote
`/downloads/` to local `/data/downloads/usenet/`.

The same rule applies to manual/secondary importers:

- Picard mounts the media tree once at `/data`; use
  `/data/downloads/{soulseek,usenet/completed/music}` as intake and
  `/data/music` as output.
- Mylar3 uses `/data/comics` and the same `/data/downloads` tree.
- Explo is an exception: its Docker image defines separate `/data` output and
  `/slskd` source volume roles. Migration may copy across mounts; do not mount
  the whole media root at Explo's `/data`, because it treats that directory as
  the music-library destination.

In each *arr app, keep **Use Hardlinks instead of Copy** enabled. Usenet jobs
that are no longer needed by the downloader can be renamed into the library;
active torrents are hardlinked so they can continue seeding.

#### Unraid NFS source

> [!IMPORTANT]
> An Unraid share must remain pinned to its configured pool while the Docker
> host mounts a direct `/mnt/<pool>/<share>` export. Files moved to an array
> disk or another pool will not appear through that export.
>
> Before changing the share's primary/secondary storage or mover policy:
>
> 1. Stop Docker on the consuming host.
> 2. Change the NFS export and `/etc/fstab` mount source to the share's new
>    backing path, or deliberately switch back to `/mnt/user/<share>`.
> 3. Remount `/mnt/unraid/media` and verify the expected files are visible.
> 4. Start Docker only after the mount is verified.
>
> Never run mover or change the pool assignment first; doing so can make media
> appear missing to Lidarr, Navidrome, Soulseek, and the other media stacks.

When the media share is pinned to one pool, export and mount that pool's
backing path (`/mnt/<pool>/<share>`) instead of its
`/mnt/user/<share>` path. The latter traverses Unraid's FUSE `shfs` layer and
can leave `.fuse_hidden*` files and apparently non-empty directories when
applications move or unlink open media files.

Restrict a direct export to the consuming host and use root squashing. Keep
the local mount point `/mnt/unraid/media` unchanged so stack bind mounts do
not need to change.

### Local DNS and automatically reconciled mDNS

Use local DNS as the normal path. Configure one wildcard rewrite in AdGuard
Home, Pi-hole, or the network resolver:

```text
*.home.arpa → CADDY_LAN_IP
```

Add matching `app.home.arpa` site labels to Caddy snippets as they are migrated.
Unlike mDNS, normal DNS works across routed VLANs and the wildcard means new
stacks require no resolver update. The existing `.local` names can remain as a
compatibility layer.

`scripts/sync-local-hosts.py` discovers running Compose projects from Docker's
standard `com.docker.compose.project.working_dir` label, extracts `.local` site
labels from each active stack's runtime `caddy_snippet.conf`, and reconciles a
marked block in both `/etc/avahi/hosts` and `/etc/hosts`. It preserves all
unmanaged content, writes atomically, and reloads Avahi only after a change.

Preview or manually apply:

```bash
./scripts/sync-local-hosts.sh --print
sudo ./scripts/sync-local-hosts.sh --apply
./scripts/sync-local-hosts.sh --check
```

Use `--all-configured` to preview every runtime snippet regardless of container
state. Set a stable address with `--interface eno1`, `--ip 192.168.1.10`,
`MDNS_INTERFACE`, or `MDNS_IP`. Without one, the address used by the default
IPv4 route is selected.

For exceptional aliases, copy `scripts/local-hosts.overrides.example` to the
gitignored `scripts/local-hosts.overrides`. A `+name` line forces an alias into
the result and `-name` excludes one.

Install the two-minute systemd reconciliation timer:

```bash
sudo install -m 0755 scripts/sync-local-hosts.py /usr/local/libexec/sync-local-hosts
sudo install -m 0644 scripts/sync-local-hosts.service scripts/sync-local-hosts.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now sync-local-hosts.timer
```

The installed script discovers active stacks from Compose's standard working
directory labels, so the unit contains no repository or username-specific
paths. If discovery must be constrained, put `MDNS_REPO_ROOT=/path/to/repo` in
`/etc/default/sync-local-hosts`. To pin the LAN interface, set
`MDNS_INTERFACE=eno1` there instead.

When exactly one complete `~/.config/hblock` directory exists under `/home`,
the reconciler automatically manages its `footer.list` and regenerates
`/etc/hosts` only when the footer changed. Ambiguous systems must set
`HBLOCK_CONFIG_DIR=/path/to/.config/hblock`. The generated command is
equivalent to:

```bash
sudo hblock -S "$HBLOCK_CONFIG_DIR/sources.list" \
  -A "$HBLOCK_CONFIG_DIR/allow.list" \
  -O /etc/hosts \
  -F "$HBLOCK_CONFIG_DIR/footer.list"
```

Without hblock, the default target is `/etc/hosts`; `--no-hblock` disables
automatic detection explicitly. Other LAN devices resolve aliases from Avahi.
Crossing VLANs still requires an mDNS reflector; prefer `home.arpa` DNS instead.

---

## Optional optimizations

### 1. Shared env file (TZ & locale)

Many stacks use the same `TZ`, locale, and host storage roots. You can set
`TZ`, `LANG`, `LC_ALL`, `LC_CTYPE`, `MEDIA_ROOT`, and `LAB_ROOT` in one place
instead of repeating them. Preparation scripts read `MEDIA_ROOT` and
`LAB_ROOT` from their process environment; per-stack path variables still take
precedence.

**Setup:** From the `docker/` repo root, copy the template and edit:

```bash
cp shared.env.example shared.env
# Edit timezone, locale, and optional roots. Do NOT commit shared.env.
```

**Do not commit real values**, `shared.env` is gitignored; only `shared.env.example` is in the repo.

#### Using the shared env file

**Docker Compose (CLI)**
From any stack directory, pass both env files (later files override earlier ones for the same key, so `stack.env` overrides `shared.env` for any duplicate keys):

```bash
cd stacks/hedgedoc
docker compose --env-file ../../shared.env --env-file stack.env up -d
```

You can use a shell alias or script if you prefer, e.g.:

```bash
alias compose-shared='docker compose --env-file ../../shared.env --env-file stack.env'
compose-shared up -d
```

Stacks stay runnable without the shared file: if you use only `stack.env` (e.g. `docker compose up -d` with `env_file: stack.env` in the compose), existing behaviour is unchanged.

**Portainer**
Portainer does not load a host path like `shared.env` when deploying from Git or the web editor, so use one of these:

- **Recommended:** Add the same four variables to each stack's **Environment variables** in Portainer. When creating or editing a stack, in the "Environment variables" section add:
  - `TZ` = your timezone (e.g. `America/Denver`)
  - `LANG` = `en_US.UTF-8` (or your locale)
  - `LC_ALL` = `en_US.UTF-8`
  - `LC_CTYPE` = `en_US.UTF-8`
  You can copy them from your local `shared.env` (or from `shared.env.example`) and paste name/value pairs into Portainer. Add `MEDIA_ROOT` and `LAB_ROOT` only to stacks that reference them. Stacks that already define these in their compose will use the values you set in Portainer (compose typically uses `${TZ:-default}` so the Portainer env wins when provided).

- **If you deploy from the host (e.g. Portainer with a bind-mounted compose path):** Some setups let you specify an env file path for the stack. If your Portainer has access to the host filesystem and supports an env file path, you can point it at `shared.env` in the `docker/` directory; otherwise use the manual variables above.

- **Optional:** Keep a single "reference" note (e.g. in your runbook or a Portainer stack description) listing the four variable names and your chosen values so you can paste them into new stacks quickly.

Result: one place to edit (either `shared.env` on disk or your Portainer reference); stacks remain independent and work with or without the shared file.

### 2. Optional shared Redis

Several stacks run their own Redis (Outline, Nextcloud, Immich, LibreChat, SearXNG, Paperless-ngx, Authentik, Infisical, etc.). Redis supports **multiple logical databases** (DB 0, 1, 2, …) in one instance.

- **Benefit:** One Redis container to run and patch; slightly lower total memory if you have many small Redis users.
- **Tradeoff:** All stacks using it depend on the same container and version; you must start the shared Redis stack before those apps.

**If you want a shared Redis:**

1. Add a small **redis** stack (or reuse an existing one that you're comfortable sharing) on a dedicated internal dependency network, with a single Redis container and a volume for persistence.
2. In each app stack that currently has its own Redis:
   - Remove the Redis service and its volume from that stack's compose.
   - Point the app to the shared Redis host (e.g. `redis-shared:6379`) and set the **DB index** (e.g. `redis://redis-shared:6379/0` for app A, `/1` for app B). Use different DB numbers per app to avoid key collisions.
3. Document which app uses which DB index (e.g. in this file or in ENV-VARS.md).

Stacks that don't opt in keep their bundled Redis; modularity is preserved.

### 3. Optional shared Postgres (advanced)

Many stacks run their own Postgres (Gitea, Firefly III, Hedgedoc, Outline, Nextcloud, Keycloak, etc.). You *can* run a **single Postgres** server with **multiple databases** (one per app) and point each stack at that server with a different `POSTGRES_DB` (or equivalent).

- **Benefits:** One Postgres to backup, patch, and tune.
- **Tradeoffs:**
  - All participating stacks depend on one Postgres version and availability.
  - You must create databases and users (and optionally extensions) by hand or via an init script.
  - Removing a stack is less "delete this compose" and more "drop this DB and stop the app."

Recommendation: only consider this if you explicitly want to centralize DB management. Otherwise, per-stack Postgres keeps stacks independent and is the default in this repo.

---

## One-time setup checklist

To avoid "network/volume does not exist" when bringing up stacks:

1. **Networks** (if not already created):
   - `docker network create ingress-public`
   - `docker network create ingress-admin`
   - `docker network create ingress-sensitive`
   - `docker network create edge-services`
   - `docker network create --internal telemetry`
   - `docker network create --internal mail-clients`
   - `docker network create mail-egress`
   - `docker network create --internal ai-backend`
   - `docker network create media-automation`
   - `docker network create media-services`
   - `docker network create dns-services`
   - `docker network create security-research`
   - `docker network create --internal document-services`
   - `docker network create --internal backup`
   - `docker network create torrents`   (if you use qbittorrent / *arr)
   - `docker network create usenet`    (if you use NZBGet / *arr)

2. **External volumes / host paths** (if your stacks declare them as `external: true` and you haven't created them yet):
   - Ensure host media paths exist before deploying media stacks, e.g.:
     - `/mnt/unraid/media/{tv,movies,music,books,comics}`
     - `/mnt/unraid/media/downloads/usenet`

3. **MinIO:** Deploy the minio stack and create buckets (e.g. `outline`, `restic`) and access keys; set the corresponding env in Outline, Restic, etc.

4. **Postfix:** Deploy once on internal `mail-clients` plus relay-only `mail-egress`; configure relay and allowed domains, then attach each mail client only to `mail-clients` and set SMTP host to `smtp-relay` (port `587`).

5. **Ollama:** Deploy once on internal `ai-backend`; set `OLLAMA_BASE_URL=http://ollama:11434` in Open WebUI, LibreChat, etc.

---

## Summary

| Resource      | Status        | Action |
|---------------|---------------|--------|
| Networks      | Shared        | Create the three `ingress-*` zones and each required internal service plane once |
| MinIO         | Shared        | Deploy minio stack; create buckets; set env in Outline, Restic, etc. |
| Postfix       | Shared        | Deploy postfix stack; set SMTP in apps that send mail |
| Ollama        | Shared        | Deploy ollama stack; set `OLLAMA_BASE_URL` in AI UIs |
| External vols | Shared        | Create named volumes once when required by stacks |
| TZ/locale     | Optional share| Copy `shared.env.example` → `shared.env`; use with `--env-file` (CLI) or add the four vars in Portainer (see above) |
| Redis         | Optional share| One Redis + different DB indices per app (opt-in per stack) |
| Postgres      | Optional share| Single Postgres with multiple DBs (advanced; not recommended by default) |

Keeping each stack self-contained (with its own DB/Redis in the repo) preserves modularity; the options above let you **optionally** consolidate where it makes sense for your environment.
