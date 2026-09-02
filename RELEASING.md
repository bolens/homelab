# Delivery playbook

Homelab continuously delivers portable stack examples and generated catalog
content from protected `main`; it has no tagged product release. Merging does
not authorize pulling images, deploying stacks, or changing live services.

## Prepare and validate

Branch from current `github/main`. Read every file and local README for each
touched stack. Update Compose, environment example, stack metadata,
preparation, ingress example, and documentation together. Use placeholders only
and never inspect or stage live secrets or ignored runtime configuration.

```sh
make validate-changed BASE=github/main
make ci-local
```

Regenerate catalog or topology output from its source rather than hand-editing
it. Record optional validator skips accurately.

## Review, deliver, and verify

Open a GitHub pull request, require all checks and resolved conversations, and
squash-merge. Verify GitHub `main` and the intended Gitea mirror point to the
reviewed content and Pages completes when documentation changes. Repository
validation must remain read-only.

## Recover

Fix repository defects through a corrective PR. Any live deployment needs a
target-specific backup, health checks, and rollback plan before authorization.
Never use destructive volume removal as routine recovery; restore the previous
image/config and verify persistence and ingress explicitly.

Fleet policy: <https://github.com/bolens/.github/blob/main/RELEASING.md>.
