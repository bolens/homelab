import { createPollBodySchema } from '@asking-ng/contracts/poll';
import { Link } from '@tanstack/react-router';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import React, { useEffect, useMemo, useRef, useState } from 'react';
import type { ZodError } from 'zod';
import { apiUrl } from '../apiBase';
import CopyFeedbackButton from '../components/CopyFeedbackButton';
import { IconShare } from '../components/icons/UiIcons';
import { shareUrlForPoll } from '../helpers/pollUrl';
import { withUtm } from '../lib/withUtm';
import { useDocumentTitle } from '../hooks/useDocumentTitle';
import { apiFetch, isApiFetchError } from '../http';
import { useT } from '../i18n/I18nContext';
import type { MessageKey } from '../i18n/locales';
import {
  billingExportReminder,
  billingUpgradeHintFromError,
  billingPastDueBannerPayload,
  billingUsageAtCap,
  billingUsageWarningSeverity,
  type ProfileBillingApiPayload,
} from '../lib/profileBillingApi';
import { fetchConsentRegion, type ConsentRegionHint } from '../lib/cookieConsent';
import { profileBillingQueryKey } from '../lib/queryKeys';
import { streamingObsDocHref } from '../lib/streamingObsDocHref';
import { getStoredUserJwt, subscribeUserJwtChanged } from '../lib/userSession';
import {
  ActionRow,
  Button,
  Card,
  Checkbox,
  Container,
  cx,
  FormRow,
  FormSection,
  Input,
  Notice,
  PageHeader,
  Select,
  Textarea,
  VisuallyHidden,
} from '../ui';
import { isWebShareLikelyAvailable, shareUrlNative } from '../lib/webShare';
import { errMsg } from '../utils/errMsg';

type CreatePollResponse = {
  status: string;
  data: {
    id: string;
    api_key: string;
    webhook_secrets?: Array<{ url: string; secret: string }>;
    embed_read_token?: string;
  };
};

const POLL_TEMPLATE_IDS = [
  'ama-priority',
  'this-or-that',
  'bracket-matchup',
  'qa-upvote',
  'weekly-retro',
] as const;
type PollTemplateId = (typeof POLL_TEMPLATE_IDS)[number];

function isPollTemplateId(id: string): id is PollTemplateId {
  return (POLL_TEMPLATE_IDS as readonly string[]).includes(id);
}

const POLL_TEMPLATE_I18N: Record<
  PollTemplateId,
  { label: MessageKey; title: MessageKey; options: MessageKey; notes: MessageKey }
> = {
  'ama-priority': {
    label: 'home.pollTemplate.ama-priority.label',
    title: 'home.pollTemplate.ama-priority.title',
    options: 'home.pollTemplate.ama-priority.options',
    notes: 'home.pollTemplate.ama-priority.notes',
  },
  'this-or-that': {
    label: 'home.pollTemplate.this-or-that.label',
    title: 'home.pollTemplate.this-or-that.title',
    options: 'home.pollTemplate.this-or-that.options',
    notes: 'home.pollTemplate.this-or-that.notes',
  },
  'bracket-matchup': {
    label: 'home.pollTemplate.bracket-matchup.label',
    title: 'home.pollTemplate.bracket-matchup.title',
    options: 'home.pollTemplate.bracket-matchup.options',
    notes: 'home.pollTemplate.bracket-matchup.notes',
  },
  'qa-upvote': {
    label: 'home.pollTemplate.qa-upvote.label',
    title: 'home.pollTemplate.qa-upvote.title',
    options: 'home.pollTemplate.qa-upvote.options',
    notes: 'home.pollTemplate.qa-upvote.notes',
  },
  'weekly-retro': {
    label: 'home.pollTemplate.weekly-retro.label',
    title: 'home.pollTemplate.weekly-retro.title',
    options: 'home.pollTemplate.weekly-retro.options',
    notes: 'home.pollTemplate.weekly-retro.notes',
  },
};

const SHARE_PRESET_IDS = ['stream-chat', 'discord', 'x-post'] as const;

function createPollErrorMessage(
  err: ZodError,
  t: (key: MessageKey, vars?: Record<string, string | number>) => string,
): string {
  const issue = err.issues[0];
  if (!issue) return t('home.err.invalid');
  const top = issue.path[0];
  if (top === 'title') return t('home.err.title');
  if (top === 'options') {
    if (issue.code === 'too_small') return t('home.err.twoOptions');
    if (issue.code === 'too_big') return t('home.err.maxOptions');
    if (issue.code === 'custom' && String(issue.message).toLowerCase().includes('duplicate')) {
      return t('home.err.dup');
    }
  }
  if (top === 'expiration') return t('home.err.expiration');
  if (top === 'webhook_targets') {
    const nested = issue.path[2];
    if (nested === 'secret') return t('home.err.webhookSecret');
    return t('home.err.webhookUrl');
  }
  if (top === 'show_notes') return t('home.err.showNotes');
  if (top === 'phase') return t('home.err.phase');
  return issue.message || t('home.err.invalid');
}

/** UTM tags align with My Polls / Poll share presets for consistent campaign analytics. */
function homePostCreateTrackedPollShareUrl(pollId: string, presetId: string): string {
  const base = shareUrlForPoll(pollId);
  if (presetId === 'discord') {
    return withUtm(base, { source: 'discord', medium: 'community', campaign: 'live_poll' });
  }
  if (presetId === 'x-post') {
    return withUtm(base, { source: 'x', medium: 'social', campaign: 'live_poll' });
  }
  return withUtm(base, { source: 'stream', medium: 'chat', campaign: 'live_poll' });
}

