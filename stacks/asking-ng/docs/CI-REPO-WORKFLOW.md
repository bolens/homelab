# asking-ng CI and repository workflow ⚙️

## Purpose

Reference for CI execution requirements, workflow responsibilities, monorepo extraction, and Buildx warnings.

## Use This When

- Actions are not running and you need to confirm root-repo requirements.
- You are splitting `stacks/asking-ng` into its own repository.
- You need to understand which workflow file owns which validation/build path.

## Related Docs

- [../README.md](../README.md)
- [API-REFERENCE.md](API-REFERENCE.md)
- [OPERATIONS.md](OPERATIONS.md)
- [API-MIGRATION-TRACKER.md](API-MIGRATION-TRACKER.md)
- [LEGAL-COPY-MATRIX.md](LEGAL-COPY-MATRIX.md)

## Root Requirement for GitHub Actions

> [!IMPORTANT]
> GitHub Actions only run when this project is the Git repository root. If this folder is nested inside another repo (for example `stacks/asking-ng`), workflow files can exist but will not execute.

## Workflow Summary

When this project is the Git root (standalone repo or checked-out submodule at `.`):

| File | What it does |
|---|---|
| `client.yml` | Root `pnpm install`, Biome (`pnpm run check:ci`), then `pnpm exec turbo run verify --filter=client` (lint, knip, typecheck, tests + coverage, production build). Playwright e2e runs in a second job (builds `@asking-ng/contracts` first). |
| `api.yml` | Root `pnpm install`, Biome at repo root, then `pnpm exec turbo run verify --filter=api` (lint, knip, typecheck, tests + coverage, `tsc` build; contracts build runs as dependency). |
| `docker.yml` | `docker compose` build/up, then internal API checks via `docker compose exec asking-api` (`/ready`, `/info`, poll CRUD, duplicate-vote guard, `slo-smoke.mjs`, and `read-model-reconcile-smoke.mjs`). CI no longer depends on host loopback port mapping. |

## Split Out from a Monorepo (Optional)

If this project still lives under a path like `stacks/asking-ng` in another repo, you can extract subtree history and push to a new remote (install [`git-filter-repo`](https://github.com/newren/git-filter-repo) first):

```bash
# From a clone of the monorepo (adjust path for your layout)
git filter-repo --path stacks/asking-ng/ --path-rename stacks/asking-ng/:
git remote add origin https://github.com/YOU/asking-ng.git
git branch -M main
git push -u origin main
```

Notes:

- `--path-rename ...:` moves the subtree to repository root.
- If history is not needed, copy folder to a new directory, run `git init`, and commit.
- After extraction, delete old `stacks/asking-ng` copy in monorepo to avoid dual sources of truth.

For homelab consumption after split:

- Use this repo as a submodule, or
- Point compose `build.context` at a clone, or
- Pull images built from this repo CI/registry.

## Docker Buildx Warning

If `docker compose build` warns that the Buildx plugin should be installed, builds still work with the classic builder.

- Installing Buildx removes the warning and standardizes BuildKit usage.
- Install docs: [Docker Buildx install](https://docs.docker.com/build/buildx/install/).
- Additional context: [Docker Compose: Buildx plugin warning](https://github.com/homelab-user/homelab/blob/main/documents/TROUBLESHOOTING.md).

## Release Gate: Identity-Linked Legal Copy

When a PR changes identity-linked legal/privacy copy, treat this as a required
release gate before merge.

Trigger paths (minimum):

- `client/src/i18n/locales/en.ts` keys:
  - `home.voteEligibility.regionLegalNote.*`
  - `poll.identityLinkedRegionalNotice.*`
- Locale overrides that redefine the same keys.
- Any change to `client/src/lib/cookieConsent.ts` region mapping semantics.

Checklist:

1. Confirm copy intent still matches `docs/LEGAL-COPY-MATRIX.md`.
2. Update matrix rows if trigger, messaging goal, or key mapping changed.
3. Verify `Home`, `MyPolls`, and `Poll` still render region-aware variants for
   `eu` / `non-eu` / `unknown`.
4. Run lints and type checks for client i18n surfaces.
5. Include a short legal/compliance note in PR description when semantics
   changed (not required for typo-only edits).
