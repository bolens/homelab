# homelab Spec Kit project guide

Portable Docker Compose stack examples and generated catalog content, separate from live
homelab deployments.

Read this guide with `AGENTS.md` and `.specify/memory/constitution.md` before
specifying, planning, or implementing a substantial change. It is project-owned
guidance, not an upstream-managed template.

## Source and ownership map

- `stacks/`
- `documents/PREPARATION-STANDARDS.md`
- `shared.env.example`
- `scripts/`
- `site/`
- `Makefile`

## Specification and plan decisions

Name the stack and read all of its files. Plan Compose, environment examples, stack
metadata, preparation, ingress, and README changes as one contract. Document mounts,
ownership, ports, networks, privileges, dependencies, and readiness.

## Acceptance evidence

Check missing required configuration, idempotent preparation, preserved existing runtime
files, secret-free diagnostics, and metadata/catalog consistency. Use placeholders and
isolated fixtures. Describe backup and rollback requirements before any live deployment
task.

## Validation and operational limits

```sh
make validate
```

Use make validate-changed BASE=origin/main or make ci-local for broader changes,
following RELEASING.md. Validation does not authorize image pulls, directory creation
over missing mounts, service changes, or destructive volume removal.

## Working through Spec Kit

Use Spec Kit for new capabilities, architectural or security-sensitive changes,
migrations, and coordinated changes that need a written contract. Keep narrow fixes,
dependency updates, and prose maintenance in the normal PR workflow.

For a new feature, record observable acceptance criteria in `spec.md`, source ownership
and constitution checks in `plan.md`, and evidence-bearing work in `tasks.md` under the
feature directory created by Spec Kit. Resolve material unknowns before implementation.
Mark tasks complete only after their stated verification, and distinguish completed,
skipped, blocked, and manual checks. Retain completed feature documents as decision
history; do not backfill feature specifications for already finished code.

Keep `.specify/templates/`, `.specify/scripts/`, and generated Codex skills under their
integration manifests. Use this guide and the constitution for local customization.
Regenerate managed files through Spec Kit and verify that project-owned memory survives
updates. Follow `RELEASING.md` for push, merge, release or delivery, and recovery.
