# logseq-sync (community backend) – EXPERIMENTAL

This stack is a thin wrapper around the community [logseq-sync](https://github.com/bcspragu/logseq-sync) backend implementation. It is **experimental** and not an official Logseq product. Integration with the Logseq clients may require code modifications or custom builds; see the upstream repository for current status and instructions.

## Quick start (high level)

1. **Clone the upstream repo**

   From this directory:

   ```bash
   chmod +x clone-repo.sh
   ./clone-repo.sh
   ```

   This clones or updates `https://github.com/bcspragu/logseq-sync` into `./repo`.

2. **Review upstream docs**
   - Read the upstream README and docs in `./repo` to understand how to build and configure the backend.

3. **Build and run**

   ```bash
   docker compose build
   docker compose up -d
   ```

   The `docker-compose.yml` in this stack expects a `Dockerfile` in `./repo` that builds the backend image.

4. **Configure Logseq clients**
   - Follow the upstream project’s guidance for pointing Logseq at your self-hosted sync backend (may require experimental builds or config flags).

## Configuration

| Item        | Details                                                      |
| ----------- | ------------------------------------------------------------ |
| **Access**  | Typically via Caddy on `monitor` (e.g. `logseq-sync.yourdomain.com`) |
| **Network** | `monitor`                                                    |
| **Storage** | `logseq_sync_data` (backend data, depending on upstream impl) |

Because this backend is community-driven and evolving, keep a close eye on its documentation and issues for breaking changes.

