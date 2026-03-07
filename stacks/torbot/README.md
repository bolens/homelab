# OWASP TorBot

Dark Web OSINT tool: crawl .onion sites, extract links and emails, check if links are live, save results as JSON or tree. [OWASP TorBot](https://owasp.org/www-project-torbot/) project; upstream [DedSecInside/TorBot](https://github.com/DedSecInside/TorBot). **No official Docker image** — you must build from upstream once and set `TORBOT_IMAGE`, or use an image from your registry.

**Website:** https://owasp.org/www-project-torbot/  
**Docs:** https://github.com/DedSecInside/TorBot#readme  
**GitHub:** https://github.com/DedSecInside/TorBot  
**Releases:** https://github.com/DedSecInside/TorBot/releases  

## Quick start

1. **Get an image.** TorBot does not publish an official image. Build from the [upstream repo](https://github.com/DedSecInside/TorBot) (or use the Dockerfile in this stack), tag and push to your registry, e.g.:

   ```bash
   docker build -t harbor.yourdomain.com/homelab/torbot:latest -f stacks/torbot/Dockerfile stacks/torbot
   docker push harbor.yourdomain.com/homelab/torbot:latest
   ```

2. **Prepare** and set the image:

   ```bash
   ./prepare-stack.sh
   # Edit stack.env: TORBOT_IMAGE=harbor.yourdomain.com/homelab/torbot:latest
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
| **Tor** | `dperson/torproxy` on internal network; SOCKS at `tor:9050`. |
| **Image** | No official image. Set `TORBOT_IMAGE` to an image you built from upstream (or from the Dockerfile in this stack) and pushed to your registry. |
| **Network** | `torbot` (internal); Tor and TorBot share it — always use `--host tor --port 9050`. |

## Portainer

Stacks → Add stack → **Repository** → Compose path `stacks/torbot/docker-compose.yml`. Set `TORBOT_IMAGE` in the stack Environment to your registry image (build from upstream or from this stack’s Dockerfile once, then push).
