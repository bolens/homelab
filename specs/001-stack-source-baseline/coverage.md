# Requirement coverage

| Requirement | Source and acceptance evidence |
| --- | --- |
| FR-001 | `documents/STACK-METADATA.md`, metadata audit against Compose, and each stack source record. |
| FR-002 | `scripts/prepare-stack-lib.sh`, preparation standards and source audit; generated .env has explicit stack.env ownership. |
| FR-003 | `specs/002-media-preparation`, explicit require-existing helper policy and six isolated storage regression tests; optional overrides remain opt-in under preparation standards. |
| FR-004 | `scripts/validate-compose-config.py` staging of shared.env.example/stack.env.example and `docker compose config` invocation. |
| FR-005 | Catalog/topology/Pages generator --check modes and topology artifact validation. |
| FR-006 | `documents/DEVELOPMENT-WORKFLOW.md`, sync-gitea-from-github.sh ancestry/ref guards, and RELEASING.md. |

## Verification receipt

The initial make validate gate passed catalog/Compose/source checks on the inspected base (217 metadata records, 214 Compose stack directories). Two existing metadata advisories identify asking and harbor entries without Compose. The implementation review then reproduced unsafe media-directory creation; specs/002-media-preparation owns the corrective requirement. Six storage regressions and the broader Python helper suite pass on the correction, along with preparation/metadata/hygiene audits and reproducible catalog/Pages checks. PR #70 head fec8c9d5bf511d737ab305bbaecf83d6b5821c2b passed all hosted checks, including repository/Compose validation and site-quality tests. Local privileged Docker execution remains unavailable. No live preparation or services were used. Separate self-review checked the policy branch before mkdir, rejection without path disclosure, unchanged application-local defaults, all 16 media wrappers, and the explicit .env synchronization exception.
