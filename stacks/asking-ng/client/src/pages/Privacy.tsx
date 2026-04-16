import { Link } from '@tanstack/react-router';
import { useMemo } from 'react';
import { useDocumentTitle } from '../hooks/useDocumentTitle';
import { useT } from '../i18n/I18nContext';
import { configuredAnalyticsProviders, legalLastUpdated, securityContactEmail } from '../lib/legalSite';
import { Card, cx } from '../ui';

function trimEnv(key: keyof ImportMetaEnv): string {
  const raw = import.meta.env[key];
  return typeof raw === 'string' ? raw.trim() : '';
}

export default function Privacy() {
  const t = useT();
  useDocumentTitle(t('policy.docTitle'));

  const legalEmail = trimEnv('VITE_LEGAL_CONTACT_EMAIL');
  const legalUrl = trimEnv('VITE_LEGAL_CONTACT_URL');
  const lastUpdated = legalLastUpdated();
  const secEmail = securityContactEmail();
  const providers = useMemo(() => configuredAnalyticsProviders(), []);

  return (
    <article className='ui-page-shell site-public about-page'>
      <header className='ui-page-hero'>
        <h1 className='ui-page-hero-title'>{t('policy.title')}</h1>
        <p className='ui-page-hero-tagline about-page__intro'>{t('policy.lead')}</p>
        {lastUpdated ? (
          <p className='terms-disclaimer'>
            {t('policy.lastUpdated', { date: lastUpdated })}
          </p>
        ) : null}
      </header>

      <div className='about-page__panels'>
        <Card as='section' className='about-page__panel' padding='none'>
          <h2 className='ui-flow-heading'>{t('policy.section.summary.title')}</h2>
          <p>{t('policy.section.summary.body')}</p>
        </Card>

        <Card as='section' className='about-page__panel' padding='none'>
          <h2 className='ui-flow-heading'>{t('policy.section.collect.title')}</h2>
          <p>{t('policy.section.collect.body')}</p>
          <ul className='terms-list'>
            <li>{t('policy.section.collect.bulletAccount')}</li>
            <li>{t('policy.section.collect.bulletPoll')}</li>
            <li>{t('policy.section.collect.bulletVote')}</li>
            <li>{t('policy.section.collect.bulletTechnical')}</li>
          </ul>
        </Card>

        <Card as='section' className='about-page__panel' padding='none'>
          <h2 className='ui-flow-heading'>{t('policy.section.cookies.title')}</h2>
          <p>{t('policy.section.cookies.body')}</p>
          <p>
            <Link to='/settings'>{t('policy.section.cookies.settingsLink')}</Link>
          </p>
        </Card>

        <Card as='section' className='about-page__panel' padding='none'>
          <h2 className='ui-flow-heading'>{t('policy.section.subprocessors.title')}</h2>
          <p>{t('policy.section.subprocessors.intro')}</p>
          {providers.length === 0 ? (
            <p>{t('policy.section.subprocessors.none')}</p>
          ) : (
            <ul className='terms-list'>
              {providers.includes('umami') ? <li>{t('policy.section.subprocessors.umami')}</li> : null}
              {providers.includes('plausible') ? <li>{t('policy.section.subprocessors.plausible')}</li> : null}
              {providers.includes('matomo') ? <li>{t('policy.section.subprocessors.matomo')}</li> : null}
            </ul>
          )}
        </Card>

        <Card as='section' className='about-page__panel' padding='none'>
          <h2 className='ui-flow-heading'>{t('policy.section.webhooks.title')}</h2>
          <p>{t('policy.section.webhooks.body')}</p>
        </Card>

        <Card as='section' className='about-page__panel' padding='none'>
          <h2 className='ui-flow-heading'>{t('policy.section.llm.title')}</h2>
          <p>{t('policy.section.llm.body')}</p>
        </Card>

        <Card as='section' className='about-page__panel' padding='none'>
          <h2 className='ui-flow-heading'>{t('policy.section.retention.title')}</h2>
          <p>{t('policy.section.retention.body')}</p>
        </Card>

        <Card as='section' className='about-page__panel' padding='none'>
          <h2 className='ui-flow-heading'>{t('policy.section.rights.title')}</h2>
          <p>{t('policy.section.rights.body')}</p>
          <p>
            <Link to='/settings'>{t('policy.section.rights.settingsLink')}</Link>
          </p>
        </Card>

        <Card as='section' className='about-page__panel' padding='none'>
          <h2 className='ui-flow-heading'>{t('policy.section.status.title')}</h2>
          <p>{t('policy.section.status.body')}</p>
          <p>
            <Link to='/status'>{t('policy.section.status.link')}</Link>
          </p>
        </Card>

        <Card as='section' className='about-page__panel' padding='none'>
          <h2 className='ui-flow-heading'>{t('policy.section.contact.title')}</h2>
          <p>{t('policy.section.contact.intro')}</p>
          {secEmail ? (
            <p>
              <a className='site-footer__link' href={`mailto:${secEmail}`}>
                {t('policy.contact.securityEmail', { email: secEmail })}
              </a>
            </p>
          ) : null}
          {legalEmail || legalUrl ? (
            <p className='terms-contact-actions'>
              {legalEmail ? (
                <a className='site-footer__link' href={`mailto:${legalEmail}`}>
                  {t('terms.contact.emailCta', { email: legalEmail })}
                </a>
              ) : null}
              {legalEmail && legalUrl ? ' · ' : null}
              {legalUrl ? (
                <a className='site-footer__link' href={legalUrl} rel='noopener noreferrer' target='_blank'>
                  {t('terms.contact.urlCta')}
                </a>
              ) : null}
            </p>
          ) : null}
        </Card>

        <Card as='section' className='about-page__panel' padding='none'>
          <h2 className='ui-flow-heading'>{t('policy.section.legal.title')}</h2>
          <p>{t('policy.section.legal.body')}</p>
          <p>
            <Link to='/terms'>{t('policy.section.legal.termsLink')}</Link>
          </p>
        </Card>
      </div>

      <nav className='about-page__actions' aria-label={t('policy.nav.actions')}>
        <Link to='/' className={cx('ui-button', 'ui-button--md', 'ui-button--primary')}>
          {t('policy.cta.home')}
        </Link>
        <Link to='/terms' className={cx('ui-button', 'ui-button--md', 'ui-button--secondary')}>
          {t('policy.cta.terms')}
        </Link>
      </nav>
    </article>
  );
}
