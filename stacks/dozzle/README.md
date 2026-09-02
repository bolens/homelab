# Dozzle

Real-time Docker container log viewer. It uses a scoped Docker API proxy to
list containers and stream logs without mounting the Docker socket into the UI.

**Website:** https://dozzle.dev
**Docs:** https://dozzle.dev/guide/
**GitHub:** https://github.com/amir20/dozzle
**Docker image:** https://hub.docker.com/r/amir20/dozzle
**Releases:** https://github.com/amir20/dozzle/releases

## Quick start

1. From this directory: **`./prepare-stack.sh`**, creates `stack.env` (if missing), **`DOZZLE_CONFIG_DIR`** on the host (default **`~/.config/dozzle`**), seeds **`users.yaml`** from **[users.yaml.example](users.yaml.example)** when no `users.yaml`/`users.yml` exists yet, copies **`stack.env` → `.env`** for Compose `${HOME}` interpolation, and ensures the **`ingress-admin`** network exists.
2. Ensure the **`ingress-admin`** network exists if you skipped the script (e.g. `docker network create ingress-admin` or deploy Caddy first).
3. **`docker compose up -d`** (after prepare, Compose reads `.env` for bind-mount paths).
4. Access via Caddy (e.g. https://dozzle.home or https://dozzle.example.com). Start from this stack's committed [caddy_snippet.conf.example](caddy_snippet.conf.example); the prepared private `caddy_snippet.conf` is imported by the main Caddyfile.

## Configuration

| Item | Details |
|------|---------|
| **Ports** | Optional `8082:8080` for direct host access. Caddy reaches Dozzle by `dozzle:8080` on `ingress-admin`. |
| **Volumes** | **Auth data:** host dir **`DOZZLE_CONFIG_DIR`** (default **`~/.config/dozzle`**) → container **`/data`** (`users.yaml` / `users.yml`). |
| **Network** | `ingress-admin` (external) for Caddy; private `docker-api` for the scoped Docker API proxy. |
| **Env** | See [stack.env.example](stack.env.example), [ENV-VARS.md](../../documents/ENV-VARS.md), and [SHARED-RESOURCES.md](../../documents/SHARED-RESOURCES.md). `DOZZLE_LOCAL_HOST_LABEL` names the local engine in the host selector; `DOZZLE_REMOTE_AGENT` adds remote engines. Set **`DOZZLE_AUTH_PROVIDER=simple`** only with a valid **`users.yaml`** (see below). **`stack.env` → `.env`** is for Compose interpolation only; only selected values are passed into Dozzle. |
| **Health** | Uses Dozzle's built-in **`/dozzle healthcheck`** (see https://dozzle.dev/guide/healthcheck ), the image has no `wget`/`sh`. |

## Host views

The local socket proxy exposes every container on this Docker engine regardless
of the container's segmented application networks. Keep Dozzle on
`ingress-admin`; joining `ingress-public`, `ingress-sensitive`, or application
networks does not add container visibility.

Set `DOZZLE_LOCAL_HOST_LABEL` to give the local engine a useful name. To add
other Docker engines, deploy a Dozzle agent on each remote host and set a
comma-separated `DOZZLE_REMOTE_AGENT` value:

```dotenv
DOZZLE_LOCAL_HOST_LABEL=docker-host
DOZZLE_REMOTE_AGENT=host-a:7007|host-a|Production,host-b:7007|host-b|Lab
```

The `endpoint|name|group` form creates named, collapsible host groups and merged
group log views. Agent endpoints should be reachable only over a trusted private
network or VPN. A remote Dozzle agent mounts that host's Docker socket directly;
do not place this stack's Docker socket proxy in front of an agent.

## Simple auth (file-based)

1. In **`stack.env`**, set **`DOZZLE_AUTH_PROVIDER=simple`** (and **`DOZZLE_CONFIG_DIR`** if not using the default).
2. Run **`./prepare-stack.sh`** again, if **`users.yaml`** / **`users.yml`** are not present yet, it copies **[users.yaml.example](users.yaml.example)** to **`DOZZLE_CONFIG_DIR/users.yaml`** (existing files are never overwritten).
3. Replace the placeholder password with a real bcrypt entry:

   ```bash
   docker run -it --rm amir20/dozzle generate admin --password YOUR_PASSWORD --email you@example.com --name Admin > /path/to/your/DOZZLE_CONFIG_DIR/users.yaml
   ```

   Or merge the generated `users:` block into the existing file.

4. **`docker compose up -d`** (or restart the Dozzle container).

Dozzle reads **`/data/users.yaml`** or **`/data/users.yml`** inside the container (i.e. files in **`DOZZLE_CONFIG_DIR`** on the host). See https://dozzle.dev/guide/authentication

**Blank UI:** Do **not** set **`simple`** without a valid **`users.yaml`**. Behind **Cloudflare**, turn off **Rocket Loader** for your Dozzle hostname if the SPA stays blank.

## Portainer

1. Create the **`ingress-admin`** network if needed.
2. Set stack environment variables to match **`stack.env.example`**, especially **`DOZZLE_CONFIG_DIR`** as an **absolute host path** (Compose on the Portainer host does not expand `~`).
3. On the host (or a job), create **`users.yaml`** under that directory (or run **`./prepare-stack.sh`** from a checkout that has the same **`stack.env`**, then deploy).

## Caddy

Use `reverse_proxy dozzle:8080`. Caddy and Dozzle share only the dedicated
`ingress-admin` network. See [caddy_snippet.conf.example](caddy_snippet.conf.example)
and [stacks/caddy/Caddyfile.example](../caddy/Caddyfile.example).

## Start

`./prepare-stack.sh` then `docker compose up -d` from this directory.
