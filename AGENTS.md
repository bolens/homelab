# Agent guidance

[Documentation](documents/README.md) maps architecture, deployment, state, and document ownership.

For stack behavior or configuration changes, read [.specify/memory/constitution.md](.specify/memory/constitution.md),
the target stack's [README.md](README.md), and its tracked contract files: Compose,
environment example, metadata, preparation, and ingress examples. Follow their
tracked dependencies. For prose-only edits, read the affected documentation and
the tracked sources needed to verify its claims. Use [CONTRIBUTING.md](CONTRIBUTING.md) and
[RELEASING.md](RELEASING.md) for validation and delivery. Each stack is an independent public,
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
- Preparation follows [documents/PREPARATION-STANDARDS.md](documents/PREPARATION-STANDARDS.md), is idempotent,
  preserves existing runtime config, avoids value disclosure, and does not
  start containers.
- Do not hand-edit generated catalog/topology content. Regenerate from source
  and review the complete diff.
- Use focused validators, then `make validate`; reserve
  `make validate-changed BASE=<rev>` or `make ci-local` for appropriately broad
  work. Report optional-tool skips accurately.

## Planning and evidence

Use the [project guide](.specify/memory/project-guide.md) and
[constitution](.specify/memory/constitution.md) for substantial changes. The guide
owns Spec Kit scope, retained history, retrospective requirements, and acceptance
evidence. Prose maintenance uses the normal repository workflow.

## Context and handoffs

- Search before reading. Use bounded source excerpts for exploratory reads over
  350 lines, and inspect required guidance and actual source before editing.
- When delegation is permitted, assign a bounded question or output, paths, and
  check. Return source locations, changes, and verification gaps for final review.
- Keep durable corrections in the [project guide](.specify/memory/project-guide.md)
  or owning contract. Replace superseded advice and read it before reuse.
  Temporary progress belongs in task notes. Preserve existing authority rules.
