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
   - **Domain:** select your zone (e.g. `bolens.dev`).
   - So the application domain is `portainer.bolens.dev`—the same hostname as in your tunnel’s Public Hostnames.
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

Users hitting `https://portainer.bolens.dev` will be sent to your IdP to sign in; after that they reach your app.

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

- When adding the application, you can set **Application domain** to a path, e.g. `portainer.bolens.dev/admin`.
- Or create a second application with the same subdomain but a path, and attach different policies. Path-based apps work alongside the root application.

---

## 4. No Caddy or tunnel config changes

- **Tunnel:** Keep your existing Public Hostnames (e.g. `portainer.bolens.dev` → `localhost:80`). No change.
- **Caddy:** No change. Access runs in front of the tunnel; by the time traffic reaches Caddy it’s already been allowed by Access. You do **not** need to add Access headers in Caddy unless an app explicitly uses them (e.g. for username).

If you previously used **basic auth** in Caddy for that hostname, you can remove it and rely on Access instead, or keep both (Access first, then optional app-level auth).

---

## 5. Optional: pass identity to the app

Access can send user identity in headers (e.g. `CF-Access-JWT-Assertion` or headers you configure). Most homelab apps don’t need this; they use their own login. If you want to use JWT or headers, see [Cloudflare Access – JWT validation](https://developers.cloudflare.com/cloudflare-one/identity/users/validating-json/) and **Access** → **Applications** → your app → **Overview** → **Application identity**.

---

## Summary

| Step | Where | What |
|------|--------|------|
| 1 | Zero Trust → Access → Applications | Add application → Self-hosted → same subdomain as tunnel hostname |
| 2 | Same app → Policies | Add Allow policy: SSO (IdP) or One-time PIN or email list |
| 3 | (Optional) | Restrict by path; remove Caddy basic auth for that hostname |
| 4 | — | Tunnel and Caddy unchanged |

**References**

- [Cloudflare Access – Applications](https://developers.cloudflare.com/cloudflare-one/applications/)
- [Cloudflare Access – Policies](https://developers.cloudflare.com/cloudflare-one/policies/access/)
- [Identity providers (Zero Trust)](https://developers.cloudflare.com/cloudflare-one/identity/idp-integration/)
