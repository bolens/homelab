# Validation

Run focused `test_tagger_lookup.py`, cache, adapter, NFS and service fixtures with unittest discovery under `stacks/mylar3/config`, then the existing Mylar image gate and repository checks. The loopback server must observe two fresh issue requests and one shared volume request. Expiry or changed credential context must restore the volume request.

For unchanged publication, forbid archive-copy creation and provide little free disk space while verifying unchanged content, attributes and replay. Corrupt or raced sources must not report success. Compare repeated controlled timing runs; report synthetic timings separately from live behavior.

Authorized rollout: keep all other services running, wait for Mylar idle and shared writer ownership, verify scoped app-state backups and isolated restore, deploy the published digest, then verify data, health and unchanged backend/settings. Prefer disposable fixtures for performance probes. Any selected live comic mutation needs a specific verified backup. Retain backup on inconclusive checks; restore prior image/state on loss, then remove only operation backups after proof.