export default function Home() {
  const t = useT();
  useDocumentTitle(t('home.docTitle'));
  const [webhookTargets, setWebhookTargets] = useState<
    Array<{
      url: string;
      secret: string;
      include_results_snapshot?: boolean;
      include_owner_snapshot?: boolean;
      include_owner_events?: boolean;
    }>
  >([{ url: '', secret: '' }]);
  const [answers, setAnswers] = useState<string[]>(['', '']);
  const [title, setTitle] = useState('');
  const [error, setError] = useState('');
  const [errorUpgradeUrl, setErrorUpgradeUrl] = useState<string | null>(null);
  const [errorUpgradeIsLicenseRenewal, setErrorUpgradeIsLicenseRenewal] = useState(false);
  const [limitIp, setLimitIp] = useState('yes');
  const [selectionMode, setSelectionMode] = useState<'single' | 'multi'>('single');
  const [voteEligibility, setVoteEligibility] = useState<'anonymous' | 'account' | 'platform_linked'>(
    'anonymous',
  );
  const [retentionTtlDaysInput, setRetentionTtlDaysInput] = useState('');
  const [expirationDate, setExpirationDate] = useState('never');
  const [created, setCreated] = useState<{
    id: string;
    api_key: string;
    webhook_secrets?: Array<{ url: string; secret: string }>;
    embed_read_token?: string;
  } | null>(null);
  const [linkHint, setLinkHint] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [phase, setPhase] = useState<'draft' | 'open'>('open');
  const [showNotes, setShowNotes] = useState('');
  const [generateEmbedToken, setGenerateEmbedToken] = useState(false);
  const [resultsDelaySeconds, setResultsDelaySeconds] = useState(0);
  const [resultsDelayPreset, setResultsDelayPreset] = useState<'off' | 'low' | 'medium' | 'high'>(
    'off',
  );
  const [hasUserJwt, setHasUserJwt] = useState(() => Boolean(getStoredUserJwt()));
  const [billingJwt, setBillingJwt] = useState(() => getStoredUserJwt() ?? '');
  const queryClient = useQueryClient();
  const [selectedTemplateId, setSelectedTemplateId] = useState('');
  const [sharePresetId, setSharePresetId] = useState<string>(SHARE_PRESET_IDS[0]);
  const [quickMode, setQuickMode] = useState<'default' | 'stream-safe' | 'embed-locked'>('default');
  const [consentRegion, setConsentRegion] = useState<ConsentRegionHint>('unknown');

  const titleInputRef = useRef<HTMLInputElement>(null);
  const answersGroupRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const sync = () => {
      setHasUserJwt(Boolean(getStoredUserJwt()));
      setBillingJwt(getStoredUserJwt() ?? '');
    };
    sync();
    return subscribeUserJwtChanged(sync);
  }, []);
  useEffect(() => {
    void fetchConsentRegion().then((region) => setConsentRegion(region));
  }, []);

  const billingUsageQuery = useQuery({
    queryKey: profileBillingQueryKey(billingJwt),
    queryFn: () =>
      apiFetch('profile/billing', {
        adminToken: false,
        bearerToken: billingJwt.trim() || undefined,
      }) as Promise<ProfileBillingApiPayload>,
    enabled: Boolean(billingJwt.trim()),
  });
  const billingUsageWarning = billingUsageWarningSeverity(billingUsageQuery.data);
  const billingPastDue = billingPastDueBannerPayload(billingUsageQuery.data);
  const exportReminder = billingExportReminder(billingUsageQuery.data);

  const focusTitle = () => {
    requestAnimationFrame(() => {
      titleInputRef.current?.focus();
      titleInputRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    });
  };

  const focusFirstAnswer = () => {
    requestAnimationFrame(() => {
      const first = answersGroupRef.current?.querySelector('input');
      if (first instanceof HTMLInputElement) {
        first.focus();
        first.scrollIntoView({ behavior: 'smooth', block: 'center' });
      } else {
        answersGroupRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    });
  };

  const addAnswer = () => {
    if (answers.length >= 32) return;
    setAnswers((prev) => [...prev, '']);
    requestAnimationFrame(() => {
      const inputs = answersGroupRef.current?.querySelectorAll('input');
      const last = inputs?.[inputs.length - 1];
      if (last instanceof HTMLInputElement) {
        last.focus();
        last.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    });
  };

  const removeAnswer = (index: number) => {
    setAnswers((prev) => {
      if (prev.length <= 2) return prev;
      return prev.filter((_, i) => i !== index);
    });
    requestAnimationFrame(() => {
      const inputs = answersGroupRef.current?.querySelectorAll('input');
      const target = inputs?.[Math.max(0, index - 1)] ?? inputs?.[0];
      if (target instanceof HTMLInputElement) target.focus();
    });
  };

  const handleAnswerChange = (text: string, i: number) => {
    const newAnswers = [...answers];
    newAnswers[i] = text;
    setAnswers(newAnswers);
  };

  const handleAnswerKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      addAnswer();
    }
  };

  const renderAnswers = () => {
    return answers.map((_answer, index) => {
      return (
        <div key={index} className='ui-poll-option-row'>
          <Input
            placeholder={t('home.optionPlaceholder')}
            className='ui-input--stack'
            maxLength={500}
            value={answers[index]}
            onChange={(e) => handleAnswerChange(e.target.value, index)}
            onKeyDown={handleAnswerKeyDown}
            aria-label={t('home.optionAria', { n: String(index + 1) })}
          />
          {answers.length > 2 ? (
            <Button
              type='button'
              variant='secondary'
              className='ui-poll-option-remove'
              onClick={() => removeAnswer(index)}
              aria-label={`${t('home.webhookTargetRemove')} ${t('home.optionAria', { n: String(index + 1) })}`}
            >
              {t('home.webhookTargetRemove')}
            </Button>
          ) : null}
        </div>
      );
    });
  };

  const handleStartOver = () => {
    setCreated(null);
    setLinkHint('');
    setError('');
    setErrorUpgradeUrl(null);
    setErrorUpgradeIsLicenseRenewal(false);
    setTitle('');
    setAnswers(['', '']);
    setLimitIp('yes');
    setSelectionMode('single');
    setVoteEligibility('anonymous');
    setRetentionTtlDaysInput('');
    setExpirationDate('never');
    setWebhookTargets([{ url: '', secret: '' }]);
    setPhase('open');
    setShowNotes('');
    setGenerateEmbedToken(false);
    setResultsDelaySeconds(0);
    setResultsDelayPreset('off');
    setSelectedTemplateId('');
    setSharePresetId(SHARE_PRESET_IDS[0]);
    setQuickMode('default');
    requestAnimationFrame(() => titleInputRef.current?.focus());
  };

  const handleSubmit = () => {
    if (submitting) return;
    setCreated(null);
    setLinkHint('');
    setErrorUpgradeUrl(null);
    setErrorUpgradeIsLicenseRenewal(false);
    const trimmedAnswers = answers.map((answer) => answer.trim());
    const filteredAnswers = trimmedAnswers.filter((answer) => answer !== '');

    const limit_ip = limitIp === 'yes';

    let expiration = 999999999999999;
    if (expirationDate === '10m') {
      expiration = Date.now() + 1000 * 60 * 10;
    } else if (expirationDate === '1h') {
      expiration = Date.now() + 1000 * 60 * 60;
    } else if (expirationDate === '1d') {
      expiration = Date.now() + 1000 * 60 * 60 * 24;
    } else if (expirationDate === '1w') {
      expiration = Date.now() + 1000 * 60 * 60 * 24 * 7;
    } else if (expirationDate === '1mo') {
      expiration = Date.now() + 1000 * 60 * 60 * 24 * 30;
    }

    const sn = showNotes.trim();
    const normalizedWebhookTargets = webhookTargets
      .map((target) => ({
        url: target.url.trim(),
        secret: target.secret.trim(),
        include_results_snapshot: target.include_results_snapshot === true,
        include_owner_snapshot: target.include_owner_snapshot === true,
        include_owner_events: target.include_owner_events === true,
      }))
      .filter((target) => target.url !== '');
    const pollData = {
      title: title.trim(),
      options: filteredAnswers,
      limit_ip,
      expiration,
      ...(selectionMode === 'multi' ? { selection_mode: 'multi' as const } : {}),
      ...(voteEligibility !== 'anonymous'
        ? {
            vote_eligibility: voteEligibility,
            account_vote_consent_ack: true as const,
            ...(voteEligibility === 'platform_linked'
              ? {
                  platform_identity_provider: 'oauth_scaffold',
                  platform_identity_consent_version: 'v1',
                }
              : {}),
          }
        : {}),
      ...(retentionTtlDaysInput.trim() !== ''
        ? {
            retention_ttl_days: Math.max(
              1,
              Math.min(3650, Number.parseInt(retentionTtlDaysInput.trim(), 10) || 0),
            ),
          }
        : {}),
      phase,
      results_delay_seconds: resultsDelaySeconds,
      ...(sn ? { show_notes: sn } : {}),
      ...(generateEmbedToken ? { generate_embed_read_token: true as const } : {}),
      ...(normalizedWebhookTargets.length > 0
        ? {
            webhook_targets: normalizedWebhookTargets.map((target) => ({
              url: target.url,
              ...(target.secret !== '' ? { secret: target.secret } : {}),
              ...(target.include_results_snapshot ? { include_results_snapshot: true } : {}),
              ...(target.include_owner_snapshot ? { include_owner_snapshot: true } : {}),
              ...(target.include_owner_events ? { include_owner_events: true } : {}),
            })),
          }
        : {}),
    };

    const parsed = createPollBodySchema.safeParse(pollData);
    if (!parsed.success) {
      setError(createPollErrorMessage(parsed.error, t));
      const firstPath = parsed.error.issues[0]?.path[0];
      if (firstPath === 'title') focusTitle();
      else focusFirstAnswer();
      return;
    }

    setSubmitting(true);
    const sessionJwt = getStoredUserJwt()?.trim();
    apiFetch('poll', {
      method: 'POST',
      body: parsed.data,
      ...(sessionJwt ? { bearerToken: sessionJwt } : {}),
    })
      .then((data) => {
        const d = data as CreatePollResponse;
        if (d.status !== 'success') {
          setError(t('home.err.createFail'));
          focusTitle();
          return;
        }
        setCreated({
          id: d.data.id,
          api_key: d.data.api_key,
          ...(d.data.webhook_secrets ? { webhook_secrets: d.data.webhook_secrets } : {}),
          ...(d.data.embed_read_token ? { embed_read_token: d.data.embed_read_token } : {}),
        });
        setError('');
        setErrorUpgradeIsLicenseRenewal(false);
        if (sessionJwt) {
          void queryClient.invalidateQueries({ queryKey: profileBillingQueryKey(sessionJwt) });
        }
      })
      .catch((err: unknown) => {
        const upgradeHint = billingUpgradeHintFromError(err, billingUsageQuery.data);
        setErrorUpgradeUrl(upgradeHint.url);
        setErrorUpgradeIsLicenseRenewal(upgradeHint.isLicenseRenewal);
        if (
          isApiFetchError(err) &&
          err.errorCode === 'USAGE_LIMIT_ACTIVE_POLLS' &&
          err.details &&
          typeof err.details === 'object' &&
          !Array.isArray(err.details)
        ) {
          const d = err.details as Record<string, unknown>;
          const cur = typeof d.current === 'number' ? d.current : 0;
          const max = typeof d.max === 'number' ? d.max : 0;
          const plan = typeof d.plan === 'string' ? d.plan : '';
          setError(t('home.err.usageLimitPolls', { current: cur, max, plan }));
        } else {
          setError(errMsg(err, t('home.err.createRetry')));
        }
        focusTitle();
      })
      .finally(() => setSubmitting(false));
  };

  const copyEmbedToken = async (): Promise<boolean> => {
    if (!created?.embed_read_token) return false;
    setLinkHint('');
    try {
      await navigator.clipboard.writeText(created.embed_read_token);
      setLinkHint(t('home.banner.embedCopyOk'));
      return true;
    } catch {
      setLinkHint(`${t('home.banner.copyManual')} ${created.embed_read_token}`);
      return false;
    }
  };

  const copyShareLink = async (): Promise<boolean> => {
    if (!created?.id) return false;
    const url = homePostCreateTrackedPollShareUrl(created.id, sharePresetId);
    try {
      await navigator.clipboard.writeText(url);
      setLinkHint(t('home.banner.copyOk'));
      return true;
    } catch {
      setLinkHint(`${t('home.banner.copyManual')} ${url}`);
      return false;
    }
  };

  const shareCreatedPoll = async () => {
    if (!created?.id) return;
    setLinkHint('');
    const url = homePostCreateTrackedPollShareUrl(created.id, sharePresetId);
    const r = await shareUrlNative({
      url,
      title: title.trim() || t('home.pageH1'),
      text: title.trim() ? `${title.trim()} — ${url}` : url,
    });
    if (r.kind === 'shared') {
      setLinkHint(t('poll.shareDone'));
      return;
    }
    if (r.kind === 'aborted') return;
    await copyShareLink();
  };

  const showNativeShare = useMemo(
    () =>
      Boolean(
        created?.id && isWebShareLikelyAvailable(homePostCreateTrackedPollShareUrl(created.id, sharePresetId)),
      ),
    [created?.id, sharePresetId],
  );
  const shareUrl = created?.id ? homePostCreateTrackedPollShareUrl(created.id, sharePresetId) : '';
  const shareSnippet = useMemo(() => {
    if (!created?.id) return '';
    const cleanTitle = title.trim() || t('home.shareSnippetDefaultTitle');
    const url = homePostCreateTrackedPollShareUrl(created.id, sharePresetId);
    if (sharePresetId === 'discord') {
      return t('home.sharePreset.discord.snippet', { title: cleanTitle, url });
    }
    if (sharePresetId === 'x-post') {
      return t('home.sharePreset.x-post.snippet', { title: cleanTitle, url });
    }
    return t('home.sharePreset.stream-chat.snippet', { title: cleanTitle, url });
  }, [created?.id, sharePresetId, title, t]);
  const qrImageUrl = useMemo(() => {
    if (!shareUrl) return '';
    // Using a public QR renderer avoids bundling extra QR dependencies.
    return `https://api.qrserver.com/v1/create-qr-code/?size=320x320&margin=12&data=${encodeURIComponent(shareUrl)}`;
  }, [shareUrl]);

  const embedViewerUrl = useMemo(() => {
    const tok = created?.embed_read_token?.trim();
    const pid = created?.id;
    if (!tok || !pid) return '';
    return `${apiUrl(`poll/${encodeURIComponent(pid)}/embed`)}?embed_token=${encodeURIComponent(tok)}`;
  }, [created?.embed_read_token, created?.id]);

  const copyShareSnippet = async (): Promise<boolean> => {
    if (!shareSnippet) return false;
    setLinkHint('');
    try {
      await navigator.clipboard.writeText(shareSnippet);
      setLinkHint(t('home.postCreate.snippetCopyOk'));
      return true;
    } catch {
      setLinkHint(t('home.postCreate.snippetCopyManual', { snippet: shareSnippet }));
      return false;
    }
  };

  const handleApplyTemplate = () => {
    if (!isPollTemplateId(selectedTemplateId)) return;
    const keys = POLL_TEMPLATE_I18N[selectedTemplateId];
    const optionLines = t(keys.options)
      .split('\n')
      .map((line) => line.trim())
      .filter(Boolean);
    if (optionLines.length < 2) return;
    setError('');
    setTitle(t(keys.title));
    setAnswers(optionLines);
    setPhase('open');
    setShowNotes(t(keys.notes));
    setGenerateEmbedToken(false);
    setRetentionTtlDaysInput('');
    setResultsDelaySeconds(0);
    setResultsDelayPreset('off');
    requestAnimationFrame(() => titleInputRef.current?.focus());
  };

  const handleClearTemplateSelection = () => {
    setSelectedTemplateId('');
  };

  const handleQuickModeApply = (mode: 'default' | 'stream-safe' | 'embed-locked') => {
    setQuickMode(mode);
    if (mode === 'default') {
      setPhase('open');
      setLimitIp('yes');
      setVoteEligibility('anonymous');
      setResultsDelaySeconds(0);
      setResultsDelayPreset('off');
      setGenerateEmbedToken(false);
      return;
    }
    if (mode === 'stream-safe') {
      setPhase('open');
      setLimitIp('yes');
      setVoteEligibility('anonymous');
      setResultsDelaySeconds(20);
      setResultsDelayPreset('medium');
      setGenerateEmbedToken(false);
      return;
    }
    setPhase('draft');
    setLimitIp('yes');
    setVoteEligibility('anonymous');
    setResultsDelaySeconds(20);
    setResultsDelayPreset('medium');
    setGenerateEmbedToken(true);
  };

  const activeFeatureBadges = [
    phase === 'draft' ? t('home.featureBadge.draftStart') : null,
    selectionMode === 'multi' ? t('home.featureBadge.multiChoice') : null,
    voteEligibility !== 'anonymous' ? t('home.featureBadge.accountVotes') : null,
    limitIp === 'yes' ? t('home.featureBadge.oneIp') : null,
    resultsDelaySeconds > 0
      ? t('home.featureBadge.resultsDelay', { seconds: resultsDelaySeconds })
      : null,
    generateEmbedToken ? t('home.featureBadge.embedQueued') : null,
    showNotes.trim() !== '' ? t('home.featureBadge.notesAdded') : null,
    webhookTargets.some((target) => target.url.trim() !== '')
      ? t('home.featureBadge.webhookForm')
      : null,
  ].filter(Boolean) as string[];
  const createdFeatureBadges = created
    ? [
        phase === 'draft' ? t('home.featureBadge.createdDraft') : t('home.featureBadge.createdLive'),
        selectionMode === 'multi' ? t('home.featureBadge.multiChoice') : null,
        voteEligibility !== 'anonymous' ? t('home.featureBadge.accountVotes') : null,
        limitIp === 'yes' ? t('home.featureBadge.oneIp') : t('home.featureBadge.multiIp'),
        resultsDelaySeconds > 0
          ? t('home.featureBadge.resultsDelay', { seconds: resultsDelaySeconds })
          : null,
        created.embed_read_token ? t('home.featureBadge.embedGenerated') : null,
        (created.webhook_secrets?.length ?? 0) > 0 ? t('home.featureBadge.webhookGenerated') : null,
      ].filter(Boolean)
    : [];

  return (
    <Container size='lg' className='ui-page-shell asking-public-layout asking-home-page' id='asking-home-page'>
      {created ? (
        <PageHeader
          className='ui-page-hero'
          titleId='asking-home-page__title'
          titleClassName={cx('ui-page-hero-title', 'ui-page-hero-title--success')}
          title={t('home.banner.title')}
        />
      ) : (
        <PageHeader
          className='ui-page-hero'
          titleId='asking-home-page__title'
          titleClassName='ui-page-hero-title'
          subtitleClassName='ui-page-hero-tagline'
          title={t('home.pageH1')}
          subtitle={t('home.hero.tagline')}
        />
      )}
      {created && (
        <Card as='section' className='ui-created-banner ui-success-card'>
          <p className='ui-copy-muted'>
            {t('home.banner.nextIntro')} <Link to='/my-polls'>{t('nav.myPolls')}</Link>
            {t('home.banner.nextBetweenLinks')}
            <Link to='/admin'>{t('nav.admin')}</Link>
            {t('home.banner.nextEnd')}
          </p>
          <p className='ui-inline-actions'>
            <Link to='/$id' params={{ id: created.id }} className={cx('ui-button', 'ui-button--md', 'ui-button--primary')}>
              {t('home.banner.open')}
            </Link>
            <CopyFeedbackButton onCopy={copyShareLink}>{t('home.banner.copy')}</CopyFeedbackButton>
            {showNativeShare ? (
              <Button
                type='button'
                variant='secondary'
                className='ui-button--with-inline-icon'
                onClick={() => void shareCreatedPoll()}
              >
                <IconShare className='ui-button__icon' aria-hidden />
                {t('home.banner.share')}
              </Button>
            ) : null}
          </p>
          {createdFeatureBadges.length > 0 ? (
            <div className='ui-feature-badges'>
              {createdFeatureBadges.map((item) => (
                <span key={item} className='ui-feature-badge'>
                  {item}
                </span>
              ))}
            </div>
          ) : null}
          <details className='ui-postcreate-card' open>
            <summary className='ui-postcreate-summary' id='asking-home-page__distribution-summary'>
              {t('myPolls.distributionHeading')}
            </summary>
            <section className='ui-share-kit' aria-labelledby='asking-home-page__distribution-summary'>
              <p className='ui-copy-muted'>{t('myPolls.distributionHint')}</p>
              <p className='ui-copy-muted'>
                <a href={streamingObsDocHref()} target='_blank' rel='noopener noreferrer'>
                  {t('docs.streamingObsBrowserSource')}
                </a>
              </p>
              <div className='ui-share-kit-controls'>
                <label htmlFor='asking-home-page__share-preset'>{t('home.postCreate.sharePresetLabel')}</label>
                <Select
                  id='asking-home-page__share-preset'
                  className='ui-input--stack'
                  value={sharePresetId}
                  onChange={(e) => setSharePresetId(e.target.value)}
                >
                  {SHARE_PRESET_IDS.map((presetId) => (
                    <option key={presetId} value={presetId}>
                      {presetId === 'stream-chat'
                        ? t('home.sharePreset.stream-chat.label')
                        : presetId === 'discord'
                          ? t('home.sharePreset.discord.label')
                          : t('home.sharePreset.x-post.label')}
                    </option>
                  ))}
                </Select>
              </div>
              <Textarea
                className='ui-input--stack ui-share-kit-snippet'
                readOnly
                value={shareSnippet}
                aria-label={t('home.postCreate.shareSnippetAria')}
                rows={4}
              />
              <p className='ui-inline-actions'>
                <CopyFeedbackButton onCopy={copyShareSnippet}>
                  {t('home.postCreate.copySnippet')}
                </CopyFeedbackButton>
              </p>
              <div className='ui-share-kit-qr-wrap'>
                {qrImageUrl ? (
                  <img
                    src={qrImageUrl}
                    alt={t('home.postCreate.qrAlt')}
                    className='ui-share-kit-qr'
                    loading='lazy'
                  />
                ) : null}
                <p className='ui-copy-muted'>
                  <a
                    href={qrImageUrl}
                    target='_blank'
                    rel='noreferrer'
                    className='asking-home-page__jump-link'
                  >
                    {t('home.postCreate.qrOpenNewTab')}
                  </a>
                </p>
              </div>
            </section>
          </details>
          {linkHint ? (
            <Notice tone='info' className='ui-copy-muted' aria-live='polite'>
              {linkHint}
            </Notice>
          ) : null}
          <details className='ui-postcreate-card'>
            <summary className='ui-postcreate-summary'>{t('home.postCreate.accessSecretsSummary')}</summary>
            <p className='ui-copy-subtle'>{t('home.banner.secretHint')}</p>
            <details>
              <summary className='ui-disclosure-summary--simple'>{t('home.banner.showSecret')}</summary>
              <code className='ui-code-block'>{created.api_key}</code>
            </details>
          {created.webhook_secrets && created.webhook_secrets.length > 0 ? (
            <>
              <p className='ui-copy-subtle ui-webhook-label-spacer'>
                {t('home.banner.webhookSecret')}
              </p>
              <details open>
                <summary className='ui-disclosure-summary--simple'>
                  {t('home.banner.showWebhookSecret')}
                </summary>
                {created.webhook_secrets.map((target) => (
                  <code key={target.url} className='ui-code-block'>
                    {target.url} {'->'} {target.secret}
                  </code>
                ))}
              </details>
            </>
          ) : null}
          {created.embed_read_token ? (
            <>
              <p className='ui-copy-subtle ui-webhook-label-spacer'>
                {t('home.banner.embedToken')}
              </p>
              <details open>
                <summary className='ui-disclosure-summary--simple'>
                  {t('home.banner.showEmbedToken')}
                </summary>
                <code className='ui-code-block'>{created.embed_read_token}</code>
              </details>
              <p className='ui-inline-actions'>
                <CopyFeedbackButton onCopy={copyEmbedToken}>
                  {t('home.banner.copyEmbed')}
                </CopyFeedbackButton>
              </p>
              {embedViewerUrl ? (
                <>
                  <p className='ui-copy-subtle ui-webhook-label-spacer'>
                    {t('myPolls.embedFrameUrl')}
                  </p>
                  <p className='ui-copy-muted'>{t('myPolls.embedFrameUrlHint')}</p>
                  <code className='ui-code-block'>{embedViewerUrl}</code>
                  <p className='ui-inline-actions'>
                    <CopyFeedbackButton
                      onCopy={async () => {
                        try {
                          await navigator.clipboard.writeText(embedViewerUrl);
                          setLinkHint(t('myPolls.copyDone'));
                          return true;
                        } catch {
                          return false;
                        }
                      }}
                    >
                      {t('myPolls.sharePresetCopyLink')}
                    </CopyFeedbackButton>
                  </p>
                </>
              ) : null}
            </>
          ) : null}
          </details>
          <p className='ui-form-action-gap'>
            <Button
              type='button'
              variant='secondary'
              onClick={handleStartOver}
            >
              {t('home.startOver')}
            </Button>
          </p>
        </Card>
      )}
      {!created ? (
        <form
          id='asking-home-page__create-poll-form'
          className='ui-form-page-gap'
          onSubmit={(e) => {
            e.preventDefault();
            handleSubmit();
          }}
          aria-label={t('home.form.aria')}
        >
          <Card padding='none' className='ui-card--form-panel'>
            <section className='ui-flow' aria-labelledby='asking-home-page__flow-heading'>
              <h2 className='ui-flow-heading' id='asking-home-page__flow-heading'>
                {t('home.flow.title')}
              </h2>
              <ol className='ui-flow-list ui-flow-list--loose'>
                <li>{t('home.flow.step1')}</li>
                <li>{t('home.flow.step2')}</li>
                <li>{t('home.flow.step3')}</li>
                <li>{t('home.flow.step4')}</li>
              </ol>
            </section>

            <FormRow
              className='ui-form-block'
              label={t('home.templateGallery.label')}
              htmlFor='asking-home-page__template-gallery'
              hint={t('home.templateGallery.hint')}
            >
              <ActionRow className='asking-home-page__manage-row'>
                <Select
                  id='asking-home-page__template-gallery'
                  className='ui-input--stack'
                  value={selectedTemplateId}
                  onChange={(e) => setSelectedTemplateId(e.target.value)}
                >
                  <option value=''>{t('home.templateGallery.placeholder')}</option>
                  {POLL_TEMPLATE_IDS.map((templateId) => (
                    <option key={templateId} value={templateId}>
                      {t(POLL_TEMPLATE_I18N[templateId].label)}
                    </option>
                  ))}
                </Select>
                <Button
                  type='button'
                  variant='secondary'
                  onClick={handleApplyTemplate}
                  disabled={!selectedTemplateId}
                >
                  {t('home.templateGallery.apply')}
                </Button>
                <Button
                  type='button'
                  variant='secondary'
                  onClick={handleClearTemplateSelection}
                  disabled={!selectedTemplateId}
                >
                  {t('home.templateGallery.clear')}
                </Button>
              </ActionRow>
            </FormRow>

            <FormRow className='ui-form-block' label={t('home.titleLabel')} htmlFor='asking-home-page__poll-title'>
              <Input
                ref={titleInputRef}
                id='asking-home-page__poll-title'
                placeholder={t('home.titlePlaceholder')}
                className='ui-input--stack'
                maxLength={500}
                value={title}
                onChange={(e) => setTitle(e.target.value)}
              />
            </FormRow>

            <FormSection className='ui-form-block' title={t('home.answersHeading')} titleId='asking-home-page__answers-heading'>
              <div ref={answersGroupRef} role='group' aria-labelledby='asking-home-page__answers-heading'>
                {renderAnswers()}
              </div>
              <Button
                type='button'
                variant='secondary'
                size='sm'
                className='ui-button--lane-secondary'
                onClick={addAnswer}
                disabled={answers.length >= 32}
              >
                {t('home.addOption')}
              </Button>
              <p className='ui-form-hint'>
                {t('home.optionsTip')} ({answers.length}/32)
              </p>
            </FormSection>

            <FormSection
              className='ui-form-block'
              aria-label={t('home.quickMode.sectionAria')}
              title={t('home.quickMode.title')}
              titleId='asking-home-page__quick-mode-heading'
              hint={t('home.quickMode.hint')}
            >
              <ActionRow className='asking-home-page__manage-row'>
                <Button
                  type='button'
                  variant='secondary'
                  onClick={() => handleQuickModeApply('default')}
                  aria-pressed={quickMode === 'default'}
                >
                  {t('home.quickMode.standard')}
                </Button>
                <Button
                  type='button'
                  variant='secondary'
                  onClick={() => handleQuickModeApply('stream-safe')}
                  aria-pressed={quickMode === 'stream-safe'}
                >
                  {t('home.quickMode.stream')}
                </Button>
                <Button
                  type='button'
                  variant='secondary'
                  onClick={() => handleQuickModeApply('embed-locked')}
                  aria-pressed={quickMode === 'embed-locked'}
                >
                  {t('home.quickMode.embed')}
                </Button>
              </ActionRow>
              <p className='ui-form-hint'>{t('home.quickMode.presetsFootnote')}</p>
            </FormSection>

            {activeFeatureBadges.length > 0 ? (
              <FormSection
                className='ui-form-block'
                aria-label={t('home.audienceSafeguards.aria')}
                title={t('home.audienceSafeguards.title')}
                titleId='asking-home-page__audience-safeguards-heading'
              >
                <p className='ui-copy-muted'>{activeFeatureBadges.join(' · ')}</p>
              </FormSection>
            ) : null}

            <details className='ui-disclosure'>
              <summary className='ui-disclosure-summary'>
                <span className='ui-disclosure-summary-title'>{t('home.moreOptions')}</span>
                <span className='ui-disclosure-summary-hint'>{t('home.moreOptionsHint')}</span>
              </summary>
              <div className='ui-settings-grid ui-disclosure-body'>
                <section className='ui-settings-panel' aria-labelledby='asking-home-page__settings-heading'>
                  <h2 className='ui-field-heading' id='asking-home-page__settings-heading'>
                    {t('home.settings')}
                  </h2>
                  <div className='ui-setting-row'>
                    <label htmlFor='asking-home-page__limit-ip'>{t('home.limitIp')}</label>
                    <Select
                      name='limit_ip'
                      id='asking-home-page__limit-ip'
                      value={limitIp}
                      onChange={(e) => setLimitIp(e.target.value)}
                    >
                      <option value='yes'>{t('home.yes')}</option>
                      <option value='no'>{t('home.no')}</option>
                    </Select>
                  </div>
                  <div className='ui-setting-row'>
                    <label htmlFor='asking-home-page__selection-mode'>{t('home.selectionMode')}</label>
                    <Select
                      name='selection_mode'
                      id='asking-home-page__selection-mode'
                      value={selectionMode}
                      onChange={(e) => setSelectionMode(e.target.value === 'multi' ? 'multi' : 'single')}
                    >
                      <option value='single'>{t('home.selectionMode.single')}</option>
                      <option value='multi'>{t('home.selectionMode.multi')}</option>
                    </Select>
                  </div>
                  <div className='ui-setting-row'>
                    <label htmlFor='asking-home-page__vote-eligibility'>{t('home.voteEligibility')}</label>
                    <Select
                      name='vote_eligibility'
                      id='asking-home-page__vote-eligibility'
                      value={voteEligibility}
                      onChange={(e) =>
                        setVoteEligibility(
                          e.target.value === 'account' || e.target.value === 'platform_linked'
                            ? e.target.value
                            : 'anonymous',
                        )
                      }
                    >
                      <option value='anonymous'>{t('home.voteEligibility.anonymous')}</option>
                      <option value='account'>{t('home.voteEligibility.account')}</option>
                      <option value='platform_linked'>{t('home.voteEligibility.platformLinked')}</option>
                    </Select>
                  </div>
                  <p className='ui-form-hint'>{t('home.voteEligibility.hint')}</p>
                  {voteEligibility !== 'anonymous' ? (
                    <>
                      <p className='ui-form-hint'>{t('home.voteEligibility.accountConsentNote')}</p>
                      <p className='ui-form-hint'>
                        {t(
                          consentRegion === 'eu'
                            ? 'home.voteEligibility.regionLegalNote.eu'
                            : consentRegion === 'non-eu'
                              ? 'home.voteEligibility.regionLegalNote.nonEu'
                              : 'home.voteEligibility.regionLegalNote.unknown',
                        )}
                      </p>
                    </>
                  ) : null}
                  <div className='ui-setting-row'>
                    <label htmlFor='asking-home-page__expiration'>{t('home.expiration')}</label>
                    <Select
                      name='expiration'
                      id='asking-home-page__expiration'
                      value={expirationDate}
                      onChange={(e) => setExpirationDate(e.target.value)}
                    >
                      <option value='never'>{t('home.exp.never')}</option>
                      <option value='10m'>{t('home.exp.10m')}</option>
                      <option value='1h'>{t('home.exp.1h')}</option>
                      <option value='1d'>{t('home.exp.1d')}</option>
                      <option value='1w'>{t('home.exp.1w')}</option>
                      <option value='1mo'>{t('home.exp.1mo')}</option>
                    </Select>
                  </div>
                  <div className='ui-setting-row'>
                    <label htmlFor='asking-home-page__retention-ttl-days'>{t('home.retentionTtlDays')}</label>
                    <Input
                      id='asking-home-page__retention-ttl-days'
                      className='ui-input--stack'
                      type='number'
                      min={1}
                      max={3650}
                      step={1}
                      value={retentionTtlDaysInput}
                      onChange={(e) => setRetentionTtlDaysInput(e.target.value)}
                      placeholder={t('home.retentionTtlDays.placeholder')}
                    />
                  </div>
                  <p className='ui-form-hint'>{t('home.retentionTtlDays.hint')}</p>
                </section>
                <section className='ui-settings-panel' aria-labelledby='asking-home-page__webhook-heading'>
                  <h2 className='ui-field-heading' id='asking-home-page__webhook-heading'>
                    {t('home.webhookHeading')}
                  </h2>
                  <p className='ui-copy-muted'>{t('home.webhookIntro')}</p>
                  {!hasUserJwt ? (
                    <p className='ui-copy-muted'>
                      <Link to='/login'>{t('nav.signIn')}</Link>
                      {' — '}
                      {t('home.webhookSignInHint')}
                    </p>
                  ) : null}
                  {webhookTargets.map((target, idx) => (
                    <ActionRow key={`asking-home-page__webhook-row-${idx}`} className='asking-home-page__manage-row'>
                      <VisuallyHidden as='label' htmlFor={`asking-home-page__webhook-url-${idx}`}>
                        {t('home.webhookUrl')}
                      </VisuallyHidden>
                      <Input
                        id={`asking-home-page__webhook-url-${idx}`}
                        className='ui-input--stack'
                        maxLength={2048}
                        value={target.url}
                        onChange={(e) =>
                          setWebhookTargets((prev) =>
                            prev.map((row, rowIdx) =>
                              rowIdx === idx ? { ...row, url: e.target.value } : row,
                            ),
                          )
                        }
                        placeholder={t('home.webhookUrl')}
                        autoComplete='off'
                      />
                      <VisuallyHidden as='label' htmlFor={`asking-home-page__webhook-secret-${idx}`}>
                        {t('home.webhookSecret')}
                      </VisuallyHidden>
                      <Input
                        id={`asking-home-page__webhook-secret-${idx}`}
                        className='ui-input--stack'
                        maxLength={128}
                        type='password'
                        value={target.secret}
                        onChange={(e) =>
                          setWebhookTargets((prev) =>
                            prev.map((row, rowIdx) =>
                              rowIdx === idx ? { ...row, secret: e.target.value } : row,
                            ),
                          )
                        }
                        placeholder={t('home.webhookSecret')}
                        autoComplete='off'
                      />
                      <Button
                        type='button'
                        variant='secondary'
                        onClick={() =>
                          setWebhookTargets((prev) =>
                            prev.length <= 1 ? [{ url: '', secret: '' }] : prev.filter((_, i) => i !== idx),
                          )
                        }
                      >
                        {t('home.webhookTargetRemove')}
                      </Button>
                      <Checkbox
                        id={`asking-home-page__webhook-results-snapshot-${idx}`}
                        checked={target.include_results_snapshot === true}
                        onChange={(e) =>
                          setWebhookTargets((prev) =>
                            prev.map((row, rowIdx) =>
                              rowIdx === idx
                                ? { ...row, include_results_snapshot: e.target.checked }
                                : row,
                            ),
                          )
                        }
                        label={t('home.webhookIncludeResultsSnapshot')}
                      />
                      <Checkbox
                        id={`asking-home-page__webhook-owner-snapshot-${idx}`}
                        checked={target.include_owner_snapshot === true}
                        onChange={(e) =>
                          setWebhookTargets((prev) =>
                            prev.map((row, rowIdx) =>
                              rowIdx === idx ? { ...row, include_owner_snapshot: e.target.checked } : row,
                            ),
                          )
                        }
                        label={t('home.webhookIncludeOwnerSnapshot')}
                      />
                      <Checkbox
                        id={`asking-home-page__webhook-owner-events-${idx}`}
                        checked={target.include_owner_events === true}
                        onChange={(e) =>
                          setWebhookTargets((prev) =>
                            prev.map((row, rowIdx) =>
                              rowIdx === idx ? { ...row, include_owner_events: e.target.checked } : row,
                            ),
                          )
                        }
                        label={t('home.webhookIncludeOwnerSnapshot')}
                      />
                    </ActionRow>
                  ))}
                  <Button
                    type='button'
                    variant='secondary'
                    disabled={webhookTargets.length >= 10}
                    onClick={() => setWebhookTargets((prev) => [...prev, { url: '', secret: '' }])}
                  >
                    {t('home.webhookTargetAdd')}
                  </Button>
                  <p className='ui-form-hint'>{t('home.webhookSnapshotsHint')}</p>
                </section>
                <section className='ui-settings-panel' aria-labelledby='asking-home-page__creator-heading'>
                  <h2 className='ui-field-heading' id='asking-home-page__creator-heading'>
                    {t('home.creatorHeading')}
                  </h2>
                  <div className='ui-setting-row'>
                    <label htmlFor='asking-home-page__phase'>{t('home.phaseLabel')}</label>
                    <Select
                      id='asking-home-page__phase'
                      name='phase'
                      value={phase}
                      onChange={(e) => setPhase(e.target.value === 'draft' ? 'draft' : 'open')}
                    >
                      <option value='open'>{t('home.phaseOpen')}</option>
                      <option value='draft'>{t('home.phaseDraft')}</option>
                    </Select>
                  </div>
                  <FormRow
                    className='ui-form-block'
                    label={t('home.showNotesLabel')}
                    htmlFor='asking-home-page__show-notes'
                    hint={t('home.showNotesHint')}
                  >
                    <Textarea
                      id='asking-home-page__show-notes'
                      className='ui-input--stack'
                      rows={4}
                      maxLength={10_000}
                      value={showNotes}
                      onChange={(e) => setShowNotes(e.target.value)}
                      placeholder={t('home.showNotesPlaceholder')}
                      aria-label={t('home.showNotesLabel')}
                    />
                  </FormRow>
                  <div className='ui-setting-row ui-setting-row--checkbox'>
                    <Checkbox
                      id='asking-home-page__embed-token'
                      checked={generateEmbedToken}
                      onChange={(e) => setGenerateEmbedToken(e.target.checked)}
                      label={t('home.embedTokenCheck')}
                    />
                  </div>
                  <p className='ui-form-hint'>{t('home.embedTokenHint')}</p>
                  <FormRow
                    className='ui-form-block'
                    label={t('home.resultsDelayLabel')}
                    htmlFor='asking-home-page__results-delay'
                    hint={t('home.resultsDelayHint')}
                  >
                    <Select
                      id='asking-home-page__results-delay'
                      className='ui-input--stack'
                      value={resultsDelayPreset}
                      onChange={(e) => {
                        const preset = e.target.value as 'off' | 'low' | 'medium' | 'high';
                        setResultsDelayPreset(preset);
                        if (preset === 'off') setResultsDelaySeconds(0);
                        if (preset === 'low') setResultsDelaySeconds(10);
                        if (preset === 'medium') setResultsDelaySeconds(20);
                        if (preset === 'high') setResultsDelaySeconds(30);
                      }}
                    >
                      <option value='off'>{t('home.resultsDelayPreset.off')}</option>
                      <option value='low'>{t('home.resultsDelayPreset.low')}</option>
                      <option value='medium'>{t('home.resultsDelayPreset.medium')}</option>
                      <option value='high'>{t('home.resultsDelayPreset.high')}</option>
                    </Select>
                  </FormRow>
                </section>
              </div>
            </details>

            <div className='ui-form-footer ui-form-footer--sticky-narrow'>
              {billingPastDue ? (
                <Notice tone='error' className='ui-usage-banner' role='alert'>
                  {t('billing.pastDueBanner')}{' '}
                  <a
                    href={billingPastDue.portalUrl}
                    target='_blank'
                    rel='noreferrer'
                    className='ui-link'
                  >
                    {t('billing.openCustomerPortal')}
                  </a>
                </Notice>
              ) : null}
              {billingUsageWarning ? (
                billingUsageWarning === '95' ? (
                  <Notice tone='error' className='ui-usage-banner' role='status'>
                    {t('billing.usageNearLimit95')}
                  </Notice>
                ) : (
                  <p className='ui-copy-muted ui-usage-banner' role='status'>
                    {t('billing.usageNearLimit80')}
                  </p>
                )
              ) : null}
              {exportReminder ? (
                <p
                  className={
                    exportReminder.atCap || exportReminder.nearCap === '95'
                      ? 'ui-alert ui-alert--danger ui-usage-banner'
                      : 'ui-copy-muted ui-usage-banner'
                  }
                  role='status'
                >
                  {t('developer.billingExportUsage', {
                    current: exportReminder.current,
                    max: exportReminder.max,
                  })}
                </p>
              ) : null}
              {billingUsageQuery.data?.usage?.limitsEnforced &&
              typeof billingUsageQuery.data.usage.activePolls === 'number' &&
              typeof billingUsageQuery.data.usage.maxActivePolls === 'number' ? (
                billingUsageAtCap(billingUsageQuery.data) ? (
                  <Notice tone='error' className='ui-usage-banner' role='status'>
                    {t('home.pollUsageBanner', {
                      current: billingUsageQuery.data.usage.activePolls,
                      max: billingUsageQuery.data.usage.maxActivePolls,
                      plan: billingUsageQuery.data.billing?.plan ?? 'free',
                    })}
                  </Notice>
                ) : (
                  <p className='ui-copy-muted ui-usage-banner' role='status'>
                    {t('home.pollUsageBanner', {
                      current: billingUsageQuery.data.usage.activePolls,
                      max: billingUsageQuery.data.usage.maxActivePolls,
                      plan: billingUsageQuery.data.billing?.plan ?? 'free',
                    })}
                  </p>
                )
              ) : null}
              <Button
                type='submit'
                size='lg'
                fullWidth
                className='ui-button--lane-primary'
                disabled={
                  submitting ||
                  (Boolean(billingJwt.trim()) &&
                    billingUsageAtCap(billingUsageQuery.data) === true)
                }
                aria-busy={submitting}
              >
                {submitting ? t('home.submitting') : t('home.submit')}
              </Button>
              <div aria-live='polite'>
                {error ? (
                  <Notice tone='error'>
                    {error}
                    {errorUpgradeUrl ? (
                      <>
                        {' '}
                        <a
                          href={errorUpgradeUrl}
                          target='_blank'
                          rel='noreferrer'
                          className='ui-link'
                        >
                          {t(
                            errorUpgradeIsLicenseRenewal ? 'home.renewLicenseCta' : 'home.upgradeCta',
                          )}
                        </a>
                      </>
                    ) : null}
                  </Notice>
                ) : null}
              </div>
            </div>
          </Card>
        </form>
      ) : null}
    </Container>
  );
}
