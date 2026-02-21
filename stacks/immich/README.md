# Immich

Self-hosted photo and video backup: upload from phones and the web, face detection, search, and albums.

**Website:** https://immich.app  
**Docs:** https://immich.app/docs  
**GitHub:** https://github.com/immich-app/immich

## Quick start

1. **Environment**
   - Copy `.env.example` to `.env`.
   - Generate and set `DB_PASSWORD` (see **Generating keys and secrets** below).
   - Set `TZ` to your timezone if different from America/Denver.
2. **Deploy:** `docker compose up -d` (or add the stack in Portainer and set the same vars in the stack Environment).
3. **First run:** Open Immich via Caddy (or http://host:2283), create the admin user, then configure OAuth and other options in **Administration → Settings**.

## Generating keys and secrets

**DB_PASSWORD** (required) – Postgres password. Must be alphanumeric only (no spaces). Generate:

```bash
openssl rand -hex 16 | tr -d '\n' | head -c 24
```

Set the output as `DB_PASSWORD` in `.env`.

The stack uses **named volumes** (library, pgdata, model-cache, redisdata) so it works when deployed from Portainer’s web editor.

## Configuration

| Item | Details |
|------|---------|
| **Port** | 2283 (proxied via Caddy; host port exposed for direct access if needed) |
| **Network** | `monitor` (external) — Caddy can reverse-proxy to `immich-server:2283` |
| **Images** | immich-server, immich-machine-learning, Valkey (Redis), Postgres with vector extension |
| **Env** | `DB_PASSWORD` required; `TZ`, `IMMICH_VERSION`, optional `IMMICH_CONFIG_FILE` (see .env.example) |
| **Storage** | Named volumes: `library` (uploads), `pgdata`, `model-cache`, `redisdata` |

## Google OAuth (login with Google)

To use Google as the login method:

### 1. Google Cloud Console

1. Go to [Google Cloud Console](https://console.cloud.google.com/) → **APIs & Services** → **Credentials**.
2. **Create credentials** → **OAuth client ID**.
3. Application type: **Web application**.
4. **Authorized redirect URIs** — add **all** of these (replace with your Immich URL and port if not using Caddy):
   - `https://immich.yourdomain.com/auth/login`
   - `https://immich.yourdomain.com/user-settings`
   - `app.immich:///oauth-callback` (required for mobile app)
   - If you use the mobile app and your provider doesn’t allow custom schemes, also add:  
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
   - **Button text:** e.g. “Sign in with Google”  
   - **Auto register:** optional (create users on first Google sign-in)  
   - **Auto launch:** optional (skip login page and go straight to Google)  
   - **Mobile redirect:** if your Google client doesn’t allow `app.immich:///oauth-callback`, enable **Mobile Redirect URI Override** and set it to `https://immich.yourdomain.com/api/oauth/mobile-redirect`, and add that URL to Google’s redirect URIs.
3. Save. Test login on web and, if used, on the mobile app.

### 3. Optional: config file (e.g. for automation)

You can put OAuth and other options in a JSON/YAML config file and mount it into the server container, then set `IMMICH_CONFIG_FILE=/path/in/container/immich.json` in `.env`. Example OAuth section:

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
4. **Redirect URLs** — add **all** of these (use your Immich URL):
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
   - **Button text:** e.g. “Sign in with Cloudflare”  
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

Ensure the Immich stack is on the `monitor` network so Caddy can reach `immich-server:2283`.

## Start

From this directory: `docker compose up -d`.  
In Portainer: Stacks → Add stack → paste the compose and set `DB_PASSWORD` (and optionally `TZ`, `IMMICH_VERSION`) in **Environment**.
