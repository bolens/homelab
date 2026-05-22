# code-server (VS Code in the browser)

LinuxServer image **`lscr.io/linuxserver/code-server`**. No host config directory is required: settings and extensions persist in the Docker volume **`code_server_config`** mounted at **`/config`**.

## Quick start

1. **`./prepare-stack.sh`** — creates **`stack.env`** from **`stack.env.example`** when missing, copies **`stack.env` → `.env`** for Compose interpolation, ensures the **`monitor`** network exists.
2. Edit **`stack.env`**: set **`PASSWORD`**, **`PROXY_DOMAIN`** (your public hostname, e.g. `code.example.com`), **`PUID`/`PGID`** if needed.
3. **`docker compose up -d`**
4. Open **`https://<PROXY_DOMAIN>`** via Caddy (see [caddy_snippet.conf](caddy_snippet.conf)).

## Environment

See **[stack.env.example](stack.env.example)** and [ENV-VARS.md](../../documents/ENV-VARS.md). Optional **`../../shared.env`** supplies **`TZ`** / locale.

## Caddy

Upstream is **`code-server:8443`** (container web port). Reload Caddy after editing **`caddy_snippet.conf`**.

## Reference

- [LinuxServer code-server](https://docs.linuxserver.io/images/docker-code-server/)
- [code-server proxy guide](https://github.com/coder/code-server/blob/main/docs/guide.md)
