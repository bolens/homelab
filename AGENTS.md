# Agent guidance

Before Spec Kit planning or implementation, read
`.specify/memory/project-guide.md` with the project constitution. It maps
requirements to this repository's source, acceptance evidence, and validation.

For stack behavior or configuration changes, read `.specify/memory/constitution.md`,
the target stack's `README.md`, and its tracked contract files: Compose,
environment example, metadata, preparation, and ingress examples. Follow their
tracked dependencies. For prose-only edits, read the affected documentation and
the tracked sources needed to verify its claims. Use `CONTRIBUTING.md` and
`RELEASING.md` for validation and delivery. Each stack is an independent public,
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
feature directories under `specs/` as decision history. Backfill finished work
only when explicitly requested. Label those
specifications as retrospective baselines, record the inspected revision, and map
requirements to source and acceptance evidence. Separate observed behavior from
corrective requirements. Never imply the specification preceded its code or mark
unverified checks complete.

## Context and handoffs

- Locate source with targeted searches before reading. For exploratory reads of
  files over 350 lines, select relevant ranges. Read required guidance and actual
  source before edits or correctness claims; summaries do not replace them.
- When delegation is permitted, give each worker one question or concrete output,
  allowed paths, and a check. Return findings with source locations, changed paths,
  and verification gaps. Keep final review with the coordinating agent.
- Record durable user corrections in the [project guide](.specify/memory/project-guide.md)
  or owning contract with scope, reason, and evidence. Replace superseded advice;
  read relevant corrections before reusing assumptions. Keep temporary progress
  in task notes and preserve existing authority rules.
