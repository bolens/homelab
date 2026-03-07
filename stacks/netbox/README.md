# NetBox (pointer stack)

NetBox is an IPAM (IP address management) and DCIM (data center infrastructure management) tool for documenting networks, devices, racks, and circuits. The recommended Docker deployment is maintained in the **netbox-docker** project.

**Website:** https://netbox.dev/  
**Docs:** https://docs.netbox.dev/  
**Docker (netbox-docker):** https://github.com/netbox-community/netbox-docker  

## Deployment model

This repository does **not** duplicate the full `netbox-docker` compose file. Instead, treat this directory as a pointer:

- Use the upstream `netbox-docker` repo (clone it under a path you control).
- Expose NetBox on the `monitor` network and add a Caddy site block (e.g. `https://netbox.yourdomain.com`) that reverse-proxies to the NetBox HTTP port.

### Suggested layout (example)

From somewhere under your Docker host filesystem (outside this repo if you prefer):

```bash
git clone -b release https://github.com/netbox-community/netbox-docker.git
cd netbox-docker
cp env/netbox.env.example env/netbox.env
# edit env/netbox.env (DB passwords, secrets, SUPERUSER_*, etc.)
docker compose pull
docker compose up -d
```

Then:

- Attach the NetBox container to the same Docker network as Caddy (e.g. `monitor`), or expose a host port and let Caddy proxy to `host.docker.internal:<port>`.
- Add a Caddy site block for `netbox.yourdomain.com` that reverse-proxies to the NetBox HTTP service.

## Why pointer-only?

NetBox’s official Docker deployment is multi-service (PostgreSQL, Redis, workers, housekeeping) and is actively maintained upstream. Keeping that config in one place avoids it drifting from the recommended setup. This stack exists to:

- Remind you that NetBox is a good fit for documenting your homelab.
- Provide a name and placeholder for Caddy, ENV, and topology docs.

