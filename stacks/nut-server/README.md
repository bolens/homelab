# NUT Server (Network UPS Tools)

Self-hosted NUT server (`upsd`) for exposing UPS status to LAN clients and monitoring tools.

**Website:** https://networkupstools.org  
**Docs:** https://networkupstools.org/docs/user-manual.chunked/  
**Container image:** https://github.com/instantlinux/docker-tools/tree/master/images/nut-upsd  

## Quick start

1. Run:

   ```bash
   ./prepare-stack.sh
   ```

   This creates `stack.env` (if missing), `caddy_snippet.conf` (if missing), ensures your config directory exists, and ensures Docker network `monitor` exists.

2. Ensure `NUT_CONFIG_DIR` points to your existing host config directory (default already matches your current setup):

   ```env
   NUT_CONFIG_DIR=/home/youruser/.config/nut-server
   ```

3. Confirm required files exist in that directory:
   - `ups.conf`
   - `upsd.conf`
   - `upsd.users`
   - `upsmon.conf`

4. Deploy from this directory:

   ```bash
   docker compose up -d
   ```

## Configuration

| Item | Details |
|------|---------|
| **NUT port** | `3493` — published on the host as `3493:3493` and reachable on `monitor` as `nut-server:3493` |
| **Config mount** | `${NUT_CONFIG_DIR}:/etc/nut` |
| **Network** | `monitor` external Docker network |
| **Runtime env** | `../../shared.env` (optional) + `stack.env` |

## Hostname `nut-server` vs running `upsc` on the host

`nut-server` is a **Docker service name**. It resolves for other containers on the `monitor` network (for example `upsc ups@nut-server:3493` **inside** another stack container). It does **not** resolve from your normal host shell unless you add it yourself.

From the **same machine** as Docker, after `docker compose up -d`:

```bash
upsc ups@127.0.0.1:3493
```

To use the name `nut-server` from the host, add a hosts entry (one line):

```bash
# /etc/hosts — use your Docker host IP if upsc runs on another machine
127.0.0.1 nut-server
```

Then:

```bash
upsc ups@nut-server:3493
```

## Notes

- NUT is a TCP service (not HTTP). The included Caddy snippet provides a small `.home/.local` status page only.
- For TCP proxying through Caddy on `3493`, use a Caddy layer4 config in your Caddy stack.
