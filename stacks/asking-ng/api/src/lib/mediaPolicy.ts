type MediaAttachment = {
  kind: 'image' | 'video';
  url: string;
  preview_url?: string;
  alt?: string;
};

type MediaModeration = {
  status: 'active' | 'reported' | 'takedown';
  reported_reason?: string | null;
  last_action_at?: string | null;
  last_actor?: string | null;
};

export function normalizeMediaAttachment(raw: unknown): MediaAttachment | null {
  if (!raw || typeof raw !== 'object') return null;
  const r = raw as Record<string, unknown>;
  const kind = r.kind === 'image' || r.kind === 'video' ? r.kind : null;
  const url = typeof r.url === 'string' ? r.url.trim() : '';
  if (!kind || !url) return null;
  const preview_url =
    typeof r.preview_url === 'string' && r.preview_url.trim() ? r.preview_url.trim() : undefined;
  const alt = typeof r.alt === 'string' && r.alt.trim() ? r.alt.trim() : undefined;
  return { kind, url, ...(preview_url ? { preview_url } : {}), ...(alt ? { alt } : {}) };
}

export function normalizeMediaModeration(raw: unknown): MediaModeration {
  if (!raw || typeof raw !== 'object') return { status: 'active' };
  const r = raw as Record<string, unknown>;
  const status = r.status === 'reported' || r.status === 'takedown' ? r.status : 'active';
  const reported_reason =
    typeof r.reported_reason === 'string' && r.reported_reason.trim() !== ''
      ? r.reported_reason.trim()
      : null;
  const last_action_at =
    typeof r.last_action_at === 'string' && r.last_action_at.trim() !== ''
      ? r.last_action_at.trim()
      : null;
  const last_actor =
    typeof r.last_actor === 'string' && r.last_actor.trim() !== '' ? r.last_actor.trim() : null;
  return { status, reported_reason, last_action_at, last_actor };
}
