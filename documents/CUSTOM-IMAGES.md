# Custom container images

[Documentation](README.md)

GitHub Actions builds the images in `.github/custom-images.json` and publishes
them to GHCR after changes reach `main`. Pull requests build the same matrix
without publishing it.

Each image has two tags:

- `ghcr.io/bolens/homelab-<name>:latest`
- `ghcr.io/bolens/homelab-<name>:sha-<commit>`

Use the commit tag for reproducible deployments. The workflow attaches build
provenance and an SBOM to each published image.

Most listed stacks use GHCR by default. Their Compose images have a stack-specific
`*_IMAGE` override. Set that variable to
`harbor.bolens.dev/homelab/<name>:latest` in `stack.env` or Portainer when
GHCR is unavailable. Compose cannot automatically try a second registry.

Nodepad CI runs `stacks/nodepad/clone-repo.sh` before building. That script
fetches a pinned upstream revision and applies the tracked patches. Its image is
`ghcr.io/bolens/homelab-nodepad`. The patched Readarr metadata service is
`ghcr.io/bolens/homelab-rreading-glasses`. These two stacks retain their existing
local build defaults; operators can select the published image explicitly.

The matrix excludes images whose required source is unavailable in CI:

- AIL Framework's build and runtime stages require its local vendor checkout.
- The SearxNG 4get images require operator-verified source directories.

Those images remain local builds until their source preparation is made
reproducible in CI.
