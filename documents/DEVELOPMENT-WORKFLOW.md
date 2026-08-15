# Development workflow: GitHub source and Gitea mirror

GitHub is the authoritative repository. Self-hosted Gitea is a
fast-forward-only mirror for redundancy and local visibility. Pull requests,
Dependabot updates, and normal pushes land on GitHub first.

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

Daily workflow:

```bash
git pull --ff-only
git push
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
Direct commits to Gitea are unsupported; if a backup diverges, synchronization
fails for that repository while the remaining repositories are still checked.

---

## 3. Local CI before pushing

Install the hooks once:

```bash
make hooks-install
```

Each commit checks staged secrets, whitespace, dependency configuration,
GitHub workflow syntax/security, changed Dockerfiles, Compose rendering,
metadata, preparation scripts, and generated documentation. Run the full
all-files and Git-history suite on demand:

```bash
make ci-local
```

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

---

## 4. Woodpecker CI

1. In **Woodpecker**, enable this repository (it must be linked to your **Gitea** forge).
2. Ensure the **Woodpecker agent** can run Docker steps (default for a Docker-based agent).
3. Pipelines are defined in **`.woodpecker.yml`** at the repo root:
   - **gitleaks** — secret scan on the git checkout (history included).
   - **repository-validation** — runs the complete Compose, preparation,
     metadata, environment-example, documentation, and generated-file checks.

To skip a run for a commit message, use `[CI SKIP]` or `[SKIP CI]` (Woodpecker convention).

If **gitleaks** reports findings in **tracked** files, fix or allowlist via [Gitleaks config](https://github.com/gitleaks/gitleaks) (e.g. repo-root `.gitleaks.toml`). Local-only files such as `stack.env` are not in git and are not part of the default `gitleaks detect` scan of committed history—avoid committing them.

---

## 5. GitHub Actions

GitHub runs the same repository validation plus a committed-content Gitleaks
scan. The primary workflow uses read-only repository permissions and is
suitable for a backup mirror or pull-request checks.

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
Security-reporting workflows grant
`security-events: write` only to jobs that upload results; other workflows and
jobs retain read-only or empty default permissions.

CodeQL uses the committed advanced workflow in
`.github/workflows/codeql.yml`. Do not also enable GitHub's default CodeQL
setup, because that would duplicate analysis.

---

## 6. Related docs

- [stacks/woodpecker-ci/README.md](../stacks/woodpecker-ci/README.md) — deploy Woodpecker server/agent and Gitea OAuth.
- [scripts/README.md](../scripts/README.md) — `scan-secrets-gitleaks.sh` for local scans (including `--no-git` for the working tree).
