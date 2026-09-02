# OWASP TorBot

Dark Web OSINT tool: crawl .onion sites, extract links and emails, check if links are live, save results as JSON or tree. [OWASP TorBot](https://owasp.org/www-project-torbot/) project; upstream [DedSecInside/TorBot](https://github.com/DedSecInside/TorBot). The stack defaults to the repository's GHCR build; set `TORBOT_IMAGE` to use the Harbor mirror or another registry.

**Website:** https://owasp.org/www-project-torbot/
**Docs:** https://github.com/DedSecInside/TorBot#readme
**GitHub:** https://github.com/DedSecInside/TorBot
**Releases:** https://github.com/DedSecInside/TorBot/releases

## Quick start

1. **Choose an image.** The stack uses the repository's GHCR builds by default. To use another registry, build and push the included images, then set `TORBOT_IMAGE` and `TORBOT_TOR_IMAGE` in `stack.env`.

   ```bash
   docker build -t harbor.yourdomain.com/homelab/torbot:latest -f stacks/torbot/Dockerfile stacks/torbot
   docker build -t harbor.yourdomain.com/homelab/torbot-tor:latest -f stacks/torbot/Dockerfile.tor stacks/torbot
   docker push harbor.yourdomain.com/homelab/torbot:latest
   docker push harbor.yourdomain.com/homelab/torbot-tor:latest
   ```

2. **Prepare** the local environment file:

   ```bash
   ./prepare-stack.sh
   # Optional mirror overrides:
   # TORBOT_IMAGE=harbor.yourdomain.com/homelab/torbot:latest
   # TORBOT_TOR_IMAGE=harbor.yourdomain.com/homelab/torbot-tor:latest
   ```

3. **Start the stack** (Tor + TorBot):

   ```bash
   docker compose up -d
   ```

4. **Wait for Tor to bootstrap** (first run can take a minute):

   ```bash
   docker compose logs -f tor
   ```

   When you see Tor ready (e.g. bootstrapped 100%), press Ctrl+C.

5. **Run a crawl** (always use `--host tor --port 9050`):

   ```bash
   docker compose exec torbot torbot -u http://example.onion --host tor --port 9050 --save json
   ```

## Usage examples

| Command | Description |
|--------|-------------|
| `torbot -u http://xxx.onion --host tor --port 9050` | Crawl one .onion URL (default depth 1) |
| `torbot -u http://xxx.onion --host tor --port 9050 --depth 2 --save json` | Deeper crawl, save as JSON |
| `torbot -u http://xxx.onion --host tor --port 9050 --visualize tree` | Show link tree |
| `torbot -u http://xxx.onion --host tor --port 9050 -q` | Quiet (no header) |
| `torbot -u https://example.com --host tor --port 9050 --disable-socks5` | Crawl clearnet without Tor |

Help: `docker compose exec torbot torbot --help`
If the `torbot` binary is not found: `docker compose exec torbot python -m torbot -u http://example.onion --host tor --port 9050`

## Configuration

| Item | Details |
|------|---------|
| **Access** | CLI only; no web UI, no host ports. Run via `docker compose exec torbot torbot ...`. |
| **Tor** | Alpine 3.24 image with the current Tor package; SOCKS at `tor:9050`. |
| **Images** | Defaults to `ghcr.io/bolens/homelab-torbot:latest` and `ghcr.io/bolens/homelab-torbot-tor:latest`; `stack.env` can select registry mirrors. |
| **Network** | `torbot` (internal); Tor and TorBot share it, always use `--host tor --port 9050`. |
| **Health** | TorBot is healthy only when its Python package imports and the Tor SOCKS endpoint accepts a TCP connection. |

## Portainer

Stacks → Add stack → **Repository** → Compose path `stacks/torbot/docker-compose.yml`. The GHCR images require no overrides. Set `TORBOT_IMAGE` and `TORBOT_TOR_IMAGE` only when using another registry.
