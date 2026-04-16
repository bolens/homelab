import { useEffect, useState } from 'react';
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
  type CookieConsentState,
} from '../lib/cookieConsent';
import { Button } from '../ui';
import CookieConsentCategoriesForm from './CookieConsentCategoriesForm';

function useCookieConsentState(): CookieConsentState {
  const [state, setState] = useState<CookieConsentState>(() => getCookieConsentState());

  useEffect(() => {
    const onChange = () => {
      setState(getCookieConsentState());
    };
    window.addEventListener(COOKIE_CONSENT_CHANGED_EVENT, onChange as EventListener);
    return () => window.removeEventListener(COOKIE_CONSENT_CHANGED_EVENT, onChange as EventListener);
  }, []);

  return state;
}

export default function CookieConsentBanner() {
  const t = useT();
  const consentState = useCookieConsentState();
  const [regionReady, setRegionReady] = useState(false);
  const [region, setRegion] = useState<ConsentRegionHint>('unknown');
  const [showGranular, setShowGranular] = useState(false);
  const [functional, setFunctional] = useState(false);
  const [analytics, setAnalytics] = useState(false);

  useEffect(() => {
    void fetchConsentRegion().then((r) => {
      setRegion(r);
      setShowGranular(prefersGranularConsentUi(r));
      const parsed = getParsedGranularConsent();
      if (parsed) {
        setFunctional(parsed.functional);
        setAnalytics(parsed.analytics);
      }
      setRegionReady(true);
    });
  }, []);

  if (consentState !== 'unknown' || !regionReady) return null;

  const onSaveGranular = () => {
    saveGranularConsent({ functional, analytics, marketing: false }, 'banner', region);
  };

  const switchToSimple = () => {
    setGranularUiPreference(false);
    setShowGranular(false);
  };

  const switchToGranular = () => {
    setGranularUiPreference(true);
    setShowGranular(true);
  };

  return (
    <aside
      className='cookie-consent-banner'
      role='dialog'
      aria-live='polite'
      aria-label={t('cookie.banner.aria')}
    >
      <p className='cookie-consent-banner__text'>{t('cookie.banner.body')}</p>

      {showGranular ? (
        <>
          <CookieConsentCategoriesForm
            idPrefix='banner'
            functional={functional}
            analytics={analytics}
            onChange={(patch) => {
              if (patch.functional !== undefined) setFunctional(patch.functional);
              if (patch.analytics !== undefined) setAnalytics(patch.analytics);
            }}
          />
          <div
            className={`cookie-consent-banner__actions cookie-consent-banner__actions--split${
              region === 'eu' ? ' cookie-consent-banner__actions--end' : ''
            }`}
          >
            {region !== 'eu' ? (
              <Button
                type='button'
                variant='ghost'
                size='sm'
                className='cookie-consent-banner__link'
                onClick={switchToSimple}
              >
                {t('cookie.banner.simpleChoice')}
              </Button>
            ) : null}
            <Button type='button' variant='secondary' size='sm' onClick={onSaveGranular}>
              {t('cookie.categories.save')}
            </Button>
          </div>
        </>
      ) : (
        <div className='cookie-consent-banner__actions cookie-consent-banner__actions--stack'>
          <div className='cookie-consent-banner__actions cookie-consent-banner__actions--row'>
            <Button type='button' variant='secondary' size='sm' onClick={() => saveCookieConsent('rejected', 'banner')}>
              {t('privacy.cookie.keepOff')}
            </Button>
            <Button type='button' variant='secondary' size='sm' onClick={() => saveCookieConsent('accepted', 'banner')}>
              {t('privacy.cookie.allow')}
            </Button>
          </div>
          <Button type='button' variant='ghost' size='sm' className='cookie-consent-banner__link' onClick={switchToGranular}>
            {t('cookie.banner.customize')}
          </Button>
        </div>
      )}
    </aside>
  );
}
