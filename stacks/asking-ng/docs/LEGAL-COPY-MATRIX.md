# Legal copy matrix (identity-linked voting)

This document is the review checklist for legal/privacy copy shown when poll
`vote_eligibility` is `account` or `platform_linked`.

Use it with:

- `GET /telemetry/consent-region` (`eu` / `non-eu` / `unknown`)
- UI keys under `home.voteEligibility.regionLegalNote.*`
- UI keys under `poll.identityLinkedRegionalNotice.*`

## Purpose

- Keep one canonical source for what each region profile should communicate.
- Make product/legal reviews diff-friendly before copy changes ship.
- Avoid accidental copy drift between create, edit, and vote surfaces.

## Region profiles

| Profile | Trigger | Required messaging goals | Current UI keys |
|---|---|---|---|
| `eu` | Consent region endpoint resolves `eu` | Explicitly call out stronger consent/disclosure expectations and retention rights in stricter jurisdictions | `home.voteEligibility.regionLegalNote.eu`, `poll.identityLinkedRegionalNotice.eu` |
| `non-eu` | Consent region endpoint resolves `non-eu` | Warn that local jurisdiction can still impose identity-linking obligations; keep operator action-oriented wording | `home.voteEligibility.regionLegalNote.nonEu`, `poll.identityLinkedRegionalNotice.nonEu` |
| `unknown` | Consent region endpoint resolves `unknown` or fetch fails | Treat as conservative fallback; instruct operator to apply strictest consent/retention posture | `home.voteEligibility.regionLegalNote.unknown`, `poll.identityLinkedRegionalNotice.unknown` |

## Surface mapping

| Product surface | When shown | Copy source |
|---|---|---|
| Create poll (`Home`) | When `vote_eligibility != anonymous` | `home.voteEligibility.accountConsentNote` + region variant |
| Edit poll (`My Polls`) | When `vote_eligibility != anonymous` | `home.voteEligibility.accountConsentNote` + region variant |
| Vote page (`Poll`) | When poll is identity-linked | region-specific `poll.identityLinkedRegionalNotice.*` |

## Approval workflow (minimum)

1. Draft copy update in `client/src/i18n/locales/en.ts`.
2. Update this matrix if keys, triggers, or messaging goals change.
3. Mirror overrides in locale packs that customize these keys.
4. Legal/privacy review sign-off before release if semantics changed.
5. Update roadmap/API docs when policy scope changes.

## Non-goals

- This file is not legal advice.
- This file does not define retention defaults by plan.
- This file does not replace jurisdiction-specific counsel review.
