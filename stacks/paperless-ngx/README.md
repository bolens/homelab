# Paperless-ngx

Document management: scan, OCR, and search your paperwork.

**Website:** https://docs.paperless-ngx.com
**Docs:** https://docs.paperless-ngx.com
**GitHub:** https://github.com/paperless-ngx/paperless-ngx
**Docker image:** https://github.com/paperless-ngx/paperless-ngx/pkgs/container/paperless-ngx
**Releases:** https://github.com/paperless-ngx/paperless-ngx/releases

## Quick start

1. Set environment variables (required for reverse proxy and security):
   - **Portainer stack:** Add `PAPERLESS_URL` and `PAPERLESS_SECRET_KEY` Generate the secret with the command in **Generating keys and secrets** below.
   - **CLI / stack.env:** Copy `stack.env.example` to `stack.env` and set `PAPERLESS_URL` and `PAPERLESS_SECRET_KEY`.
2. Deploy: `docker compose up -d` or deploy the stack in Portainer.
3. Open via Caddy and create the initial admin user.

## Generating keys and secrets

**PAPERLESS_SECRET_KEY** (required when exposed publicly) – session/cookie signing. Generate:

```bash
openssl rand -hex 32
```

Set the output as `PAPERLESS_SECRET_KEY` in `stack.env` or in the Portainer stack Environment. Also set `PAPERLESS_URL` to your public URL (e.g. `https://paperless.yourdomain.com`).

Config uses **named volumes** for export and consume (no bind-mounted `./export` or `./consume`), so the stack works when deployed from Portainer's web editor.

## Configuration

| Item | Details |
|------|---------|
| **Port** | 8000 (proxied via Caddy only; no host port) |
| **Network** | `ingress-sensitive` for Caddy; `document-services` for API clients; private default network for PostgreSQL and Redis |
| **Image** | `ghcr.io/paperless-ngx/paperless-ngx:latest` |
| **Env** | `PAPERLESS_URL`, `PAPERLESS_SECRET_KEY` (set in stack or .env) |
| **Consume** | Named volume `consume`, add files via container/volume or bind mount override |

## Adding documents to consume (named volume)

To drop files into the consume volume from the host, either bind-mount a host directory in a one-off container and copy, or override the compose to use `./consume` when you deploy from a directory that has it.

## Start

From this directory: `docker compose up -d`. Or in Portainer: Stacks → Add stack → paste compose and set `PAPERLESS_URL` and `PAPERLESS_SECRET_KEY` in Environment.

## Private collections and per-user originals

Use ordinary accounts for daily access. Paperless object ownership and permissions
control collection privacy. Superusers can access every collection. Documents and
metadata without an owner are visible to all users with the relevant global
permission. A filesystem folder does not enforce Paperless permissions.

For each account, keep **Settings → Permissions → Default permissions** private:
the current user owns uploads and new metadata, with no additional users or groups
granted access. Grant the global document and UI permissions needed for ordinary
use, without user administration, workflow administration or instance configuration
permissions. Review existing documents, tags, correspondents, document types,
storage paths and API integrations for unintended sharing.

### External sharing

Grant ordinary users **Add**, **View** and **Delete** permissions for **ShareLink**
and **ShareLinkBundle** to create, list and revoke document links and ZIP shares.
These permissions do not grant access to another user's private documents.

Recipients with a share link can retrieve its selected file without a Paperless
account. Set an expiration when creating a link, and delete the link to revoke it.
If Cloudflare Access protects the hostname, create a separate path-specific Access
application for `paperless.yourdomain.com/share/*` with a **Bypass → Everyone**
policy. Keep the root hostname and all other paths under their existing Access
policy. Restrict the exception to `/share/*`, where Paperless validates each link.
Verify working, expired and revoked links without Access cookies, and confirm that
the document list and direct API downloads still require authentication.

### Originals storage

To store originals under a directory for each owner, set these values in
`stack.env`, using an existing directory on the Docker host:

```dotenv
PAPERLESS_ORIGINALS_PATH=/srv/documents/paperless
PAPERLESS_FILENAME_FORMAT={{ owner_username }}/{{ created_year }}/{{ doc_pk }}-{{ title }}
PAPERLESS_CONSUMER_RECURSIVE=true
```

Verify the filesystem is mounted, then create the chosen directory with access for
the Paperless service UID/GID. Preparation does not create it. The override refuses
a missing directory instead of creating one over a missing remote mount.

Deploy with both Compose files:

```bash
docker compose --env-file stack.env -f docker-compose.yml -f docker-compose.storage.yml up -d
```

For Portainer's web editor, merge the override's `webserver.volumes` entry into the
base definition and set these environment variables. The path must exist on the
deployment host, which may differ from the machine running Portainer.

Originals then use `PAPERLESS_ORIGINALS_PATH/<username>/<year>/<id>-<title>.<ext>`.
The `media` volume still holds OCR archive copies and thumbnails. Database, search
index, inbox and export storage also remain separate from originals. Back up both
the originals directory and all existing persistent volumes. Keep usernames stable
and choose names that remain distinct after filename sanitization.

### Import ownership

Web uploads use the uploading account's ownership defaults. For scanner imports,
create an early **Consumption Started** workflow restricted to **Consume Folder**
that assigns unmatched imports to a designated administrator. Add later workflows
for each account, matching `/usr/src/paperless/consume/<username>/*`, assigning that
account as owner, and granting no additional view or edit permissions. Later owner
assignments override the fallback. Drop files into the corresponding subfolder.
Add the matching workflow when creating a new account.

Configure an explicit owner on each email import rule. API clients must authenticate
as the intended owner or explicitly assign ownership. Review AI integrations that
use an administrator token, since they can access all collections. Test two ordinary
accounts against document lists, detail pages and downloads before relying on privacy.

### Existing installations and rollback

Before changing storage, stop document writers, record accounts and document counts,
and back up configuration and every persistent volume. Restore to isolated storage
and verify file integrity and database readability before proceeding. Assign owners
to existing ownerless documents deliberately rather than guessing their collection.

With writers stopped, copy the existing `media/documents/originals` contents into
the verified host directory and compare all file hashes. Enable the bind and filename
format, then run Paperless's `document_renamer` command to reorganize existing files.
Per-document storage paths override the global format and must also be reviewed.
Never move or rename tracked document files manually. Verify counts, ownership,
downloadable originals and OCR copies after the change.

To roll back, stop writers and restore the verified configuration and complete state
with the prior image. If new documents arrived after migration, preserve them before
restoring an older snapshot. Remove only this operation's temporary backup and restore
copies after successful verification, preserving existing backups.

See upstream [permissions](https://docs.paperless-ngx.com/usage/#permissions),
[filename handling](https://docs.paperless-ngx.com/advanced_usage/#file-name-handling)
and [document renamer](https://docs.paperless-ngx.com/administration/#document-renamer).
