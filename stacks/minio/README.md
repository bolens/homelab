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
     - optionally `MINIO_SERVER_URL` to your Caddy URL (e.g. `https://minio.yourdomain.com`).
2. **Deploy**

   ```bash
   docker compose up -d
   ```

3. **Access**
   - MinIO serves:
     - S3 API on port `9000`,
     - Web console on port `9001`.
   - Put it behind Caddy on the `monitor` network (e.g. `https://minio.yourdomain.com` → `minio:9001` for the console; S3 API may share the same hostname or a separate one, depending on your Caddy/CNAME setup).

## Configuration

| Item        | Details                                                                 |
| ----------- | ----------------------------------------------------------------------- |
| **Access**  | Via Caddy (reverse-proxy to `minio:9001` for console; `minio:9000` for S3 API) |
| **Network** | `monitor` (so apps and backup tools can reach it)                      |
| **Image**   | `minio/minio:latest`                                                   |
| **Storage** | `minio_data` volume for object data and metadata                       |
| **Caddy**   | See [stacks/caddy/Caddyfile.example](../caddy/Caddyfile.example) for `minio.yourdomain.com` → `minio:9001` (console) |

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

