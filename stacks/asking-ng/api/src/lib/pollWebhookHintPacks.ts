export type PollWebhookHintLocale = 'en' | 'en-gb' | 'es';

export type PollWebhookCommandAliasMap = {
  vote: string[];
  results: string[];
};

export type PollWebhookHintPack = {
  chat_vote_short: string;
  chat_results_short: string;
  command_aliases: PollWebhookCommandAliasMap;
};

export const SUPPORTED_POLL_WEBHOOK_HINT_LOCALES: readonly PollWebhookHintLocale[] = [
  'en',
  'en-gb',
  'es',
];

export function coercePollWebhookHintLocale(raw: string): PollWebhookHintLocale {
  const t = raw.trim().toLowerCase().replace(/_/g, '-');
  if (t === 'en-gb') return 'en-gb';
  if (t === 'es' || t === 'es-es') return 'es';
  return 'en';
}

export function resolvePollWebhookHintLocale(
  requested: unknown,
  fallback: PollWebhookHintLocale,
): PollWebhookHintLocale {
  if (typeof requested !== 'string') return fallback;
  const t = requested.trim().toLowerCase().replace(/_/g, '-');
  if (t === 'en-gb') return 'en-gb';
  if (t === 'es' || t === 'es-es') return 'es';
  if (t === 'en' || t === '') return 'en';
  return fallback;
}

export function pollWebhookHintPackForLocale(
  pollId: string,
  locale: PollWebhookHintLocale,
): PollWebhookHintPack {
  if (locale === 'es') {
    return {
      chat_vote_short: `!votar ${pollId} <opción>`,
      chat_results_short: `!resultados ${pollId}`,
      command_aliases: {
        vote: [`/votar ${pollId} <opción>`, `!votar ${pollId} <opción>`, `!v ${pollId} <option>`],
        results: [`/resultados ${pollId}`, `!resultados ${pollId}`, `!r ${pollId}`],
      },
    };
  }
  if (locale === 'en-gb') {
    return {
      chat_vote_short: `!vote ${pollId} <option>`,
      chat_results_short: `!results ${pollId}`,
      command_aliases: {
        vote: [`/vote ${pollId} <option>`, `!v ${pollId} <option>`],
        results: [`/results ${pollId}`, `!r ${pollId}`],
      },
    };
  }
  return {
    chat_vote_short: `!vote ${pollId} <option>`,
    chat_results_short: `!results ${pollId}`,
    command_aliases: {
      vote: [`/vote ${pollId} <option>`, `!v ${pollId} <option>`],
      results: [`/results ${pollId}`, `!r ${pollId}`],
    },
  };
}

export function buildAllPollWebhookHintPacks(
  pollId: string,
): Record<PollWebhookHintLocale, PollWebhookHintPack> {
  const out = {} as Record<PollWebhookHintLocale, PollWebhookHintPack>;
  for (const loc of SUPPORTED_POLL_WEBHOOK_HINT_LOCALES) {
    out[loc] = pollWebhookHintPackForLocale(pollId, loc);
  }
  return out;
}
