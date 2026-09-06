# Plan: Portable stack examples and generated catalog

The [specification](spec.md) preserves existing behavior. Use the project guide
and constitution for implementation constraints. Keep upstream-managed templates,
helpers, and integration manifests unchanged.

## Source ownership

- `stacks`
- `shared.env.example`
- `scripts/prepare-stack-lib.sh`
- `scripts/validate-compose-config.py`
- `scripts/audit-prepare-scripts.py`
- `scripts/audit-stack-metadata.py`
- `scripts/build-stack-catalog.py`
- `documents/PREPARATION-STANDARDS.md`
- `documents/STACK-METADATA.md`
- `Makefile`

## Constitution check

Preserve the existing constitution, canonical source ownership, explicit operational authority, deterministic failure behavior, and native validation. This retrospective baseline changes project-owned documentation; it introduces no live deployment, credentials, privileged action, or product release.

## Validation

```sh
make validate
make docs-check pages-check
```

Run checks in an isolated checkout. Commands are instructions, not evidence of
a pass. Record results in `coverage.md`, keep incomplete work in `tasks.md`, and
follow `RELEASING.md` for reviewed delivery. No live operation is required solely
to create this retrospective baseline.
