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
acceptance. Size disposable test filesystems above the production storage
reserve plus fixture demand. A filesystem equal to the reserve correctly refuses
positive allocation; increase fixture capacity without weakening the guard. For the owning workflow suite, `MYLAR_WORKFLOW_SOURCE` points to
the module directory containing `search.py`, `api.py` and `queues/`, not its
repository parent. Require the native-source test to run rather than accepting
its optional host-only skip as image proof.
Run native import and retained-pack fixture families through
`stacks/mylar3/config/run_import_api_controls.py`, with the required archive SDK
available. The owning runner assembles the generated API, predecessor sources
and host-module layout in private scratch; importing its component suites
directly from the checkout does not provide that fixture environment.
When adding a pinned nested source or fixture, check its owning `.dockerignore`
contract as well as source-map closure. A recorded source hash does not prove the
file reaches the image build context; verify the actual owning-source export.
When a pinned manifest or embedded cohort changes, trace its literal hash consumers
in installers and owning tests as well as file-map rows. Refresh only current
contracts, preserve historical preimages, and run the owning installer tests and
checked fixture-copy closure before pushing. A closed file map alone does not
prove those semantic pins agree.
For cross-runtime source verification, hash the exact source bytes or extracted
source text. Python's AST fields and dump format vary by version; a host-derived
`ast.dump` hash cannot verify unchanged source in another Python runtime. Keep
the whole-file pin and behavioral acceptance checks alongside any method pins.
On Btrfs, a reused directory descriptor can return a stale first listing after a
mutation. Enumerate through a fresh descriptor opened relative to the original
bound directory, verify its identity before and after reading, and retain exact
namespace and metadata comparisons. Reproduce the complete write/cleanup path
on disposable data on the actual filesystem; a temporary filesystem can miss
this behavior. Preserve the primary operation error separately from final
closure failures so cleanup diagnostics do not hide the original refusal.
A nonempty workflow rollback journal can make the publication guard refuse startup
before SQLite can perform its normal recovery. Preserve the database and journal
together; do not delete the journal or disable the guard to restore availability.
Use a stopped, reviewed recovery path with verified preimages and independent
SQLite recovery on isolated copies before touching the original. Keep recovery
locks separate from shutdown prevention: an external SQLite RESERVED lock can
mask a hot journal, and a process-local store lock does not cover direct database
writers. Verify the actual writer paths and lock behavior on disposable fixtures.
When Writer contention persists, identify the owning process through kernel lock
inventory and confirm its application identity before changing wait limits. An
empty device/inode match alone does not establish that the lock is free. A bounded
nonblocking Python stack snapshot without local variables can distinguish slow
admission validation from network work or a blocked worker. Keep the snapshot
private, and preserve the original readiness checks.
The maintained Komga effective-scope observer lives in
`stacks/komga/effective_scope/`. Compile and transport the complete generated class
inventory, including nested classes; a primary-class pin does not prove runtime
closure. Keep configured image/process/output bindings outside public source and
collect fresh original-bound evidence. Use the actual framework file-resource
resolution before path checks. Require the exact bind list shape and
multiplicity, not Docker's list order. Preserve fixed trusted source/function/line
failures before an outer wrapper catches an exception; a type-only summary can
hide a host custody failure after a successful target case.
Mylar health diagnostics currently call `queue_control.Store.save`, which atomically
replaces `ddl-control.json` even when no download state changes. A read-only API
request can therefore change this file's inode and timestamps. For preservation,
require exact baseline state bytes and stable ownership, device, size and parent
identity, close each individual read, and check the installed writer source.
Keep immutable backup/source witnesses strict; do not waive queue state changes.
Keep no-follow path descriptors for captured scope nodes until final acknowledgement.
A deleted inode can be reused before a pathname check, so device/inode tuples alone
do not preserve the original node. Close descriptors on capture and pre-output
failures as well as normal completion. Live database content and timestamps remain
separate from scope-node identity.
When binding a literal into a reviewed operational helper, replace only the exact
AST value byte span and require every surrounding byte to remain unchanged.
Normalizing a whole assignment line can hide a second statement on that line;
include a refusal test for that case. Keep the original helper immutable.
Retain every reviewed producer needed for later acceptance in the private
operation packet before execution, including code that assembles the effective
backup scope. A source left only in `/tmp` can disappear before the postcheck.
A retained hash or downstream output cannot replace that missing original;
preserve the evidence gap and recover or reconstruct the producer under review
before claiming its source closure.
When a rollout helper wraps another helper, test the combined path against the
real file-writing contract. The backup helper creates JSON files exclusively;
assemble the complete scope before its first write. A fixture that permits
overwriting does not verify that contract. Check capture identifiers against
actual recorded values rather than copying the same literal into code and tests.
Build schema fixtures from the actual owning creator or migration and confirm them
against retained metadata before live verification. A later `CREATE TABLE IF NOT
EXISTS` declaration may differ from the existing startup-created schema; deriving
both the verifier and its fixture from that declaration can hide the same error.
Execute extracted support functions in tests, including their hash/read paths,
to prove the retained import header supplies their dependencies. Include pinned
empty source files and the actual public-source ownership separately from
Root-private operational evidence. Neither case relaxes private-proof custody.

