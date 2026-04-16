import { useId } from 'react';
import { useT } from '../i18n/I18nContext';
import { Switch, VisuallyHidden } from '../ui';

export type CookieConsentCategoriesFormProps = {
  functional: boolean;
  analytics: boolean;
  onChange: (patch: Partial<{ functional: boolean; analytics: boolean }>) => void;
  /** Prefix for stable input ids (banner vs settings). */
  idPrefix: string;
};

export default function CookieConsentCategoriesForm({
  functional,
  analytics,
  onChange,
  idPrefix,
}: CookieConsentCategoriesFormProps) {
  const t = useT();
  const reactId = useId();
  const p = `${idPrefix}-${reactId.replace(/:/g, '')}`;

  return (
    <div className='cookie-consent-categories' role='group' aria-label={t('cookie.categories.groupAria')}>
      <p className='cookie-consent-categories__intro'>{t('cookie.categories.intro')}</p>

      <div className='cookie-consent-categories__row'>
        <div className='cookie-consent-categories__label'>
          <span className='cookie-consent-categories__name'>{t('cookie.categories.necessary')}</span>
          <span className='cookie-consent-categories__hint'>{t('cookie.categories.necessaryHint')}</span>
        </div>
        <div className='cookie-consent-categories__switch'>
          <Switch id={`${p}-necessary`} checked disabled readOnly aria-readonly='true' />
          <VisuallyHidden as='label' htmlFor={`${p}-necessary`}>
            {t('cookie.categories.necessary')}
          </VisuallyHidden>
        </div>
      </div>

      <div className='cookie-consent-categories__row'>
        <div className='cookie-consent-categories__label'>
          <span className='cookie-consent-categories__name'>{t('cookie.categories.functional')}</span>
          <span className='cookie-consent-categories__hint'>{t('cookie.categories.functionalHint')}</span>
        </div>
        <div className='cookie-consent-categories__switch'>
          <Switch
            id={`${p}-functional`}
            checked={functional}
            onChange={(e) => onChange({ functional: e.target.checked })}
          />
          <VisuallyHidden as='label' htmlFor={`${p}-functional`}>
            {t('cookie.categories.functional')}
          </VisuallyHidden>
        </div>
      </div>

      <div className='cookie-consent-categories__row'>
        <div className='cookie-consent-categories__label'>
          <span className='cookie-consent-categories__name'>{t('cookie.categories.analytics')}</span>
          <span className='cookie-consent-categories__hint'>{t('cookie.categories.analyticsHint')}</span>
        </div>
        <div className='cookie-consent-categories__switch'>
          <Switch
            id={`${p}-analytics`}
            checked={analytics}
            onChange={(e) => onChange({ analytics: e.target.checked })}
          />
          <VisuallyHidden as='label' htmlFor={`${p}-analytics`}>
            {t('cookie.categories.analytics')}
          </VisuallyHidden>
        </div>
      </div>

      <div className='cookie-consent-categories__row cookie-consent-categories__row--muted'>
        <div className='cookie-consent-categories__label'>
          <span className='cookie-consent-categories__name'>{t('cookie.categories.marketing')}</span>
          <span className='cookie-consent-categories__hint'>{t('cookie.categories.marketingOff')}</span>
        </div>
        <div className='cookie-consent-categories__switch'>
          <Switch id={`${p}-marketing`} checked={false} disabled readOnly />
          <VisuallyHidden as='label' htmlFor={`${p}-marketing`}>
            {t('cookie.categories.marketing')}
          </VisuallyHidden>
        </div>
      </div>
    </div>
  );
}
