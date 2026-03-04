# OnionScan

CLI tool for investigating Tor hidden services (onion sites). Scans for operational security issues and misconfigurations (e.g. mod_status, directory listings, EXIF, server fingerprinting). Useful for hidden-service operators and researchers.

**Website:** https://onionscan.org  
**GitHub:** https://github.com/s-rah/onionscan

## Quick start

1. **Start the stack** (brings up Tor inside the container):

   ```bash
   docker compose up -d
   ```

2. **Wait for Tor to be ready** (first run can take a minute):

   ```bash
   docker compose logs -f onionscan
   ```

   When you see Tor running (e.g. "Bootstrapped 100%"), press Ctrl+C.

3. **Run a scan**:

   ```bash
   docker compose exec onionscan onionscan <onion-address>
   ```

   Example:

   ```bash
   docker compose exec onionscan onionscan --verbose example.onion
   ```

## Usage

| Command | Description |
|--------|-------------|
| `onionscan <addr>` | Simple report (high/medium/low risk) |
| `onionscan --verbose <addr>` | Verbose output |
| `onionscan --jsonReport <addr>` | JSON report for tooling |

Custom Tor proxy (default is internal):

```bash
docker compose exec onionscan onionscan --torProxyAddress=127.0.0.1:9050 <addr>
```

Full options: see [OnionScan doc](https://github.com/s-rah/onionscan/blob/master/doc/README.md).

## Convenience alias

To run `onionscan` from your host as if it were installed locally, add to `~/.bashrc` or `~/.zshrc`:

```bash
onionscan() {
  if docker inspect --format '{{.State.Running}}' onionscan 2>/dev/null | grep -q true; then
    docker exec -it onionscan onionscan "$@"
  else
    echo "Start the stack first: cd docker/stacks/onionscan && docker compose up -d"
    return 1
  fi
}
```

Then: `onionscan --verbose example.onion`

## Configuration

| Item | Details |
|------|---------|
| **Access** | CLI only; no web UI, no ports. Run via `docker compose exec onionscan onionscan [options] <addr>`. |
| **Image** | `mpatton/onionscan:latest` ([Docker Hub](https://hub.docker.com/r/mpatton/onionscan)) |
| **Security** | `cap_drop: ALL`; container only runs Tor + onionscan binary. |

## Start

From this directory: `docker compose up -d`.  
Then run scans with `docker compose exec onionscan onionscan [options] <onion-address>`.
