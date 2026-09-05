# Agent guidance

Before Spec Kit planning or implementation, read
`.specify/memory/project-guide.md` with the project constitution. It maps
requirements to this repository's source, acceptance evidence, and validation.

Read `.specify/memory/constitution.md`, the target stack's `README.md`, and all
files in that stack before editing. Each stack is an independent public,
portable example; local stack documentation overrides nearby conventions.

- Preserve unrelated work. Change every affected contract surface together:
  Compose, `stack.env.example`, `stack.yaml`, preparation, ingress example, and
  README.
- Never read, print, edit, stage, or commit runtime secrets or ignored live
  configuration. Edit committed examples with placeholder values.
- Validation is read-only by default. Do not pull, start, stop, recreate, or
  deploy containers without explicit operational authorization. Never use
  `docker compose down -v` routinely.
- Do not create bind-mount directories when a missing remote mount could be the
  cause. Treat ports, privileges, host networking, Docker socket, devices, GPU,
  and public ingress as security-relevant contract changes.
- Preparation follows `documents/PREPARATION-STANDARDS.md`, is idempotent,
  preserves existing runtime config, avoids value disclosure, and does not
  start containers.
- Do not hand-edit generated catalog/topology content. Regenerate from source
  and review the complete diff.
- Use focused validators, then `make validate`; reserve
  `make validate-changed BASE=<rev>` or `make ci-local` for appropriately broad
  work. Report optional-tool skips accurately.

## Spec-driven changes

Use Spec Kit for new capabilities, architecture, security-sensitive behavior,
migrations, and coordinated multi-file changes. Keep narrow fixes, dependency
updates, prose edits, and release housekeeping in the normal repository
workflow unless their risk warrants a written specification. Keep completed
feature directories under `specs/` as decision history; do not backfill them for
finished work.
