# MinIO – S3-compatible object storage

[MinIO](https://min.io/) is a high-performance, S3-compatible object store. Use it as a backend for backups (e.g. the `restic` stack), application uploads, logs, and other large objects.

**Website:** https://min.io/  
**Docs:** https://docs.min.io/  
**Docker image:** https://hub.docker.com/r/minio/minio  

## Quick start

1. **Environment**
   - From this directory: copy `stack.env.example` → `stack.env`.
   - Set:
     - `MINIO_ROOT_USER` – access key (e.g. `openssl rand -hex 16`),
     - `MINIO_ROOT_PASSWORD` – secret key (e.g. `openssl rand -base64 32`),
     - `MINIO_BROWSER_REDIRECT_URL` – required when behind Caddy; use the `/console/` path (e.g. `https://minio.yourdomain.com/console/`).
2. **Deploy**

   ```bash
   docker compose up -d
   ```

3. **Access**
   - MinIO serves:
     - S3 API on port `9000`,
     - Web console on port `9001`.
   - Put it behind Caddy on the `monitor` network. Use path routing: `/console/` → `minio:9001`, `/` → `minio:9000` (see Caddyfile.example).

## Deploying via Portainer

1. **Stacks** → **Add stack** → paste the contents of `docker-compose.yml`.
2. **Environment variables** (required):
   - `MINIO_ROOT_USER` – access key (e.g. `openssl rand -hex 16`)
   - `MINIO_ROOT_PASSWORD` – secret key (e.g. `openssl rand -base64 32`)
   - `MINIO_BROWSER_REDIRECT_URL` – required when behind Caddy (e.g. `https://minio.yourdomain.com/console/`)
3. Ensure the **monitor** network exists.
4. Deploy.

## Configuration

| Item        | Details                                                                 |
| ----------- | ----------------------------------------------------------------------- |
| **Access**  | Via Caddy: `/console/` → `minio:9001`, `/` → `minio:9000` (path routing) |
| **Network** | `monitor` (so apps and backup tools can reach it)                      |
| **Image**   | `minio/minio:latest`                                                   |
| **Storage** | `minio_data` volume for object data and metadata                       |
| **Caddy**   | See [stacks/caddy/Caddyfile.example](../caddy/Caddyfile.example): path routing with `handle_path /console*` and `request_body max_size 0` |

For one-time setup and how other stacks use this backend, see [SHARED-RESOURCES.md](../../documents/SHARED-RESOURCES.md).

## Using with other stacks

- **Restic** – point `RESTIC_REPOSITORY` at MinIO, for example:

  ```bash
  RESTIC_REPOSITORY=s3:http://minio:9000/restic
  ```

  and set `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` to match `MINIO_ROOT_USER` / `MINIO_ROOT_PASSWORD`.

- **Outline, Firefly-III, etc.** – you can use MinIO as an S3 backend where those apps support S3 storage. Configure the app with:
  - S3 endpoint: `http://minio:9000` (inside Docker),
  - appropriate access/secret keys,
  - bucket name and region as required by the app.

## Notes

- For TLS termination, use Caddy in front of MinIO; MinIO itself runs with HTTP inside the Docker network.
- For production, consider pinning a specific MinIO version instead of `latest`.

