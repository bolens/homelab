# Installed ordinary pipeline checks

This batch exercises the installed Mylar package with new disposable state. It
is new verification, not a reconstruction of the lost historical 17-case batch.
Run it inside the reviewed native image without network access, live data mounts,
or a Docker socket. Supply the independently reviewed exact installed-source map.

Each case runs in its own interpreter. The matcher, archive verification,
placement, catalog update, completion acknowledgement, rename and preserved
metadata implementations are the installed production functions. The matched
first-import case supplies an already matched issue to the actual `Process_next`
under the genuine processing owner. The discovery case instead enters `Process`
and requires its actual matching result.

The only injected fault wraps the real completion-database context: it raises
a lost-response error after the original transaction commits. It never supplies
an acknowledgement, placement result or replacement publication capability.
Fixture schema comes from the installed `dbcheck` CREATE TABLE statements;
authority genesis uses the real Store, Writer and RegistryState public methods.
No daemon, scheduler or provider is started.

Target execution is required. Host syntax and helper checks establish no image,
import, reader, live-library or configured acceptance.

The owning full-image gate runs this batch automatically from `/opt/mylar3-fixes/ordinary_pipeline` after deriving the expected source map from its freshly patched source. The lightweight upstream CI lane explicitly reports that it provides no ordinary-pipeline runtime proof.

For a separate focused check, run the final image's Python with this read-only checker directory mounted at
`/checks` and the independently pinned source map at `/evidence/expected.json`:

```sh
/lsiopy/bin/python3 -I -B /checks/run.py \
  --expected-map /evidence/expected.json \
  --expected-map-sha256 <reviewed-map-sha256>
```

Use an unprivileged UID, a read-only image filesystem, no network and a writable
private `/tmp` with at least 1 GiB available. The genuine upstream free-space
check remains enabled. Each process creates a new private temporary fixture and
removes only that fixture after checking its result. The final image must contain
its real bundled Mylar dependencies, publication SDK, archive utilities and
metadata publisher; the lightweight patch-only CI base is insufficient.

The report distinguishes complete discovery from the explicit matched-input
cases. All four require actual catalog ownership and fresh completion evidence;
the lost-reply case requires the original source to remain and performs no second
processing call. The continuity case keeps its original durable acknowledgement
while verifying the genuine rename and preserved metadata transactions. Each case
also verifies that an unrelated catalog issue and series stayed unchanged.

If preserved metadata refuses, the case emits a bounded comparison of the disposable archive's original/current preservation fields, ZIP attribute changes, security and remaining supplements before fixture cleanup. The diagnostic preserves the original exception and grants no publication or terminal acceptance.
