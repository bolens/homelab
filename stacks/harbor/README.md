# Harbor – container registry (pointer stack)

[Harbor](https://goharbor.io/) is a cloud-native container registry providing policies, RBAC, replication, scanning, and a web UI. Harbor is normally installed using its own installer, which generates a dedicated `docker-compose.yml` and `harbor.yml` config.

This stack acts as a **documentation pointer** in this repo so Harbor appears alongside other stacks, but it does **not** attempt to reimplement the full Harbor compose file.

## How to deploy Harbor

1. **Download the official installer**
   - Follow the official Harbor installation docs to download the installer bundle (online or offline) on your Docker host.

2. **Generate configuration**
   - Use the installer’s `prepare` script to generate `harbor.yml` and `docker-compose.yml` in a dedicated directory (for example, `/opt/harbor`).
   - Configure:
     - External URL (e.g. `https://harbor.yourdomain.com`).
     - TLS settings (you can terminate TLS at Caddy and run Harbor HTTP-only internally, or let Harbor handle TLS).
     - Storage backend (filesystem, S3, etc.).

3. **Run Harbor**
   - Use the installer’s scripts (`./install.sh`, `docker compose up -d`, etc.) as documented upstream.

4. **Integrate with Caddy**
   - If you terminate TLS at Caddy, configure Caddy to reverse-proxy `harbor.yourdomain.com` to Harbor’s HTTP endpoint on the Docker host.

## Notes

- The `docker-compose.yml` in this directory is intentionally a minimal placeholder and does **not** define Harbor services. Always use the official Harbor installer and compose bundle.
- Once deployed, Harbor can act as the registry backend for your homelab (including CI from the `woodpecker-ci` stack) and as a pull-through/cache for external images, depending on your configuration.

