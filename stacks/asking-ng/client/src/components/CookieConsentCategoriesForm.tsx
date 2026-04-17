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
    <div
      className='asking-cookie-categories'
      id={`${idPrefix}-group`}
      role='group'
      aria-label={t('cookie.categories.groupAria')}
    >
      <p className='asking-cookie-categories__intro'>{t('cookie.categories.intro')}</p>

      <div className='asking-cookie-categories__row'>
        <div className='asking-cookie-categories__label'>
          <span className='asking-cookie-categories__name'>{t('cookie.categories.necessary')}</span>
          <span className='asking-cookie-categories__hint'>
            {t('cookie.categories.necessaryHint')}
          </span>
        </div>
        <div className='asking-cookie-categories__switch'>
          <Switch id={`${p}-necessary`} checked disabled readOnly aria-readonly='true' />
          <VisuallyHidden as='label' htmlFor={`${p}-necessary`}>
            {t('cookie.categories.necessary')}
          </VisuallyHidden>
        </div>
      </div>

      <div className='asking-cookie-categories__row'>
        <div className='asking-cookie-categories__label'>
          <span className='asking-cookie-categories__name'>
            {t('cookie.categories.functional')}
          </span>
          <span className='asking-cookie-categories__hint'>
            {t('cookie.categories.functionalHint')}
          </span>
        </div>
        <div className='asking-cookie-categories__switch'>
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

      <div className='asking-cookie-categories__row'>
        <div className='asking-cookie-categories__label'>
          <span className='asking-cookie-categories__name'>{t('cookie.categories.analytics')}</span>
          <span className='asking-cookie-categories__hint'>
            {t('cookie.categories.analyticsHint')}
          </span>
        </div>
        <div className='asking-cookie-categories__switch'>
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

      <div className='asking-cookie-categories__row asking-cookie-categories__row--muted'>
        <div className='asking-cookie-categories__label'>
          <span className='asking-cookie-categories__name'>{t('cookie.categories.marketing')}</span>
          <span className='asking-cookie-categories__hint'>
            {t('cookie.categories.marketingOff')}
          </span>
        </div>
        <div className='asking-cookie-categories__switch'>
          <Switch id={`${p}-marketing`} checked={false} disabled readOnly />
          <VisuallyHidden as='label' htmlFor={`${p}-marketing`}>
            {t('cookie.categories.marketing')}
          </VisuallyHidden>
        </div>
      </div>
    </div>
  );
}
