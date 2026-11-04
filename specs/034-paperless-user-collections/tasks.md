# Tasks: Paperless user collections

- [x] Inspect stack contracts, upstream ownership and filename behavior, and live state.
- [x] Record acceptance criteria and preservation plan before implementation.
- [x] Add opt-in originals bind, environment example and operator documentation.
- [x] Verify the isolated prechange database restore.
- [ ] Establish prechange file-manifest proof. The helper lacked stdin forwarding and did not execute. That sequencing evidence cannot be reconstructed after cleanup.
- [x] Verify a fresh postchange backup and restore, including executed file-manifest assertions.
- [x] Configure private import ownership and activate per-user originals storage.
- [x] Verify two-account isolation, original paths, downloads and preserved baseline.
- [x] Run focused example validation and `make validate`; record skips or unrelated failures.
- [x] Remove operation-created temporary copies after successful acceptance.

## Acceptance evidence

- The prechange database dump matched the isolated restored database, and native
  `pg_amcheck` passed with its extension installed only in the disposable restore.
  The initial file-manifest helper omitted Docker stdin forwarding, so its assertions
  did not execute. This was found during cleanup review. FR-004 was not fully met
  before activation. Fresh postchange backup/restore verification is recorded below.
- Both existing ordinary accounts uploaded synthetic PDFs through authenticated
  application endpoints. Owner paths and file hashes matched. Lists, detail, download,
  preview and thumbnail endpoints allowed own documents and denied the other account.
  Administrator visibility passed. No OCR archive was generated for these text PDFs.
- Native workflow execution verified each account inbox, unmatched-inbox administrator
  ownership, no additional grants and preserved web/API ownership.
- Synthetic documents and their test tasks were removed through native cleanup.
  Document count returned to the zero-document baseline. Account, authentication,
  migration and email-import tables matched the baseline. UI settings were unchanged
  except the intended private defaults. Existing images, unrelated environment values,
  mounts and network membership were preserved. Service health passed.
- Focused optional-storage rendering passed, including missing-key rejection and
  `create_host_path: false`. The repository validation gate passed using an isolated
  PyYAML environment. The externally generated PostHog bundle was skipped by the
  existing validator. The existing Stoat optional-example warning remains.
- This operation's temporary backup, restore and private configuration copies were
  removed after acceptance. Existing backups were preserved. Operational evidence
  remains private outside Git.

### Corrected recovery evidence

The fresh postchange check ran the manifest helper with stdin forwarding enabled,
parsed its output and required a nontrivial entry count. All application state
entries matched source, backup and restore copies by SHA-256, ownership, modes and
namespace. The empty originals root matched by namespace and ownership/modes.
An isolated database restore again matched its source dump and passed native
`pg_amcheck`. Paperless resumed healthy with three accounts, four ownership routes
and zero documents. These postchange checks prove current recoverability and do not
retroactively establish the missing prechange file verification. All temporary
backup/restore/configuration copies from both checks were removed after acceptance.

## External sharing follow-up

- [x] Reproduce the missing ordinary-user ShareLink permissions, then grant only
  Add/View/Delete for ShareLink and ShareLinkBundle to the existing collection group.
- [x] Restore a consistent prechange database dump in isolated PostgreSQL, compare
  schema/data and run native integrity checks. Normalize only the known equivalent
  MFA index array-cast deparse form. Remove the temporary copies after verification.
- [x] Apply the explicitly approved Cloudflare Access exception only to `/share/*`,
  preserving the existing root application and household policy.
- [x] Verify public HTTPS without cookies: four PDF links matched original hashes,
  a ZIP contained the expected file, expired links redirected with the expiration
  marker, and the same PDF/ZIP URLs stopped serving files after owner revocation.
- [x] Verify the root, login, private document API/download and neighboring `/shares/`
  paths still require Cloudflare Access. Cross-user link creation, listing and
  revocation checks denied access to the other private collection.
- [x] Remove all synthetic documents, links and ZIP shares. Counts returned to the
  zero-document/share baseline. Only the six intended sharing permissions were added.
  Paperless remained healthy. Owning README lint and whitespace checks passed.
