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

Keep the active task list focused on remaining outcomes. Mark delivered
implementation tasks complete separately from operational acceptance; link
historical failures instead of carrying them as current instructions. When
features share an acceptance operation, name one owning execution order and
reference the same original evidence from all applicable tasks. Do not repeat
accepted runs, unchanged image checks or reviews solely to obtain another task
receipt. Add corrective implementation only for a demonstrated unmet contract.

Reviewed, frozen source and its matching checked installation may be exercised
in an explicitly authorized disposable integration test before merge. Hosted CI
still gates merge, and final source, delivery and runtime evidence must join
before acceptance is complete. Reuse an unchanged immutable installation across
distinct fixtures when its contract permits. Preserve each attempt separately.

Derive preparation cardinalities from one closed inventory of the frozen source
maps, original file modes, ancestor paths and declared suite inventory. Bind that
same inventory into every supplier, wrapper, continuation and test. Compare exact
names, hashes and original signatures, rather than copying current file totals
between templates. Keep resource ceilings separate from census values. A changed
inventory requires a fresh binding, not adaptation of an already armed attempt.

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

Check the interpreter used by local hooks before rerunning environment failures.
On this workstation, the default mise Python lacks PyYAML while system Python
has it. Use the system Python for repository validation and the supported Node
26 runtime used for these site checks; keep explicit Python 3.10 recovery tests
separate.
Do not change production runtimes or validation assertions to fix that PATH.
Run repository CI with the normal `022` umask: source-ancestor controls must
observe an actual `0755` to `0700` fixture transition. Create private logs as
`0600` separately rather than imposing `077` on the test processes.

GitHub job metadata can lag completed runner output. If `gh run view --log`
refuses an apparently running job, the job-logs API may already provide its
completed log. Check the required result job and runner assignment separately;
finished build output does not replace a passing required check or justify
cancelling and repeating the workflow.

For Mylar-only updates, keep NZBGet and Komga running. Scope backups and any writer
coordination to the affected state and follow the Mylar stack's update instructions.
Do not reuse a multi-service rollout script for a single-service UI change.
When validating an image-only recreation, bind Compose's version label to the
independently observed installed CLI version. Preserve the prior profile and
require all other configuration, mount, command and runtime fields to match the
reviewed transition. Bind replacement labels to the original Compose logical
service/instance identity rather than assuming they equal the container name.
Compare complete mount entries independent of order. Normalize empty/null DNS
arrays only for absent Compose settings, preserving actual overrides and raw
profiles. A metadata hold before startup does not justify repeating a verified
backup or recreating the same container again.
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

For privileged diagnostic output under a user-owned parent, retain the original
parent and output directory descriptors. Create exclusive no-follow report files
relative to that output descriptor, and verify directory identity, ancestry and
namespace before and after writes. A private mode and final-leaf `O_NOFOLLOW`
alone do not prevent parent-path replacement. Preserve the primary operation
error when later output or cleanup custody also refuses.

For the health-only cache allocation test, state the observation endpoint
explicitly: verified child termination and payload removal precede the sole
consistent AFTER snapshot and typed comparison. Keep exact source checks through
that endpoint. Later custody and owned-directory cleanup are separate evidence;
report subsequent live database drift without claiming its contents are verified
or preserved through cleanup. This bounded test contract supplies no current
import, ACK, NFS, factory or worker-start authority and does not relax those
operations' own preservation requirements.

Precreate private mode0600 operation logs under umask077, then assert umask022
before disposable births that require exact mode0711 searchability. Preserve
failed parents unchanged and use a fresh generation. Bind generation names by
explicit literals or AST fields; do not replace single-letter fragments across
identifiers. Compare non-binding code before executing generated helpers.

Before running a synthetic recovery constructor as Root, classify every created
file and directory by its consuming contract. Child factual baseline,
preparation and execute/terminal-history records and their preparation directory
belong to UID1000. Apply those owners before capturing references, directory9
or enclosing vectors. Request, SDK, generated native-scope, image metadata and
Root custody controls retain their Root ownership. Check the complete derived
factual-reference set before entering the dialogue. A UID1000-only preflight
must assert its identity and cannot establish Root constructor correctness.
Keep synthetic worker process/role ownership limitations explicit. Correct the
current constructor, never mutate frozen attempts or weaken owner-read guards.

For disposable multi-service recovery fixtures, preserve the failed creator's
original journal and namespace before diagnosing a Docker allocation failure.
Exhausted default address pools are a host prerequisite, not archive or import
acceptance. A network with no active endpoints can still be referenced by stopped
or Created containers: inspect both NetworkSettings and HostConfig across the
complete container census. Before specifically authorized unrelated-network
removal, close that census under a brief coordinated lifecycle pause. Task-owned
fixture cleanup follows its exclusive-resource contract and still verifies exact
identity, references and absence. Keep the original network profile and use a
fresh creator generation afterward.

