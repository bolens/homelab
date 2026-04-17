import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { apiUrl } from '../apiBase';
import { useDocumentTitle } from '../hooks/useDocumentTitle';
import { type ApiFetchError, apiFetch } from '../http';
import { useLocaleTag, useT } from '../i18n/I18nContext';
import type { MessageKey } from '../i18n/locales';
import { formatLocaleInteger } from '../lib/formatLocaleDisplay';
import {
  billingExportReminder,
  billingUpgradeHintFromError,
  billingPastDueBannerPayload,
  billingUsageWarningSeverity,
  type BillingUsageWarningsPayload,
  type ProfileBillingApiPayload,
} from '../lib/profileBillingApi';
import {
  invalidateDeveloperLlmQueries,
  llmModelsQueryKey,
  llmStatusQueryKey,
  profileBillingQueryKey,
  profileLlmGatewayTokenQueryKey,
} from '../lib/queryKeys';
import { getStoredUserJwt, subscribeUserJwtChanged } from '../lib/userSession';
import { streamingObsDocHref } from '../lib/streamingObsDocHref';
import {
  Button,
  Container,
  FormRow,
  Inline,
  Input,
  Notice,
  PageHeader,
  SectionPanel,
  Select,
  Textarea,
} from '../ui';
import { errMsg } from '../utils/errMsg';

const LLM_GATEWAY_STORAGE_KEY = 'askingNgLlmGatewayToken';

type LlmStatusPayload = {
  provider: string;
  ollamaBaseUrl?: string;
  lmStudioBaseUrl?: string;
  gatewayAuth: boolean;
  ollamaAuth?: boolean;
};

type ModelsPayload = {
  data?: { id?: string }[];
};

type ChatCompletionPayload = {
  choices?: { message?: { content?: string } }[];
};

type ProfilePayload = {
  user?: {
    llmGatewayToken?: string | null;
    billingPlan?: string;
  };
};

type PolarBillingPayload = ProfileBillingApiPayload;

function polarBillingHasLinks(data: PolarBillingPayload | undefined): boolean {
  const pol = data?.polar;
  if (!pol || typeof pol !== 'object') return false;
  return Boolean(
    (typeof pol.customerPortalUrl === 'string' && pol.customerPortalUrl.trim() !== '') ||
      (typeof pol.checkoutCloudTeamUrl === 'string' && pol.checkoutCloudTeamUrl.trim() !== '') ||
      (typeof pol.checkoutCloudProUrl === 'string' && pol.checkoutCloudProUrl.trim() !== ''),
  );
}

function formatBillingUsageWarnings(
  w: BillingUsageWarningsPayload,
  t: (key: MessageKey, opts?: Record<string, string | number>) => string,
): string {
  const parts: string[] = [];
  if (w.activePolls) {
    parts.push(
      t('developer.billingWarnMeter', { meter: t('developer.billingMeterPolls'), level: w.activePolls }),
    );
  }
  if (w.votesThisMonth) {
    parts.push(
      t('developer.billingWarnMeter', { meter: t('developer.billingMeterVotes'), level: w.votesThisMonth }),
    );
  }
  if (w.dataExports) {
    parts.push(
      t('developer.billingWarnMeter', { meter: t('developer.billingMeterExports'), level: w.dataExports }),
    );
  }
  if (w.pollWebhooksThisUtcMinute) {
    parts.push(
      t('developer.billingWarnMeter', {
        meter: t('developer.billingMeterWebhooks'),
        level: w.pollWebhooksThisUtcMinute,
      }),
    );
  }
  if (w.campaignAttribution) {
    parts.push(
      t('developer.billingWarnMeter', {
        meter: t('developer.billingMeterCampaign'),
        level: w.campaignAttribution,
      }),
    );
  }
  return parts.join(t('developer.billingWarnListSep'));
}

function modelIdsFromPayload(data: ModelsPayload): string[] {
  const rows = data.data ?? [];
  return rows
    .map((r) => r.id)
    .filter((id): id is string => typeof id === 'string' && id.length > 0);
}

