import { useEffect, useState } from 'react';
import { useNavigate } from '@tanstack/react-router';
import { apiUrl } from '../apiBase';
import { apiFetch, isApiFetchError } from '../http';
import { useT } from '../i18n/I18nContext';
import {
  COOKIE_CONSENT_CHANGED_EVENT,
  fetchConsentRegion,
  getCookieConsentState,
  getParsedGranularConsent,
  prefersGranularConsentUi,
  saveCookieConsent,
  saveGranularConsent,
  setGranularUiPreference,
  type ConsentRegionHint,
  type CookieConsentChoice,
  type CookieConsentState,
} from '../lib/cookieConsent';
import { clearStoredUserJwt, getStoredUserJwt } from '../lib/userSession';
import { Button, FormRow, Inline, Input, Stack } from '../ui';
import CookieConsentCategoriesForm from './CookieConsentCategoriesForm';

function consentToLabel(state: CookieConsentState, t: ReturnType<typeof useT>): string {
  if (state === 'accepted') return t('privacy.cookie.status.allowed');
  if (state === 'rejected') return t('privacy.cookie.status.off');
  return t('privacy.cookie.status.notSet');
}

export default function PrivacySettingsSection() {
  const t = useT();
  const navigate = useNavigate();
  const [consentState, setConsentState] = useState<CookieConsentState>(() => getCookieConsentState());
  const [region, setRegion] = useState<ConsentRegionHint>('unknown');
  const [showGranular, setShowGranular] = useState(() => prefersGranularConsentUi('unknown'));
  const [functional, setFunctional] = useState(false);
  const [analytics, setAnalytics] = useState(false);
  const [deletePassword, setDeletePassword] = useState('');
  const [deleteConfirm, setDeleteConfirm] = useState('');
  const [deleteBusy, setDeleteBusy] = useState(false);
  const [deleteMsg, setDeleteMsg] = useState<string | null>(null);
  const [deleteErr, setDeleteErr] = useState<string | null>(null);
  const [exportBusy, setExportBusy] = useState(false);
  const [exportErr, setExportErr] = useState<string | null>(null);
  const isSignedIn = Boolean(getStoredUserJwt());

  useEffect(() => {
    const syncFromStorage = () => {
      setConsentState(getCookieConsentState());
      const parsed = getParsedGranularConsent();
      if (parsed) {
        setFunctional(parsed.functional);
        setAnalytics(parsed.analytics);
      } else {
        setFunctional(false);
        setAnalytics(getCookieConsentState() === 'accepted');
      }
    };
    syncFromStorage();
    window.addEventListener(COOKIE_CONSENT_CHANGED_EVENT, syncFromStorage as EventListener);
    return () => window.removeEventListener(COOKIE_CONSENT_CHANGED_EVENT, syncFromStorage as EventListener);
  }, []);

  useEffect(() => {
    void fetchConsentRegion().then((r) => {
      setRegion(r);
      setShowGranular(prefersGranularConsentUi(r));
      const parsed = getParsedGranularConsent();
      if (parsed) {
        setFunctional(parsed.functional);
        setAnalytics(parsed.analytics);
      }
    });
  }, []);

  const setConsent = (next: CookieConsentChoice) => {
    saveCookieConsent(next, 'settings');
    setConsentState(next);
  };

  const onSaveGranular = () => {
    saveGranularConsent({ functional, analytics, marketing: false }, 'settings', region);
    setConsentState(analytics ? 'accepted' : 'rejected');
  };

  const canDelete = deletePassword.trim().length > 0 && deleteConfirm.trim() === 'DELETE';

  return (
    <section className='settings-privacy' aria-label={t('privacy.sectionTitle')}>
      <h2 className='settings-privacy__title'>{t('privacy.sectionTitle')}</h2>
      <p className='settings-privacy__lead'>{t('privacy.sectionLead')}</p>

      <div className='settings-privacy__card'>
        <h3 className='settings-privacy__card-title'>{t('privacy.cookie.title')}</h3>
        <p className='settings-privacy__text'>{t('privacy.cookie.copy')}</p>
        <p className='settings-privacy__status'>
          {t('privacy.cookie.current')}: <strong>{consentToLabel(consentState, t)}</strong>
        </p>

        {showGranular ? (
          <>
            <CookieConsentCategoriesForm
              idPrefix='settings-privacy'
              functional={functional}
              analytics={analytics}
              onChange={(patch) => {
                if (patch.functional !== undefined) setFunctional(patch.functional);
                if (patch.analytics !== undefined) setAnalytics(patch.analytics);
              }}
            />
            <Inline gap='sm' wrap className='settings-privacy__actions mt-3'>
              {region !== 'eu' ? (
                <Button
                  type='button'
                  variant='secondary'
                  size='sm'
                  onClick={() => {
                    setGranularUiPreference(false);
                    setShowGranular(false);
                  }}
                >
                  {t('privacy.cookie.simpleMode')}
                </Button>
              ) : null}
              <Button type='button' variant='secondary' size='sm' onClick={onSaveGranular}>
                {t('cookie.categories.save')}
              </Button>
            </Inline>
          </>
        ) : (
          <>
            <Inline gap='sm' wrap className='settings-privacy__actions'>
              <Button type='button' variant='secondary' size='sm' onClick={() => setConsent('rejected')}>
                {t('privacy.cookie.keepOff')}
              </Button>
              <Button type='button' variant='secondary' size='sm' onClick={() => setConsent('accepted')}>
                {t('privacy.cookie.allow')}
              </Button>
            </Inline>
            <p className='settings-privacy__text settings-privacy__text--compact mb-0 mt-2'>
              <Button
                type='button'
                variant='ghost'
                size='sm'
                className='settings-privacy__inline-link'
                onClick={() => {
                  setGranularUiPreference(true);
                  setShowGranular(true);
                  const parsed = getParsedGranularConsent();
                  if (parsed) {
                    setFunctional(parsed.functional);
                    setAnalytics(parsed.analytics);
                  } else {
                    setFunctional(false);
                    setAnalytics(consentState === 'accepted');
                  }
                }}
              >
                {t('privacy.cookie.customize')}
              </Button>
            </p>
          </>
        )}
      </div>

      <div className='settings-privacy__card'>
        <h3 className='settings-privacy__card-title'>{t('privacy.export.title')}</h3>
        <p className='settings-privacy__text'>{t('privacy.export.copy')}</p>
        <Button
          type='button'
          variant='secondary'
          size='sm'
          disabled={!isSignedIn || exportBusy}
          onClick={async () => {
            setExportBusy(true);
            setExportErr(null);
            try {
              const jwt = getStoredUserJwt();
              if (!jwt) {
                setExportErr(t('privacy.export.errNeedAuth'));
                return;
              }
              const res = await fetch(apiUrl('profile/export'), {
                headers: { Authorization: `Bearer ${jwt}` },
              });
              if (!res.ok) {
                setExportErr(t('privacy.export.errFail'));
                return;
              }
              const blob = await res.blob();
              const cd = res.headers.get('Content-Disposition');
              const match = cd?.match(/filename="([^"]+)"/);
              const filename = match?.[1] ?? 'asking-ng-data-export.json';
              const url = URL.createObjectURL(blob);
              const a = document.createElement('a');
              a.href = url;
              a.download = filename;
              a.rel = 'noopener';
              document.body.appendChild(a);
              a.click();
              a.remove();
              URL.revokeObjectURL(url);
            } catch {
              setExportErr(t('privacy.export.errFail'));
            } finally {
              setExportBusy(false);
            }
          }}
        >
          {exportBusy ? t('privacy.export.busy') : t('privacy.export.cta')}
        </Button>
        {exportErr ? <p className='settings-privacy__msg text-danger mt-2 mb-0'>{exportErr}</p> : null}
      </div>

      <div className='settings-privacy__card settings-privacy__danger'>
        <h3 className='settings-privacy__card-title'>{t('privacy.delete.title')}</h3>
        <p className='settings-privacy__text'>{t('privacy.delete.copy')}</p>
        {!isSignedIn ? <p className='settings-privacy__msg text-warning'>{t('privacy.delete.needSignIn')}</p> : null}
        <Stack gap='md'>
          <FormRow label={t('privacy.delete.password')} htmlFor='settings-delete-password'>
            <Input
              id='settings-delete-password'
              className='ui-input--stack'
              type='password'
              autoComplete='current-password'
              value={deletePassword}
              onChange={(e) => setDeletePassword(e.target.value)}
              disabled={!isSignedIn}
            />
          </FormRow>
          <FormRow label={t('privacy.delete.confirmLabel')} htmlFor='settings-delete-confirm'>
            <Input
              id='settings-delete-confirm'
              className='ui-input--stack'
              type='text'
              spellCheck={false}
              value={deleteConfirm}
              onChange={(e) => setDeleteConfirm(e.target.value)}
              placeholder='DELETE'
              disabled={!isSignedIn}
            />
          </FormRow>
          <Button
            type='button'
            variant='danger'
            size='sm'
            disabled={!isSignedIn || !canDelete || deleteBusy}
            onClick={async () => {
              setDeleteBusy(true);
              setDeleteMsg(null);
              setDeleteErr(null);
              try {
                await apiFetch('profile', {
                  method: 'DELETE',
                  body: { password: deletePassword },
                });
                clearStoredUserJwt();
                try {
                  localStorage.removeItem('adminToken');
                } catch {
                  /* private mode */
                }
                setDeleteMsg(t('privacy.delete.done'));
                await navigate({ to: '/' });
              } catch (err) {
                if (isApiFetchError(err) && err.status === 401) {
                  setDeleteErr(t('privacy.delete.errInvalidPassword'));
                } else {
                  setDeleteErr(t('privacy.delete.errFail'));
                }
              } finally {
                setDeleteBusy(false);
              }
            }}
          >
            {deleteBusy ? t('privacy.delete.deleting') : t('privacy.delete.cta')}
          </Button>
        </Stack>
        {deleteMsg ? <p className='settings-privacy__msg text-success mt-2 mb-0'>{deleteMsg}</p> : null}
        {deleteErr ? <p className='settings-privacy__msg text-danger mt-2 mb-0'>{deleteErr}</p> : null}
      </div>
    </section>
  );
}
