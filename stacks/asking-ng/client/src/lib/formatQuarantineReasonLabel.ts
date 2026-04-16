import type { MessageKey } from '../i18n/locales';

export type TMessage = (key: MessageKey, vars?: Record<string, string | number>) => string;

/** Human-readable quarantine reason for My Polls, admin rollups, etc. */
export function formatQuarantineReasonLabel(t: TMessage, code: string | null): string {
  if (!code || code === '_unknown') return '—';
  if (code === 'soft_throttle_over_limit') return t('myPolls.quarantineReasonSoftThrottle');
  if (code === 'ip_burst') return t('myPolls.quarantineReasonIpBurst');
  if (code === 'chat_burst') return t('myPolls.quarantineReasonChatBurst');
  if (code === 'soft_plus_burst') return t('myPolls.quarantineReasonSoftPlusBurst');
  if (code === 'soft_chat_burst') return t('myPolls.quarantineReasonSoftChatBurst');
  if (code === 'ip_chat_burst') return t('myPolls.quarantineReasonIpChatBurst');
  if (code === 'triple_signal') return t('myPolls.quarantineReasonTripleSignal');
  return t('myPolls.quarantineReasonOther', { code });
}
