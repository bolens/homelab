# Paperclip

Orchestrate AI agents, assign work, and track budgets from a web dashboard.
Paperclip includes email/password authentication through Better Auth.

- [Project](https://paperclip.ing)
- [Documentation](https://docs.paperclip.ing)
- [Source](https://github.com/paperclipai/paperclip)
- [Container image](https://github.com/paperclipai/paperclip/pkgs/container/paperclip)
- [Pinned release](https://github.com/paperclipai/paperclip/releases/tag/v2026.1106.0)

## Deployment

1. Run `./prepare-stack.sh`. It preserves existing runtime files, copies the
   environment and Caddy examples, ensures `ingress-admin`, and refreshes `.env`
   from `stack.env`. It never starts containers.
2. Edit `stack.env`. Set `PAPERCLIP_PUBLIC_URL` to the HTTPS origin and set
   `BETTER_AUTH_SECRET`, `POSTGRES_PASSWORD`, and
   `PAPERCLIP_TOOL_ACTION_SIGNING_SECRET` to separate new `openssl rand -hex 32`
   values. Keep these secrets.
3. Replace `paperclip.example.com` in the ignored `caddy_snippet.conf`.
4. Start with `docker compose --env-file stack.env up -d`.
5. Validate the existing Caddy configuration, including its stack-snippet import,
   then reload Caddy. See [Caddy](../caddy/README.md).
6. Add a Cloudflare Tunnel published application route for your hostname to
   `http://caddy:80`. HTTPS terminates at Cloudflare. The supplied snippet sets
   the forwarded HTTPS headers and supports WebSocket upgrades.
7. Generate a private, one-time admin invite with the helper below, then open
   that invite and create your account. It expires after 24 hours and does not
   replace an existing administrator. Do not publish the invite or its output.
8. After creating the intended accounts, set `PAPERCLIP_AUTH_DISABLE_SIGN_UP=true`
   and run `docker compose --env-file stack.env up -d` to close registration.

Generate the first administrator invite from this directory:

```bash
docker compose --env-file stack.env exec -T paperclip node --input-type=module < bootstrap-admin.mjs
```

The helper uses the bundled CLI and a disposable configuration file inside the
container. It preserves server configuration and does not pass `--force`.

Keep signup closed outside the initial setup window. A login page alone does not
restrict who can register. Cloudflare Access is optional additional protection,
but remote agents and webhooks need an explicit machine-access policy if enabled.

## Hosts with exhausted Docker address pools

If network creation fails with `all predefined address pools have been fully
subnetted`, inspect existing Docker subnets and host/VPN routes. Choose an unused
small private subnet, set `PAPERCLIP_SUBNET` in `stack.env`, and opt in by copying
`docker-compose.subnet.yml` to the ignored `docker-compose.override.yml`.
Preparation never enables this override. Standard Compose discovery loads it
alongside the base file. When passing explicit `-f` options, pass both files:

```bash
docker compose --env-file stack.env -f docker-compose.yml -f docker-compose.override.yml up -d
```

Do not remove existing networks or change Docker's global pools to deploy this
stack. A small `/28` leaves room for the two services and their bridge gateway.

## Environment variables

| Variable | Purpose |
| --- | --- |
| `PAPERCLIP_PUBLIC_URL` | Required HTTPS origin for login, cookies, and links |
| `BETTER_AUTH_SECRET` | Required persistent session-signing secret |
| `PAPERCLIP_TOOL_ACTION_SIGNING_SECRET` | Required independent key for signed approval actions |
| `POSTGRES_PASSWORD` | Required PostgreSQL password, use hex to avoid URL escaping |
| `PAPERCLIP_AUTH_DISABLE_SIGN_UP` | Close account registration after onboarding |
| `PAPERCLIP_SUBNET` | Optional private subnet used only by the opt-in network override |
| `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY` | Optional provider credentials for local adapters |

Locale settings belong in the optional `../../shared.env`. Provider credentials
can be configured later through Paperclip. Without credentials, the dashboard
starts but agents cannot make paid provider calls. No host home directory,
provider credential directory, Docker socket, or device is mounted.

## Storage and runtime

The digest-pinned `2026.1106.0` image runs the server and bundled agent CLIs.
Public authenticated mode requires a separate PostgreSQL connection. A pinned
PostgreSQL 17 service stores its database in `paperclip_paperclip_pgdata` on the
private stack network, with no host port or Caddy network access. Named volume
`paperclip_paperclip_data` persists `/paperclip`: uploads, encryption key,
workspaces, backups, and CLI state.
The entrypoint initializes volume ownership and drops to UID/GID 1000.

Only the app joins `ingress-admin` for Caddy. Port 3100 is internal, with no host
port published. Public exposure uses authenticated mode with an explicit URL.
The app has a 2 CPU, 4 GiB memory, and 2048 process ceiling. PostgreSQL has
a 1 CPU and 1 GiB memory ceiling. Agent workloads
share these limits. Raise them deliberately if agent runs need more resources.

## Selected release and existing overrides

[2026.1106.0](https://github.com/paperclipai/paperclip/releases/tag/v2026.1106.0)
removes the Pipelines experiment while retaining its stored records. New agents
use the native Runner on supported hosts; existing agents retain their runner.
Run-history API clients must paginate, and run-failure reporting is now opt-in.
Review those changes against the existing agent and API configuration before an
operator upgrades the service.

The optional Codex Git workaround below remains a separate, explicitly pinned
`2026.1023.0` image with its original source-hash guards. Selecting that override
keeps that image rather than the updated base image. Its maintained port or
retirement needs its own source and authentication verification. Preserve the
existing override selection until that work is accepted.

## Codex and private GitHub repositories

Connect GitHub in Paperclip, then attach the repository under the project's
Configuration tab. A connector alone does not create a local Git checkout.
Paperclip can clone private repositories with the responsible user's existing
managed GitHub identity. OpenAI sign-in does not authenticate GitHub.

Release `2026.1023.0` omits its scoped GitHub broker capability from Codex shell
environments. This causes `GitHub capability_missing` even with a connected
account. The optional local image fixes the CLI and ACP allowlists while retaining
the exclusions for provider keys, GitHub tokens, and other host secrets:

```bash
docker compose --env-file stack.env -f docker-compose.yml -f docker-compose.codex-git.yml build paperclip
docker compose --env-file stack.env -f docker-compose.yml -f docker-compose.codex-git.yml up -d --no-deps paperclip
```

If using the subnet override, also pass `-f docker-compose.override.yml` before
the Codex override. Keep the same file list for later deployments. Preparation
does not enable this workaround. The build context excludes runtime configuration.
The patch verifies both upstream source hashes and refuses other versions. Review
and retire it when upgrading to a release with the corrected allowlist.

The broker still checks each operation against the run's identity and policy.
No persistent GitHub token or host credential directory is added. Verify a fresh
agent shell can fetch the attached private repository and create a local commit.
Do not use a push as an authentication test. Preserve a verified backup before
recreating the service, and retain the original image for rollback.

## Optional nested Codex sandbox

Docker's default seccomp policy blocks the namespace operations used by Codex's
Linux sandbox. If agent commands report disabled user namespaces even though the
host permits them, opt in to `docker-compose.codex-sandbox.yml` alongside the
existing Compose files. For the local Git workaround, for example:

```bash
docker compose --env-file stack.env -f docker-compose.yml -f docker-compose.codex-git.yml -f docker-compose.codex-sandbox.yml up -d --no-deps --pull never --no-build paperclip
```

Preserve a verified recoverable backup before recreation, and retain this override
on later deployments. This enables inner sandbox creation; it does not disable
Codex approval, filesystem or network policies. It adds no capability, privileged
mode, device, Docker socket, host mount or host sysctl change. The server still
drops to UID/GID 1000. The outer container's networking and volume access remain
those of the other Compose files.

`codex-seccomp.json` is the Moby default profile at commit
`4b8214fc4971e06172938a1f1554ccff6647ee80`, upstream SHA-256
`6416b47770785a41ac59073cdc77d9fe98517df2799dc83ef207e622de3053f6`,
with one added allow rule for `clone`, `unshare`, `setns`, `mount`, `umount2` and
`pivot_root`. Kernel capability checks still apply. These operations are required
to create and populate the nested sandbox, and expose more kernel namespace/mount
surface than Docker's default. The remainder of the default deny policy is
retained, including the `clone3` fallback and blocked privileged syscalls. Do not
substitute `seccomp=unconfined` or add `SYS_ADMIN` to resolve a later failure.

When updating Docker or Codex, compare the pinned profile with the new Moby
default and carry forward only the verified nested-sandbox exceptions. Verify an
unprivileged command starts, a workspace write succeeds, an outside-workspace
write fails, and current network restrictions hold. A passing CLI smoke check
does not prove provider authentication or application acceptance. Preparation
does not enable the override. To roll back, recreate the same app image with the
previous Compose file list, leaving the persistent volumes intact.

## Optional agent build and Chromium tools

The server's Node runtime is separate from project build requirements. Operators
can prepare a persistent Node 26 toolchain with private Chromium OS libraries in
a dedicated Root-owned `paperclip_web_tools` volume at `/opt/paperclip-web`. It adds no service, port, Docker socket, host
package, credential or agent privilege. Paperclip application code is unchanged.
This is a Debian 13/Linux x86_64 recipe for the pinned image. Preparation checks
the Node archive against the official HTTPS checksum list and downloads Debian
packages using authenticated repository metadata. It extracts libraries into a
private prefix rather than installing them into the operating system.

The same release includes pinned Markdownlint and Spec Kit, plus an isolated
standalone Python with pip and `ensurepip`. It also exposes ShellCheck, Ruff,
actionlint, zizmor, Hadolint, Gitleaks, uv/uvx, ps, zip/unzip and xz. The wrapper exposes these tools and
Markdown link-parser dependencies on PATH. System Python remains unchanged.
Spec Kit is installed from its official tagged source; uv comes from a pinned,
SHA-256-verified PyPI wheel and supplies its catalog-pinned CPython distribution.
Additional native checker binaries come from official GitHub release assets,
with exact URLs and SHA-256 digests in the manifest. ShellCheck and archive/process
utilities come from the same authenticated Debian extraction. Package inventories
and lockfiles remain with each release. uv uses agent-owned persistent storage
for later environments; the prepared release remains immutable.

Configure the tool versions, bootstrap checksum, release revision, timeout and heap limit in
`web-toolchain.json`. Run these explicit operator commands from this directory:

```bash
docker compose exec -T paperclip sh -c 'cat > /tmp/web-toolchain.json' < web-toolchain.json
docker compose exec -T paperclip bash -s -- /tmp/web-toolchain.json < prepare-web-toolchain.sh
```

Agents run project commands from an isolated checkout through the stable entry:

```bash
/opt/paperclip-web/web/bin/run node --version
/opt/paperclip-web/web/bin/run npm run build
/opt/paperclip-web/web/bin/run node scripts/check-guides-browser.mts --engine=chromium
```

The wrapper admits one build/browser command at a time, limits it to 15 minutes
by default, and sets a 1536 MiB Node heap limit. Existing container CPU/memory
ceilings still apply. Busy exits with 75; record an owned dependency rather than
polling. It does not authorize arbitrary tests, external browser sessions or
live-account actions. Project instructions and the task's scope still govern
which commands can run. Builds and browser jobs must use the same exact source
and artifact identity. Browser execution is synthetic and local unless separately
authorized.

Browser binaries remain matched to the project's locked Playwright/Puppeteer
dependency. Install only the required browser as UID 1000, using the project-local
CLI through this wrapper and its persistent `/paperclip/.cache/ms-playwright`
cache. Do not run `install --with-deps` as an agent: the operator has already
prepared private OS libraries. Puppeteer can use its pinned downloaded browser,
or an explicitly compatible executable via `PUPPETEER_EXECUTABLE_PATH`; an
installed Chromium alone does not prove protocol/version compatibility.

For updates, edit the manifest and increment its revision, then run preparation
again. A changed manifest without a revision bump is refused. It builds a new
immutable release under `/opt/paperclip-web/releases/`, checks Node, qualifies the relocated developer CLIs and a fresh
Python venv, and atomically selects it via the `web` symlink.
Preparation never executes browser caches or other agent-owned files as Root.
Qualify the project-pinned browser separately as UID1000. The operator manifest
must be Root-owned and not writable by agents; staging stays private until
promotion. Existing releases under the older agent-owned `/paperclip/toolchains`
path must be prepared afresh in the dedicated volume, not copied or executed
as Root. An existing ready release is a no-op. Active jobs retain their resolved release.
Failed preparation retains scratch for diagnosis without replacing the current
release. No automatic updates, image rebuild or service restart occur.

Rollback by atomically repointing `web` to the previous retained ready release.
Do not remove a release while jobs use it. Retain the current and previous
release, their manifest/checksums, and remove older releases or failed scratch
only during explicit maintenance after confirming they are unused. Back up this
volume through the normal stack policy. A base-image/OS upgrade requires renewed
library and browser qualification; do not assume a persistent prefix is compatible.

## Verification and troubleshooting

- `docker compose ps` should report healthy. The health check requests
  `/api/health` internally with a two-minute initial grace period.
- Check the HTTPS login page and verify unauthenticated requests to
  `/api/companies` are refused. Check that the hostname resolves and the tunnel
  points to Caddy if the page is unavailable.
- Sign in, create a company, and confirm it survives a service recreation before
  trusting persistence. Run an adapter environment check before assigning work.
- A 502 usually means the app is unready or Caddy lacks `ingress-admin` access.
  Login origin errors usually mean `PAPERCLIP_PUBLIC_URL` or forwarded HTTPS
  headers do not match the browser URL.
- Inspect logs privately. Startup output can include an ownership-claim secret.

## Backup, upgrade, and rollback

Before an upgrade, record the image digest, app record counts, and representative
uploads/workspaces. Stop both services in this stack, then back up both complete named volumes
and private `stack.env`, `.env`, and Caddy snippet. Keep backups outside Git.
Restore to an isolated volume, compare file hashes, and verify PostgreSQL
readability with the matching version before applying an update.

Review upstream migrations before changing the image pin. Start the new version,
verify login and adapter behavior, and compare companies, agents, tasks, files,
and database integrity with the baseline. A healthy container alone is insufficient.
If verification fails, stop both stack services and restore the verified volumes and config
with the prior image. An older image alone may not read migrated data. Retain
backup evidence if verification is inconclusive. Remove only disposable backup
and restore copies created for a completed, verified operation. Never use
`docker compose down -v` for routine maintenance.
