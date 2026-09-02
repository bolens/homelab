# Custom container images

GitHub Actions builds the repository's self-contained Dockerfiles and publishes
them to GHCR after changes reach `main`. Pull requests build the same matrix
without publishing it.

Each image has two tags:

- `ghcr.io/bolens/homelab-<name>:latest`
- `ghcr.io/bolens/homelab-<name>:sha-<commit>`

Use the commit tag for reproducible deployments. The workflow attaches build
provenance and an SBOM to each published image.

Stacks use GHCR by default. Each Compose image has a stack-specific
`*_IMAGE` override. Set that variable to
`harbor.bolens.dev/homelab/<name>:latest` in `stack.env` or Portainer when
GHCR is unavailable. Compose cannot automatically try a second registry.

The matrix excludes images whose build context is not committed:

- AIL Framework's build and runtime stages require its local vendor checkout.
- Nodepad requires the source created by `clone-repo.sh`.
- The SearxNG 4get images require operator-verified source directories.

Those images remain local builds until their source preparation is made
reproducible in CI.
