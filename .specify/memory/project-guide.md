# homelab Spec Kit project guide

[Documentation](../../documents/README.md)

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

For Mylar-only updates, keep NZBGet and Komga running. Scope backups and any writer
coordination to the affected state and follow the Mylar stack's update instructions.
Do not reuse a multi-service rollout script for a single-service UI change.
Release the external deployment Writer guard before ordinary Mylar startup,
following the [owning README](../../stacks/mylar3/README.md); use scoped Writer
windows for preservation checks or actual repairs. Keep verified normal Mylar
availability separate from unfinished bulk, experimental-normalizer and
archive-recovery acceptance. Those operations remain inactive until their own
gates pass; implementation and isolated tests establish no live admission.
Validate private operational helpers in the selected application’s actual Python
runtime before protected execution. Host-only tests do not prove container runtime
compatibility; use portable streaming hashes when the runtime lacks
`hashlib.file_digest`. Keep runtime compatibility checks separate from live data
acceptance.

Keep operational helper source, proof inputs, receipts and resume notes on private
persistent storage outside Git. Reserve temporary filesystems for disposable test
fixtures. Before a planned reboot, verify the checkpoint and its referenced files
are durable; after reboot, recapture process epochs and live file bindings rather
than treating retained historical proof as fresh authorization.

Do not copy the entire comic library for routine interface, image or configuration
updates. Back up affected application state and verify the library in place. If
an operation changes existing media, preserve those specific files first. Reserve
full-library copies for major library changes.

Before a large application-state backup, measure its size and verify free space
on the destination filesystem for both the backup and isolated restore. Prefer
disk storage for large snapshots: tmpfs output consumes memory and can exhaust a
backup helper's container allowance even when its process uses little memory.
Place large backup and isolated-restore copies on the dedicated backup filesystem
when available, rather than consuming application storage. After the owning
operation is verified, remove its disposable restore copy while preserving the
required backup and unresolved original evidence.

## Session scope and operational checkpoints

Record the human's authorized targets, actions and later changes in a private,
persistent session checkpoint. Read it before resuming operational work. Existing
scoped authorization survives continuation and a new authentication prompt.
Authentication permits privileged execution of that command; it does not expand
the authorized work. Honor the latest access pause or scope change. Ask again
only when a proposed action exceeds or cannot be tied to the recorded scope.
Keep permissions for named-chat coordination and delegated work equally specific.
The checkpoint records human authorization and cannot create new permission.
Follow the current [delivery rules](../../RELEASING.md), including any revocation
of a temporary CI exception.

Reuse accepted evidence only when its source bytes, selected checks, configuration
and relevant runtime still match. Recheck changed inputs rather than repeating
unaffected broad suites. Record exact source, image and live acceptance separately.
A partial manifest or matching database copies do not verify a backup if its
owning helper refuses a later preservation check.

Protected temporary control copies may run from volatile storage. Persist the
source hashes, stopped-state baseline, backup/restore receipts and final outcome
before the next state-changing phase or release of their original custody.
A timed-out Docker client can leave its helper container running. Identify that
exact helper and establish its terminal state before restarting a writer that it
could still exclude. Keep failure captures private and bounded, with a fixed
assertion callsite for diagnosis. Preserve failed evidence and service recovery
requirements rather than interpreting a generic exit code as completion.

## Working through Spec Kit

Use Spec Kit for new capabilities, architectural or security-sensitive changes,
migrations, and coordinated changes that need a written contract. Keep narrow fixes,
dependency updates, and prose maintenance in the normal PR workflow.

For a new feature, record observable acceptance criteria in `spec.md`, source ownership
and constitution checks in `plan.md`, and evidence-bearing work in `tasks.md` under the
feature directory created by Spec Kit. Resolve material unknowns before implementation.
Mark tasks complete only after their stated verification, and distinguish completed,
skipped, blocked, and manual checks. Retain completed feature documents as decision
history. Backfill finished work only when explicitly requested. Label those
specifications as retrospective baselines, record the inspected revision, and map
requirements to source and acceptance evidence. Separate observed behavior from
corrective requirements. Never imply the specification preceded its code or mark
unverified checks complete.

Keep `.specify/templates/`, `.specify/scripts/`, and generated Codex skills under their
integration manifests. Use this guide and the constitution for local customization.
Regenerate managed files through Spec Kit and verify that project-owned memory survives
updates. Follow `RELEASING.md` for push, merge, release or delivery, and recovery.

The retrospective specification register is [specs/README.md](../../specs/README.md).
