# Reader supplement implementation plan

## Sources and ownership
Mylar tagger_enrichment owns validated missing-field selection. The existing tagger_adapter publication path owns recovery, archive reconciliation and preservation. tagger_supplement owns the offline preview/apply entry point and per-file restored backups. tagger_service supplies derived additions to future Modern tagging. README, module inventory and image checks document and validate this behavior.

## Constitution checks
Public examples use placeholders. No service, mount, ingress, privilege or environment changes are required. Operations remain explicit and guarded; backups and restoration precede publication. Live state and secrets never enter Git.

## Verification and rollout
Run enrichment and publisher regression tests, the full checked image, repository validation and CI. Review before merge and publication. Back up and restore-verify complete Mylar state under writer exclusion before image deployment. Supplement one canary and inspect reader results, then process the scoped roots with per-file verified backups. Compare a repeat preview, catalog/database integrity and container health. Remove only operation-owned backups after success.
