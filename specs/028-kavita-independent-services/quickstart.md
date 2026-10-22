# Validation and operation

1. Run `python3 -m unittest discover -s stacks/kavita/providers -p 'test_*.py'` against fixture transports.
2. Apply the independent patch to an isolated export of the pinned upstream commit and verify functional authorization and official-mode invariants.
3. Render the default and provider override with synthetic env files in an isolated directory. Run preparation preservation fixtures, focused validators and `make validate`.
4. Build the gateway and fork images without mounting live state; run authenticated health/capability and provider contract checks against disposable state.
5. Configure the catalog Hardcover token privately; run bounded genuine read probes without returning private account data or tokens. Other credentials stay blank until configured.
6. Account writes require the intended user's connection and explicit scoped acceptance fixture. Compare remote state before/after and handle uncertain responses without false success.
7. Before live Kavita recreation, capture image/config/data baseline, quiesce it, back up state, restore to a private isolated directory and verify completeness and database integrity.
8. After rollout verify books, users, bookmarks/progress, metadata locks and requested provider features. Roll back image/config and verified state on failure. Do not claim full parity while any capability or acceptance gate remains missing.

## Account-safety acceptance

Run the provider suite first. For a full native run, supply a pristine export of the pinned commit, a separate patched source tree and compiled model/services assemblies:

```sh
KAVITA_SOURCE_EXPORT=/path/to/pristine-pinned-export \
KAVITA_PATCHED_SOURCE=/path/to/patched-export \
KAVITA_MODEL_ASSEMBLY=/path/to/patched-export/Kavita.Models/bin/Release/net10.0/Kavita.Models.dll \
KAVITA_SERVICES_ASSEMBLY=/path/to/patched-export/Kavita.Services/bin/Release/net10.0/Kavita.Services.dll \
python3 -m unittest discover -s stacks/kavita/independent -p 'test_*.py'
```

The current full gate expects 17 Python integration tests with zero skips, including 13 actual native queue/controller/wire cases. The provider suite currently has 143 cases. The native test starts disposable loopback processes with a fixture key and simulated upstream transport. It does not start containers or use personal credentials. See `independent/test_native_queue.py` and `independent/native_queue_fixture.py` for the fixture lifecycle.

Before image replacement, back up and verify both persistent volumes. Start the candidates against restored copies on an isolated network. Record all lock fields by primary key, provider settings and existing library/user/reading identities. After the live update, compare those records, test EPUB reading and confirm the daily Calibre sync remains enabled. Keep account acceptance open until the intended provider account and scope have been verified.

## Recovery and storage checks

Run `providers/test_storage.py` through the provider suite. It uses deliberately small quotas to exercise pressure, restart, migration of legacy receipts and parallel reservation. The independent suite additionally starts fresh native processes to verify persisted capabilities, key/origin binding, corruption refusal and durable capability revocation. Native queue tests exercise the real credential-clear controller and reconnection, plus cold-start creation during a gateway outage.

Do not delete protected receipts to recover space: doing so removes retry protection. At capacity the native event remains pending. Reconcile its remote outcome and native acknowledgment before any operator-directed retirement of protected evidence. Normal metadata/reconciled-receipt cleanup is automatic. Back up the configuration snapshot and provider database with their existing volumes.
