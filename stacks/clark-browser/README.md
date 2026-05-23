# clark-browser

Stealth Chromium for browser automation. Anti-fingerprinting patches compiled
directly into Chromium source — not fragile JS shims. Exposes a CDP endpoint
that Playwright connects to via connect_over_cdp().

- Repo: https://github.com/clark-labs-inc/clark-browser
- Protocol: Chrome DevTools Protocol (CDP) on port 9222
- Playwright usage: pw.chromium.connect_over_cdp("http://localhost:9222")

## Services

| Container | Role | Port |
|---|---|---|
| clark-browser | CDP + stealth Chromium | 127.0.0.1:9222 |

## Build & Setup

No public image — builds from the upstream clark-browser PyPI package + downloads
the patched Chromium binary at build time (~750 MB image).

1. docker compose build   # downloads Chromium binary (~270 MB) into the image
2. cp stack.env.example stack.env
3. docker compose up -d
4. Copy caddy_snippet.conf.example if you want a hostname

First build takes a few minutes (Chromium download). Subsequent rebuilds are fast
(binary cached in the clark-cache named volume).

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
