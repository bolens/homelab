# Kasm Workspaces

Container streaming platform for **browser-based access to desktops and applications**. Delivers on-demand, disposable Docker containers (Remote Browser Isolation, DaaS, secure remote access) streamed to the web—no client software or VPN required. Powered by KasmVNC.

**Homepage:** https://www.kasmweb.com/  
**Docs:** https://docs.kasmweb.com/  
**GitHub:** https://github.com/linuxserver/docker-kasm  
**Docker image:** lscr.io/linuxserver/kasm  

## Quick start

1. **Prepare stack** (creates `stack.env` from example if missing):

   ```bash
   ./prepare-stack.sh
   # or: cp stack.env.example stack.env
   ```

2. **Deploy**:

   ```bash
   docker compose up -d
   ```

3. **Add Caddy blocks** for `kasm.yourdomain.com` (main UI) and `kasm-setup.yourdomain.com` (setup wizard). See [Caddy reverse proxy](#caddy-reverse-proxy) below.

4. **Complete setup wizard** at `https://kasm-setup.yourdomain.com` (first run only). Set admin and user passwords. Default users are `admin@kasm.local` and `user@kasm.local`.

5. **Use the main UI** at `https://kasm.yourdomain.com`. After setup, you can remove the `kasm-setup` Caddy block if desired.

**Monitoring setup progress:** The setup wizard can show a metrics/status page after a refresh. To see what the backend is still doing (install steps, DB init, etc.), stream the container logs:

```bash
docker logs -f kasm
```

Use `Ctrl+C` to stop following. If the wizard is still running, return to `https://kasm-setup.yourdomain.com` once logs indicate setup is ready.

**Monitoring workspace installation:** When you install workspaces from a registry, the UI can show “Installing…” for a long time with no progress bar. To see actual activity:

1. **Stream container logs** – Pull and install activity from the inner Docker (DinD) and Kasm agents often appears here:
   ```bash
   docker logs -f kasm
   ```
   Watch for pull progress, layer extraction, or errors (e.g. `manifest unknown`, network timeouts, no space left).

2. **Check that images are landing** – In another terminal, list images inside the Kasm container every so often; new entries mean installs are progressing:
   ```bash
   docker exec kasm docker images
   ```

**Removing old workspace images (e.g. switching weekly → daily):** To remove all images with a given tag (e.g. `1.18.0-rolling-weekly`) so you can use a different tag (e.g. `1.18.0-rolling-daily`), run:
   ```bash
   docker exec kasm docker images --format "{{.Repository}}:{{.Tag}}" | grep "1.18.0-rolling-weekly" | while read img; do docker exec kasm docker rmi "$img"; done
   ```
   Then in **Admin** → **Workspaces**, edit each affected workspace and set the image tag to the new one (e.g. `kasmweb/brave:1.18.0-rolling-daily`). Re-install or pull the new images from the registry (or manually: `docker exec kasm docker pull kasmweb/brave:1.18.0-rolling-daily`).

3. **If it stays stuck** – Refresh the Workspaces / Registry page; sometimes the UI doesn’t update when installs finish. If logs show repeated errors, fix the cause (e.g. image tag, registry access, or disk space) and retry or restart the container.

## Configuration

| Item        | Details |
|------------|---------|
| **Access** | Via Caddy only (no host ports; reverse proxy to `kasm:443` for main UI, `kasm:3000` for setup wizard) |
| **Network** | Internal `kasm` network plus external `monitor` so Caddy can reach the web UI |
| **Image**   | `lscr.io/linuxserver/kasm:latest` |
| **Storage** | Named volumes `kasm_data` (Docker/install data) and `kasm_profiles` (persistent workspace profiles) |
| **Auth**    | Users and passwords set during the setup wizard; default `admin@kasm.local` and `user@kasm.local` |
| **Privileged** | Required (DinD – Docker in Docker for spawning workspace containers) |

**Resource limits:** The stack sets CPU and memory **limits** on the Kasm container (`deploy.resources.limits` in `docker-compose.yml`). The Kasm agent inside the container sees only this capacity, so you don’t need to set compute overrides in the admin UI—workspaces use whatever is available within those limits. Adjust `limits.cpus` and `limits.memory` (e.g. `"4"` and `8G`) to dedicate the desired share of the host to Kasm. After changing limits, recreate the container: `docker compose up -d`.

**GPU:** The compose file reserves all NVIDIA GPUs when the host has the **nvidia-container-toolkit** installed. Workspace images can then use GPU. If you have no GPU or no toolkit, use the CPU-only override so the container starts: `cp docker-compose.override.yml.example docker-compose.override.yml` (the example omits the GPU reservation). With GPU, do not use that override.

## Caddy reverse proxy

Kasm uses a self-signed certificate internally. Use `tls_insecure_skip_verify` when proxying to HTTPS.

**Main UI** (port 443). Include `Host` and `X-Forwarded-For` so Kasm sees the public hostname and session cookies work when loading workspaces:

```
kasm.yourdomain.com {
    reverse_proxy https://kasm:443 {
        header_up Host {host}
        header_up X-Forwarded-Proto https
        header_up X-Forwarded-Host {host}
        header_up X-Forwarded-For {remote}
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
        header_up Host {host}
        header_up X-Forwarded-Proto https
        header_up X-Forwarded-Host {host}
        header_up X-Forwarded-For {remote}
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

## Administering workspaces (available apps)

Log in as admin at `https://kasm.yourdomain.com`, then use the admin UI to control which workspace images (apps) are available and to whom:

| Where | What to do |
|-------|------------|
| **Admin** → **Workspaces** | List of all workspace images. **Enabled**: turn a workspace on or off; disabled workspaces are not available to anyone. **Hide Workspace on Dashboard**: hide from the user dashboard but keep enabled (e.g. for group-only access). |
| **Admin** → **Workspaces** → *edit a workspace* | Set **Docker Image** (name and tag), CPU/memory, GPU, registry; set **Persistent Profile Path** (e.g. `/profiles/ubuntu-focal/{username}/`) if using persistent profiles. |
| **Admin** → **Groups** | Control which users see which workspaces. Workspaces can be assigned to groups; users only see workspaces for groups they belong to (plus “all users” workspaces). |
| **Admin** → **Images** | In some versions, image/registry management is under **Images**; use it to add or fix Docker images used by workspaces. |

**Making certain workspaces not available to the default users group:** By default, new workspaces are often added to the "Default User" / "All Users" group. To restrict a workspace to specific groups only: (1) **Admin** → **Workspaces** → edit the workspace → under **Groups** (or **Allowed Groups**), remove **Default User** / **All Users** and assign only the groups that should see it. (2) Optionally enable **Hide Workspace on Dashboard** so it doesn’t appear on the main dashboard for users who have access via another group. (3) To stop new workspaces from being auto-added to the default group, set the global setting **Add Images to Default Group** (or **Add Workspaces To Default Group**) to **False** in **Admin** → **Settings** or **Server** settings; then assign each new workspace to the desired groups manually.

**Admin can't add groups or update a user's groups:** Kasm uses permission-based access. If **Add Group** or editing user groups is missing or disabled:

- **Admin in Administrators group:** **Access Management** (or **Admin**) → **Groups** → **Administrators** → **Users** tab. Ensure your admin account (e.g. `admin@kasm.local`) is listed; add it if not.
- **Permissions:** **Groups** → **Administrators** → **Edit** → **Permissions** tab. Enable **Groups Create**, **Groups Modify**, **Groups Delete**, **Users Modify**, and typically **Global Admin**. Save.
- **Assigning users to groups:** **Groups** → **Edit** (the group) → **Users** tab is where you add/remove users. The user edit screen may not show group membership in all versions.

Details: [Kasm Workspaces administration](https://docs.kasm.com/docs/latest/guide/workspaces/index.html), [Groups](https://docs.kasm.com/docs/latest/guide/groups.html), and [group permissions](https://docs.kasm.com/docs/latest/guide/groups/group_permissions.html).

## Workspace registries (extra images)

Besides the built-in Kasm Technologies and Kasm AI registries, you can add the **LinuxServer.io** community registry for more desktops and apps:

1. In Kasm: **Workspaces** → **Workspace Registry** (or **Registry** in the nav) → **Add new** / **Workspace Registry Link**.
2. Use the **root URL only**: `https://kasmregistry.linuxserver.io` (do **not** use `.../1.1/`; that path can fail to add in some versions).
3. Click **Add**. Some setups may only list a subset of workspaces (e.g. two browsers) from that registry; you can install those and add more workspaces manually (Admin → Workspaces → Add, using image names from [LinuxServer’s Kasm registry](https://kasmregistry.linuxserver.io/) or [baseimage-kasmvnc docs](https://docs.linuxserver.io/images/docker-baseimage-kasmvnc/)). Review any workspace that shows an orange “review” warning before installing.

## Portainer

1. **Stacks** → **Add stack**.
2. Paste the `docker-compose.yml` contents.
3. Create `stack.env` from `stack.env.example` (optional overrides).
4. Deploy. Add the Caddy blocks as above.

## Troubleshooting

**Wizard stopped or not showing:** If you stopped the setup wizard by accident or the wizard page no longer appears, Kasm has written `/opt/NO_WIZARD` so it no longer serves the wizard. You can either delete that file (quick) or reset the whole install (full do-over).

- **Option A – Re-show the wizard (keep existing install state):** Delete the flag file and restart the container so the wizard is served again:
  ```bash
  docker exec kasm rm -f /opt/NO_WIZARD
  docker restart kasm
  ```
  Then open `https://kasm-setup.yourdomain.com` again. If the install was already complete, you may see the main UI on the setup port; if it was only partially done, the wizard should resume.

- **Option B – Full reset (fresh install):** From the stack directory: `docker compose down`, then `docker volume rm kasm_kasm_data` (or the matching `*kasm_data*` volume from `docker volume ls`), then `docker compose up -d`. You will go through the full wizard from scratch; any partial setup is lost.

**"Connection failed" when loading a workspace / "Error, missing authenticate cookies":** The workspace stream requires Kasm auth cookies. If the browser doesn't send them, you get connection failed. Try: log out and back in at the main Kasm URL; launch the workspace from the same tab (don't open the workspace link in a new tab/window that never had the session). If you use a reverse proxy (e.g. Caddy), ensure it forwards cookies and doesn't strip them; the workspace URL should be on the same site (same domain) as the main Kasm UI so cookies are sent. Clearing cookies or using a private window can also cause this.

**versions.txt 404 for kasmregistry.linuxserver.io/1.18/:** Kasm may try to fetch version info from the LinuxServer registry; that path can return 404 and is often harmless (log noise). If it bothers you, remove the LinuxServer registry from Workspaces → Registry or ignore the error.

**"manifest unknown" when starting a workspace:** The workspace’s Docker image tag may be invalid or the image was removed from the registry. Kasm images do **not** use a `latest` tag; use a versioned tag (e.g. `1.18.0-rolling-weekly`, `1.18.0`, or `develop`). In Admin → Workspaces (edit the workspace) or Admin → Images, set the image to e.g. `kasmweb/brave:1.18.0-rolling-weekly` instead of `kasmweb/brave:latest`. When pulling manually to monitor progress, use the same tag: `docker exec kasm docker pull kasmweb/brave:1.18.0-rolling-weekly`.

**"Unexpected error while creating" / workspace won't start / containerd "failed to save daemon pid" or "connection refused" in logs:** The inner Docker (DinD) can leave orphaned containerd shim state after a restart or crash, so containerd fails to start and no workspace containers can be created. Fix: stop Kasm, clear the orphaned runtime state in the data volume, then start again (pulled images and Kasm DB are kept):

  ```bash
  cd /path/to/docker/stacks/kasm
  docker compose stop kasm
  docker run --rm -v kasm_kasm_data:/opt alpine sh -c "
    rm -rf /opt/docker/containerd/daemon/io.containerd.runtime.v2.task
    rm -rf /opt/docker/containerd/daemon/io.containerd.sandbox.controller.v1.shim
    mkdir -p /opt/docker/containerd/daemon/io.containerd.runtime.v2.task
    mkdir -p /opt/docker/containerd/daemon/io.containerd.sandbox.controller.v1.shim
    chmod 1733 /opt/docker/containerd/daemon/io.containerd.runtime.v2.task
    chmod 700 /opt/docker/containerd/daemon/io.containerd.sandbox.controller.v1.shim
  "
  docker compose up -d kasm
  ```

  Then try launching a workspace again.

  **If Doom (or another workspace) still shows "Unexpected error" after the above:** The failure is often **device passthrough** (e.g. webcam or GPU) when the device doesn’t exist inside the Kasm container. Try: **Admin** → **Access Management** → **Groups** → open the group your user is in → set **Allow Kasm Webcam** to **false**, then try launching the workspace again. To see the exact error: launch the workspace once, then immediately run:
  `docker exec kasm sh -c 'for c in kasm_manager kasm_api kasm_agent; do echo "=== $c ==="; docker logs $c 2>&1 | tail -100 | grep -iE "error|exception|500|traceback|create|device|gathering"; done'`
  The output will show which container logged the failure and the device or API error (e.g. `error gathering device ... /dev/video0`).

**"Unexpected error" with `plugin "rclone" not found` in logs:** Kasm is trying to create a volume using the **rclone** Docker volume plugin (used for Storage Providers / cloud mounts), but the inner Docker in the LinuxServer image doesn’t have that plugin. Fix: **disable the Storage Provider** so sessions don’t request rclone volumes. In the Kasm UI go to **Settings** → **Storage** (or **Server** → **Storage**), find the provider that uses rclone (e.g. MinIO/S3) and set it to **disabled**, or delete it. If users have added a **Cloud Storage** mapping in their profile (profile icon → Edit Profile → Cloud Storage), they can remove that mapping so their sessions no longer request the rclone volume. After that, try launching the workspace again.

**"No resources are available to create the kasm":** Kasm could not find an agent with capacity. On a single-node (LinuxServer) setup, the inner Docker is the only agent. Check:

1. **Agent enabled** – **Admin** → **Infrastructure** → **Docker Agents**. Ensure the agent is **enabled** (toggle on). If it was disabled or the container restarted, wait a minute for "Last Reported" to update.
2. **Zone assignment** – **Admin** → **Zones** → **Default** (or the zone your workspace uses). Ensure the server/agent is **assigned** to that zone so workspaces can be scheduled on it.
3. **Resources** – The agent may report 0 free CPUs/memory. In **Admin** → **Infrastructure** → **Docker Agents**, open the agent and set **Compute overrides** (e.g. override available CPUs and memory to match your host) so Kasm sees capacity. Alternatively, edit the workspace in **Admin** → **Workspaces** and lower its required CPUs/memory.
4. **Image on agent** – The workspace image must be present on the agent. Run `docker exec kasm docker images` and confirm the image (e.g. Doom) is listed; if not, pull it or install the workspace from the registry and wait for the pull to finish.

## Health and monitoring

- No dedicated health endpoint. Use a generic HTTP check to `https://kasm.yourdomain.com` in Uptime Kuma.
- Kasm is resource-heavy: 4GB+ RAM for core services; 8GB+ recommended for the Docker host when running workspaces.

## Optional: persistent profiles

The stack mounts `kasm_profiles` to `/profiles`. When configuring a workspace in the admin UI, set **Persistent Profile Path** to e.g. `/profiles/ubuntu-focal/{username}/` for user-specific persistence. See [Kasm persistent profiles](https://www.kasmweb.com/docs/latest/how_to/persistent_profiles.html).

## Optional: MinIO (S3) persistent profiles

If you use the **minio** stack and have created a bucket named `kasm`, you can store persistent profiles in MinIO instead of (or in addition to) the local `/profiles` volume. Kasm and MinIO must both be on the `monitor` network so Kasm can reach `http://minio:9000`.

1. **Bucket:** Create bucket `kasm` in the MinIO console (e.g. `https://minio.yourdomain.com/console/`) if you have not already.
2. **Kasm Server Settings:** In the Kasm UI go to **Settings** → **Storage** (or **Server** settings). Set:
   - **Object Storage Key** = MinIO access key (e.g. `MINIO_ROOT_USER` from the minio stack’s `stack.env`).
   - **Object Storage Secret** = MinIO secret key (e.g. `MINIO_ROOT_PASSWORD`).
   - If your Kasm version has an **Object Storage Endpoint** or **S3 Endpoint URL** field, set it to `http://minio:9000`.
3. **Restart Kasm API** after saving (e.g. `docker restart kasm` or restart from the Kasm admin UI if available).
4. **Per workspace:** In **Admin** → **Workspaces** → edit a workspace → set **Persistent Profile Path** to an S3 path in the `kasm` bucket, e.g. `s3://kasm/profiles/{username}/` so each user gets a prefix under the bucket. Use `{username}` or `{user_id}` as required by your Kasm version.

Users’ profile data will then be stored in MinIO. See [Kasm S3 persistent profiles](https://docs.kasm.com/docs/latest/guide/persistent_data/persistent_profiles.html) and [S3 storage](https://docs.kasm.com/docs/latest/guide/storage_providers/s3.html).

### MinIO as a Storage Provider (mount bucket in sessions)

To let users mount your MinIO bucket (e.g. `kasm`) inside their Kasm session (e.g. at `/s3`), add an S3-compatible **Storage Provider** that points at MinIO. Storage providers use the Rclone Docker volume plugin; the volume config is a JSON structure as in the [Docker SDK create_volume](https://docker-py.readthedocs.io/en/stable/api.html#docker.api.volume.VolumeApiMixin.create_volume) API.

1. **Settings** → **Storage** → **Add**.
2. **Name:** e.g. `MinIO` or `S3 (MinIO)`.
3. **Storage Provider Type:** `S3` or `Custom`.
4. **Default Target:** Absolute path inside the session where the mapping will be mounted (e.g. `/s3`).
5. **Volume Configuration:** JSON with `driver` and `driver_opts`. For MinIO (S3-compatible), use a custom endpoint in `driver_opts`. Example (adjust keys if your Kasm/Rclone version expects different names, e.g. `s3-endpoint` vs `endpoint`):

   ```json
   {
     "driver": "rclone",
     "driver_opts": {
       "type": "s3",
       "s3-provider": "Other",
       "s3-endpoint": "http://minio:9000",
       "s3-env-auth": "false",
       "s3-region": "us-east-1",
       "uid": "1000",
       "gid": "1000",
       "allow_other": "true"
     }
   }
   ```

   If your version supports `MinIO` as `s3-provider`, you can set `"s3-provider": "MinIO"` and keep `s3-endpoint`. Credentials are not stored here; each user supplies them when adding a Storage Mapping.
6. **Mount Configuration:** `{}` (or leave as in the UI).
7. **Save.**

Users then go to **profile icon** → **Edit Profile** → **Cloud Storage** → **Add Storage Mapping**, choose this provider, and enter the MinIO **Access Key**, **Secret Key**, and **Bucket** (e.g. `kasm`). After that, the bucket is available inside sessions at the Default Target path (e.g. `/s3`).

**File browser shortcuts and file chooser:** To show cloud mount shortcuts in the session file manager (Thunar) and allow browser workspaces (e.g. Chrome, Firefox) to access them, set **Admin** → **Workspaces** → Edit workspace → **Docker Run Config Override (JSON)** to include `CLOUD_MOUNTS` and optionally `KASM_RESTRICTED_FILE_CHOOSER`. Example values are in `stack.env.example`; see [Storage Mappings](https://docs.kasm.com/docs/latest/guide/persistent_data/storage_mappings/index.html) (File Browser shortcuts, KASM_RESTRICTED_FILE_CHOOSER).

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