Removing an unused manually addressed network does not free an automatic pool.
When no removable automatic allocation remains, use the reviewed explicit Creator
v4 subnet request rather than changing daemon-wide pools or deleting retained
fixtures. Check all host IPv4 routing tables and the complete Docker IPAM census,
retain the before/created profile joins and keep the internal-only role contract.
Conflict or unknown outcomes require a fresh generation; an explicit subnet does
not supply NFS, application, terminal or cleanup acceptance.
When adding an owning engine method, update the privileged batch's exact
code-object admission and exercise the actual dispatcher with bounded local
pipes. A substituted Driver alone cannot prove the saved-ID transport accepts
the new caller. Preserve all source-global, owner, engine and argument joins.
Enforce subprocess output limits while draining both pipes. A size check after
complete capture does not bound memory. Retain both owned pipes before fallible
selector setup, and attempt termination, reaping and closure independently while
preserving the primary failure.

Before creating a disposable NFS-backed container, verify source-directory
traversal from the Docker daemon's identity as well as the fixture owner. A
root-squashed NFS export can admit the user while refusing the daemon at private
ancestors. Do not retry a failed create, chmod an existing library or failed
fixture, or change export privileges to bypass this refusal. Use only the owning
explicit disposable geometry contract; keep library and retention leaves private
and prove the actual bind with a new empty fixture before connected acceptance.

A successful flat NFS bind does not prove that Docker can resolve a nested
probe behind private retention ancestors. Test the exact source lookup boundary
before consuming a recovery packet. Where the owning plan13 contract explicitly
admits the retention-root probe bind, retain original R identity/FD authority
separately from freshly observed prepared-to-write directory metadata. Keep the
nested fixture identity unchanged, preserve unrelated retention entries, and
retain the direct-fixture route for original legacy geometry. Read-only mount
observation and daemon bindability are separate prerequisites.

The configured reader-parent installer and disposable Creator use different SDK
inputs. Derive the installer's subset from its pinned base manifest's
required_sdk_names, joined to the accepted current image map. Preserve the
Creator's complete current SDK map separately. Optional historical-base hashes
can differ; never replace current image hashes with historical values to make
installation pass. Preserve the installer's original output_refs before source
cohort execution and do not reinstall afterward.

When a required installed module changes, advance the current base manifest and
its fixed supplier hash through an explicitly reviewed source change. Preserve
historical manifests and configured output references in their original frozen
generations. A prospective source-derived base is not installed-image evidence:
capture and join the newly published image before creating a new configured
supplier generation. Never overwrite or refresh the old generation's references.

Size disposable test filesystems above the production storage
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
prove those semantic pins agree. The private-copy recovery collection does not
replace the owning native reader controls: run `run_publication_reader_controls.py`
and its canonical cohort-import test when lifecycle or admission source changes.
Trace direct dependency literals in both admission and archive preparation, then
the Parent base-admission pin and current import-time test pins; a closed JSON
map can still contain a caller that refuses the new module. Trace inherited operational suppliers and generated
health programs too: a new top-level image receipt can still invoke an older
embedded module hash. Prepare an exact source-bound supplier successor, preserve
the predecessor, and verify old-source refusal and new-source acceptance before
rollout.
Before publishing maintained Python changes, run the exact Source lint Python rules from the pinned fleet tooling: `ruff check --isolated --select E9,F` over the paths selected by `.github/source-lint.json`, using the pinned workflow runtime. Local `make ci-local` does not replace this separate hosted gate. An unused import or binding still changes a pinned source file when removed, so refresh its owning hash and verify downstream consumers.
Preserve unchanged source-map formatting. API/auth source hashes can be
misclassified as credentials after reserialization; verify their source
provenance and keep secret scanning enabled.
When a declared test suite grows, update its exact owning runner count and
aggregate assertions together, then execute the complete suite inventory before
pushing. Keep strict collection and zero-skip checks; historical evidence counts
remain unchanged.
For the cacheable Mylar tagging stage, regenerate and check its explicit dependency
manifest and Docker COPY block with `config/tagging_stage_inputs.py` before
refreshing the outer source maps. Keep tagging and remaining checks as independent
branches of the same pinned runtime, joined by the mandatory aggregate stage.
A build result may reuse unchanged public source/runtime checks; it cannot reuse
live freshness, ownership, import or acknowledgement decisions. The default
standalone verifier must continue to run every suite.
The retained-pack worker fixture also has an inner `source-pins.json` census.
Update that census before refreshing the standalone map, then refresh the import
API map and its nested standalone-manifest pin. Outer-map closure alone does not
verify the inner Python-source census; run the source-copy semantic check before
starting the expensive native image gate.
For ordinary pack observation, use the exact selected `packWork` branch or
`pack_intake.snapshot()`. Unselected `packWork` and recurring discovery update
capture/cursor state and are not read-only inventory. A discovered capture with
zero recorded members can enter the ordinary inventory path; eligibility depends
on its actual source generation, current ownership and owning admission checks.
Do not require pre-existing member records or infer import acceptance from them.
For isolated Python component checks, `-I` child interpreters ignore environment-only
bytecode suppression. Make exact regular private fixture copies read-only before
their first metadata witness so imports cannot create bytecode there. Keep full
source metadata and canonical `/app` checks intact; label private-copy execution
separately from installed-source proof, without changing `__file__` or waiving guards.
Komga 1.29 introduces independently configurable session SQLite state through
`sessionsDb.file` and JDBC sessions enabled by its Docker defaults. Inventory all
configuration databases and journal companions for an update. A fixed five-role
scope or database/tasks-only schema from the 1.28.1 recovery tools cannot accept
this version by changing only the JAR hash: preserve that historical schema and
implement a reviewed versioned session-scope successor with actual target-image
proof before recovery uses the new reader. Portable image delivery alone does
not establish that compatibility.
For NFS source audits, inspect the assigned current worktree rather than the shared
primary checkout. `ExactCalls` deliberately refuses generic create/start calls.
The configured path uses the existing `nfs-probe` and `nfs-lease` dialogues,
`LifecycleParent.open_nfs_child`, `HostProbeReplies` and `HostWriterLease` for
birth and session custody. Trace actual call sites before treating an obsolete
comment or an unused public default as missing implementation.

