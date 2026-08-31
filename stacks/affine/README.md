# AFFiNE

AFFiNE is a self-hosted collaborative knowledge workspace combining docs, whiteboards, and a knowledge graph in one app.

**Website:** https://affine.pro
**Docs:** https://docs.affine.pro/self-host-affine
**GitHub:** https://github.com/toeverything/AFFiNE

## Usage

Accessed via browser through Caddy on the `ingress-public` network. The current
self-host architecture runs the AFFiNE server with a one-shot schema migration
job, PostgreSQL/pgvector, and Redis. Only the AFFiNE application joins the
ingress network; its database and cache remain on an internal network.

## Setup

1. Run `./prepare-stack.sh`.
2. Set `AFFINE_SERVER_EXTERNAL_URL` to the public AFFiNE URL in `stack.env`.
3. Replace `DB_PASSWORD` with a unique, randomly generated password.
4. Validate and deploy:

   ```bash
   docker compose --env-file stack.env config --quiet
   docker compose --env-file stack.env up -d
   docker compose --env-file stack.env ps
   ```

The `affine-migration` container must finish successfully before `affine`
starts. It is expected to remain in the exited state after a successful run.

## Environment variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `AFFINE_SERVER_EXTERNAL_URL` | Yes | None | Public URL for callbacks and generated links |
| `DB_USERNAME` | Yes | `affine` | Dedicated PostgreSQL role |
| `DB_PASSWORD` | Yes | None | Unique PostgreSQL password |
| `DB_DATABASE` | No | `affine` | Dedicated PostgreSQL database |

## Migration from `affine-self-hosted`

This stack replaces the retired single-container
`ghcr.io/toeverything/affine-self-hosted` deployment. The old `affine_data`
volume does not contain the PostgreSQL database required by current AFFiNE and
is not mounted automatically.

Before upgrading a host that ran the old stack:

1. Back up the old `affine_data` volume and do not run
   `docker compose down -v`.
2. Export any accessible workspaces from the old AFFiNE instance.
3. Deploy this stack as a fresh current instance.
4. Import supported exports through AFFiNE.

There is no automatic in-place conversion in this Compose stack. Keep the old
volume until the new instance and imported workspaces have been verified.

## Notes

- The `ingress-public` network must exist before deployment.
- Back up `affine_storage`, `affine_config`, and `affine_postgres` together.
  Redis data is persisted for resilience but is not a substitute for the
  PostgreSQL and storage backups.
- Images are pinned to immutable multi-platform manifest digests. Dependency
  automation can propose reviewed digest updates.
- First-run setup happens in the browser on initial visit.