function assistantText(data: unknown): string {
  if (!data || typeof data !== 'object') return '';
  const c = (data as ChatCompletionPayload).choices?.[0]?.message?.content;
  return typeof c === 'string' ? c : '';
}

const webhookResultsSnapshotExample = JSON.stringify(
  {
    event: 'poll_updated',
    poll_id: 'poll_123',
    data: {
      poll_path: '/poll_123',
      results_path: '/poll_123/results',
      streamer_context: {
        poll_title: 'What should we play next?',
        phase: 'open',
        voting_paused: false,
        archived: false,
        selection_mode: 'single',
        schedule_utc_ms: {
          open_at: null,
          lock_at: null,
          reveal_at: null,
          expires_at: 1760000000000,
        },
      },
      results_snapshot: {
        captured_at_ms: 1759999900000,
        effective_phase: 'open',
        results_delay_applied: true,
        results_visible_through_ms: 1759999870000,
        boosted_voting_enabled: false,
        options: [
          { option: 'Mario Kart', vote_count: 42 },
          { option: 'Tetris 99', vote_count: 31 },
        ],
        metrics: {
          total_votes: 73,
          total_weighted_votes: 73,
        },
      },
    },
  },
  null,
  2,
);

const webhookOwnerSnapshotExample = JSON.stringify(
  {
    event: 'vote',
    poll_id: 'poll_123',
    data: {
      owner_snapshot: {
        captured_at_ms: 1759999900000,
        effective_phase: 'open',
        results_delay_applied: true,
        moderation_counters: {
          votes_last_1m: 8,
          unique_ip_hashes_last_1m: 6,
          unique_accounts_last_1m: 2,
          top_ip_votes_last_1m: 2,
          quarantined_votes_pending: 3,
          quarantined_votes_pending_account_linked: 1,
          votes_account_linked_last_24h: 14,
          votes_anonymous_last_24h: 201,
          trust_ip_burst: { enabled: true, window_sec: 10, vote_threshold: 4 },
          trust_chat_burst: { enabled: false },
        },
        delayed_votes_pending: 11,
      },
    },
  },
  null,
  2,
);

