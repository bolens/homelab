# Immich

Self-hosted photo and video backup: upload from phones and the web, face detection, search, and albums.

**Website:** https://immich.app
**Docs:** https://immich.app/docs
**GitHub:** https://github.com/immich-app/immich
**Docker image:** https://github.com/immich-app/immich/pkgs/container/immich-server
**Releases:** https://github.com/immich-app/immich/releases

## Quick start

1. **Environment**
   - Copy `stack.env.example` to `stack.env`.
   - Generate and set `DB_PASSWORD` (see **Generating keys and secrets** below).
   - Set `TZ` to your timezone if different from America/Denver.
2. **Deploy:** `docker compose up -d` (or add the stack in Portainer and set the same vars in the stack Environment).
3. **First run:** Open Immich via Caddy (or http://localhost:2283 from the host), create the admin user, then configure OAuth and other options in **Administration → Settings**.

## Generating keys and secrets

**DB_PASSWORD** (required) – Postgres password. Must be alphanumeric only (no spaces). Generate:

```bash
openssl rand -hex 16 | tr -d '\n' | head -c 24
```

Set the output as `DB_PASSWORD` in `stack.env`.

The base stack uses **named volumes** (library, pg16data, model-cache, redisdata)
so it works when deployed from Portainer's web editor. An optional storage
override places finalized originals on an existing host filesystem.

## Configuration

| Item | Details |
|------|---------|
| **Port** | 2283 (proxied via Caddy; also bound to 127.0.0.1:2283 for localhost-only direct access) |
| **Network** | `ingress-public` for the server, the private stack network for dependencies, and internal `telemetry` for machine-learning health probes |
| **Images** | immich-server, immich-machine-learning, Valkey (Redis), Postgres with vector extension |
| **Env** | `DB_PASSWORD` required; `TZ`, `IMMICH_VERSION`, optional `IMMICH_CONFIG_FILE` (see `stack.env.example`) |
| **Storage** | Named volumes: `library` (application files), `pg16data`, `model-cache`, `redisdata`; optional `IMMICH_LIBRARY_PATH` for finalized originals |

Run `./prepare-stack.sh` before deployment to create the required shared networks.
Only `immich-machine-learning` joins `telemetry`, allowing Blackbox Exporter to
probe `http://immich-machine-learning:3003/ping`. Its inference port is not
published to the host. PostgreSQL and Valkey remain on the stack network.
An exporter on another network cannot resolve this Docker service hostname.

## Per-user originals on a host filesystem

The optional `docker-compose.storage.yml` binds `IMMICH_LIBRARY_PATH` to
`/data/library`. The main `library` named volume stays at `/data`, retaining
upload staging, thumbnails, transcoded videos, profiles and database dumps.
PostgreSQL, Valkey and the model cache retain their existing volumes.

Verify the intended filesystem is mounted and writable before creating an empty
destination, for example `/srv/media/photos/immich`. Set `IMMICH_LIBRARY_PATH`
in `stack.env`, then run `./prepare-stack.sh`. Preparation checks that the
directory exists and refreshes `.env`; it never creates this media directory.
The bind mount also disables automatic host-directory creation. An existing
directory alone does not prove a remote filesystem is mounted.

For a new deployment, select the override explicitly:

```bash
docker compose --env-file stack.env -f docker-compose.yml -f docker-compose.storage.yml up -d
```

Include both files for every subsequent recreation. Alternatively set
`COMPOSE_FILE=docker-compose.yml:docker-compose.storage.yml` in `stack.env` and
run preparation to refresh the generated `.env`. In Portainer, merge the
override into the stack definition and supply `IMMICH_LIBRARY_PATH` in Environment.

In **Administration → Settings → Storage Template**, choose **Custom** and keep
hash verification enabled. For date folders and sortable names that preserve the
original filename, use:

```text
{{y}}/{{MM}}/{{dd}}/{{y}}{{MM}}{{dd}}_{{HH}}{{mm}}{{ss}}_{{filename}}
```

Immich appends the extension and resolves name collisions with a sequence number.
For example, `alice/2026/10/31/20261031_143025_IMG_1234.jpg`. Finalized originals use:

```text
IMMICH_LIBRARY_PATH/<storage-label-or-user-id>/<date-and-filename-template>
```

In **Administration → Users → Edit**, assign each account a unique storage label,
such as `alice` or `bob`. Future users share the same mount and global template;
without a storage label, Immich uses their unique user ID. Labels affect disk
paths; Immich's own permissions still control who can see each user's photos.
Do not add the managed originals directory as an external library or edit its
files outside Immich.

Uploads first occupy local `/data/upload` until processing moves them to the
remote library. Keep local staging capacity available. Hash verification covers
the move across filesystems. Monitor free space on both local staging and remote
originals, since either filesystem can fill independently. See upstream
[custom locations](https://docs.immich.app/guides/custom-locations/) and
[storage templates](https://docs.immich.app/administration/storage-template/).

### Migrating an existing deployment

Stop application writers, record account/asset counts and file hashes, and back
up the database, application volume and affected configuration. Verify an
isolated restore before changing storage. Copy the existing named volume's
`library/` subtree, including its `.immich` marker, to the empty destination
while writers are stopped. Preserve metadata and verify copied bytes before
enabling the override. Keep the existing named volume for rollback.

Recreate only the server with both Compose files, then verify its mount, health,
signed-in access, record counts and baseline files. If changing an existing
user label or template, run **Storage Template Migration** from Job Queues to
move existing originals through Immich. Back up both the host originals path
and the main application volume, which can still contain unprocessed originals,
along with PostgreSQL. Database dumps alone do not contain the media.

If migration fails, stop writers and restore the previous Compose selection and
verified database/files as required. After new uploads have reached remote
storage, copy their originals back and verify them before removing the bind
mount. Simply dropping the override would hide those files from Immich.

## Version and upgrades

The server and machine-learning images default to [v3.3.5](https://github.com/immich-app/immich/releases/tag/v3.3.5).
`IMMICH_VERSION` overrides both tags. For Compose interpolation, pass it with
`docker compose --env-file stack.env ...`, set it in `.env`, or export it in the
shell. The service-level `env_file` does not select image tags. In Portainer,
set it in the stack Environment.

Before upgrading an existing v2 deployment, follow the [v3 migration guide](https://immich.app/blog/v3-migration).
It covers removed environment variables, the x86-64-v2 CPU requirement for
machine learning, and migration from pgvecto.rs to VectorChord. The database
image in this stack includes VectorChord, but an existing database's migration
must be verified before deploying v3.

Back up and verify restoration of the database and library before a live upgrade.
After deployment, verify login, asset counts, uploads, search, and existing media.
If rollback is needed after a database migration, restore the verified backup
with the prior compatible images and configuration.

## Google OAuth (login with Google)

To use Google as the login method:

### 1. Google Cloud Console

1. Go to [Google Cloud Console](https://console.cloud.google.com/) → **APIs & Services** → **Credentials**.
2. **Create credentials** → **OAuth client ID**.
3. Application type: **Web application**.
4. **Authorized redirect URIs**, add **all** of these (replace with your Immich URL and port if not using Caddy):
   - `https://immich.yourdomain.com/auth/login`
   - `https://immich.yourdomain.com/user-settings`
   - `app.immich:///oauth-callback` (required for mobile app)
   - If you use the mobile app and your provider doesn't allow custom schemes, also add:
     `https://immich.yourdomain.com/api/oauth/mobile-redirect`
5. Copy the **Client ID** and **Client secret**.

### 2. Immich Administration

1. Log in as admin → **Administration** → **Settings**.
2. Find **OAuth** and set:
   - **Enabled:** true
   - **Issuer URL:** `https://accounts.google.com`
   - **Client ID:** (from Google)
   - **Client secret:** (from Google)
   - **Scope:** `openid email profile`
   - **Signing algorithm:** RS256
   - **Button text:** e.g. "Sign in with Google"
   - **Auto register:** optional (create users on first Google sign-in)
   - **Auto launch:** optional (skip login page and go straight to Google)
   - **Mobile redirect:** if your Google client doesn't allow `app.immich:///oauth-callback`, enable **Mobile Redirect URI Override** and set it to `https://immich.yourdomain.com/api/oauth/mobile-redirect`, and add that URL to Google's redirect URIs.
3. Save. Test login on web and, if used, on the mobile app.

### 3. Optional: config file (e.g. for automation)

You can put OAuth and other options in a JSON/YAML config file and mount it into the server container, then set `IMMICH_CONFIG_FILE=/path/in/container/immich.json` in your env file (e.g. `stack.env` or Portainer Environment). Example OAuth section:

```json
"oauth": {
  "enabled": true,
  "issuerUrl": "https://accounts.google.com",
  "clientId": "YOUR_GOOGLE_CLIENT_ID",
  "clientSecret": "YOUR_GOOGLE_CLIENT_SECRET",
  "scope": "openid email profile",
  "buttonText": "Sign in with Google",
  "autoRegister": true,
  "mobileOverrideEnabled": false,
  "mobileRedirectUri": ""
}
```

Full config shape and options: https://immich.app/docs/install/config-file and **Administration → Settings** (copy from there).

## Cloudflare Access (OIDC)

If you already use **Cloudflare Zero Trust** with an identity provider (Google, GitHub, etc.), you can use Cloudflare as the OIDC provider for Immich so users log in via your existing Access flow.

### 1. Cloudflare Zero Trust – OIDC application

1. In [Cloudflare One](https://one.dash.cloudflare.com/) go to **Access** → **Applications** → **Add an application**.
2. Choose **OIDC** → **SaaS**.
3. **Application name:** e.g. `Immich`.
4. **Redirect URLs**, add **all** of these (use your Immich URL):
   - `https://immich.yourdomain.com/auth/login`
   - `https://immich.yourdomain.com/user-settings`
   - `app.immich:///oauth-callback` (for mobile app)
   - If the mobile app needs an HTTP redirect: `https://immich.yourdomain.com/api/oauth/mobile-redirect`
5. **Scopes:** ensure `openid`, `email`, and `profile` are included (default).
6. Create the application, then under **OIDC** copy:
   - **Client ID**
   - **Client secret**
   - **Issuer** (base URL): `https://<team-name>.cloudflareaccess.com/cdn-cgi/access/sso/oidc/<application-id>/`
     Your team name is under **Settings** → **Team name and domain**. The application ID is in the URL when you edit the app or in the issuer path.
7. Configure **Identity providers** and **Access policies** as usual, then save.

### 2. Immich Administration

1. Log in as admin → **Administration** → **Settings**.
2. Find **OAuth** and set:
   - **Enabled:** true
   - **Issuer URL:** your Cloudflare OIDC issuer, e.g.
     `https://<team-name>.cloudflareaccess.com/cdn-cgi/access/sso/oidc/<application-id>/`
     (Trailing slash is fine; Immich will use discovery.)
   - **Client ID:** (from Cloudflare)
   - **Client secret:** (from Cloudflare)
   - **Scope:** `openid email profile`
   - **Signing algorithm:** RS256
   - **Button text:** e.g. "Sign in with Cloudflare"
   - **Auto register:** optional (create users on first sign-in)
   - **Auto launch:** optional (skip Immich login page and go straight to Cloudflare)
   - **Mobile redirect:** if you use the mobile app and added the `/api/oauth/mobile-redirect` URL in Cloudflare, enable **Mobile Redirect URI Override** and set it to `https://immich.yourdomain.com/api/oauth/mobile-redirect`.
3. Save and test login (web and mobile if used).

### 3. Optional: config file (Cloudflare OAuth)

If you use a config file and mount it into the server, you can set the OAuth block to point at Cloudflare:

```json
"oauth": {
  "enabled": true,
  "issuerUrl": "https://YOUR_TEAM.cloudflareaccess.com/cdn-cgi/access/sso/oidc/YOUR_APP_ID/",
  "clientId": "YOUR_CLIENT_ID",
  "clientSecret": "YOUR_CLIENT_SECRET",
  "scope": "openid email profile",
  "buttonText": "Sign in with Cloudflare",
  "autoRegister": true,
  "mobileOverrideEnabled": false,
  "mobileRedirectUri": ""
}
```

Replace `YOUR_TEAM`, `YOUR_APP_ID`, and the client credentials with the values from your Cloudflare Access OIDC application.

## Caddy reverse proxy

Example Caddy vhost (e.g. in your Caddyfile):

```
immich.yourdomain.com {
  reverse_proxy immich-server:2283
}
```

Ensure the Immich stack is on the `ingress-public` network so Caddy can reach `immich-server:2283`.

## Start

From this directory: `docker compose up -d`.
In Portainer: Stacks → Add stack → paste the compose and set `DB_PASSWORD` (and optionally `TZ`, `IMMICH_VERSION`) in **Environment**.
