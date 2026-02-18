# Uptime Kuma

Self-hosted uptime monitoring and status page. Monitors HTTP(s), TCP, ping, and more; supports many notification channels (Telegram, email, Discord, etc.).

**First run:** Open http://localhost:3001 (or https://kuma.home once Caddy is up) and create an admin account.

**Monitoring:**
- **Other containers (Caddy, self):** Use the shared `monitor` network. In Uptime Kuma set: **Caddy** → `http://caddy:80`, **Uptime Kuma (self)** → `http://uptime-kuma:3001`.
- **Host services (Portainer):** Use **host.docker.internal**, e.g. `https://host.docker.internal:9443` (disable "Verify SSL" if needed).

The `monitor` network is created automatically by the first stack you deploy (Caddy or Uptime Kuma); the other stack attaches to it. No manual `docker network create` needed.

**Caddy heartbeat still failing?** Run these on bamboo.local:

1. **Both on same network:**  
   `docker network inspect monitor --format '{{range .Containers}}{{.Name}} {{end}}'`  
   You should see both `caddy` and `uptime-kuma`.

2. **Reach Caddy from Uptime Kuma container:**  
   `docker exec uptime-kuma wget -qO- --timeout=2 http://caddy:80 | head -1`  
   Should return the "Caddy is running..." line.

3. **Monitor settings in Uptime Kuma:** URL = `http://caddy:80` (HTTP, not HTTPS). No keyword required; leave "Verify SSL" off for HTTP.

**Start:** `docker compose up -d` or deploy as a stack in Portainer.
