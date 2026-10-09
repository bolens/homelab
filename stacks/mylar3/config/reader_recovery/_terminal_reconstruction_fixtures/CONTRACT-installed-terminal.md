# Selected-image terminal CLI harness

Run this standalone script inside the selected final image as UID 1000. The root agent owns the container invocation. The script itself makes no Docker calls, HTTP calls, protected filesystem changes, or native daemon observations. All created files live in its automatically removed private temporary directory.

Pass the actual physical private provider path, its adjacent observer and terminal producer helper, a fresh private checked SDK map, that map's SHA256, and the selected image ID. Provider, observer, and helper must have exactly the successor source-manifest bytes, be UID 1000 owned mode 0600, and have no symlink ancestors. Do not modify any installed package source, source filename, module identity, or `__file__`. The SDK map is supplied by root from the real installed package; no historical fixture map is embedded.

Invocation (paths and hashes supplied by root):

```
python3 -I -B /harness/terminal_cli.py \
  --provider /private-tools/comic_negative_reader_action.py \
  --sdk-map /private-tools/current-sdk-map.json \
  --sdk-sha256 <fresh-map-sha256> \
  --selected-image sha256:<selected-image-id>
```

The harness loads the checked actual provider to obtain genuine installed SDK modules. It checks canonical birth/lifecycle/scope physical paths, source hashes and shared module identities. It constructs a genuine canonical Writer only for its new detached state directory. Then it launches the actual provider CLI with its genuine `sys.orig_argv`, stdin/stdout pipe descriptors, and fresh birth protocol. The provider's pinned implementation owns all exact-type checks, scope construction, Controller/Writer construction, independent observer reconstruction, report creation and final raw closures. The harness does not substitute those factories or types.

The parent observations and durable declarations are synthetic disposable test fixtures. Reader databases have a complete 14-column BOOK table with 11 rows, a second opaque table, and independent tasks databases. The five two-cell edits, file retention, native byte baselines, source/counterpart/retained/restore facts, receipts, and nine accepted-control joins are constructed solely in the detached tree. Real SQLite/file signatures and real child birth ancestor facts are used. The execute report and ACK are also explicitly synthetic declarations, sealed before the verify-terminal child starts. Their original refs bind the fixture preimage and receipts. These declarations were not produced by an owning negative aggregate, SQL commit, TerminalClearance or protected native process. Success proves the factual factory can consume coherent detached immutable evidence through genuine installed types; it does not prove owning mutation provenance, actual protected process custody, parent admission, NFS equality, scheduling, execution authority or live acceptance.

Two complete fresh scenarios are required: forward factual CLI result with all rights false; and a late real current database mode change after the report exists, with Held and no ACK. The latter uses a parent challenge event rather than monkeypatching child code. Any failure remains a failed gate, never a fallback to replacement types or receipts minted into capabilities. PARENT_SHA stays None.

Source validation before root execution: Python 3.10 grammar; Ruff E9/F; help entrypoint. No selected-image positive result is claimed by the author.
