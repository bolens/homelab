# Optional original-file storage contract

- File: `stacks/immich/docker-compose.storage.yml`.
- Input: `IMMICH_LIBRARY_PATH`, required nonempty absolute existing directory.
- Target: `/data/library`, read/write, automatic host-directory creation disabled.
- Base `/data` named volume and all service/network/resource settings are retained.
- Preparation validates a configured path without creating it. It never opts into
  the override itself and preserves existing environment values.
- Runtime selection persists in ignored Compose inputs. All future server
  recreations must include both files to keep existing originals accessible.
- Backups cover both the selected host directory and all existing named volumes.
- Folder naming is Immich's global storage template plus per-user label/ID.
