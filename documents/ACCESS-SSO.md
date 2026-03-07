# Cloudflare Access SSO for tunnel subdomains

Use **Cloudflare Zero Trust Access** to put a login (SSO or one-time PIN) in front of subdomains that are already exposed via your Cloudflare Tunnel. No Caddy or app config changes are required—Access runs at the Cloudflare edge before traffic reaches your tunnel.

**Typical use:** Replace or supplement basic auth (or app-only login) with Google/GitHub/Okta SSO or email one-time PIN for hostnames like `portainer.yourdomain.com`, `paperless.yourdomain.com`, etc.

---

## Prerequisites

- A **Cloudflare Tunnel** already set up and running (see the [cloudflare-tunnel stack README](../stacks/cloudflare-tunnel/README.md)).
- **Public Hostnames** in the tunnel pointing at your app (e.g. `portainer.yourdomain.com` → HTTP → `localhost:80` so Caddy routes by host).
- The domain (e.g. `yourdomain.com`) added to Cloudflare with DNS managed by Cloudflare (required for the tunnel).

Access is part of **Cloudflare Zero Trust**. The free tier includes a limited number of Access users; see [Cloudflare Zero Trust pricing](https://www.cloudflare.com/plans/zero-trust/).

---

## 1. Open Zero Trust and create an Access application

1. In [Cloudflare Dashboard](https://dash.cloudflare.com), go to **Zero Trust** (or [one.dash.cloudflare.com](https://one.dash.cloudflare.com)).
2. Choose **Access** → **Applications** → **Add an application**.
3. Choose **Self-hosted**.
4. **Application name:** e.g. `Portainer` (for your reference).
5. **Session Duration:** how long before users must sign in again (e.g. 24 hours).
6. **Application domain:** use the **exact subdomain** that your tunnel already exposes:
  - **Subdomain:** e.g. `portainer` (or whatever hostname you use).
  - **Domain:** select your zone (e.g. `yourdomain.com`).
  - So the application domain is `portainer.yourdomain.com`—the same hostname as in your tunnel’s Public Hostnames.
7. Click **Save**.

Traffic to that hostname will now be checked by Access before it is sent through the tunnel to Caddy and your app.

---

## 2. Add a policy (who can log in)

Right after saving the application you’ll be prompted to add a policy. You can also go to **Access** → **Applications** → your app → **Policies** and add or edit there.

### Option A: SSO (Google, GitHub, Azure AD, Okta, etc.)

1. In Zero Trust go to **Settings** → **Authentication** → **Login methods**.
2. Add and configure an **identity provider** (e.g. Google, GitHub, Azure AD, Okta, or generic OIDC/SAML). Follow Cloudflare’s prompts (redirect URLs, client ID/secret, etc.).
3. Back in **Access** → **Applications** → your app → **Policies** → **Add a policy**:
  - **Policy name:** e.g. `Allow team SSO`.
  - **Action:** **Allow**.
  - **Configure rules:**
    - **Include** → e.g. **Emails ending in** → `@yourdomain.com`,  
    or **Identity provider group** if you use an IdP that sends groups (e.g. Google Workspace, Okta).
  - Add **Require** or **Exclude** rules if needed (e.g. require a specific country or exclude certain emails).
4. Save.

Users hitting `https://portainer.yourdomain.com` will be sent to your IdP to sign in; after that they reach your app.

### Option B: One-time PIN (no IdP)

Good for a small number of users without setting up an IdP:

1. In **Policies** → **Add a policy**:
  - **Action:** **Allow**.
  - **Include** → **Login Methods** → **One-time PIN**.
2. Save.

Users will get a code by email; they enter it and then can access the app. No SSO provider required.

### Option C: Allow specific emails (with any login method)

- **Include** → **Emails** or **Emails ending in** and list the addresses or domain. Users must log in with an IdP or one-time PIN; Access then checks that their email matches.

---

## 3. (Optional) Restrict by path

To protect only part of a hostname (e.g. `/admin`):

- When adding the application, you can set **Application domain** to a path, e.g. `portainer.yourdomain.com/admin`.
- Or create a second application with the same subdomain but a path, and attach different policies. Path-based apps work alongside the root application.

---

## 3b. Special case: Headscale (keep domain accessible for Tailscale clients)

**Headscale’s hostname must stay reachable** by Tailscale clients (phones, laptops, servers) for login and registration. Those clients talk to the server over HTTPS but are not browsers—if you put Cloudflare Access on the **entire** hostname, they would get an HTML login page instead of the API response and **client login would break**.

**Ways to protect Headscale while keeping the domain usable for clients:**

1. **Don’t put Access on the Headscale hostname.** Rely on Headscale’s own auth (pre-auth keys, OIDC if you use it) and exposure only via your tunnel. The hostname is “protected” by not being widely advertised and by requiring a valid key to join the tailnet.
2. **Protect only a path (if you run an admin UI on the same host).** Headscale has no built-in web UI. If you run a separate admin UI (e.g. Headplane, headscale-admin) on the **same** hostname under a path (e.g. `headscale.yourdomain.com/admin`), create an Access application **only for that path** (`headscale.yourdomain.com/admin`). Then only `/admin` requires SSO; Tailscale client traffic to `/register`, `/key`, `/ts`, etc. is unchanged and clients can log in.
3. **Separate hostname for admin.** Run the admin UI on a different hostname (e.g. `headscale-admin.yourdomain.com`) and put Access on that hostname only. Leave `headscale.yourdomain.com` without an Access application so clients can reach it.

**Summary:** Do **not** add an Access application for the full `headscale.yourdomain.com` if Tailscale clients need to reach it. Use path-based Access only for an admin path, or a separate admin hostname, or no Access and rely on Headscale auth + exposure control.

---

## 4. No Caddy or tunnel config changes

- **Tunnel:** Keep your existing Public Hostnames (e.g. `portainer.yourdomain.com` → `localhost:80`). No change.
- **Caddy:** No change. Access runs in front of the tunnel; by the time traffic reaches Caddy it’s already been allowed by Access. You do **not** need to add Access headers in Caddy unless an app explicitly uses them (e.g. for username).

If you previously used **basic auth** in Caddy for that hostname, you can remove it and rely on Access instead, or keep both (Access first, then optional app-level auth).

---

## 5. Optional: pass identity to the app

Access can send user identity in headers (e.g. `CF-Access-JWT-Assertion` or headers you configure). Most homelab apps don’t need this; they use their own login. If you want to use JWT or headers, see [Cloudflare Access – JWT validation](https://developers.cloudflare.com/cloudflare-one/identity/users/validating-json/) and **Access** → **Applications** → your app → **Overview** → **Application identity**.

---

## Services and SSO

### Cloudflare Access (edge SSO)

**Any service** exposed via your Cloudflare Tunnel can be protected with Cloudflare Access (SSO or one-time PIN). You add an Access application per hostname (e.g. `portainer.yourdomain.com`); no change is required in the app or Caddy. Stacks in this repo that are typically exposed behind the tunnel therefore all “support” SSO in the sense that you can put Access in front of them.

**Currently behind Access (this setup):** **cadvisor**, **dozzle**. Other hostnames can be added the same way in Zero Trust → Access → Applications.

| Service / stack                           | Behind Access? | Notes                                                              |
| ----------------------------------------- | -------------- | ------------------------------------------------------------------ |
| **adguard-home**                          | Yes            | Protect DNS/admin UI hostname (e.g. adguard-home.yourdomain.com or dns.yourdomain.com). |
| **audiobookshelf**                        | Yes            | Protect hostname.                                                  |
| **alertmanager**                          | Yes            | Protect hostname if exposed; usually internal.                     |
| **archivebox**                            | Yes            | Protect hostname; control anonymous access via `PUBLIC_INDEX`, `PUBLIC_SNAPSHOTS`, and `PUBLIC_ADD_VIEW`. |
| **authentik**                             | Yes            | Protect hostname; `AUTHENTIK_HOST` must match or OAuth/redirects break. |
| **asf**                                   | Yes            | Protect ASF IPC hostname; set `IPCPassword` in ASF.json.           |
| **actual-budget**                         | Yes            | Protect hostname; set server URL in Actual desktop/mobile app to that URL. |
| **baserow**                               | Yes            | Protect hostname; set `BASEROW_PUBLIC_URL` to that URL.            |
| **bookstack**                             | Yes            | Protect hostname; set `APP_URL` to that URL; change default admin password. |
| **calibre-web**                           | Yes            | Protect hostname; app has its own login (change default admin password). |
| **caddy**                                 | Yes            | Reverse proxy; protect the hostnames that Caddy serves.            |
| **cloudflare-tunnel**                     | N/A            | Tunnel itself; Access runs at the edge before traffic reaches it.  |
| **convertx**                              | Yes            | Protect hostname; app has accounts (JWT); set `ACCOUNT_REGISTRATION=false` after first user. |
| **diun** / **watchtower**                 | Yes            | Protect if exposed via tunnel.                                     |
| **dozzle**                                | Yes            | Protect Dozzle hostname; optional `users.yaml` auth in app.        |
| **freshrss**                              | Yes            | Protect hostname.                                                  |
| **grafana**                               | Yes            | Protect Grafana hostname; set `GF_SERVER_ROOT_URL` to that URL.    |
| **guacamole**                             | Yes            | Protect Guacamole hostname; app has its own login, Access adds an extra SSO/OTP gate. |
| **headscale**                             | Path or none   | See [§3b Headscale](#3b-special-case-headscale-keep-domain-accessible-for-tailscale-clients): do not protect full hostname or client login breaks. Protect only an admin path or separate admin hostname. |
| **home-assistant**                        | Yes            | Protect hostname (e.g. home-assistant.yourdomain.com or home.yourdomain.com). |
| **homarr**                                | Yes            | Protect hostname (dashboard).                                       |
| **immich**                                | Yes            | Protect Immich hostname; OAuth redirect URIs must use that URL.    |
| **infisical**                             | Yes            | Protect hostname; `SITE_URL` must match or OAuth breaks.           |
| **it-tools**                              | Yes            | Protect hostname (no app login).                                   |
| **kasm**                                  | Yes            | Protect kasm.yourdomain.com and kasm-setup.yourdomain.com; app has its own login (admin@kasm.local, user@kasm.local). |
| **komga**                                 | Yes            | Protect hostname; create first user in the web UI.                |
| **kavita**                                | Yes            | Protect hostname; run setup wizard and create users in the web UI. |
| **lanraragi**                             | Yes            | Protect hostname; no built-in auth; use Access or set a password in Settings. |
| **linkstack**                             | Yes            | Protect hostname.                                                  |
| **linkwarden**                            | Yes            | Protect hostname; set `NEXTAUTH_URL` to that URL.                  |
| **linkding**                              | Yes            | Protect hostname.                                                  |
| **librechat**                             | Yes            | Protect LibreChat hostname for social/OAuth redirects.             |
| **mealie**                                | Yes            | Protect hostname; set `BASE_URL` to that URL.                      |
| **meilisearch**                           | Yes            | Protect hostname if exposing search API; set `MEILI_MASTER_KEY` when production. |
| **mylar3**                                | Yes            | Protect Mylar3 hostname; configure download clients and indexers in the UI. |
| **navidrome**                             | Yes            | Protect Navidrome hostname; optional `ND_BASEURL` should match it. |
| **n8n**                                   | Yes            | Protect n8n hostname; ensure `N8N_HOST` / `WEBHOOK_URL` match.     |
| **nzbget**                                | Yes            | Protect NZBGet hostname; web UI is authenticated but Access adds an outer SSO/OTP layer. |
| **nzbhydra2**                             | Yes            | Protect NZBHydra 2 hostname; indexer admin UI benefits from SSO/OTP. |
| **ntfy**                                  | Yes            | Protect hostname; set `NTFY_BASE_URL` to that URL.                 |
| **ntopng**                                | Yes            | Protect hostname if exposed (traffic analytics UI).                 |
| **open-notebook**                         | Yes            | Protect hostname; optional UI password in app.                     |
| **open-webui**                            | Yes            | Protect Open WebUI hostname for OAuth redirects.                   |
| **paperless-ngx**                         | Yes            | Protect Paperless hostname.                                        |
| **password-pusher**                       | Yes            | Protect hostname; optional logins use SMTP (see smtp-relay stack). |
| **perplexica**                            | Yes            | Protect hostname.                                                  |
| **portainer** (if used)                   | Yes            | Common use case; protect e.g. `portainer.yourdomain.com`.          |
| **privatebin**                            | Yes            | Protect hostname.                                                  |
| **prometheus** / **cadvisor**             | Yes            | Usually internal; protect if you expose them.                      |
| **searx-ng**                              | Yes            | Protect hostname.                                                  |
| **slink**                                 | Yes            | Protect hostname; set `ORIGIN` to that URL; optional user approval. |
| **snipe-it**                              | Yes            | Protect hostname; set `APP_URL` to that URL.                       |
| **stirling-pdf**                          | Yes            | Protect hostname (PDF tools).                                       |
| **sonarr**                                | Yes            | Protect Sonarr hostname; use Access as an outer auth layer in front of app auth. |
| **radarr**                                | Yes            | Protect Radarr hostname; use Access as an outer auth layer in front of app auth. |
| **lidarr**                                | Yes            | Protect Lidarr hostname; use Access as an outer auth layer in front of app auth. |
| **readarr**                               | Yes            | Protect Readarr hostname; use Access as an outer auth layer in front of app auth. |
| **romm**                                  | Yes            | Protect RomM hostname; set `ROMM_BASE_URL` to that URL.                            |
| **bazarr**                                | Yes            | Protect Bazarr hostname; subtitles and media library details stay behind SSO/OTP. |
| **prowlarr**                              | Yes            | Protect Prowlarr hostname; indexer API keys and credentials stay behind SSO/OTP. |
| **plex**                                  | Yes            | Protect Plex web hostname if exposed via tunnel; Plex also has its own account auth. |
| **jellyfin**                              | Yes            | Protect Jellyfin hostname; app has its own accounts, Access adds an outer SSO/OTP layer. |
| **rtorrent-flood**                        | Yes            | Protect Flood UI hostname; torrent and tracker details are sensitive and should sit behind SSO/OTP. |
| **emby**                                  | Yes            | Protect Emby hostname; app has its own accounts, Access adds an outer SSO/OTP layer. |
| **firefly-iii**                           | Yes            | Protect hostname; set `APP_URL` to that URL. |
| **gitea**                                 | Yes            | Protect hostname; set `GITEA_ROOT_URL` to that URL; OAuth apps use it for redirects. |
| **hedgedoc**                              | Yes            | Protect hostname; set `CMD_DOMAIN` to match. |
| **joplin-server**                         | Yes            | Protect hostname; set `APP_BASE_URL` to that URL. |
| **keycloak**                              | Yes            | Protect hostname; `KC_HOSTNAME` must match or OAuth/redirects break. |
| **mailpit**                               | Yes            | Protect hostname; shows caught emails (internal-only SMTP).                          |
| **minio**                                 | Yes            | Protect console hostname (e.g. minio.yourdomain.com); optional `MINIO_SERVER_URL`. |
| **nextcloud**                             | Yes            | Protect hostname; add hostname to `NEXTCLOUD_TRUSTED_DOMAINS`. |
| **outline**                               | Yes            | Protect hostname; set `URL` to that URL; IdP redirect URIs use it. |
| **scrutiny**                              | Yes            | Protect hostname. |
| **seafile**                               | Yes            | Protect hostname; set `SEAFILE_SERVER_HOSTNAME` to match. |
| **syncthing**                             | Yes            | Protect hostname. |
| **vaultwarden**                           | Yes            | Protect Vaultwarden hostname; optional `ADMIN_TOKEN` for `/admin`. |
| **vikunja**                               | Yes            | Protect hostname; set `VIKUNJA_SERVICE_PUBLICURL` to that URL (with trailing slash). |
| **woodpecker-ci**                         | Yes            | Protect hostname (e.g. ci.yourdomain.com); Gitea OAuth redirect must match. |
| **web-check**                             | Yes            | Protect hostname.                                                  |
| **yourls**                                | Yes            | Protect shortener hostname(s).                                     |
| **zigbee2mqtt**                           | Yes            | Protect Zigbee2MQTT admin UI hostname.                             |


### Native app SSO (OAuth / OIDC / SAML / LDAP)

These services support **in-app** SSO configuration (Google, GitHub, OIDC, LDAP, etc.). You can use them together with Cloudflare Access (Access in front, then app login) or rely on app SSO only.


| Service           | Native SSO options                                           | Where to configure                                                                                                    |
| ----------------- | ------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------- |
| **Grafana**       | OAuth (generic, Google, GitHub, etc.), LDAP                  | Grafana UI: Configuration → Auth; or `GF_AUTH_`* env vars (see Grafana docs)                                          |
| **Immich**        | Google OAuth, **Cloudflare Access OIDC** (Zero Trust as IdP) | Administration → Settings → OAuth; or `IMMICH_CONFIG_FILE` with OAuth block                                           |
| **Infisical**     | Google, GitHub, GitLab OAuth                                 | `CLIENT_ID_*_LOGIN` / `CLIENT_SECRET_*_LOGIN` in `.env`; see Infisical docs                                           |
| **Linkwarden**    | Many SSO providers (NextAuth)                                | Env vars; see [Linkwarden env docs](https://docs.linkwarden.app/self-hosting/environment-variables) and `.env.sample` |
| **LibreChat**     | OAuth2, LDAP, social login (Google, Microsoft)               | Settings → Authentication; `config/auth.json`, `config/librechat.yaml`                                                |
| **n8n**           | OIDC, LDAP (self-hosted)                                     | n8n docs / app settings                                                                                               |
| **Open WebUI**    | OAuth, LDAP/AD                                               | Settings → Authentication                                                                                             |
| **Paperless-ngx** | OIDC (optional)                                              | App config / env; see [Paperless-ngx configuration](https://docs.paperless-ngx.com/configuration/)                    |


### No native SSO (Access or app password only)


| Service                                                   | Auth model                                                         |
| --------------------------------------------------------- | ------------------------------------------------------------------ |
| **convertx**, **it-tools**, **privatebin**, **searx-ng**, **slink**, **web-check** | No login or minimal / app accounts only; use Access to protect hostname |
| **Dozzle**                                                | Optional built-in auth via `users.yaml` (no OAuth/LDAP)            |
| **Open Notebook**                                         | Optional `OPEN_NOTEBOOK_PASSWORD`                                  |
| **Password Pusher**                                       | Optional user logins (SMTP for confirmation); no IdP SSO           |
| **Vaultwarden**                                           | Bitwarden-compatible login; optional `ADMIN_TOKEN` for admin panel |
| **YOURLS**                                                | `YOURLS_USER` / `YOURLS_PASS` (admin login)                        |


---

## Summary


| Step | Where                              | What                                                              |
| ---- | ---------------------------------- | ----------------------------------------------------------------- |
| 1    | Zero Trust → Access → Applications | Add application → Self-hosted → same subdomain as tunnel hostname |
| 2    | Same app → Policies                | Add Allow policy: SSO (IdP) or One-time PIN or email list         |
| 3    | (Optional)                         | Restrict by path; remove Caddy basic auth for that hostname       |
| 4    | —                                  | Tunnel and Caddy unchanged                                        |


**References**

- [Cloudflare Access – Applications](https://developers.cloudflare.com/cloudflare-one/applications/)
- [Cloudflare Access – Policies](https://developers.cloudflare.com/cloudflare-one/policies/access/)
- [Identity providers (Zero Trust)](https://developers.cloudflare.com/cloudflare-one/identity/idp-integration/)

