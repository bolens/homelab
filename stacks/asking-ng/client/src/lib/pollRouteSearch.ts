import { z } from 'zod';

const pollSearchSchema = z.object({
  /** Read-only embed / overlay gate (matches API `embed_token` / `X-Poll-Embed-Token`). */
  embed_token: z.string().max(512).optional().catch(undefined),
  /** Campaign attribution pass-through to API impression analytics. */
  utm_source: z.string().max(64).optional().catch(undefined),
  utm_medium: z.string().max(64).optional().catch(undefined),
  utm_campaign: z.string().max(96).optional().catch(undefined),
});

type PollRouteSearch = z.infer<typeof pollSearchSchema>;

export function parsePollSearch(raw: unknown): PollRouteSearch {
  const r = pollSearchSchema.safeParse(raw);
  return r.success ? r.data : {};
}
