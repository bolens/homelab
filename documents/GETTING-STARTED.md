# Getting started

This is the shortest safe path from a new clone to one working stack. The
repository is a catalog: deploy only the services you need.

## 1. Prepare the host

Install Git, Python 3, Docker Engine, and the Docker Compose plugin. Give your
user Docker access, or run Docker commands through your normal privilege
workflow. PyYAML is required for repository validation; ShellCheck and Gitleaks
are strongly recommended for contributors.

Clone the repository, then run:

```bash
make doctor
make validate
make hooks-install
```

`make doctor` is read-only. Warnings about an `ingress-*` zone, `telemetry`, `usenet`, or `torrents`
are expected until you select a stack that needs those networks.

## 2. Set host-wide values

Create the optional shared timezone and locale file:

```bash
cp shared.env.example shared.env
```

Edit `shared.env`. It is ignored by Git. Never place real passwords, API keys,
hostnames, IP addresses, or personal paths in an `.example` file.

Media stacks default to paths below `/mnt/unraid/media`. If your storage lives
elsewhere, change the path variables in that stack's `stack.env`. Confirm a
remote filesystem is mounted before starting Docker; an empty local directory
at the same path can otherwise receive data unexpectedly.

## 3. Choose and prepare a stack

Read `stacks/<name>/README.md`, then:

```bash
cd stacks/<name>
./prepare-stack.sh
```

If a stack has no preparation script, copy only the examples its README names,
usually:

```bash
cp stack.env.example stack.env
cp caddy_snippet.conf.example caddy_snippet.conf
```

Edit `stack.env`, generate unique secrets, and replace example domains. If a
preparation script exists, run it again after editing so `.env` stays in sync.
Do not commit `stack.env`, `.env`, live Caddy snippets, or application configs.

## 4. Create required shared resources

The stack README and Compose file declare any external networks or volumes.
Common one-time networks are:

```bash
docker network create ingress-public
docker network create ingress-admin
docker network create ingress-sensitive
docker network create --internal telemetry
docker network create --internal mail-clients
docker network create mail-egress
docker network create --internal ai-backend
docker network create usenet
docker network create torrents
```

Create only what your selected stacks require. The three `ingress-*` networks are
limited to Caddy and HTTP backends in the corresponding trust zone; other shared
dependencies use their dedicated internal network.
The download networks connect compatible clients and *arr applications.

## 5. Validate and deploy

From the stack directory:

```bash
docker compose config --quiet
docker compose pull
docker compose up -d
docker compose ps
docker compose logs --tail 100
```

Do not use `docker compose down -v` during routine maintenance: `-v` removes
named volumes. Back up application data and databases before major upgrades.

For a web application, merge or import its generated `caddy_snippet.conf` using
the Caddy workflow documented by that stack. Point the Cloudflare Tunnel at
Caddy, not directly at every application container. Internally, Caddy reaches a
service by its Compose service/container name and container port, such as
`http://sonarr:8989`.

## 6. Verify and maintain

Check the container health state, local Caddy route, and public hostname. Then
re-run:

```bash
make doctor
make validate
make secrets
```

Before committing, inspect `git status`, review the complete diff, and run
`make ci-local`. Installed pre-commit hooks run the staged subset
automatically. Run `make secrets-files` as an additional local safety check;
that mode scans ignored runtime files too, so do not paste its raw findings
into issues or chat.

For shared networks, mounts, MinIO, mail, and AI backends, continue with
[Shared resources](SHARED-RESOURCES.md). For failures, use
[Troubleshooting](TROUBLESHOOTING.md). Repository maintainers should also read
[Development workflow](DEVELOPMENT-WORKFLOW.md).
