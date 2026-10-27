# TwitchDropsMiner Stack

This stack runs [TwitchDropsMiner](https://github.com/rangermix/TwitchDropsMiner) using Docker Compose.

## Usage

1. Copy `stack.env.example` to `stack.env` and edit as needed (set your timezone).
2. Run:
   ```sh
   docker compose up -d
   ```
3. Open the UI in your browser (direct: port **8080** if published; via Caddy: copy and customize [caddy_snippet.conf.example](caddy_snippet.conf.example), e.g. **twitchdrops.example.com**, then reload Caddy).
4. Log in with your Twitch account and configure mining via the web UI.

If the page stays **blank** through **Cloudflare**, disable **Rocket Loader** (and auto JS minify) for `twitchdrops.*`; the UI relies on **Socket.IO** / WebSockets.

### Data persistence
- The named volume `twitchdropsminer_data` persists login and settings at `/app/data`.
- The named volume `twitchdropsminer_logs` persists logs at `/app/logs`.

When updating, preserve both volumes, `TZ`, and custom container options. Reload
the dashboard afterward to receive the updated assets. The [upstream update
notes](https://github.com/rangermix/TwitchDropsMiner/releases/tag/v2.3.0) describe
the retained settings and dashboard sign-in flow.

### Environment variables
- `TZ`: Set your timezone (e.g., `Europe/Berlin`).

## Reference
- [TwitchDropsMiner GitHub](https://github.com/rangermix/TwitchDropsMiner)
- [Docker Hub Image](https://hub.docker.com/r/rangermix/twitch-drops-miner)
