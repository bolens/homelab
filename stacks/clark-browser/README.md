# clark-browser

Stealth Chromium for browser automation. Anti-fingerprinting patches compiled
directly into Chromium source, not fragile JS shims. Exposes a CDP endpoint
that Playwright connects to via connect_over_cdp().

- Repo: https://github.com/clark-labs-inc/clark-browser
- Protocol: Chrome DevTools Protocol (CDP) on port 9222
- Playwright usage: pw.chromium.connect_over_cdp("http://localhost:9222")

## Services

| Container | Role | Port |
|---|---|---|
| clark-browser | CDP + stealth Chromium | 127.0.0.1:9222 |

## Build & Setup

Builds from the upstream clark-browser PyPI package + downloads
the patched Chromium binary at build time (~750 MB image).

1. docker compose build   # downloads Chromium binary (~270 MB) into the image
2. cp stack.env.example stack.env
3. docker compose up -d
4. Copy caddy_snippet.conf.example if you want a hostname

First build takes a few minutes (Chromium download). Subsequent rebuilds are fast
(binary cached in the clark-cache named volume).

The build uses digest-pinned Node 24 LTS and Python 3.14. Keep the Node
release on a supported LTS line when updating its image; a successful build
does not establish browser/CDP compatibility. Verify Chromium startup and a
Playwright CDP connection against the built image before deployment.

## Connect with Playwright

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp("http://localhost:9222")
    page = browser.new_page()
    page.goto("https://bot.sannysoft.com")
    print(page.title())
    browser.close()

## Notes

- shm_size=1gb is recommended for Chromium stability.
- The named volume clark-cache persists the downloaded Chromium binary across rebuilds.
- One Chromium process per container. For per-identity fingerprints, run multiple
  containers on different ports.
- The Chromium binary is ~270 MB (Linux x86_64) and is fetched from GitHub Releases.

## CDP launcher contract

The PyPI 0.2.1 wheel supplies browser-launch APIs but omits upstream's
`bin/clarkserve`. This image installs an MIT-attributed adapter based on upstream
commit `96f79abdc7b8611a1dafd23a2d16c5f20d99ba4e`. It uses the pinned package's
argument resolver for fingerprint/platform/fonts/network, WebRTC and WebGPU
options. Nonempty proxy username/password settings refuse startup: Chromium's
direct proxy switch supports an unauthenticated proxy server, not that credential
adapter. Values are never included in the refusal message.

Chromium listens on private container loopback 9223. The adapter retains the
existing container port 9222: it accepts only bounded CDP discovery GET requests
and WebSocket upgrades, rewrites validated loopback debugger URLs to the incoming
explicitly approved Host/http-or-https origin, and forwards WebSocket bytes without interpreting CDP.
Caddy's default Host and X-Forwarded-Proto handling preserves hostname/wss access;
do not replace Host with the upstream's loopback address. Absolute targets,
foreign Origin headers and malformed/framed requests refuse. The adapter permits
32 simultaneous connections, at most 16 KiB of request headers and 1 MiB of discovery
JSON; idle WebSocket streams close after 300 seconds. Health uses `/json/version`.
No new host ports, authentication, networks or privileges are introduced.
`CLARK_LAUNCH_HYGIENE=strict` also rejects this deliberate bridge-facing adapter;
the upstream default warns. Keep this unauthenticated administrative endpoint on
the existing loopback host publication and protected admin ingress.

The image build runs offline adapter controls against the installed Clark APIs
and requires successful binary prefetch. Those checks do not launch Chromium.
Before deployment, verify the actual published image's prefetched Chromium 148,
nonloopback discovery, hostname Playwright 1.64 CDP attachment, offline page/JS
operations and process/container cleanup. Source tests and a successful image
build do not establish that runtime result.

Review this adapter before changing the pinned Clark package version; it uses
the package's version-specific argument and font-environment helpers.

## Public origin allowlist

`CLARK_CDP_ORIGINS` explicitly adds approved public HTTP/HTTPS origins to the
fixed HTTP loopback defaults on port9222 (`localhost`, `127.0.0.1`, `[::1]`).
Use comma-separated exact origins with no path, wildcard, credentials or trailing
slash. The environment example names `https://clark.home,https://clark.local`
to match the Caddy example. Add each custom hostname/scheme deliberately before
enabling its route. The runtime checks that the request Host plus forwarded
scheme is in this allowlist before discovery or WebSocket forwarding. A foreign
Host remains refused even if its Origin matches it; an approved hostname does
not imply that every scheme or port is approved. Caddy supplies the public Host
and X-Forwarded-Proto, but those headers alone never grant approval.

Existing `stack.env` files are preserved by preparation, including when this key
is absent: absence permits only the fixed loopback defaults. Review/add the
intended hostname list manually; preparation never appends permissions. This is
a DNS-rebinding/origin guard, not authentication. Keep the existing internal
admin network and loopback-only host publication; enabling an origin does not
make public unauthenticated CDP safe.

The pinned upstream stealth arguments include `--no-sandbox`, so Chromium runs
without its own browser sandbox. Container isolation and restricted CDP access
remain part of this stack's security boundary.