export default function Developer() {
  const t = useT();
  const localeTag = useLocaleTag();
  const queryClient = useQueryClient();
  useDocumentTitle(t('developer.docTitle'));
  const [gatewayTokenInput, setGatewayTokenInput] = useState('');
  const [gatewayToken, setGatewayToken] = useState('');
  const [model, setModel] = useState('');
  const [prompt, setPrompt] = useState('');
  const [assistantOut, setAssistantOut] = useState('');
  const [chatErr, setChatErr] = useState('');
  const [chatErrUpgradeUrl, setChatErrUpgradeUrl] = useState<string | null>(null);
  const [chatErrUpgradeIsLicenseRenewal, setChatErrUpgradeIsLicenseRenewal] = useState(false);
  const [toast, setToast] = useState<{
    kind: 'ok' | 'error';
    text: string;
    upgradeUrl?: string;
    upgradeIsLicenseRenewal?: boolean;
  } | null>(null);
  const [userJwt, setUserJwt] = useState(() => getStoredUserJwt() ?? '');

  useEffect(() => {
    const jwt = getStoredUserJwt() ?? '';
    setUserJwt(jwt);
    if (jwt) return;
    const saved = sessionStorage.getItem(LLM_GATEWAY_STORAGE_KEY) ?? '';
    setGatewayTokenInput(saved);
    setGatewayToken(saved);
  }, []);

  useEffect(() => {
    return subscribeUserJwtChanged(() => {
      setUserJwt(getStoredUserJwt() ?? '');
    });
  }, []);

  useEffect(() => {
    if (!toast) return;
    const timerId = window.setTimeout(() => setToast(null), 3500);
    return () => window.clearTimeout(timerId);
  }, [toast]);

  const profileQuery = useQuery({
    queryKey: profileLlmGatewayTokenQueryKey(userJwt),
    queryFn: () =>
      apiFetch('profile', {
        adminToken: false,
        bearerToken: userJwt || undefined,
      }) as Promise<ProfilePayload>,
    enabled: Boolean(userJwt),
  });

  const billingQuery = useQuery({
    queryKey: profileBillingQueryKey(userJwt),
    queryFn: () =>
      apiFetch('profile/billing', {
        adminToken: false,
        bearerToken: userJwt || undefined,
      }) as Promise<PolarBillingPayload>,
    enabled: Boolean(userJwt),
  });

  useEffect(() => {
    if (userJwt) return;
    const saved = sessionStorage.getItem(LLM_GATEWAY_STORAGE_KEY) ?? '';
    setGatewayTokenInput(saved);
    setGatewayToken(saved);
  }, [userJwt]);

  useEffect(() => {
    if (!profileQuery.data?.user) return;
    const saved = profileQuery.data.user.llmGatewayToken?.trim() ?? '';
    setGatewayTokenInput(saved);
    setGatewayToken(saved);
  }, [profileQuery.data]);

  const statusQuery = useQuery({
    queryKey: llmStatusQueryKey(gatewayToken),
    queryFn: () =>
      apiFetch('llm/status', {
        adminToken: false,
        bearerToken: gatewayToken || undefined,
      }) as Promise<LlmStatusPayload>,
  });

  const provider = statusQuery.data?.provider ?? '';
  const llmActive = provider === 'ollama' || provider === 'lmstudio';

  const statusErr =
    statusQuery.error instanceof Error ? (statusQuery.error as ApiFetchError) : null;
  const statusNeedsToken = Boolean(statusQuery.data?.gatewayAuth || statusErr?.status === 401);

  const modelsQuery = useQuery({
    queryKey: llmModelsQueryKey(gatewayToken),
    queryFn: () =>
      apiFetch('llm/v1/models', {
        adminToken: false,
        bearerToken: gatewayToken || undefined,
      }) as Promise<ModelsPayload>,
    enabled: llmActive,
  });

  useEffect(() => {
    const ids = modelsQuery.data ? modelIdsFromPayload(modelsQuery.data) : [];
    if (ids.length === 0) return;
    setModel((m) => (m && ids.includes(m) ? m : (ids[0] ?? '')));
  }, [modelsQuery.data]);

  const modelIds = modelsQuery.data ? modelIdsFromPayload(modelsQuery.data) : [];
  const selectModelValue =
    modelIds.length > 0 && modelIds.includes(model) ? model : (modelIds[0] ?? '');
  const billingUsageWarning = billingUsageWarningSeverity(billingQuery.data);
  const billingPastDue = billingPastDueBannerPayload(billingQuery.data);
  const exportReminder = billingExportReminder(billingQuery.data);

  const saveGatewayTokenMutation = useMutation({
    mutationFn: async (rawInput: string) => {
      const v = rawInput.trim();
      if (userJwt) {
        await apiFetch('profile', {
          method: 'PUT',
          adminToken: false,
          bearerToken: userJwt || undefined,
          body: { llmGatewayToken: v || null },
        });
      } else if (v) {
        sessionStorage.setItem(LLM_GATEWAY_STORAGE_KEY, v);
      } else {
        sessionStorage.removeItem(LLM_GATEWAY_STORAGE_KEY);
      }
      return v;
    },
    onSuccess: (v) => {
      setGatewayToken(v);
      setGatewayTokenInput(v);
      setToast({ kind: 'ok', text: t('developer.gatewayTokenSaveOk') });
      invalidateDeveloperLlmQueries(queryClient, userJwt, v);
    },
    onError: (e: unknown) => {
      const hint = billingUpgradeHintFromError(e, billingQuery.data);
      setToast({
        kind: 'error',
        text: errMsg(e, t('developer.gatewayTokenSaveFail')),
        upgradeUrl: hint.url ?? undefined,
        upgradeIsLicenseRenewal: hint.isLicenseRenewal,
      });
    },
  });

  const chatMutation = useMutation({
    mutationFn: async () => {
      const resolvedModel = modelIds.length > 0 ? selectModelValue : model;
      const body = {
        model: resolvedModel,
        messages: [{ role: 'user' as const, content: prompt }],
      };
      return apiFetch('llm/v1/chat/completions', {
        method: 'POST',
        adminToken: false,
        bearerToken: gatewayToken || undefined,
        body,
      });
    },
    onSuccess: (data) => {
      setChatErr('');
      setChatErrUpgradeUrl(null);
      setChatErrUpgradeIsLicenseRenewal(false);
      setAssistantOut(assistantText(data));
    },
    onError: (e: unknown) => {
      setAssistantOut('');
      const hint = billingUpgradeHintFromError(e, billingQuery.data);
      setChatErrUpgradeUrl(hint.url);
      setChatErrUpgradeIsLicenseRenewal(hint.isLicenseRenewal);
      setChatErr(errMsg(e, t('developer.errChat')));
    },
  });

  const modelsError = modelsQuery.isError ? errMsg(modelsQuery.error, t('developer.modelsLoading')) : '';
  const statusErrUpgradeHint = billingUpgradeHintFromError(statusQuery.error, billingQuery.data);
  const modelsErrUpgradeHint = billingUpgradeHintFromError(modelsQuery.error, billingQuery.data);

  const testConnectionMutation = useMutation({
    mutationFn: async () => {
      const models = (await apiFetch('llm/v1/models', {
        adminToken: false,
        bearerToken: gatewayToken || undefined,
      })) as ModelsPayload;
      return modelIdsFromPayload(models).length;
    },
    onSuccess: (count) => {
      setToast({
        kind: 'ok',
        text: t('developer.testOk', { count: formatLocaleInteger(count, localeTag) }),
      });
    },
    onError: (e: unknown) => {
      const hint = billingUpgradeHintFromError(e, billingQuery.data);
      setToast({
        kind: 'error',
        text: errMsg(e, t('developer.testFail')),
        upgradeUrl: hint.url ?? undefined,
        upgradeIsLicenseRenewal: hint.isLicenseRenewal,
      });
    },
  });

  return (
    <Container size='lg' className='ui-page-shell asking-public-layout asking-public-layout--wider asking-developer-page' id='asking-developer-page'>
      <PageHeader
        title={t('developer.title')}
        titleId='asking-developer-page__title'
        subtitle={
          <span className='asking-developer__intro'>
            {t('developer.introBefore')}
            <code>VITE_API_BASE</code>
            {t('developer.introBetween')}
            <code>LLM_PROVIDER</code>
            {t('developer.introAfter')}
          </span>
        }
      />

      <SectionPanel
        className='asking-developer__section'
        titleId='asking-developer__openapi-heading'
        title={<span className='ui-page-heading'>{t('developer.sectionOpenApi')}</span>}
      >
        <p>
          <a href={apiUrl('api-docs/')} target='_blank' rel='noopener noreferrer'>
            {t('developer.openApiLink')}
          </a>
        </p>
      </SectionPanel>

      <SectionPanel
        className='asking-developer__section'
        titleId='asking-developer__streaming-heading'
        title={<span className='ui-page-heading'>{t('developer.sectionStreaming')}</span>}
      >
        <p>
          <a href={streamingObsDocHref()} target='_blank' rel='noopener noreferrer'>
            {t('docs.streamingObsBrowserSource')}
          </a>
        </p>
      </SectionPanel>

      <SectionPanel
        className='asking-developer__section'
        titleId='asking-developer__webhook-examples-heading'
        title={<span className='ui-page-heading'>{t('developer.sectionWebhookExamples')}</span>}
      >
        <p className='asking-developer__intro'>{t('developer.webhookExamplesIntro')}</p>
        <p className='asking-developer__intro'>
          {t('developer.webhookExamplesDocsBefore')}{' '}
          <a href={apiUrl('api-docs/')} target='_blank' rel='noopener noreferrer'>
            {t('developer.openApiLink')}
          </a>{' '}
          {t('developer.webhookExamplesDocsAfter')}
        </p>
        <p className='asking-developer__intro'>{t('developer.webhookExamplesResultsNote')}</p>
        <Textarea
          className='ui-input--stack asking-developer__textarea'
          rows={20}
          value={webhookResultsSnapshotExample}
          readOnly
          aria-label={t('developer.webhookResultsExampleAria')}
        />
        <p className='asking-developer__intro'>{t('developer.webhookExamplesOwnerNote')}</p>
        <Textarea
          className='ui-input--stack asking-developer__textarea'
          rows={20}
          value={webhookOwnerSnapshotExample}
          readOnly
          aria-label={t('developer.webhookOwnerExampleAria')}
        />
      </SectionPanel>

      {userJwt && billingQuery.isSuccess && (
        <SectionPanel
          className='asking-developer__section'
          titleId='asking-developer__billing-heading'
          title={<span className='ui-page-heading'>{t('developer.sectionBilling')}</span>}
        >
          {billingPastDue ? (
            <Notice tone='error' className='ui-usage-banner'>
              {t('billing.pastDueBanner')}{' '}
              <a href={billingPastDue.portalUrl} target='_blank' rel='noreferrer' className='ui-link'>
                {t('billing.openCustomerPortal')}
              </a>
            </Notice>
          ) : null}
          {billingUsageWarning ? (
            billingUsageWarning === '95' ? (
              <Notice tone='error' role='status'>
                {t('billing.usageNearLimit95')}
              </Notice>
            ) : (
              <p className='asking-developer__intro' role='status'>
                {t('billing.usageNearLimit80')}
              </p>
            )
          ) : null}
          <p className='asking-developer__intro'>{t('developer.billingIntro')}</p>
          <p className='asking-developer__intro'>
            <strong>{t('developer.billingCurrentPlan')}</strong>{' '}
            <code>{billingQuery.data?.billing?.plan ?? 'free'}</code>
          </p>
          {billingQuery.data?.usage?.limitsEnforced &&
          typeof billingQuery.data.usage.activePolls === 'number' &&
          typeof billingQuery.data.usage.maxActivePolls === 'number' ? (
            <p className='asking-developer__intro'>
              {t('developer.billingPollUsage', {
                current: billingQuery.data.usage.activePolls,
                max: billingQuery.data.usage.maxActivePolls,
              })}
            </p>
          ) : null}
          {billingQuery.data?.usage?.limitsEnforced &&
          typeof billingQuery.data.usage.votesThisMonth === 'number' &&
          typeof billingQuery.data.usage.maxVotesPerMonth === 'number' &&
          billingQuery.data.usage.maxVotesPerMonth < Number.MAX_SAFE_INTEGER / 2 ? (
            <p className='asking-developer__intro'>
              {t('developer.billingVoteUsage', {
                current: billingQuery.data.usage.votesThisMonth,
                max: billingQuery.data.usage.maxVotesPerMonth,
              })}
            </p>
          ) : null}
          {billingQuery.data?.usage?.limitsEnforced &&
          typeof billingQuery.data.usage.maxWsSubscribersPerPoll === 'number' ? (
            <p className='asking-developer__intro'>
              {t('developer.billingWsRoomCap', {
                max: billingQuery.data.usage.maxWsSubscribersPerPoll,
              })}
            </p>
          ) : null}
          {billingQuery.data?.usage?.limitsEnforced &&
          typeof billingQuery.data.usage.exportsToday === 'number' &&
          typeof billingQuery.data.usage.maxExportsPerDay === 'number' &&
          billingQuery.data.usage.maxExportsPerDay < Number.MAX_SAFE_INTEGER / 2 ? (
            <p className='asking-developer__intro'>
              {t('developer.billingExportUsage', {
                current: billingQuery.data.usage.exportsToday,
                max: billingQuery.data.usage.maxExportsPerDay,
              })}
            </p>
          ) : null}
          {exportReminder?.atCap ? (
            <Notice tone='error' role='status'>
              {t('billing.usageNearLimit95')}
            </Notice>
          ) : null}
          {billingQuery.data?.usage?.limitsEnforced &&
          typeof billingQuery.data.usage.maxPollLiveFanoutPerSec === 'number' ? (
            <p className='asking-developer__intro'>
              {t('developer.billingFanoutCap', {
                max: billingQuery.data.usage.maxPollLiveFanoutPerSec,
              })}
            </p>
          ) : null}
          {billingQuery.data?.usage?.limitsEnforced &&
          typeof billingQuery.data.usage.webhookDeliveriesThisUtcMinute === 'number' &&
          typeof billingQuery.data.usage.maxWebhookDeliveriesPerUtcMinute === 'number' ? (
            <p className='asking-developer__intro'>
              {t('developer.billingWebhookUsage', {
                current: billingQuery.data.usage.webhookDeliveriesThisUtcMinute,
                max: billingQuery.data.usage.maxWebhookDeliveriesPerUtcMinute,
              })}
            </p>
          ) : null}
          {billingQuery.data?.usage?.limitsEnforced &&
          typeof billingQuery.data.usage.campaignAttributionIncrementsToday === 'number' &&
          typeof billingQuery.data.usage.maxCampaignAttributionPerUtcDay === 'number' ? (
            <p className='asking-developer__intro'>
              {t('developer.billingCampaignAttributionUsage', {
                current: billingQuery.data.usage.campaignAttributionIncrementsToday,
                max: billingQuery.data.usage.maxCampaignAttributionPerUtcDay,
              })}
            </p>
          ) : null}
          {billingQuery.data?.usage?.limitsEnforced && billingQuery.data.usage.warnings ? (
            <p className='asking-developer__intro'>
              {t('developer.billingUsageWarningsLine', {
                detail: formatBillingUsageWarnings(billingQuery.data.usage.warnings, t),
              })}
            </p>
          ) : null}
          {polarBillingHasLinks(billingQuery.data) && (
          <ul className='asking-developer__list'>
            {typeof billingQuery.data?.polar?.customerPortalUrl === 'string' &&
              billingQuery.data.polar.customerPortalUrl.trim() !== '' && (
                <li>
                  <a
                    href={billingQuery.data.polar.customerPortalUrl.trim()}
                    target='_blank'
                    rel='noopener noreferrer'
                  >
                    {t('developer.billingPortal')}
                  </a>
                </li>
              )}
            {typeof billingQuery.data?.polar?.checkoutCloudTeamUrl === 'string' &&
              billingQuery.data.polar.checkoutCloudTeamUrl.trim() !== '' && (
                <li>
                  <a
                    href={billingQuery.data.polar.checkoutCloudTeamUrl.trim()}
                    target='_blank'
                    rel='noopener noreferrer'
                  >
                    {t('developer.billingCheckoutTeam')}
                  </a>
                </li>
              )}
            {typeof billingQuery.data?.polar?.checkoutCloudProUrl === 'string' &&
              billingQuery.data.polar.checkoutCloudProUrl.trim() !== '' && (
                <li>
                  <a
                    href={billingQuery.data.polar.checkoutCloudProUrl.trim()}
                    target='_blank'
                    rel='noopener noreferrer'
                  >
                    {t('developer.billingCheckoutPro')}
                  </a>
                </li>
              )}
          </ul>
          )}
        </SectionPanel>
      )}

      <SectionPanel
        className='asking-developer__section'
        titleId='asking-developer__llm-heading'
        title={<span className='ui-page-heading'>{t('developer.sectionLlm')}</span>}
      >
        {statusQuery.isLoading && <p>{t('developer.statusLoading')}</p>}
        {statusQuery.isError && (
          <Notice tone='error'>
            {errMsg(statusQuery.error, t('developer.errStatus'))}
            {statusErrUpgradeHint.url ? (
              <>
                {' '}
                <a href={statusErrUpgradeHint.url} target='_blank' rel='noreferrer' className='ui-link'>
                  {t(
                    statusErrUpgradeHint.isLicenseRenewal
                      ? 'developer.renewLicenseCta'
                      : 'developer.upgradeCta',
                  )}
                </a>
              </>
            ) : null}
          </Notice>
        )}
        {statusQuery.data && (
          <ul className='asking-developer__list'>
            <li>
              <strong>{t('developer.provider')}</strong> {statusQuery.data.provider}
            </li>
            {statusQuery.data.ollamaBaseUrl && (
              <li>
                <strong>{t('developer.ollamaUrl')}</strong>{' '}
                <code>{statusQuery.data.ollamaBaseUrl}</code>
              </li>
            )}
            {statusQuery.data.lmStudioBaseUrl && (
              <li>
                <strong>{t('developer.lmStudioUrl')}</strong>{' '}
                <code>{statusQuery.data.lmStudioBaseUrl}</code>
              </li>
            )}
            <li>
              <strong>{t('developer.gatewayAuth')}</strong>{' '}
              {statusQuery.data.gatewayAuth
                ? t('developer.gatewayAuthOn')
                : t('developer.gatewayAuthOff')}
            </li>
            {provider === 'ollama' ? (
              <li>
                <strong>{t('developer.ollamaAuth')}</strong>{' '}
                {statusQuery.data.ollamaAuth
                  ? t('developer.gatewayAuthOn')
                  : t('developer.gatewayAuthOff')}
              </li>
            ) : null}
          </ul>
        )}

        {statusNeedsToken && (
          <div className='asking-developer__stack'>
            <FormRow
              label={t('developer.gatewayTokenLabel')}
              htmlFor='asking-developer__gateway-token'
              hint={
                userJwt
                  ? t('developer.gatewayTokenStoredAccount')
                  : t('developer.gatewayTokenStoredSession')
              }
            >
              <Inline gap='sm' wrap align='center' className='asking-developer__gateway-row'>
                <Input
                  id='asking-developer__gateway-token'
                  type='password'
                  autoComplete='off'
                  className='ui-input--stack'
                  value={gatewayTokenInput}
                  onChange={(e) => setGatewayTokenInput(e.target.value)}
                />
                <Button
                  type='button'
                  variant='secondary'
                  size='sm'
                  className='ui-button--lane-secondary'
                  onClick={() => saveGatewayTokenMutation.mutate(gatewayTokenInput)}
                  disabled={saveGatewayTokenMutation.isPending}
                  aria-busy={saveGatewayTokenMutation.isPending}
                >
                  {saveGatewayTokenMutation.isPending ? t('developer.sending') : t('developer.save')}
                </Button>
              </Inline>
            </FormRow>
          </div>
        )}

        {!llmActive && statusQuery.data && (
          <p className='asking-developer__muted'>{t('developer.noLlmHint')}</p>
        )}

        {llmActive && (
          <>
            <h5 className='ui-page-heading asking-developer__heading--spaced' id='asking-developer-page__models-heading'>
              {t('developer.modelsHeading')}
            </h5>
            {modelsQuery.isLoading && <p>{t('developer.modelsLoading')}</p>}
            {modelsError ? (
              <Notice tone='error'>
                {modelsError}
                {modelsErrUpgradeHint.url ? (
                  <>
                    {' '}
                    <a href={modelsErrUpgradeHint.url} target='_blank' rel='noreferrer' className='ui-link'>
                      {t(
                        modelsErrUpgradeHint.isLicenseRenewal
                          ? 'developer.renewLicenseCta'
                          : 'developer.upgradeCta',
                      )}
                    </a>
                  </>
                ) : null}
              </Notice>
            ) : null}
            {modelsQuery.data && (
              <p className='asking-developer__intro'>
                {t('developer.modelsCount', {
                  count: formatLocaleInteger(
                    modelIdsFromPayload(modelsQuery.data).length,
                    localeTag,
                  ),
                })}
              </p>
            )}

            <h5 className='ui-page-heading asking-developer__heading--spaced-sm' id='asking-developer-page__chat-heading'>
              {t('developer.chatHeading')}
            </h5>
            <FormRow label={t('developer.modelLabel')} htmlFor='asking-developer__model-select'>
              <Select
                id='asking-developer__model-select'
                className='ui-input--stack asking-developer__model-input'
                value={modelsQuery.isLoading ? '' : modelIds.length === 0 ? '' : selectModelValue}
                onChange={(e) => setModel(e.target.value)}
                disabled={modelsQuery.isLoading || modelIds.length === 0}
                aria-busy={modelsQuery.isLoading}
              >
                {modelsQuery.isLoading ? (
                  <option value=''>{t('developer.modelsLoading')}</option>
                ) : modelIds.length === 0 ? (
                  <option value=''>{t('developer.modelSelectNoModels')}</option>
                ) : (
                  modelIds.map((id) => (
                    <option key={id} value={id}>
                      {id}
                    </option>
                  ))
                )}
              </Select>
            </FormRow>
            <FormRow
              className='asking-developer__prompt-row'
              label={t('developer.messageLabel')}
              htmlFor='asking-developer__prompt'
            >
              <Textarea
                id='asking-developer__prompt'
                className='ui-input--stack asking-developer__textarea'
                rows={4}
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                placeholder={t('developer.messagePlaceholder')}
              />
            </FormRow>
            <Inline gap='md' wrap align='center' className='asking-developer__actions'>
              <Button
                type='button'
                variant='secondary'
                size='sm'
                className='ui-button--lane-secondary'
                disabled={testConnectionMutation.isPending}
                aria-busy={testConnectionMutation.isPending}
                onClick={() => testConnectionMutation.mutate()}
              >
                {testConnectionMutation.isPending ? t('developer.testing') : t('developer.test')}
              </Button>
              <Button
                type='button'
                variant='primary'
                size='md'
                className='ui-button--lane-primary'
                disabled={
                  chatMutation.isPending ||
                  modelIds.length === 0 ||
                  modelsQuery.isLoading ||
                  !prompt.trim()
                }
                aria-busy={chatMutation.isPending}
                onClick={() => chatMutation.mutate()}
              >
                {chatMutation.isPending ? t('developer.sending') : t('developer.send')}
              </Button>
            </Inline>
            {chatErr ? (
              <Notice tone='error' role='alert'>
                {chatErr}
                {chatErrUpgradeUrl ? (
                  <>
                    {' '}
                    <a href={chatErrUpgradeUrl} target='_blank' rel='noreferrer' className='ui-link'>
                      {t(
                        chatErrUpgradeIsLicenseRenewal
                          ? 'developer.renewLicenseCta'
                          : 'developer.upgradeCta',
                      )}
                    </a>
                  </>
                ) : null}
              </Notice>
            ) : null}
            {assistantOut ? (
              <pre
                className='asking-developer__output-pre'
                role='region'
                aria-label={t('developer.chatOutputAria')}
                aria-live='polite'
              >
                {assistantOut}
              </pre>
            ) : null}
          </>
        )}
      </SectionPanel>
      {toast ? (
        <Notice
          tone={toast.kind === 'ok' ? 'success' : 'error'}
          aria-live='polite'
          className={toast.kind === 'ok' ? 'ui-copy-muted' : undefined}
          style={{
            position: 'fixed',
            right: 16,
            bottom: 16,
            zIndex: 1200,
            maxWidth: 520,
            padding: '10px 12px',
            borderRadius: 8,
            background: 'var(--color-bg-surface)',
            boxShadow: '0 4px 14px var(--color-shadow-hover)',
          }}
        >
          {toast.text}
          {toast.upgradeUrl ? (
            <>
              {' '}
              <a href={toast.upgradeUrl} target='_blank' rel='noreferrer' className='ui-link'>
                {t(toast.upgradeIsLicenseRenewal ? 'developer.renewLicenseCta' : 'developer.upgradeCta')}
              </a>
            </>
          ) : null}
        </Notice>
      ) : null}
    </Container>
  );
}
