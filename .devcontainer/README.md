# homelab devcontainer

Open this repository in VS Code and run **Dev Containers: Reopen in
Container**. A local Docker-compatible engine and the Dev Containers extension
are required. The first build downloads the pinned tool images and distribution
packages. Setup installs dependencies from this checkout's lockfiles and runs
`smoke.sh`. Rebuild the container after Dockerfile changes. Rerun
`bash .devcontainer/post-create.sh` after changing dependency lockfiles.

Includes Docker CLI/Compose, YAML validation, Python and the locked
Markdown/site tools. No host Docker socket is mounted. Compose rendering works
offline with tracked examples. Image builds or deployments require an
explicitly configured disposable engine. Do not use production stack
environment files for tests.

Run from the workspace root:

```sh
make validate
```

The editor runs as `vscode`, with its UID adjusted for the local workspace. The
source is bind-mounted at `/workspace` and is never copied into image layers.
Use a regular clone when the container cannot see a linked worktree's external
Git directory. Keep credentials in your local development environment.

`bash .devcontainer/smoke.sh` checks installed tools and checkout access. It
does not run the application test suite. No application starts automatically.
Image references include immutable digests. Dependabot monitors the Dockerfiles
where supported. Distribution packages resolve from the configured Debian
repositories at build time. Update image pins and rerun setup and native checks
together. Existing native and Nix workflows remain available independently.

For catalog browser tests, install the lockfile-matched browser and its Linux
libraries inside the container, then run the site suite:

```sh
npx --no-install playwright install --with-deps chromium
make site-test
```