Keep OCI index, platform manifest and configuration digests separate from the
daemon's local image ID. Use the reviewed immutable reference for pulls and runs.
Record the actual `docker image inspect` ID and container `Image` on that daemon.
Docker can reorder `HostConfig.Binds` for a created container. For disjoint fixed
destinations, compare duplicate-preserving membership rather than list order,
while retaining exact source, destination, access mode and actual mount checks.
Keep missing, extra, duplicate and changed mounts as refusals; this does not apply
to overlapping mount destinations where order could affect the visible tree.
Use absolute build-context, Compose and helper paths with `pkexec`; it may change
the working directory. A relative path accepted by the unprivileged shell can
therefore refer to a different location in the privileged command.
Do not infer either ID from registry metadata or assume a configuration digest
names a locally runnable image.
Compose may record a separately resolved platform-manifest identity in its image
label while the daemon reports an index identity for the container. Bind both
from independent inspection and the same public descriptor chain; compare each
raw field with its own expected identity instead of equating or normalizing them.
Inspect the image's actual complete labels before binding a recovery helper.
The current normalizer image declares source and title labels, without a revision
label. Verify its source commit through the pinned publication provenance and
repository digest; do not invent a label or require an undeclared one.

A Compose recreation may reorder environment entries and change the explicit image
selector. Compare unique environment names and exact values, rejecting malformed
or duplicate entries before ignoring order. Permit only the recorded old-to-new
selector transition; every unrelated value and runtime setting must remain equal.
Do not print environment values in diagnostics. For Docker's `OomKillDisable`,
accept a verified `false` to `null` default representation change only when every
other runtime field remains equal; reject `true`, missing fields and unknown
values.

A diagnostic that exercises the real Writer protocol needs its existing lock
file opened read/write, even when it changes no protocol bytes. Keep application,
configuration, media and state directories read-only; if admission is required,
bind only that exact existing file read/write and verify its identity and bytes
before and after. Preserve the verified parent mount's propagation. Docker can
reject `rprivate` for bind sources within its data root when the existing parent
uses `rslave`; do not substitute a broader propagation mode or writable directory.
Retry only observed transient contention before entering the tested operation,
with finite time and attempt limits. Do not replay a partially executed test or
infer admission from a prior free-lock sample. Test diagnostic inputs through the
owning adapter: the worker's `Maintenance.mylar` returns validated response data,
whereas a direct native API request returns the full response envelope. A fixture
that supplies the wrong shape can pass while the installed path always refuses.

Keep operational helper source, proof inputs, receipts and resume notes on private
persistent storage outside Git. Verify an owner-only directory ancestor by its actual
identity, owner and mode; a private filename or directory name does not restrict
access. Capture ancestor identities before reading a protected leaf, then verify
them again after the read; a later baseline can accept a replaced directory.
Correct the owning directory without rewriting retained receipt bytes or
historical file modes. Reserve temporary filesystems for disposable test fixtures.
Before a planned reboot, verify the checkpoint and its referenced files are durable; after reboot, recapture process epochs and live file bindings rather
than treating retained historical proof as fresh authorization.

Do not copy the entire comic library for routine interface, image or configuration
updates. Back up affected application state and verify the library in place. If
an operation changes existing media, preserve those specific files first. Reserve
full-library copies for major library changes.
When affected files reside on NFS, check whether their metadata is representable
on the backup filesystem before stopping the application. Btrfs cannot apply
`system.nfs4_acl` directly. Preserve unsupported metadata losslessly and prove
restoration to a compatible filesystem; silently dropping it does not verify a
complete backup. Use disposable fixtures before copying the full affected scope.

Before a large application-state backup, measure its size and verify free space
on the destination filesystem for both the backup and isolated restore. Prefer
disk storage for large snapshots: tmpfs output consumes memory and can exhaust a
backup helper's container allowance even when its process uses little memory.
Place large backup and isolated-restore copies on the dedicated backup filesystem
when available, rather than consuming application storage. After the owning
operation is verified, remove its disposable restore copy while preserving the
required backup and unresolved original evidence.

SQLite `mode=ro` and `query_only` do not prevent WAL/shared-memory sidecar
creation beside a closed database that retains WAL mode. Mount retained copies
read-only and run SQL against detached private database/companion pairs in bounded
scratch storage. Verify the retained namespace and hashes after all SQL callbacks
finish. Use a genuine closed WAL-mode fixture; a default rollback-journal fixture
does not test this behavior. Observe a running database through its supported
read-only WAL snapshot without `immutable` or a write fallback.

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

A nonblocking Writer refusal before start intent is contention, not a failed import.
Retain the failed attempt, verify the owned container never started, and use a bounded
acquisition wait with unchanged original-lock checks before a fresh attempt. Do not
reset uncertain start evidence or repeat an unaffected verified backup.
After changing a directory namespace, enumerate it through a freshly opened directory
descriptor relative to the held descriptor and verify the same physical identity.
On this host, Btrfs returned a stale first listing from a reused descriptor after a
rename; the same fixture passed on tmpfs. Test filesystem-sensitive helpers on their
actual target filesystem. Persist pre-mutation receipt vectors before changing names;
if that capture is missing, record the gap rather than reconstructing a historical vector.
Keep read-only attempt diagnostics in their own protected attempt directory, separate
from durable prestart/start-intent fences. Preserve earlier refused attempts without
resetting uncertain execution evidence. A bounded readiness wait may retry only the
observed transient reason; each final accepted sample must still satisfy the full
current health and data contract.

Reuse accepted evidence only when its source bytes, selected checks, configuration
and relevant runtime still match. Recheck changed inputs rather than repeating
unaffected broad suites. Record exact source, image and live acceptance separately.
Close an implementation milestone when its documented source and selected-image
gates pass; keep downstream configured execution under its owning tasks. Do not
substitute source parity for a required genuine runtime path, or defer an
implementation checkbox solely for a live test assigned to a later task.

For disposable Git source exports, apply and verify file permissions from the
reviewed Git tree before running security controls. `git archive` can emit mode
`0664` for a tracked `100644` file because of its archive umask. Content hashes
do not detect this difference. Require `0644` or `0755` as recorded by Git, keep
the rejected export intact, and correct the new fixture rather than weakening
the source-permission check.
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
