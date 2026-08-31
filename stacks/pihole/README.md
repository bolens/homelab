# Pi-hole Stack

This stack runs Pi-hole for network-wide ad blocking and DNS filtering in Docker.


## Usage

1. Copy `stack.env.example` to `stack.env` and edit as needed (set your web password).
2. Copy `../shared.env.example` to `../shared.env` (if not already present) and set your timezone/locale. This file is shared by all stacks.
3. Generate a strong password for the Pi-hole web UI:
   ```sh
   openssl rand -base64 32
   ```
   Set the output as `WEBPASSWORD` in `stack.env`.
4. Start the stack (from this directory):
   ```sh
   docker compose --env-file stack.env --env-file ../../shared.env up -d
   ```
5. Access the web UI via Caddy reverse proxy (see below).

### Caddy reverse proxy

All internal web access to Pi-hole should be routed through Caddy. The provided `caddy_snippet.conf` handles all HTTP/HTTPS for Pi-hole, including local and public hostnames. Do **not** expose port 80 directly; Caddy will proxy requests to the container on the Docker network.

Example Caddy snippet:
```caddyfile
pihole.home, pihole.local {
   tls internal
   reverse_proxy pihole:80
}

pihole.example.com {
   tls {
      dns cloudflare {env.CLOUDFLARE_API_TOKEN}
   }
   reverse_proxy pihole:80
}

http://pihole.example.com {
   reverse_proxy pihole:80
}
```


## Volumes
- `pihole_etc`: Stores Pi-hole configuration and data.
- `pihole_dnsmasq`: Stores custom DNSMasq configuration.

## Reference
- [Pi-hole Docker Image](https://hub.docker.com/r/pihole/pihole)
- [Pi-hole Docs](https://docs.pi-hole.net/)
