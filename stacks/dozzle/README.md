# Dozzle

Real-time Docker container log viewer. One container, no database; uses the Docker socket to list containers and stream logs. Handy when debugging which service is failing without jumping between Portainer log tabs or `docker logs`.

## Quick start

1. Ensure the `monitor` network exists (e.g. `docker network create monitor` or deploy Caddy first).
2. Start: `docker compose up -d` from this directory (or deploy as stack in Portainer).
3. Access via Caddy (e.g. https://dozzle.home or https://dozzle.bolens.dev). Caddy uses `reverse_proxy dozzle:8080` on the shared monitor network (same pattern as yourls, cadvisor, grafana).

## Portainer

The stack is Portainer-friendly: no host bind mounts (except the Docker socket), env defaults for all variables, and an external `monitor` network. To deploy:

1. Create the `monitor` network once (Networks → Add network → name `monitor`) if it does not exist.
2. Stacks → Add stack → paste or pull this compose. Optionally set **Environment variables** in the stack (e.g. `DOZZLE_HOST_PORT`, `TZ`); defaults work without them.
3. For Dozzle v10+ auth: in the compose, uncomment the `dozzle_config:/data` volume and the mount line, redeploy, then add `users.yaml` into the `dozzle_config` volume (e.g. Portainer Volumes → dozzle_config → browse / upload, or use a one-off container to copy the file in).

## Configuration

| Item | Details |
|------|---------|
| **Ports** | Optional `8082:8080` for direct host access. Caddy reaches Dozzle by `dozzle:8080` on the monitor network. |
| **Volumes** | Docker socket (read-only) for container list and logs. |
| **Network** | `monitor` (external) — same as Caddy and yourls; join the same pre-existing network. |
| **Env** | See [ENV-VARS.md](../../documents/ENV-VARS.md) for TZ/locale. Dozzle v10+ auth: put `users.yaml` in the `dozzle_config` volume (path `/data/users.yaml`). Copy from [users.yaml.example](users.yaml.example) and generate password with `docker run -it --rm amir20/dozzle generate admin --password SECRET --email you@example.com --name Admin`. |

## Copying users.yaml into the volume

After enabling the `dozzle_config` volume in the compose and redeploying, put `users.yaml` at `/data/users.yaml` inside that volume. If your stack has a project name (e.g. Portainer stack name `dozzle`), the volume may be `dozzle_dozzle_config`—use that name in the `-v` flag below.

**From host file** (run from this directory, with `users.yaml` in the current dir):

```bash
docker run --rm -v dozzle_config:/data -v "$(pwd)/users.yaml:/users.yaml:ro" alpine cp /users.yaml /data/users.yaml
```

**From stdin** (e.g. pipe generated output straight in):

```bash
docker run -it --rm amir20/dozzle generate admin --password YOUR_PASSWORD --email you@example.com --name Admin | docker run -i --rm -v dozzle_config:/data alpine sh -c "cat > /data/users.yaml"
```

**Portainer:** Volumes → select `dozzle_config` → **Browse** (or **Console** for this stack’s container) and upload or paste `users.yaml` into `/data/`. If the stack has no container with that volume yet, use a one-off container as above from a host that has Docker CLI.

Then restart the Dozzle container so it picks up the file.

## Caddy

Use `reverse_proxy dozzle:8080` (same as yourls:8080, cadvisor:8080). See [stacks/caddy/Caddyfile](../caddy/Caddyfile) for dozzle.bolens.dev.

## Start

`docker compose up -d` from this directory.
