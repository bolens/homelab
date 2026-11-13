# Development workflow: GitHub source and Gitea mirror

[Documentation](README.md)

GitHub is the authoritative repository. Self-hosted Gitea is a
fast-forward-only mirror for redundancy and local visibility. Pull requests
and Dependabot updates land on GitHub first. Every default-branch change is
squash-merged through a pull request; direct pushes and protection bypasses are
disabled.

Use **placeholder** URLs in docs you commit publicly; set real URLs in your local git remotes and in Gitea/Woodpecker settings.

---

## 1. Remotes: GitHub authoritative, Gitea mirror

After creating the repository on GitHub and Gitea:

```bash
git clone https://github.com/youruser/homelab.git
cd homelab

# Preserve the repository's established remote names.
git remote rename origin github
git remote add origin https://gitea.example.com/youruser/homelab.git
git branch --set-upstream-to=github/main main
git config remote.pushDefault github

git remote -v
# github    -> GitHub
# origin    -> Gitea
```

Daily synchronization:

```bash
git pull --ff-only
```

Synchronize Gitea manually:

```bash
cp scripts/sync-gitea-mirrors.sh scripts/sync-gitea-mirrors.local.sh
# Edit the ignored script with this host's repositories and remotes.
make mirror-sync
```

---

## 2. Automatic GitHub-to-Gitea mirror

Gitea cannot convert an existing normal repository into a pull mirror. This
repo therefore includes a user-level systemd timer that provides equivalent
safe behavior without recreating the Gitea repository:

```bash
mkdir -p ~/.config/systemd/user
install -m 0644 scripts/systemd/github-gitea-mirrors.* \
  ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now github-gitea-mirrors.timer
```

The timer runs every 15 minutes. It synchronizes the repositories configured in
the ignored, host-specific `scripts/sync-gitea-mirrors.local.sh`; start from
`scripts/sync-gitea-mirrors.sh`. For each repository, it
fetches GitHub `main`, confirms Gitea can fast-forward, pushes that exact commit
to the Gitea backup, and mirrors tags. It never force-pushes or deletes refs.
Direct commits to the configured backup refs are unsupported; if a backup diverges, synchronization
fails for that repository while the remaining repositories are still checked.

Each entry has `name|path|source-remote|backup-remote`, optionally followed by
`|destination-branch|tag-prefix`. The defaults are `main` and no tag prefix.
For a Gitea repository with its own maintained history or protected branches,
use `|github-main|github/`. This backs up GitHub's published `main` and tags to
separate refs while preserving Gitea's existing branches and tags. It does not
merge the two development histories or change Gitea's default branch.

The helper supports normal, linked, and bare repositories. It resolves configured
remote URLs, then fetches and pushes in a disposable bare repository. Local edits,
unpublished local tags, and working-copy hooks do not participate; the source is
the published GitHub ref. Source development still follows its normal PR and CI
requirements. Destination protections are respected, and a lookup failure stops
before publication. Existing destination branches must be ancestors of the source;
conflicting tags are refused. Branch and tag pushes are separate operations, so a
tag failure can follow a successful branch update; inspect both before retrying.

After changing the installed service definition, run `systemctl --user daemon-reload`
and verify its `ExecStart` points to `sync-gitea-mirrors.local.sh`. Keep the local
repository list ignored. Verify remote refs and the service result after a sync.

---

## 3. Local CI before pushing

`make ci-local` runs Mylar's portable publication controls through
`make mylar-source-check`: private-copy reader recovery, retained API and worker
handoffs, authenticated launch, workflow intake, archive adoption and NFS checks.
Set `ARCHIVING_UTILS_ROOT` to the checked archive SDK directory containing
`lib/archive_backend.py`; the complete gate refuses a missing SDK rather than
skipping its integration tests. `PUBLICATION_AUTH_BACKEND` selects the existing
fixture backend: `host` on the supported Arch host, or `target` in the Ubuntu
verification image.
They use disposable local files and SQLite, require no Docker access, and preserve
tracked source files. `MYLAR_PYTHON` selects the interpreter (default `python3`);
use Python 3.10 to match the native runtime. These source checks do not replace
the installed-image gate or protected NFS/reader integration acceptance.

Install the hooks once:

```bash
npm ci
make hooks-install
```

