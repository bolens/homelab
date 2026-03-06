# Syncthing – continuous file sync

[Syncthing](https://syncthing.net/) is a continuous file synchronization tool that keeps folders in sync across devices without a central server.

**Website:** https://syncthing.net/  
**Docs:** https://docs.syncthing.net/  
**Docker image:** https://hub.docker.com/r/syncthing/syncthing  

## Quick start

1. **Environment**
   - From this directory: copy `stack.env.example` → `stack.env` (optional; sets `TZ`).
2. **Deploy**

   ```bash
   docker compose up -d
   ```

3. **Access**
   - Syncthing’s web UI listens on port `8384` inside the container.
   - Put it behind Caddy on the `monitor` network (e.g. `https://syncthing.yourdomain.com` → `syncthing:8384`).
   - Use the UI to add devices and shared folders.

## Configuration

| Item        | Details                                                         |
| ----------- | --------------------------------------------------------------- |
| **Access**  | Via Caddy (reverse-proxy to `syncthing:8384`)                   |
| **Network** | `monitor`                                                       |
| **Image**   | `syncthing/syncthing:latest`                                    |
| **Storage** | `syncthing_config` (Syncthing config), `syncthing_data` (data) |
| **Caddy**   | See [stacks/caddy/Caddyfile.example](../caddy/Caddyfile.example) for `syncthing.yourdomain.com` → `syncthing:8384` |

Bind-mount additional host directories into the container (e.g. `/srv/docs`) if you want them to be available as Syncthing folders.

