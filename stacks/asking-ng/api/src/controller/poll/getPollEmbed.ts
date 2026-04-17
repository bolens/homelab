import {
  pollSignedReadGrantAllowed,
  readEmbedReadTokenFromRequest,
  verifyEmbedReadToken,
} from '../../lib/embedReadToken';
import { appEnv } from '../../lib/env';
import { jsonError } from '../../lib/jsonError';
import { publicPollPageUrl, publicSiteRoot } from '../../lib/sitePublicUrl';
import Poll from '../../model/Poll';
import type { AppRequestHandler } from '../../types/http';
import { singleString } from '../../utils/http';

/** oEmbed 1.0 `link` resource for rich previews (Slack, Discourse, etc.). */
const getPollEmbed: AppRequestHandler = async (req, res) => {
  const pollId = singleString(req.params['id']);
  if (!pollId) {
    jsonError(res, req, 400, 'BAD_REQUEST', 'Poll id is required.');
    return;
  }

  const poll = await Poll.findByPk(pollId, {
    attributes: ['id', 'title', 'archived', 'embedReadTokenHash'],
  });
  if (!poll) {
    jsonError(res, req, 404, 'NOT_FOUND', 'Poll not found.');
    return;
  }

  const embedHash = poll.get('embedReadTokenHash') as string | null | undefined;
  const embedToken = readEmbedReadTokenFromRequest(req);
  if (!verifyEmbedReadToken(embedHash, embedToken) && !pollSignedReadGrantAllowed(req, pollId)) {
    jsonError(
      res,
      req,
      403,
      'POLL_EMBED_TOKEN_REQUIRED',
      'Valid embed_token query parameter or X-Poll-Embed-Token header is required for this poll.',
    );
    return;
  }

  const title = poll.get('title') as string;
  const archived = !!poll.get('archived');
  const pageUrl = publicPollPageUrl(req, pollId);
  const provider = appEnv.serviceName;
  const providerSite = publicSiteRoot(req);

  const esc = (s: string) =>
    s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  const html = `<a href="${esc(pageUrl)}">${esc(title)}</a>`;

  res.setHeader('Content-Type', 'application/json; charset=utf-8');
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.json({
    version: '1.0',
    type: 'link',
    title: archived ? `${title} (archived)` : title,
    provider_name: provider,
    provider_url: providerSite || pageUrl,
    cache_age: 30,
    html,
    url: pageUrl,
  });
};

export default getPollEmbed;
