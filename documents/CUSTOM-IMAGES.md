# Custom container images

GitHub Actions builds the repository's self-contained Dockerfiles and publishes
them to GHCR after changes reach `main`. Pull requests build the same matrix
without publishing it.

Each image has two tags:

- `ghcr.io/bolens/homelab-<name>:latest`
- `ghcr.io/bolens/homelab-<name>:sha-<commit>`

Use the commit tag for reproducible deployments. The workflow attaches build
provenance and an SBOM to each published image.

The matrix excludes images whose build context is not committed:

- AIL Framework's build and runtime stages require its local vendor checkout.
- Nodepad requires the source created by `clone-repo.sh`.
- The SearxNG 4get images require operator-verified source directories.

Those images remain local builds until their source preparation is made
reproducible in CI.