The native catalog fixture must preserve the startup-created database mode.
The pinned producer uses `sqlite3.connect` without chmod and can create `0644` under
umask `022`. Admit only `0600`/`0644` under the original retained UID/GID1000 DATA `0700`
directory, with unchanged database identity and all Writer/schema/authority
checks. Test actual SQLite creation and the genuine constructor path instead
of forcing every fixture to `0600`. Keep expected early probe failures separate
from later errors: retain bounded diagnostics per original intent, without
changing the first record or replaying an operation.

Seed catalog fixtures from every field consumed by the pinned ordinary processing
route. A valid release date alone does not satisfy a consumer that slices
`LatestDate`; verify that field through the real seeded constructor/processing
path. A queued request consumed before a fixture exception is not an import or
ACK. Retain its original intent and failure evidence; never replay it to test
a source correction.

Record genuine isolated queue imports, reader scan/progress and restart as
bootstrap execution milestones. They do not accept retained live DDL, catalog-to-ACK
recovery, connected factories, NFS or publication. Preserve original receipts
and failed generations; advance aggregate tasks only on their full owning proof.

Copying the archive SDK source from its container does not copy its Python runtime.
Its canonical wrapper selects `python3` from the consumer environment; in Mylar
that remains daemon Python 3.10, even when Modern has a private newer interpreter.
Verify the installed canonical conversion command with genuine archives and
full member/directory preservation before accepting an SDK pin. A host test or
source import alone misses interpreter-dependent calls such as `hashlib.file_digest`.
A compatible helper does not extend the SDK's broader declared minimum version.

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
The reader lifecycle parent selects the original library-query transport before
sending requests. A reader name, alias or DNS name alone does not prove that the
native container can resolve it. Require a shared original network ID before
selecting native execution. An alias found only on a reader-only network must
refuse native execution. Preserve the original URL, stdin-only credentials and fixed
GET routes. Do not rewrite the host URL, connect existing services or add an error
fallback to make a query pass. A separate approved original-image read-only query
context needs its own original profile and lifecycle proof before any GET. A plan grants
no admission. Other original origins keep host HTTP. A host DNS failure does not
prove a reader permission or DTO failure. Check the owning transport context
before repeating full source captures. Retain only fixed error types, numeric
network codes and trusted source locations in shared diagnostics; keep addresses
and responses private.
An image-only recreation can change labels inherited from the old and new
images, including build and OCI revision labels. Derive those exact changes
from original immutable image metadata and protect explicit Compose overrides,
including overrides equal to an old image default. Keep independent prospective
Compose model/hash and platform-label bindings; do not ignore label keys or
compare the runtime labels only after the update. Preserve every unrelated
runtime field and original data check.
Do not equate an inherited OCI `revision` label with the repository commit.
A child Dockerfile may preserve the upstream base revision. Bind the repository
commit through the reviewed source proof and publisher provenance, and join
runtime labels to the exact index, platform manifest and OCI configuration.
Keep those digest roles distinct and protect explicit Compose label overrides.
For performance fixes, measure the complete owning path with a representative
fixture before publishing another image. Fewer callbacks can leave total latency
unchanged. A stack sample identifies work in progress; it does not prove a
persistent lock owner. Preserve fresh authority and post-callback closure when
removing repeated pure work.
For guarded pipe timing, include encoded frame sizes, short writes, backpressure
and the full closure count per response. A fixed loop of closure calls does not
measure a multi-write protocol exchange. Keep the original deadline and repeat
preservation checks before every write; validate nonblocking pipe state through
the original primitive before sending bytes.
For saved-evidence-only diagnostics, trace called functions as well as the entry
point. The live library mapper resolves paths and checks directories; calling it
would cross that boundary even when its input JSON was captured earlier. Validate
saved DTOs and serialized mount joins with pure lexical operations instead, and
trap filesystem access in the changed join's tests. Retained mapping evidence
establishes neither current root existence nor alias coverage. The owning Parent
must repeat genuine current mapping under its original admission rules.
When validating saved one-shot histories, capture the fixed original bindings,
terminal receipts and report with the same strict reader used by the unchanged
consumers. Keep the first full file and ancestor witnesses through final closure.
Read the actual outer START binding and its original nested JSON rather than
reconstructing it from a summary or assuming a prior attempt's file layout.
A terminal zero exit with zero requests does not prove an import or ACK, or grant another START.
Never replay, reset or remove an attempt to validate its history.
Before changing credentials or authorization after a principal check refuses,
compare the returned field types with the pinned application DTO. Komga 1.28.1
omits null `ageRestriction`; its absence still requires the original ADMIN, full
library-sharing and empty restriction-list checks. The reader
[network-context contract](../../stacks/mylar3/config/reader_recovery/CONTRACT-nfs-factual.md#original-library-query-network-context) owns this specific compatibility rule.
A prepared import receipt and a later healthy API response do not identify the
earlier dispatch refusal. Keep dispatch-time outcomes explicit and bounded,
preserve uncertain phases, and never replay a submitted operation to diagnose it.

The maintained Komga effective-scope observer lives in
`stacks/komga/effective_scope/`. Compile and transport the complete generated class
inventory, including nested classes; a primary-class pin does not prove runtime
closure. Keep configured image/process/output bindings outside public source and
collect fresh original-bound evidence. Use the actual framework file-resource
resolution before path checks. Require the exact bind list shape and
multiplicity, not Docker's list order. Preserve fixed trusted source/function/line
failures before an outer wrapper catches an exception; a type-only summary can
hide a host custody failure after a successful target case.
Mylar health diagnostics use `persist=False`: progress remains available in
memory without replacing `ddl-control.json`. Queue/UI diagnostics persist changed
state against the last successful save, including progress first observed by
health. Older images may rewrite identical telemetry on status reads. Check the
installed source before relying on read-only observations; deliver the correction
rather than relax full filesystem witnesses. Keep immutable backup/source
witnesses strict and reject unexplained queue state changes.
Trace every health and read-only Activity snapshot callee: workflow intake
refresh can emit an event and write its cache after ten seconds. Pass
`persist=False` from both observers while ordinary intake retains persistence
and hysteresis. Test stale reads against the actual initialized database hash,
full file signature and directory namespace, including admitted existing-only
stores and a subsequent genuine mutating intake check. Default Store reads must not
repeat chmod on an already private database, since that alone changes ctime.
Check both initialized default and admitted existing-only stores; missing-store
initialization is a separate write boundary.
Keep no-follow path descriptors for captured scope nodes until final acknowledgement.
A deleted inode can be reused before a pathname check, so device/inode tuples alone
do not preserve the original node. Close descriptors on capture and pre-output
failures as well as normal completion. Live database content and timestamps remain
separate from scope-node identity.
`mkdir(parents=True, mode=0o700)` applies that mode only to the final leaf;
new intermediate directories can still be 0755. Create every component of a new
private source projection with its required mode and ownership before capturing
full9 references. Check the complete directory census through the owning
consumer, alongside file bytes and modes. Preserve failed capsules unchanged;
correct packaging in a distinct successor rather than chmod a captured original.

When binding a literal into a reviewed operational helper, replace only the exact
AST value byte span and require every surrounding byte to remain unchanged.
Normalizing a whole assignment line can hide a second statement on that line;
include a refusal test for that case. Keep the original helper immutable.
Validate bound output paths against the owning writer's actual path contract
before execution. Literal-only binding does not prove the output name is valid.
Execute retained derivative bytes with their actual derivative filename as
`__file__`. A helper that rereads itself must witness those executed bytes, not
the unbound original under a substituted filename.
Preserve every protected-root provenance occurrence. A repeated path/origin pair
can be legitimate; match occurrences without losing multiplicity and reject
conflicting, missing or extra resolutions. Counts and candidate covers alone do
not approve supersession or establish physical protection.
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
Run preservation SQL only against separate private working copies. SQLite readonly
and query-only connections can create WAL/SHM beside closed WAL-mode databases,
including files produced by `sqlite3.backup`. Keep retained backup pairs and
pristine captured snapshots untouched, verify their original bytes and companion
namespaces, and allow readmarks only in disposable query copies. Use genuine
WAL-header fixtures rather than rollback-mode fixtures for this boundary.
Build schema fixtures from the actual owning creator or migration and confirm them
against retained metadata before live verification. A later `CREATE TABLE IF NOT
EXISTS` declaration may differ from the existing startup-created schema; deriving
both the verifier and its fixture from that declaration can hide the same error.
Disposable creation and application bootstrap have separate authority. Use the
explicit UID1000 creator and finite Polkit adapter only with original accepted
image metadata, private dedicated scratch references and reviewed image/DATA
bindings. The default root bootstrap entry point remains unchanged. Host UID1000
NFS access does not prove the root daemon can resolve mode0700 root-squashed bind
sources. Require actual bindability before claiming execution, retain unknown
creation replies without adoption or replay, and keep the worker unstarted.
Pinned Komga 1.28.1 first-admin enrollment uses the claim headers, followed by
Basic-authenticated API-key creation. Do not substitute an ordinary user endpoint
or silently extend this contract to another version. Parse virgin INI section
names from the exact installed config source without importing provider-writing
configuration code. Default archive-byte compatibility compares the hash-pinned
legacy builder within each Python runtime, preserving exact original bytes and
page/metadata checks instead of using host-only ZIP hashes as portable goldens.

Keep original Root-owned evidence under its existing ownership. The checked Parent
Tree copy projects exact originals into UID1000 child scratch; do not chown the
originals or weaken reference custody to make a child consume them. Distinguish
a read-only observer from an exposed application route: Mylar's upcoming route
can call its Wanted DateAdded backfill. Classify legitimate catalog drift by
exact keys and writer predicates, preserving every other cell and duplicate
count; column multisets alone do not prove row preservation or actor attribution.

For explicit disposable catalog fixtures, use the real startup-created full schema.
A fresh exec importing `native_writers` has no daemon startup or publication
admission. Never set its private readiness globals or reconstruct startup to
claim that authority. A finite fixture-data seed may use the installed existing
raw Writer with default pending refusals and original media snapshots, but must
identify itself as fixture seeding. Provider metadata import, daemon processing
and ordinary import acknowledgement require their own observed results.
Keep archive metadata, catalog identities and filenames coherent for discovery;
reader page verification alone does not prove native issue matching.

Modern ComicTagger's private `/opt/comictagger` runtime and vendored Legacy are
separate contracts. SourceCohort invokes `/lsiopy/bin/python3` and must verify
daemon Python 3.10. Check the actual executable and final Dockerfile assertions
before changing a runtime predicate. A private tagger version is not daemon
version evidence. Moving Modern to a source-authenticated interpreter under
`/opt/tagger-python` does not move Legacy or the daemon off Python 3.10. Check
actual interpreter paths, native libraries, licenses and final-image ABI; a host
CLI pass does not prove Jammy ICU compatibility. Shared system-library updates
can still affect the daemon. Preserve backend preferences and archive owners.

Do not assume `jobhistory.JobName` is unique: Mylar's inspected startup creator
declares plain `JobName TEXT`, and `helpers.job_management` updates by job name.
Verify the actual schema and retain duplicate multiplicity instead of collapsing
rows into a name-keyed dictionary. `library_metadata.Maintenance.tick` uses a
cyclic scan cursor: sweep completion resets it and schedules the next pass in
one hour; a policy change starts a new pass. A lexical cursor decrease across
passes is not by itself lost progress. Compare the owning policy, cursor and
sweep timing together. A row matching a writer's predicate does not prove that
actor ran; require its original causal evidence before attributing an invocation.
The installed DB connection returns `sqlite3.Row`; normalize integrity-query
results without changing its row factory. Acquire the original raw Writer and
verify the existing catalog, held descriptor and companion namespace before
constructing that connection, which can otherwise create a missing database or
recover a journal outside custody.
SQLite connection context managers commit or roll back but do not close the
connection. In disposable fixtures, use `closing(connection)` around the
transaction context so cleanup follows transaction exit. A delayed
`ResourceWarning` can point at unrelated garbage-collection code; use an
allocation traceback before changing the reported production line. Close HTML
cache handles with a context manager rather than filtering their warnings.
Execute extracted support functions in tests, including their hash/read paths,
to prove the retained import header supplies their dependencies. Include pinned
empty source files and the actual public-source ownership separately from
Root-private operational evidence. Neither case relaxes private-proof custody.

For descriptor lock checks, Linux fdinfo reports the inode superblock device;
Btrfs fstat can report a different subvolume device. Bind the original descriptor
and path with full facts, then check the exact FD's kernel lock inode, process,
type and range without treating those device namespaces as equal. Exercise the
owning lock method on the actual host filesystem as well as temporary fixtures;
a tmpfs-only contention test cannot expose this Btrfs difference.

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
The current host Docker CLI prints its `--time` deprecation warning on stdout,
even with exit code zero. Use its supported `--timeout` option for stop/restart
commands, updating paired argv producers and consumers together. Preserve exact
acknowledgement checks rather than stripping unexpected output. Retain private
CREATED and first-running profiles before comparing a startup transition; a
response hash alone cannot identify which original field changed. Keep Created
provenance separate from the validated running and terminal profiles. A retained
none-network reproduction populated EndpointID, NetworkID, SandboxID and SandboxKey
and changed the default OOM field on startup; terminal teardown cleared EndpointID
and the sandbox fields while preserving NetworkID. Validate those exact bounded
relations at their owning transitions, then require full profile/epoch closure.
Do not drop all NetworkSettings, apply the library-query hostname exception to
other children, or alter global `static()`. Audit session, probe, lease, phase,
worker and active-parent terminal consumers together. A later exited profile after
the Parent closes stdin cannot reconstruct the profile at an earlier refusal.
Do not register diagnostic files in the Parent’s generated-control table from
inside a terminal callback that already sealed that table. Stage observations
before the seal or omit optional writes; preserve the original final registry
comparison. Diagnostic capture must not change the controls it claims to observe.
An acknowledged own restart can also change Docker's generated native MAC.
Join each old/new endpoint ID and MAC to that same native member in the paired
original/current network records. Require all other network and container
fields to remain equal, keep reader/worker checks exact, and commit the native
profile, epoch and network successor together only after all guards pass.
This exception belongs only to that recorded restart, never ordinary observation.
When changing reader-recovery test counts, update the owning runner and both
aggregate expectations in `test_publication_reader_recovery_controls.py`, then
refresh the affected copy manifests. The inner collection passing does not
verify these outer regression checks. Run the outer operational semantic-pin
test before the long collection after changing a pinned host producer; keep
`genuine_current_roles.SOURCE_PINS` aligned with the actual bootstrap source.
When changing an owning Parent callback, also run the complete
`run_publication_reader_controls.py` family. Its root writer-session fixtures
compile the actual callback and are outside the inner recovery collection.
Keep extracted factories’ closure bindings aligned with their stated lifecycle
boundary: an established-running fixture retains its exact running static,
epoch and StartedAt values; it must not fabricate a Created-to-running proof or
remove the owning callback’s assertions to accommodate a missing binding.
Bind CurrentRoles source roles to their actual loaded module origins, including
the config parser; do not assume all generations share one directory. Retain
Bootstrap helper/probe/scope URIs from their original authenticated context,
with full file identity and byte closure. The disposable observer must consume
the owning static profile projection, including `NetworkSettings` rather than
`Created`, while keeping the reader’s recorded process epoch exact. Exercise
these boundaries with distinct source generations and the real profile schema.
A SourceFixture request nonce and its original `readiness_input` nonce must be
prepared as one pair. Choose the fresh nonce before deriving that input, then
capture its bytes and full file identity; validate the pair before invoking the
emitter. Do not reuse an older input with a new request nonce or rewrite its
historical reference to pass the join. A constructor refusal and attempted
cleanup do not prove resource absence; verify the retained cleanup outcome.
The archive NFS helper name derives from the immutable Bootstrap nonce. A fresh
SourceCohort alone does not give a held attempt a new helper name. Preserve the
consumed request and retained child. Prepare a distinct Creator, Bootstrap,
catalog and reader generation for a new forward attempt, then another generation
for rollback. Derive all role IDs, genesis references, Writer roots, mounts and
observer inputs from those new originals. Do not replace only the nonce or adopt
the old helper. Check network capacity before binding a new operational request.
Leave the proposed private NFS probe parent absent. Preparation binds its
existing retention grandparent and the intended child name. The owning Parent
alone creates the child. Exercise the actual active-input precreation predicate
on both an existing rejected path and the proposed absent path before execution.
An empty network inspection does not prove that a network is unused: inspect
references from stopped containers as well before any explicitly authorized
network removal.

For retained FIFO transport, compare device, inode, complete mode and ownership.
Named FIFO I/O changes mtime and ctime. A full regular-file identity check on a
FIFO can reject its own successful write. Cover both a real named-FIFO exchange
and security-metadata drift; keep regular control-file full9/hash checks intact.

If an NFS helper vanishes during namespace bootstrap, retain its original create
and first-started profiles, exact current state, bounded logs and Parent failure
trace before changing code. A missing `/proc` entry identifies a lost original
process, not its cause. Compare the actual packet budget and original lifecycle
timestamps before calling it a timeout. A generic exit code or suppressed child
exception does not authorize replay, helper replacement or reader resume.

SourceFixture logs require their exact phase filenames in one private directory
containing only those leaves. Test a preparer's output with the actual `Logs`
validator; dictionary keys alone do not verify filenames or namespace isolation.
A Writer lock is not necessarily empty: the owning `media_writer.PROTOCOL` is
stored in the real lock file. Verify its exact bytes against the authenticated
owning source and retain FD/full-file-identity closure. Never truncate or replace
the lock to satisfy an observer that assumed an empty disposable test lock.
Search the entire tracked repository for the predecessor hash before editing a
shared producer. Komga’s `effective_scope/parent.py::BOOTSTRAP_SOURCE_SHA` is a
second bootstrap consumer outside the native control collection; refresh its
source manifest and run its direct source-pin regression too.
A never-started Docker container may have empty network and endpoint IDs even
when its HostConfig names the exact original network ID. Join that CREATED
profile to a fresh inspection of the original network. Require the actual
network ID after start; do not relax later lifecycle checks to accept emptiness.

Request preparation may assemble data and check its shape. It does not verify
publication, source, filesystem or installation facts. Keep execution in the
owning validated entry point. Hashing a Python file and then reopening it with
`exec_module` does not prove which bytes executed; a post-import check detects
substitution only after code may already have run. Use the reviewed source
cohort/loader boundary rather than adding an unguarded launch wrapper.

The active Parent's parity program is itself supplied on Python's stdin, so
it cannot read a second stdin document for module names. Derive it through
`genuine_source_cohort.derive_parity_program` from the exact owning probe and
original native-map names. Embed no expected hashes; the Parent compares the
complete observed hash map. Keep the original configured Parent reference and
canonical core-test/writer-fixture sources as custody evidence, without
claiming those references execute additional tests or grant admission.
Host-only control changes may reuse an unchanged verified image/SDK capture.
They still require fresh current-host source checks and connected acceptance;
do not reinstall or refresh original installation outputs to update test counts.

The configured reader installer derives its admission source under the fixed
child operation path `/_operation`. A successor packet must preserve that child
path while replacing only the fresh host operation directory. Check both the
static mount row and the staging code that rewrites it; correcting the input
alone does not fix a controller that restores the old host-equals-child mapping.
Keep the Parent's exact approved-overlay check intact. New host source references
and installation outputs belong to a distinct checked generation; preserve the
original active-parent URI and unchanged image proofs for their original inputs.

The private read-only intent builder and the owning Parent load separate checked
host module graphs. Before Parent entry, release only the canonical
`comic_nfs_host_engine` binding owned by the completed builder. Require exact
module identity and retain foreign bindings; do not relax Parent's absent-name
or source/seal checks. Preserve suppressed exception causes in bounded private
diagnostics without changing the original exception links or hold semantics.

Common-root directory handles have one owning actor. Actor release, constructor
failure and a later finalizer must share the same tracked close state. A numeric
descriptor can be reused after release, so an untracked late `os.close` can close
an unrelated file. Exercise real release followed by descriptor reuse, preserve
the primary error and attempt all owned cleanup without swallowing close errors.

Use the owning operation’s required access mode for the existing Writer file.
Native Writer acquisition opens it read/write even when it changes no protocol
bytes. Keep application,
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
Verify actual supplier ownership and modes through the strict reader before
privileged execution, as well as checking hashes. A frozen `0444` source can fail
a reader that accepts only `0600` or `0644`. This also applies to `0400` helpers.
Preserve the frozen original; use a distinct byte-identical supplier with the
required mode and bind its exact path. Exercise that exact producer-to-reader
handoff in a regression: importing the helper directly does not test admission.
Keep failure diagnostics in the called `main()` entry point when a cached loader
bypasses the script guard; report fixed source frames and preserve the exception.
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
Observe private NFS namespaces as the eventual owning UID. A root-squashed export
can refuse UID 0 access to a UID 1000 mode-0700 directory while UID 1000 succeeds.
Preserve the first refusal and verify the owning principal and mount/device
bindings before considering a permissions change.

Distinguish a source-original reference from an installed derivative reference.
The configured installer records both and rederives the derivative bytes;
a source-cohort URI must join the recorded original source, rather than the
different installed-copy URI. Preserve both original full identities and
independent byte closure. A changed host Parent requires a new configured
installation, but does not invalidate unchanged source-cohort evidence
unless an actual consumed source or runtime contract changed. Once a checked
installation retains source URIs and full identities, freeze that source
worktree for the remaining operation. Integrate subsequent corrections in a new
worktree and create a new installation generation. Do not mutate originals or
refresh old references to make a later generation appear continuous.
Exercise cross-UID handoffs with actual owner/mode metadata. Same-user tests
cannot prove that a Root-private reader accepts UID1000-created facts. Bind
retained-owner reads only to their authenticated original roles; keep unrelated
private documents strict.

Derive archive scratch ownership from its consuming process, rather than the
privileged launcher. The configured archive child runs as UID/GID1000; its scope
guard requires scratch ownership to match. Prepare a new mode0700 scratch under
its verified existing local parent with that owner before capturing references;
do not create missing mount prefixes or widen existing permissions. Keep Root
control facts private. Account for declared image volumes in exact mount checks:
derive the `/config` bind from the original inspected native profile, cover the
parent read-only and keep only the intended nested DATA mount writable. These
source checks do not establish configured execution acceptance.

Before a large application-state backup, measure its size and verify free space
on the destination filesystem for both the backup and isolated restore. Prefer
disk storage for large snapshots: tmpfs output consumes memory and can exhaust a
backup helper's container allowance even when its process uses little memory.
Place large backup and isolated-restore copies on the dedicated backup filesystem
when available, rather than consuming application storage. After the owning
operation is verified, remove its disposable restore copy while preserving the
required backup and unresolved original evidence.

A successful flock does not validate the Writer protocol. Read-only catalog
snapshot adapters must check the existing private parent and the exact opened
file’s type, owner, mode, link count, identity and protocol bytes before and after
acquisition. Retain the detached snapshot referenced by later facts, and release
the Writer before catalog queries. Include every comic’s scanner location as well
as downloaded issues and undeleted annuals; a selected-issue query is incomplete.

When an old configuration hash refuses, locate the failed input before changing
anything. Preserve that generation and capture new process, configuration and
mount witnesses separately. A fresh INI does not make older provenance current.
Derive filesystem fields from their owning source definitions; unknown absolute
declarations retain their conservative holds.

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
Group related authorized privileged operations into one finite reviewed batch
when the operator requests fewer authentication prompts. Authenticate before
starting the batch's command deadlines. Retain checks between phases, bounded
runtime and outputs, exact owned cleanup, and the existing UID requirements.
Use a per-invocation transport only. Do not grant lasting Docker access or relay
arbitrary commands. A timeout or lost mutation reply requires retained evidence
and a state check before any fresh attempt; batching does not permit replay.
Include the protected completion export and required independent observations in
that finite command when possible. Keep transaction-bound verification separate
from later samples: background jobs can legitimately change a running database
after completion. Retain any delayed mismatch and its causal evidence, without
excluding tables or claiming that the delayed database equals its preimage.
Follow the current [delivery rules](../../RELEASING.md), including any revocation
of a temporary CI exception.

Keep at most one active archive-bootstrap fixture group: native, reader and an
inactive worker. Preserving an attempt's evidence does not require keeping its
containers running. Before admitting another group, retire the prior runtime
under the operation's authorization after its owning process has returned.
Retain original receipts, profiles, bind-mounted state and unresolved histories.
Capture final logs and writable-layer changes after stopping retired containers
and before removing them. Use exact owned container IDs, preserve volumes and
images needed for rollback, and remove only owned networks verified empty.
Inventory other suspected duplicates before removal: a shared image alone does
not make application workers, schedulers or separate databases redundant.

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

Keep fixture families that replace `sys.modules['mylar']` in separate child
processes. Collecting unrelated families before execution can leave tests bound
to different fake application objects. A symlink to installed bytes is also not
a canonical regular-file fixture: source-owned `__file__` and no-follow checks
correctly reject it. Use exact hash-verified private copies when a mechanical
fixture requires them, label that proof as copied-byte execution, and retain a
separate canonical installed-origin/type check. Keep original source and image
closure strict; diagnose private-copy metadata drift before changing its contract.
Privileged isolated-test actuators should retain bounded failure diagnostics in
the same run, including fixed source basenames and line numbers. Never decode a
binary source-capture stdout stream as a text failure log.

For disposable Git source exports, apply and verify file permissions from the
reviewed Git tree before running security controls. `git archive` can emit mode
`0664` for a tracked `100644` file because of its archive umask. Content hashes
do not detect this difference. Require `0644` or `0755` as recorded by Git, keep
the rejected export intact, and correct the new fixture rather than weakening
the source-permission check.
A partial manifest or matching database copies do not verify a backup if its
owning helper refuses a later preservation check.

For a configured cache test, distinguish payload acceptance under Writer from the
outer mount-source check after the child releases Writer. A successful child can
prove growth, refusal, accounting and payload removal while the outer operation
still refuses cleanup. Retain the exact changed child's identity and before/after
metadata privately at the failed comparison; a later observation cannot identify
that historical change. Do not relax unrelated metadata or repeat
payload writes to diagnose an unidentified source change. Derive owned aliases
from every genuine configured mapping and retain their original descriptors.
Manifest closure must include the plan's semantic caller/helper pins as well as
file hashes; matching a source bundle alone does not prove the bound caller runs.
When refreshing the configured-reader base manifest, preserve the five API/auth
source-hash entries' existing two-line key/value layout. A generic secret rule
can mistake those public SHA-256 values for API keys when both appear on one
line. Keep the values and scanning rules unchanged, then repin the base manifest,
installer and finite source maps. Do not add a secret-scan exception.

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

For NFS child control references, let the owning Parent/Tree reader apply its
source-bound role policy. A duplicate generic private/nonempty read rejects valid
public source files and the exact authenticated empty cohort stderr. Preserve
named-origin, SHA/full9, permission and final copy-closure checks; ordinary empty
controls and undeclared public roles still refuse. Test the actual owning reader
and Tree together, and distinguish an unadmitted context fixture from configured
Parent or NFS acceptance.

The assembler's original `operation_output` is a host path. Project it once with
the owning `nfs_child` mapping. `nfs_host` accepts a virtual child path and returns
its physical backing path, so applying it to the original host path can refuse
before child creation. Exercise the complete outer-input projection with real
`Paths`, distinct host/child mounts and original/physical/virtual output paths.
Identity-mapping fixtures do not verify that direction.
Completion records can likewise retain child paths such as `/_operation` or
`/config`. Map only through the exact owning operation directory or original
role's bind mount. Retain the declared reference and require the mapped host
file to match its complete signature and hash. A shared basename is insufficient.

Verify archive metadata against the owning transition. Forward repair deliberately
assigns the replacement timestamp, while rollback restores its original attributes.
Require the accepted terminal's exact target signature/hash and declared attributes;
ordinary rename timestamp expectations cannot substitute for that contract.

When the NFS cohort retains the installation receipt's original Parent source,
its path differs from the installed Parent copy. Preserve that original binding
through Producer admission. At child projection, join both exact original refs,
full signatures, fixed source hash and bytes, then use the declared installed
source's original Tree projection for both the executing module and cohort parent.
Recheck both incarnations after callbacks. Do not infer this relationship from a
shared basename/hash or relax the child self-path guard. Exercise distinct source
and installed incarnations through the real cohort consumer. A vanished helper
PID during the host's final pipe check can follow a child provenance refusal;
read its original failure record before attributing the failure to a timeout.

Check original scope/runtime observation ages against the helper's recorded start
and failure times before changing a transport deadline. Stale inputs may already
exceed their 120-second admission window before launch. Never retimestamp sealed
facts or enlarge freshness limits to admit them. Measure complete staging and
reduce repeated immutable work or move it before genuine fresh capture. Metadata
deduplication must retain exact-path conflict checks, both closure passes and
post-callback identity checks without caching across calls. Local syscall counts
do not establish configured Root/NFS latency. Bounded failure diagnostics should
retain sanitized suppressed-context frames through direct exception slots; omit
messages, locals and raw paths, and bound traversal as well as output.

A finite owner-read vector must preserve both independent Tree passes and every
existing lifetime boundary. Capture the actual constructor seal, registry,
callable, code and semantic defaults before callbacks; authenticate the same
objects again and invoke the captured original directly for final closure.
Reject replaced source-reader helpers before running them. Keep local metadata
under Root and only fixed no-follow reads under the masked owner UID; restore
Root before validation and retain primary errors, descriptor custody and poison.
Label projection wrapper counts as wrapper invocations, not kernel metadata
operations or NFS RPCs. Only measured complete Root/NFS and fresh configured
execution can establish latency or admission.

Repeated Docker event filters for the same field use OR semantics. A combined
query must retain distinct original role IDs, the original history start, a fresh
cutoff, foreign-actor rejection and the final source/Parent closure. Do not remove
a guard merely because a later guard checks the same facts. An intervening
callback may use replaced OS functions before the later guard can reject them.
