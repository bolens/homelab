# Streaming overlays: OBS and browser sources

Practical guide for showing **asking-ng** polls on stream (OBS Studio, vMix-style “browser” inputs, or any tool that can render a URL). For API contracts, see [API-REFERENCE.md](API-REFERENCE.md); for minting signed read grants, see [OPERATIONS.md — Embed Read-Only URL Grants](OPERATIONS.md#embed-read-only-url-grants).

## What to put in the browser source

| Goal | Typical URL | Notes |
|------|-------------|--------|
| Full poll UI (vote + results as configured) | Site **`/{pollId}`** (public poll page) | Good default for “show the poll on stream.” |
| Results-focused layout | Site **`/{pollId}/results`** | Same app shell; route is tuned for results viewing. |
| Compact JSON for a custom overlay | API **`GET /poll/{id}/meta`** | Bot-style metadata; pair with your own HTML/JS or a second source. |
| oEmbed discovery | API **`GET /poll/{id}/embed`** | Useful for tooling; not usually pasted into OBS directly. |

Replace `{pollId}` with the poll id. Behind **Caddy** (or similar), the public site and API often share one host with `/api` prefixing the API—use the same **HTTPS** origin you use in the browser so cookies and mixed content behave.

## Embed gate (`embed_read_token`)

If the poll has an **embed read token** configured, anonymous **reads** (poll page, meta, heatmap, export, WebSocket subscribe) require either:

- Query **`embed_token=<secret>`** (the value shown once when the token is generated), or  
- A **short-lived signed grant**: **`embed_exp`** + **`embed_sig`** on the URL (see below).

Votes still follow the poll’s vote rules (separate from read grants). Do not put **`api_key`** in a browser source URL.

## Signed read URLs (recommended for overlays)

Mint URLs **without** exposing `api_key`:

1. `POST /api/poll/{id}/embed-read-url` with **`X-Api-Key`** (poll key) or **`Authorization: Bearer`** (owner JWT).  
2. Optional query: **`ttl_seconds`** (server clamps to a safe maximum).  
3. Response **`data`** includes ready-to-paste **`poll_url`**, **`results_url`**, **`ws_url`**, **`meta_url`**, **`oembed_url`**, each already carrying **`embed_exp`** and **`embed_sig`**.

**Requirements:** poll must already have an embed read token configured (`409 EMBED_GATE_DISABLED` otherwise). Signing needs **`JWT_SECRET`** on the API (`503 EMBED_SIGNING_UNAVAILABLE` if missing).

**TTL:** When `embed_exp` passes, the page or API will reject the grant. For long shows, re-run the mint step on a timer (e.g. every 25–50 minutes) and update the Browser Source URL, or use automation that refreshes OBS scene items.

## OBS Studio: Browser Source

1. **Sources** → **+** → **Browser**.  
2. **URL**: paste **`poll_url`** or **`results_url`** from the mint response (or a public URL + `embed_token` if you accept rotating that token manually).  
3. **Width / Height**: match your canvas (e.g. **1920×1080**) or a smaller box if you crop in OBS. The poll UI is responsive; very small boxes may need scene scaling.  
4. **Shutdown source when not visible**: optional; saves GPU when the scene is inactive.  
5. **Refresh browser when scene becomes active**: useful after you **update the URL** when grants expire.

**FPS:** Default is fine; lower FPS slightly if you have many browser sources.

**Custom CSS (OBS):** You can inject CSS to hide chrome (e.g. nav/footer) only if you accept breakage when the app layout changes—prefer a dedicated minimal route in product later rather than fragile selectors.

## Live updates without reloading the page

The normal poll page subscribes to **`ws_url`** from the same mint response (WebSocket). If you build a **custom** overlay HTML that reads **`/poll/:id/meta`**, open **`ws_url`** in JS for `update` events and re-fetch meta as needed.

## Audio and “browser source mute”

The default poll UI is not designed for alert sounds. Keep the Browser Source **muted** in OBS unless you explicitly add audio and want it on stream.

## Security checklist

- Never commit or screen-share **`api_key`** or long-lived **`embed_token`** unintentionally.  
- Prefer **`embed-read-url`** outputs for anything OBS or chat bots log.  
- Rotate **`embed_read_token`** from **My Polls** / owner tools if a URL leaks.

## See also

- [OPERATIONS.md — Embed Read-Only URL Grants](OPERATIONS.md#embed-read-only-url-grants)  
- [CREATOR-STREAMER-ROADMAP.md](CREATOR-STREAMER-ROADMAP.md) (distribution UX backlog)  
- [API-REFERENCE.md](API-REFERENCE.md) (routes and auth tables)

The SPA shows an **OBS / browser source** link on **Home** (post-create), **My Polls**, **Poll** owner distribution, and **Developer**. Set **`VITE_STREAMING_OBS_DOC_URL`** at **client image build** to point that link at your fork or internal wiki (see `stack.env.example`).
