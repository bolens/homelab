# Immich

Self-hosted photo and video backup: upload from phones and the web, face detection, search, and albums.

**Website:** https://immich.app  
**Docs:** https://immich.app/docs  
**GitHub:** https://github.com/immich-app/immich

## Quick start

1. **Environment**
   - Copy `.env.example` to `.env`.
   - Set `DB_PASSWORD` to a strong alphanumeric value (e.g. `openssl rand -hex 16 | tr -d '\n' | head -c 24`).
   - Set `TZ` to your timezone if different from America/Denver.
2. **Deploy:** `docker compose up -d` (or add the stack in Portainer and set the same vars in the stack Environment).
3. **First run:** Open Immich via Caddy (or http://host:2283), create the admin user, then configure OAuth and other options in **Administration → Settings**.

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
