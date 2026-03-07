# Kasm Workspaces

Container streaming platform for **browser-based access to desktops and applications**. Delivers on-demand, disposable Docker containers (Remote Browser Isolation, DaaS, secure remote access) streamed to the web—no client software or VPN required. Powered by KasmVNC.

**Homepage:** https://www.kasmweb.com/  
**Docs:** https://docs.kasmweb.com/  
**GitHub:** https://github.com/linuxserver/docker-kasm  
**Docker image:** lscr.io/linuxserver/kasm  

## Quick start

1. **Copy env template**:

   ```bash
   cp stack.env.example stack.env
   ```

2. **Deploy**:

   ```bash
   docker compose up -d
   ```

3. **Add Caddy blocks** for `kasm.yourdomain.com` (main UI) and `kasm-setup.yourdomain.com` (setup wizard). See [Caddy reverse proxy](#caddy-reverse-proxy) below.

4. **Complete setup wizard** at `https://kasm-setup.yourdomain.com` (first run only). Set admin and user passwords. Default users are `admin@kasm.local` and `user@kasm.local`.

5. **Use the main UI** at `https://kasm.yourdomain.com`. After setup, you can remove the `kasm-setup` Caddy block if desired.

## Configuration

| Item        | Details |
|------------|---------|
| **Access** | Via Caddy only (no host ports; reverse proxy to `kasm:443` for main UI, `kasm:3000` for setup wizard) |
| **Network** | Internal `kasm` network plus external `monitor` so Caddy can reach the web UI |
| **Image**   | `lscr.io/linuxserver/kasm:latest` |
| **Storage** | Named volumes `kasm_data` (Docker/install data) and `kasm_profiles` (persistent workspace profiles) |
| **Auth**    | Users and passwords set during the setup wizard; default `admin@kasm.local` and `user@kasm.local` |
| **Privileged** | Required (DinD – Docker in Docker for spawning workspace containers) |

## Caddy reverse proxy

Kasm uses a self-signed certificate internally. Use `tls_insecure_skip_verify` when proxying to HTTPS.

**Main UI** (port 443):

```
kasm.yourdomain.com {
    reverse_proxy https://kasm:443 {
        header_up X-Forwarded-Proto https
        header_up X-Forwarded-Host {host}
        flush_interval -1
        transport http {
            tls_insecure_skip_verify
        }
    }
}
```

**Setup wizard** (port 3000, first run only):

```
kasm-setup.yourdomain.com {
    reverse_proxy https://kasm:3000 {
        header_up X-Forwarded-Proto https
        header_up X-Forwarded-Host {host}
        transport http {
            tls_insecure_skip_verify
        }
    }
}
```

Replace `kasm.yourdomain.com` and `kasm-setup.yourdomain.com` with your real hostnames (e.g. `kasm.yourdomain.com`). After setup is complete, you can remove the `kasm-setup` block.

### Reverse proxy: set Proxy Port to 0

After installation, configure Kasm for reverse proxy use:

1. Log in as admin at `https://kasm.yourdomain.com`.
2. Go to **Admin** → **Zones** → **Default**.
3. Set **Proxy Port** to `0` so workspace sessions launch correctly behind the proxy. See [Kasm reverse proxy docs](https://www.kasmweb.com/docs/latest/how_to/reverse_proxy.html#update-zones).

## Portainer

1. **Stacks** → **Add stack**.
2. Paste the `docker-compose.yml` contents.
3. Create `stack.env` from `stack.env.example` (optional overrides).
4. Deploy. Add the Caddy blocks as above.

## Health and monitoring

- No dedicated health endpoint. Use a generic HTTP check to `https://kasm.yourdomain.com` in Uptime Kuma.
- Kasm is resource-heavy: 4GB+ RAM for core services; 8GB+ recommended for the Docker host when running workspaces.

## Optional: persistent profiles

The stack mounts `kasm_profiles` to `/profiles`. When configuring a workspace in the admin UI, set **Persistent Profile Path** to e.g. `/profiles/ubuntu-focal/{username}/` for user-specific persistence. See [Kasm persistent profiles](https://www.kasmweb.com/docs/latest/how_to/persistent_profiles.html).

## Optional: GPU support

For NVIDIA GPU passthrough to workspace containers, add to the `kasm` service:

```yaml
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]
```

Ensure the [NVIDIA Container Runtime](https://github.com/NVIDIA/nvidia-container-runtime) is installed on the host.

## Updating

1. Pull the latest image: `docker compose pull`.
2. Recreate the container: `docker compose up -d`.
3. **In-app update:** Perform the update in the Kasm admin panel. Image updates alone do not upgrade Kasm; use the admin UI.
