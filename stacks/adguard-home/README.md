# AdGuard Home

Network-wide DNS-level ad and tracker blocking. Run AdGuard Home on your Docker host as the primary DNS server for your LAN and expose the web UI via Caddy.

**Website:** https://adguard.com/adguard-home/overview.html  
**Docs:** https://adguard-dns.io/kb/adguard-home/  
**Docker image:** https://hub.docker.com/r/adguard/adguardhome  
**GitHub:** https://github.com/AdguardTeam/AdGuardHome  

## Quick start

1. From this directory, copy `stack.env.example` → `stack.env` and adjust `TZ` / locale if needed.
2. Start the stack:

   ```bash
   docker compose up -d
   ```

3. On first run, access the setup wizard via Caddy (e.g. `https://dns.yourdomain.com` or `https://adguard-home.yourdomain.com`) using the example site block in the Caddyfile. Complete the wizard and create an admin account.
4. Point your router or DHCP server to this Docker host’s IP as the primary DNS server (port 53).

## Configuration

| Item        | Details                                                                                                     |
| ----------- | ----------------------------------------------------------------------------------------------------------- |
| **Access**  | DNS on host ports `53/tcp+udp` and `853/tcp`; HTTPS UI via Caddy (reverse-proxy to `adguard-home:3000/80`) |
| **Volumes** | `adguard_conf` (YAML config, filters, settings), `adguard_work` (runtime data, stats)                      |
| **Network** | `monitor` — shared with Caddy and other app stacks                                                         |
| **Env**     | See `stack.env.example` and `documents/ENV-VARS.md` for TZ/locale.                                         |

### Caddy

Add a site block in the main Caddyfile for the AdGuard Home UI, for example:

```caddyfile
adguard-home.home, adguard-home.local {
	tls internal
	reverse_proxy adguard-home:3000
}
```

For a public hostname (via Cloudflare Tunnel), use a placeholder such as:

```caddyfile
adguard.yourdomain.com {
	reverse_proxy adguard-home:3000
}
```

Then protect that hostname with Cloudflare Access as desired.

