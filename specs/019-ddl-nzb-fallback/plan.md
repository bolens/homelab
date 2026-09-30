# Implementation plan

Extend `stacks/mylar3/config/workflow.py` to admit Failed entries only for an exhaustion-triggered handoff. Check the matching DDL-control release fingerprint and terminal receipt under existing ownership locks. Persist a per-release fallback receipt with the reservation before queue submission. Consider at most one eligible exhausted entry per scheduler cycle, after intake checks.

Retain NZB-only provider filtering, native single-issue validation, duplicate ownership checks and uncertain-send review. A fallback no-result restores Failed without calling DDL recovery. Ordinary manual and waiting-age handoffs retain Queued restoration. Restart recovery must repair the native status for reserved exhausted entries before search.

Add fixture coverage to `test_workflow.py`, already included in the image gate. Document the behavior and exclusions in the README and module ownership map. Compose, environment, metadata, preparation and ingress retain their existing contracts: the image uses the same private config journal, networks, clients and authenticated routes, with no new runtime inputs or privileges.

Constitution checks: portable configuration, no live state access, no media writes, no new mounts or ingress. Validate focused workflow and ownership tests, generated documentation, then `make validate`. Report unavailable native/image checks separately.
