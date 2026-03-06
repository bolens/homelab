# Keycloak – identity provider / SSO

[Keycloak](https://www.keycloak.org/) is an open-source identity and access management solution. It provides SSO, identity brokering, and user management, and can act as an OpenID Connect / OAuth 2.0 / SAML IdP for your other stacks (e.g. Outline, Grafana, Immich, Linkwarden).

**Website:** https://www.keycloak.org/  
**Docs:** https://www.keycloak.org/documentation  
**Container docs:** https://www.keycloak.org/server/containers  

## Quick start

1. **Environment**
   - From this directory: copy `stack.env.example` → `stack.env`.
   - Set:
     - `POSTGRES_PASSWORD` – strong DB password,
     - `KEYCLOAK_ADMIN_PASSWORD` – admin console password,
     - `KC_HOSTNAME` – public URL behind Caddy (e.g. `https://keycloak.yourdomain.com`).
2. **Deploy**

   ```bash
   docker compose up -d
   ```

3. **Access**
   - Keycloak listens on port `8080` inside the container.
   - Put it behind Caddy on the `monitor` network, e.g.:
     - `https://keycloak.yourdomain.com` → `keycloak:8080`
   - Then open the URL and log in with `KEYCLOAK_ADMIN` / `KEYCLOAK_ADMIN_PASSWORD`.

## Configuration

| Item        | Details                                                                        |
| ----------- | ------------------------------------------------------------------------------ |
| **Access**  | Via Caddy (reverse-proxy to `keycloak:8080`)                                  |
| **Network** | `monitor` (so apps and Caddy can reach it) + default internal network for DB  |
| **Images**  | `quay.io/keycloak/keycloak:latest`, `postgres:16-alpine`                      |
| **Storage** | `keycloak_pg_data` volume for Postgres data                                   |
| **Caddy**   | See [stacks/caddy/Caddyfile.example](../caddy/Caddyfile.example) for `keycloak.yourdomain.com` → `keycloak:8080` |

## Integrations

- Use Keycloak as an OIDC / OAuth 2.0 IdP for:
  - Stacks that support OIDC natively (e.g. Outline, Grafana, Immich, Linkwarden, LibreChat, etc.).
  - Cloudflare Access (Zero Trust) if you want Keycloak to back Access as an IdP.
- Typical pattern:
  - Create a **realm** for your homelab.
  - Create **clients** for each app (set redirect URIs to the app’s Caddy URL).
  - Configure each app with the corresponding client ID/secret and discovery URL.

## Notes

- This stack uses Postgres for persistence. For production, consider pinning a specific Keycloak image tag instead of `latest`.
- When changing `KC_HOSTNAME` or TLS settings, restart the stack to ensure Keycloak picks up the new configuration.

