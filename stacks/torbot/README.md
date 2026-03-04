# OWASP TorBot

Dark Web OSINT tool: crawl .onion sites, extract links and emails, check if links are live, save results as JSON or tree. [OWASP TorBot](https://owasp.org/www-project-torbot/) project; upstream [DedSecInside/TorBot](https://github.com/DedSecInside/TorBot).

**Project:** https://owasp.org/www-project-torbot/  
**GitHub:** https://github.com/DedSecInside/TorBot

## Quick start

1. **Start the stack** (builds TorBot image on first run, starts Tor):

   ```bash
   docker compose up -d
   ```

2. **Wait for Tor to bootstrap** (first run can take a minute):

   ```bash
   docker compose logs -f tor
   ```

   When you see Tor ready (e.g. bootstrapped 100%), press Ctrl+C.

3. **Run a crawl** (use `--host tor --port 9050` so TorBot uses the Tor container):

   ```bash
   docker compose exec torbot torbot -u http://example.onion --host tor --port 9050 --save json
   ```

   Without `--host tor --port 9050`, TorBot would try 127.0.0.1:9050 and fail (Tor runs in the `tor` container).

## Usage examples

| Command | Description |
|--------|-------------|
| `torbot -u http://xxx.onion --host tor --port 9050` | Crawl one .onion URL (default depth 1) |
| `torbot -u http://xxx.onion --host tor --port 9050 --depth 2 --save json` | Deeper crawl, save as JSON |
| `torbot -u http://xxx.onion --host tor --port 9050 --visualize tree` | Show link tree |
| `torbot -u http://xxx.onion --host tor --port 9050 -q` | Quiet (no header) |
| `torbot -u https://example.com --host tor --port 9050 --disable-socks5` | Crawl clearnet without Tor |

Help:

```bash
docker compose exec torbot torbot --help
```

If `torbot` is not found, try:

```bash
docker compose exec torbot python -m torbot -u http://example.onion --host tor --port 9050
```

## Configuration

| Item | Details |
|------|---------|
| **Access** | CLI only; no web UI, no host ports. Run via `docker compose exec torbot torbot ...`. |
| **Tor** | `dperson/torproxy` on internal network; SOCKS at `tor:9050`. |
| **Image** | TorBot built from [DedSecInside/TorBot](https://github.com/DedSecInside/TorBot) (dev branch) in `./Dockerfile`. |
| **Network** | `torbot` (internal); Tor and TorBot share it so TorBot uses `--host tor --port 9050`. |

## Rebuild after upstream changes

```bash
docker compose build --no-cache torbot
docker compose up -d
```

## Start

From this directory: `docker compose up -d`.  
Then run crawls with `docker compose exec torbot torbot -u <url> --host tor --port 9050 [options]`.
