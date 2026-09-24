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
- Keep runtime secrets and ignored live configuration out of output, Git, and
  committed examples. Use placeholder values in examples. Access live
  configuration only for requested operational work under the workflow below.
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

## Live configuration and updates

A request to update or repair a live service authorizes the necessary scoped
configuration access and lifecycle actions. Do not request a separate exception
for that access. Repository-only work and validation remain read-only.

1. Record the current image, configuration, data locations, and application data
   baseline. Back up the configuration and all persistent state the operation
   could change. Keep backups private and outside Git. Quiesce the service or
   use an application-consistent backup method.
2. Verify the backup before updating: restore it to an isolated location and
   check completeness, file integrity, and database readability as applicable.
   Do not proceed if verification fails.
3. Apply the requested update, preserving unrelated settings and data.
4. Verify service health and application behavior, then compare the data with
   the baseline. Check records, files, and database integrity as applicable;
   a healthy container alone does not prove the data survived.
5. If data is missing or corrupted, stop the updated service and restore the
   verified backup with the prior compatible image and configuration. Verify
   recovery before resuming service. If verification is inconclusive, retain
   the backup and report the gap rather than declaring success.
6. After successful update or rollback verification, remove only the temporary
   backup and restore copies created for this operation. Preserve existing
   backups and retention policies. Report the update or rollback and evidence.

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
