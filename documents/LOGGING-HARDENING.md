# Logging hardening and migration

## Docker log rotation

The repository baseline is `config/docker/daemon.json`. It uses Docker's
`local` driver with a 10 MiB × 3 compressed-file ceiling per container.

Changing the daemon default requires a Docker daemon restart. Existing
containers retain their old logging driver until each container is recreated,
so roll stacks in small batches and verify health between batches:

```bash
docker compose --env-file stacks/STACK/stack.env \
  -f stacks/STACK/docker-compose.yml up -d --force-recreate
docker inspect CONTAINER --format '{{.HostConfig.LogConfig.Type}} {{json .HostConfig.LogConfig.Config}}'
```

Do not recreate every stack at once. Portainer-managed stacks and stacks with
external environment/config paths must be redeployed through their normal
deployment path.

## Alloy Docker access

Alloy connects to `alloy-docker-socket-proxy` rather than mounting
`/var/run/docker.sock`. The proxy permits only the read endpoints required for
container discovery, events, and network metadata; `POST=0` disables Docker
API writes.

Container log collection currently remains backward-compatible: an absent
`logging` label is accepted, `logging=true` is explicit opt-in, and
`logging=false` is explicit opt-out. Before switching to strict opt-in, add
`logging: "true"` to every intended service and compare the inventory against
Alloy's discovered targets.

## Loki 3 migration

The active Loki 2.9.8 configuration introduces TSDB schema v13 at
`2026-08-05T00:00:00Z`. Keep Loki 2.9.8 running until logs have been written
under that schema. Then:

1. Back up the `loki_data` volume and active configuration.
2. Confirm `/loki/tsdb-index` contains data newer than the schema boundary.
3. Validate a Loki 3 configuration with `-verify-config=true`.
4. Remove deprecated `shared_store` keys.
5. Upgrade one minor release at a time, checking `/ready`, recent writes, and
   queries across both the old boltdb-shipper and new TSDB periods.

Do not move the schema boundary backward after it has been deployed.
