# Delivery playbook

Homelab continuously delivers portable stack examples and generated catalog
content from protected `main`; it has no tagged product release. Merging does
not authorize pulling images, deploying stacks, or changing live services.

## Prepare and validate

Branch from current `origin/main`. Use `AGENTS.md` to select required tracked
sources and local stack documentation. For contract changes, update Compose,
environment example, stack metadata, preparation, ingress example, and
documentation together. Use placeholders only
and never inspect or stage live secrets or ignored runtime configuration.

```sh
make validate-changed BASE=origin/main
make ci-local
```

Regenerate catalog or topology output from its source rather than hand-editing
it. Record optional validator skips accurately.

## Push

Follow the [fleet push and merge steps](https://github.com/bolens/.github/blob/main/RELEASING.md#push-and-merge).
After the local checks pass, inspect the diff, commit focused changes, and push
only the feature branch to the GitHub remote. Confirm `git remote get-url --push
origin` names `bolens/homelab` on GitHub; use the corresponding remote name if
your checkout uses another alias:

```sh
git push --set-upstream origin HEAD
```

Confirm `github` points to `bolens/homelab` on GitHub before pushing.
Do not push `main`, force-push, skip failing hooks, or bypass protection.

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

## Source lint

The Source lint workflow checks maintained python, javascript, css files selected by
[`.github/source-lint.json`](.github/source-lint.json) on every pull request
and push to `main`. Existing native checks remain part of the merge gate.
Use the [shared local reproduction instructions](https://github.com/bolens/.github/blob/7603518f305fb76f7bb1b9979f2692521f633b82/docs/source-lint.md)
with the same tooling revision pinned in
[the workflow](.github/workflows/source-lint.yml). Review exclusions when adding
source files; generated and imported files retain their native validation.
Require the new check to pass on the current PR head before merging.

## Custom-image CI selection

`.github/custom-images.json` owns the build matrix. Dorny selects images whose
build contexts changed, including deletions and renames. Images sharing a context
are rebuilt together. Selector, inventory, and workflow changes select all images;
manual runs also validate all images. Run `python3 -m unittest discover -s
scripts/tests -p test_ci_custom_images.py` locally when changing this contract.
Only trusted `main` runs publish to GHCR. PR and other branch runs only build.
Publishing runs finish without cancellation so a newer push cannot interrupt the
set of selected image publications.

The `Custom images` result runs on every PR, including those with no selected
images. It rejects failed detection, cancelled builds, and unexpected skips, and
is required alongside the repository's existing branch-protection checks.
