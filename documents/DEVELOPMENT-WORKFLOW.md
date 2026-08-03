# Development workflow: Gitea, Woodpecker CI, and GitHub backup

This repo is designed so you can use **self-hosted Gitea** as the day-to-day remote, **Woodpecker CI** for pipelines, and **GitHub** (or another forge) as a **read-only mirror** for backup and visibility.

Use **placeholder** URLs in docs you commit publicly; set real URLs in your local git remotes and in Gitea/Woodpecker settings.

---

## 1. Remotes: Gitea canonical, GitHub mirror

After creating the repository on **Gitea** (e.g. `https://gitea.example.com/youruser/homelab`) and on **GitHub** (e.g. `https://github.com/youruser/homelab`):

```bash
# Clone from Gitea (or add origin if you already have a local copy)
git clone https://gitea.example.com/youruser/homelab.git
cd homelab

# Backup / mirror remote (HTTPS or SSH)
git remote add github https://github.com/youruser/homelab.git
# or: git remote add github git@github.com:youruser/homelab.git

git remote -v
# origin    -> Gitea
# github    -> GitHub
```

Daily workflow:

```bash
git push -u origin main
```

To push **both** remotes after each successful change (optional if you use Gitea push mirror below):

```bash
./scripts/push-github-mirror.sh main
```

---

## 2. Automatic mirror from Gitea (recommended)

So you do not have to remember `git push github`:

1. In **Gitea**: open the repo → **Settings** → **Git Hooks** / **Mirroring** (wording varies by Gitea version) → **Add push mirror**.
2. Set **Mirror URL** to your GitHub repo (`https://github.com/youruser/homelab.git` or SSH).
3. Use a **GitHub personal access token** (classic: `repo` scope) as the password for HTTPS, or deploy keys for SSH.
4. Enable **sync on push** (or periodic sync) per Gitea’s options.

Then a single `git push origin` updates Gitea; Gitea pushes to GitHub.

---

## 3. Woodpecker CI

1. In **Woodpecker**, enable this repository (it must be linked to your **Gitea** forge).
2. Ensure the **Woodpecker agent** can run Docker steps (default for a Docker-based agent).
3. Pipelines are defined in **`.woodpecker.yml`** at the repo root:
   - **gitleaks** — secret scan on the git checkout (history included).
   - **repository-validation** — runs the complete Compose, preparation,
     metadata, environment-example, documentation, and generated-file checks.

To skip a run for a commit message, use `[CI SKIP]` or `[SKIP CI]` (Woodpecker convention).

If **gitleaks** reports findings in **tracked** files, fix or allowlist via [Gitleaks config](https://github.com/gitleaks/gitleaks) (e.g. repo-root `.gitleaks.toml`). Local-only files such as `stack.env` are not in git and are not part of the default `gitleaks detect` scan of committed history—avoid committing them.

---

## 4. GitHub Actions (optional)

GitHub runs the same repository validation plus a committed-content Gitleaks
scan. The workflow uses read-only repository permissions and is suitable for a
backup mirror or pull-request checks.

---

## 5. Related docs

- [stacks/woodpecker-ci/README.md](../stacks/woodpecker-ci/README.md) — deploy Woodpecker server/agent and Gitea OAuth.
- [scripts/README.md](../scripts/README.md) — `scan-secrets-gitleaks.sh` for local scans (including `--no-git` for the working tree).
