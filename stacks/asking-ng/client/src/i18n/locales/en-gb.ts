/** English (UK) UI strings (same keys as {@link ./en}). */
import { en } from './en';

const enGbOverrides = {
  'nav.locale.en-us': 'English (US)',
  'nav.locale.en-gb': 'English (UK)',
  'nav.themeLabel': 'Colour theme',
  'nav.colorVisionLabel': 'Colour vision',
  'home.banner.copyOk': 'Link copied to clipboard.',
  'home.err.maxOptions': 'At most 32 options are allowed.',
  'billing.usageNearLimit80':
    'You are above 80% of a plan limit (active polls, monthly votes, or daily exports). Monitor usage or upgrade before limits block new activity.',
  'billing.usageNearLimit95':
    'You are at or above 95% of a plan limit. New polls, votes, or exports may be blocked soon — upgrade or free capacity now.',
} satisfies Partial<Record<keyof typeof en, string>>;

export const enGb = { ...en, ...enGbOverrides } satisfies Record<keyof typeof en, string>;