Each commit checks staged secrets, whitespace, dependency configuration,
GitHub workflow syntax/security, changed Dockerfiles, Compose rendering,
metadata, preparation scripts, and generated documentation. Run the full
all-files and Git-history suite on demand. Prepare a separate checkout of
`bolens/.github` at the exact `tooling-ref` in
`.github/workflows/source-lint.yml`, install its locked tools with
`npm ci --ignore-scripts --prefix /path/to/shared/tools/source-lint`, and provide
Ruff 0.17.4. This shared toolchain separately requires Node
`^22.22.2 || ^24.15.0 || >=26.0.0`. For Homelab source lint and full local CI,
use the intersection with this repository's Node range: Node 24.15.0 or newer
within 24.x, or Node 26.x. These are supported prerequisites. The local
source-lint wrapper does not check the Node version. Node 24.0 through 24.14
satisfies Homelab's package range but does not support this shared toolchain.
The shared source lint runs first, using the hosted configuration and rules.
Missing tools, a different checkout revision or changed tooling stop the gate;
validation does not clone or install tools automatically.

```bash
make ci-local JAVA_HOME_21=/path/to/jdk-21 SOURCE_LINT_TOOLING=/path/to/shared
```

After the Mylar controls, `ci-local` runs the Komga source/compile gate through
`make komga-source-check`, the same target used by hosted validation. Set
`JAVA_HOME_21` to a JDK 21 installation. It defaults to the hosted runner's
`JAVA_HOME_21_X64` when available. A missing JDK or failed gate stops the command;
the gate runs without Docker and does not observe or change service state.

The final secret scan checks every commit reachable from candidate `HEAD`. It
does not include unrelated local branch or snapshot histories. The staged-file
secret hook still checks new changes before commit. `make secrets` retains the
repository-wide scan across all refs.

Repository validation ShellChecks every tracked `*.sh` file, including
stack-local entrypoints and preparation helpers. GitHub pull requests render
only changed stacks when all changes are under `stacks/` or `portainer/`;
global configuration or tooling changes automatically trigger rendering of
every stack. The equivalent local command is:

```bash
make validate-changed BASE=origin/main
```

The hooks require Python with PyYAML, pre-commit, ShellCheck, Gitleaks,
actionlint, and Hadolint. The zizmor hook uses a native installation when
available and otherwise uses its pinned Docker image.

Install the locked Python validation dependency into the virtual environment or
managed Python interpreter used by `python3`:

```bash
python3 -m pip install --require-hashes -r .github/requirements-validation.txt
```

The lock includes the PyYAML source archive for interpreters without an allowed
wheel. Run `python3 -c 'import yaml; print(yaml.__version__)'` before validation
to confirm that the selected interpreter can import it.

Run the Pages browser suite separately because it starts Chrome and is slower
than the commit-time checks:

```bash
make site-test
```

To opt in to the same browser suite before every push, install the locked
Node dependencies and Playwright's Chrome browser, then install the pre-push
hook:

```bash
npm ci
npx --no-install playwright install chrome
make hooks-install-site
```

The opt-in hook uses two workers and CI mode, so it starts its own local
server and fails if port 4173 is already occupied. A failed test blocks the
push. `make hooks-install` and `make ci-local` do not enable or run this
browser hook. Hook installation is shared by linked worktrees; each checkout
used for pushing needs its own installed Node dependencies.

Run the hook directly with
`pre-commit run pre-push-site-browser-tests --hook-stage pre-push --all-files`.
To remove the optional push hook, run `pre-commit uninstall --hook-type pre-push`.
The commit hook remains installed.

CI runs the same locked Playwright and Axe suite before it publishes GitHub
Pages. The tests cover serious accessibility violations, catalog search and
filters, keyboard skip navigation, JavaScript errors, and mobile overflow.

---

## CI organization

