# SearXNG

Privacy-respecting metasearch engine. Aggregates results from multiple search engines.

**Website:** https://docs.searxng.org  
**Docs:** https://docs.searxng.org  
**GitHub:** https://github.com/searxng/searxng  
**Docker image:** https://hub.docker.com/r/searxng/searxng  
**Releases:** https://github.com/searxng/searxng/releases  

## Quick start

1. Run `./prepare-stack.sh` (creates `stack.env` and copies `settings.yml.example` to your configured `SEARXNG_SETTINGS_PATH` when missing).
2. Set a secret via environment (required). Generate and set `SEARXNG_SECRET` (see **Generating keys and secrets** below).
3. Set `SEARXNG_BASE_URL` in `stack.env` to the same HTTPS URL you use in Caddy (so result links and the UI resolve correctly).
4. Deploy: `docker compose --env-file stack.env up -d` (or deploy the stack in Portainer with the same variables).
5. Copy `caddy_snippet.conf.example` to your Caddy includes as `caddy_snippet.conf`, edit hostnames, then reload Caddy.
6. Access via Caddy at your public hostname (example: `https://search.example.com`).

## Generating keys and secrets

**SEARXNG_SECRET** (required) – used for signing. Generate:

```bash
openssl rand -hex 32
```

Set the output as `SEARXNG_SECRET` in `stack.env` or in the Portainer stack Environment.

Config is loaded from a host file path (`SEARXNG_SETTINGS_PATH`, default: `~/.config/searx-ng/settings.yml`) and bind-mounted to `/etc/searxng/settings.yml`. This keeps API/search settings (including JSON format for Perplexica) persistent across restarts and updates. Secret, base URL, and Redis URL are still set by environment variables.

## Configuration

| Item | Details |
|------|---------|
| **Port** | 8080 (proxied via Caddy) |
| **Network** | `ingress-public` for Caddy; private default network for Valkey |
| **Image** | `searxng/searxng:latest` |
| **Config** | Bind mount `${SEARXNG_SETTINGS_PATH}` -> `/etc/searxng/settings.yml`; override secret/base URL/redis via env vars |

## Start

From this directory: `./prepare-stack.sh && docker compose --env-file stack.env up -d`.

## Portainer

- Preferred: **Stacks** → **Add stack** → **Repository**, compose path `stacks/searx-ng/docker-compose.yml`.
- On the Docker host, run `./prepare-stack.sh` first so `stack.env`, `caddy_snippet.conf`, and the host `settings.yml` exist.
- In Portainer's stack environment, set at least `SEARXNG_SECRET`, `SEARXNG_BASE_URL` (public HTTPS URL), and `SEARXNG_SETTINGS_PATH` (absolute path on the host to `settings.yml`).
- Attach SearXNG to `ingress-public` so Caddy can reach `searxng:8080`.
- Do not publish HTTP ports from this stack if Caddy is the front door.

## Backup

- Backup `${SEARXNG_SETTINGS_PATH}` (engine/search config) and Docker volumes `searxng_data`, `searxng_valkey_data`.
- Recommended cadence: weekly for config + cache snapshots, and before major SearXNG upgrades.

## Optional 4get-hijacked engines