Use the [shared CI vocabulary](https://github.com/bolens/.github/blob/main/docs/woodpecker-transition.md#ci-organization): `validate`, `test`, `site` and `publish` describe purpose; existing workflow names and required status identities stay unchanged. Run commands from the repository root with the documented toolchain.

| Phase / group | Canonical local entrypoint | Native mapping / retained owner |
| --- | --- | --- |
| `validate` / repository and secrets | `make validate-changed BASE=origin/main`; full `make ci-local JAVA_HOME_21=/path/to/jdk-21 SOURCE_LINT_TOOLING=/path/to/shared` after the setup above | `woodpecker` / `repository-validation`, `gitleaks`; strict validation checks all portable contracts and generated content. |
| `validate` / source and workflow policy | `make source-lint SOURCE_LINT_TOOLING=/path/to/shared`; `actionlint`; `zizmor --offline --min-severity medium --min-confidence medium .github .pre-commit-config.yaml` | `source-and-workflow-policy` also owns pinned Spec Kit integrity and Hadolint. |
| `test` / source and compiler controls | Existing focused Make targets documented above and in the owning stack guides | `komga-source-controls`, `kavita-dotnet-controls`, and `publisher-broker-tests`; private or installed-runtime controls remain separate from portable source proof. |
| `site` / generated site and browser checks | `make pages-check`; `make site-test` | `site-quality`; Pages retains its own publication-coupled browser acceptance and protected OIDC deployment. |
| `validate` / scheduled links | `python3 scripts/ci/check-native-links.py` with the pinned Lychee tool | `weekly-documentation-links` on cron/manual; internal failures are fatal, external reporting is explicitly nonblocking. |
| `publish` / custom images | The reviewed image contexts and selectors in `.github/custom-images.json` and [RELEASING.md](../RELEASING.md#custom-image-ci-selection) | Retained hosted builds/runtime checks publish only selected trusted-main images. Native validation has no publisher credentials or host Docker socket. |

Duplicate hosted Source lint, Dockerfile Lint, Workflow Security and Weekly Maintenance workflows are retired. The retained repository-validation workflow still owns its nonportable checks; managed security, actual image builds, metadata and deployment remain hosted. The recovery rules below preserve replacement-check proof and operator authority. Repository validation does not deploy any stack.

## 4. Woodpecker CI

Enable the intended repository on the native GitHub or Gitea forge and use the
root `.woodpecker.yml`. It retains the single `woodpecker` result on every push,
PR, manual run and cron, without path filters that could omit a required result.
The Linux Docker backend needs no published port, host mount, Docker socket,
privileged step, registry login or pipeline secret for these checks.

The pipeline runs:

- full-history Gitleaks and `make validate-strict`, including all portable stack
  contracts, generated content and the existing Python/Node suites;
- pinned shared source lint, actionlint, offline zizmor, Spec Kit integrity and
  Hadolint for tracked files named exactly `Dockerfile`;
- the existing Komga source/compile controls with JDK 21;
- the default-CI Kavita compiler controls with .NET SDK 10.0.403 and Node 26.7.0,
  requiring at least nine executed tests and no skips;
- the locked Playwright/Axe site suite using the existing Chrome channel;
- publisher-broker race tests and vet; and
- internal documentation links on cron/manual runs, with external URLs remaining
  a report-only check under the existing weekly workflow's exact arguments.

Tool downloads retain a 15-second socket inactivity timeout, a 256 MiB byte bound
and the pinned SHA-256 check. EOF and verified content determine completion; a
progressing download is not cut off by a second total bootstrap timer. The
existing pipeline timeout still bounds the whole CI job.

The general repository suite can still report optional compiler probes skipped
in its Node image. The dedicated .NET lane closes the ordinary hosted compiler
coverage; optional installed-assembly/source probes still require their explicit
private inputs and are not claimed as executed. Neither lane runs application
services or accesses live data.

Each link scan has a 180-second reporting ceiling. An external timeout prints an
explicit incomplete-report warning and establishes no link success; it remains
nonblocking. Internal errors/timeouts and missing tools remain fatal, as do
checksum or tool-install failures before a scan.

The wrapper-based validation lanes check the exact committed revision in separate
full disposable clones. Their Python environments, npm modules, downloads and
caches live under a unique `/tmp` directory and are removed on exit. The existing
Gitleaks and Go lanes use the initial pipeline checkout. Docker/Compose are checksum-bound CLI tools
used only to render configurations; their socket points to an absent task-local
path. Compose is registered in the disposable container's standard system plugin
directory so fixtures can use their own empty `HOME`/`DOCKER_CONFIG` without
losing the plugin. Registration refuses host execution, checksum changes and
existing unrelated plugins. No host plugin directory is changed. No Alpine/glibc
Python environment or browser cache is shared across images.

Public executable pins and SHA-256 checksums are in
[`scripts/ci/native-tools.json`](../scripts/ci/native-tools.json). The bootstrap
checks HTTPS origins, archive paths, entry types, size limits and hashes before
executing tools. Chrome for Testing is the fixed Google artifact selected there;
Playwright's Chrome channel and locked test dependencies remain unchanged.
Native Python tools use the hashed
[requirements](../.github/requirements-native-ci.txt). Refresh a tool's version,
primary-source checksum and coupled tests together; rerun its actual image lane.
Renovate monitors Woodpecker image references, and Dependabot monitors the Python
requirements. The raw executable manifest requires a reviewed coordinated update.

### Hosted retirement and recovery

`WOODPECKER_LINUX_CI` defaults off. With it absent or false, existing hosted pure
validation still runs. An operator may set it to `true` only after the same native
candidate passes a PR, a genuine merged-main push and a configured weekly cron
(the existing Monday 08:41 UTC schedule), and the protected branch requires the
actual native result on the latest SHA. Keep native trust/fork approval enabled.
There is no publishing-flag dependency for homelab. This source change does not
set the variable, create a cron or change protection.

To recover, clear `WOODPECKER_LINUX_CI` and verify the hosted required producers
on a new run before changing protection. Preserve the native check until its
replacement is proven. GitHub retains actual Docker image builds/runtime tests
and publication, Mylar and converter fixtures, CodeQL, dependency review,
Scorecard, Pages OIDC deployment and deployment-bound browser evidence, metadata
automation and Spec Kit update PRs. The Pages job's own pre-deployment browser
check remains coupled to its publication rather than trusting an unrelated run.

To skip a run for a commit message, use `[CI SKIP]` or `[SKIP CI]` (Woodpecker convention).

If **gitleaks** reports findings in **tracked** files, fix or allowlist via [Gitleaks config](https://github.com/gitleaks/gitleaks) (e.g. repo-root `.gitleaks.toml`). Local-only files such as `stack.env` are not in git and are not part of the default `gitleaks detect` scan of committed history, avoid committing them.

---

## 5. GitHub Actions

GitHub retains the same portable validation as the default fallback described
above, plus the Docker, deployment and managed security exceptions. Validation
uses read-only repository permissions.

Additional narrowly scoped workflows provide:

- advanced CodeQL analysis for Python and GitHub Actions with the
  `security-extended` query suite;
- pull-request dependency review for newly introduced high or critical
  vulnerabilities;
- actionlint and zizmor checks for workflow correctness and security;
- Hadolint checks for maintained Dockerfiles;
- weekly repository, secret, and documentation-link checks; and
- weekly OpenSSF Scorecard results in GitHub code scanning.

Actions are pinned to immutable commit SHAs. Dependabot proposes grouped,
reviewed updates for Actions, Dockerfiles, Compose images, and the root npm
manifest. Those managers are disabled in Renovate to prevent duplicate pull
requests; Renovate remains available for other supported dependency types.
Dockerfile update directories are listed explicitly and checked for complete,
non-overlapping coverage. Acquire and Privotron stay on Python 3.13 until their
application locks support a newer runtime; their separate update group still
receives digest refreshes. AIL's native builder stays on Ubuntu 22.04, enforced by
the custom-image contract test. The interim Ubuntu 25.10 release is explicitly
ignored; this does not suppress other stacks' selected Ubuntu 26.04 digest
updates. Docker ignore conditions use numeric Bundler requirements such as
`0.15.6`, rather than image tags such as `v0.15.6`; local validation checks this
syntax. Treat runtime migrations as reviewed application changes.

Database major upgrades require a verified restore/migration and matching volume
contracts. PostgreSQL, PostGIS and MongoDB major proposals are held for that work;
current-major security and digest updates remain enabled. Inspect the published
engine version for floating database tags before accepting a digest refresh.

Security-reporting workflows grant
`security-events: write` only to jobs that upload results; other workflows and
jobs retain read-only or empty default permissions.

CodeQL uses the committed advanced workflow in
`.github/workflows/codeql.yml`. Do not also enable GitHub's default CodeQL
setup, because that would duplicate analysis.

---

## 6. Related docs

- [stacks/woodpecker-ci/README.md](../stacks/woodpecker-ci/README.md), deploy Woodpecker server/agent and Gitea OAuth.
- [scripts/README.md](../scripts/README.md), `scan-secrets-gitleaks.sh` for local scans (including `--no-git` for the working tree).