An experimental, hardened overlay integrates selected
[`4get-hijacked`](https://github.com/cra88y/4get-hijacked) scrapers as custom
SearXNG engines. It is opt-in because the wrapper project does not publish a
license or ready-to-run sidecar image. Its 4get dependency is AGPLv3-only.
Review both projects before deployment and do not redistribute the unlicensed
wrapper without permission from its author.

The local build removes upstream's unpinned Git clone and TLS-verification
bypass. Both source trees must be operator-managed, clean Git checkouts at the
documented commits. Base images are pinned by digest and the curl-impersonate
archive is verified by SHA-256. The sidecar runs non-root with a read-only
filesystem, all capabilities dropped, and no published port. The derived
SearXNG image copies custom Python engines during build instead of running the
application container as root. Local build patches also authenticate sidecar
requests, cap request/result sizes, allowlist scraper methods, escape rendered
content, and reject media/result URLs that resolve to non-public addresses.
The build fails if these patches no longer apply to the pinned source.

Enabling private-network and HTTP outbound access is limited to the overlay
but expands what SearXNG engines can reach, so do not install untrusted engine
modules. Debian packages still resolve at build time from signed repositories;
retain the built local image if you need byte-for-byte rollback.

1. Clone and pin both reviewed source revisions over verified TLS:

   ```bash
   git clone https://github.com/cra88y/4get-hijacked.git ~/src/4get-hijacked
   git -C ~/src/4get-hijacked checkout c7a3cd7789db9fd406053db6f3a022189560a534
   git clone https://git.lolcat.ca/lolcat/4get.git ~/src/4get
   git -C ~/src/4get checkout 8328d93b17de34c255673c2b98be7eb0f828f6c5
   ```

2. Set both source paths and revisions in `stack.env`, generate
   `FOURGET_SIDECAR_SECRET` with `openssl rand -hex 32`, export that file's
   values without printing them, then run the mandatory clean-checkout guard:

   ```bash
   set -a
   source stack.env
   set +a
   ./verify-4get-sources.sh
   ```

3. Merge the entries from `settings-4get-additions.yml.example` into the
   top-level `engines:` list in the configured `settings.yml`. Do not replace
   the list or expose proxy credentials in committed files.
4. Build and deploy the base file with the opt-in overlay:

   ```bash
   docker compose --env-file stack.env \
     -f docker-compose.yml -f docker-compose.4get.yml \
     up -d --build
   ```

The overlay enables Brave, DuckDuckGo, Marginalia, Mojeek, Mwmbl, Wiby, Yep,
and YouTube wrappers. Google CSE remains available as a disabled wrapper while
the native Google CSE engine provides the default Google-backed coverage. The
direct Google wrapper remains disabled because it is unfinished in the pinned
upstream revision. The upstream sidecar accepts `FOURGET_PROXIES`, but
proxy URLs may contain credentials and must be supplied only through private
runtime configuration. This deployment accepts comma-separated HTTP(S) URLs
with explicit ports, for example `http://user:password@proxy.example:8080`;
percent-encode reserved characters in credentials.

The sidecar secret is required by Compose and must be identical in both
containers. Do not expose the sidecar port or reuse this value for another
service. Its basic health endpoint remains unauthenticated because it is only
reachable on the private Compose network.

The curl-impersonate v0.6.1 archive is pinned to SHA-256
`cf68ce8d4fd5a848cb62fd782c6eb6c8a17d473adba658198e2528ce48923c12`.
Review and update that checksum deliberately when changing the archive.

## Troubleshooting

### Searches return no results

Open the **Engines** tab on a results page and check for timeouts, rate limits,
or CAPTCHAs. Public engines can reject a shared datacenter egress IP even when
SearXNG itself is healthy. The example settings explicitly enable Bing,
DuckDuckGo, Brave, Yahoo, and Google CSE as a diverse general-search set, and
disable general providers that commonly reject server traffic. The direct
Google HTML engine is disabled because current upstream versions mark it
inactive and its parser returns no results. Google CSE is the working,
Google-backed fallback and does not require a local API key.

`prepare-stack.sh` preserves an existing settings file. Existing deployments
must add the following block to their configured `SEARXNG_SETTINGS_PATH`, then
recreate the SearXNG service:

```yaml
engines:
  - name: bing
    engine: bing
    shortcut: bi
    disabled: false
  - name: duckduckgo
    disabled: false
  - name: brave
    disabled: false
  - name: yahoo
    disabled: false
  - name: google
    disabled: true
  - name: google cse
    disabled: false
  - name: startpage
    disabled: true
  - name: qwant
    disabled: true
  - name: yep
    disabled: true
  - name: mojeek
    disabled: true
```

### Cloudflare Access blocks `manifest.json`

A browser may report a CORS error when Cloudflare Access redirects
`/manifest.json` to the Access login hostname. This affects PWA metadata, not
server-side search aggregation. To remove the warning, add a more-specific
Cloudflare Access self-hosted application for
`search.example.com/manifest.json` with a **Bypass** policy. Keep the root
`search.example.com` application protected. Only bypass this public,
non-sensitive metadata path; do not bypass `/search` or the entire hostname.
