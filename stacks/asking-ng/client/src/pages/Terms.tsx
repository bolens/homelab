import { Link } from '@tanstack/react-router';
import { useMemo } from 'react';
import { useDocumentTitle } from '../hooks/useDocumentTitle';
import { useT } from '../i18n/I18nContext';
import { legalLastUpdated } from '../lib/legalSite';
import { Card, cx } from '../ui';

function trimEnv(key: keyof ImportMetaEnv): string {
  const raw = import.meta.env[key];
  return typeof raw === 'string' ? raw.trim() : '';
}

export default function Terms() {
  const t = useT();
  useDocumentTitle(t('terms.docTitle'));

  const legalEmail = trimEnv('VITE_LEGAL_CONTACT_EMAIL');
  const legalUrl = trimEnv('VITE_LEGAL_CONTACT_URL');
  const jurisdiction = trimEnv('VITE_LEGAL_JURISDICTION');
  const lastUpdated = legalLastUpdated();

  const lawBody = useMemo(
    () =>
      t('terms.section.law.body', {
        jurisdiction: jurisdiction || t('terms.law.jurisdictionFallback'),
      }),
    [jurisdiction, t],
  );

  return (
    <article className='ui-page-shell site-public about-page'>
      <header className='ui-page-hero'>
        <h1 className='ui-page-hero-title'>{t('terms.title')}</h1>
        <p className='ui-page-hero-tagline about-page__intro'>{t('terms.lead')}</p>
        <p className='terms-disclaimer'>{t('terms.notLegalAdvice')}</p>
        {lastUpdated ? (
          <p className='terms-disclaimer'>{t('terms.lastUpdated', { date: lastUpdated })}</p>
        ) : null}
      </header>

      <div className='about-page__panels'>
        <Card as='section' className='about-page__panel' padding='none'>
          <h2 className='ui-flow-heading'>{t('terms.section.contact.title')}</h2>
          <p>{t('terms.section.contact.intro')}</p>
          <ul className='terms-list'>
            <li>{t('terms.section.contact.bulletAbuse')}</li>
            <li>{t('terms.section.contact.bulletCopyright')}</li>
            <li>{t('terms.section.contact.bulletPrivacy')}</li>
          </ul>
          {legalEmail || legalUrl ? (
            <p className='terms-contact-actions'>
              {legalEmail ? (
                <>
                  <a className='site-footer__link' href={`mailto:${legalEmail}`}>
                    {t('terms.contact.emailCta', { email: legalEmail })}
                  </a>
                  {legalUrl ? ' · ' : null}
                </>
              ) : null}
              {legalUrl ? (
                <a className='site-footer__link' href={legalUrl} rel='noopener noreferrer' target='_blank'>
                  {t('terms.contact.urlCta')}
                </a>
              ) : null}
            </p>
          ) : (
            <p className='terms-contact-placeholder'>{t('terms.contact.configureHint')}</p>
          )}
        </Card>

        <Card as='section' className='about-page__panel' padding='none'>
          <h2 className='ui-flow-heading'>{t('terms.section.eligibility.title')}</h2>
          <p>{t('terms.section.eligibility.body')}</p>
        </Card>

        <Card as='section' className='about-page__panel' padding='none'>
          <h2 className='ui-flow-heading'>{t('terms.section.use.title')}</h2>
          <p>{t('terms.section.use.body')}</p>
        </Card>

        <Card as='section' className='about-page__panel' padding='none'>
          <h2 className='ui-flow-heading'>{t('terms.section.api.title')}</h2>
          <p>{t('terms.section.api.body')}</p>
        </Card>

        <Card as='section' className='about-page__panel' padding='none'>
          <h2 className='ui-flow-heading'>{t('terms.section.content.title')}</h2>
          <p>{t('terms.section.content.body')}</p>
        </Card>

        <Card as='section' className='about-page__panel' padding='none'>
          <h2 className='ui-flow-heading'>{t('terms.section.ip.title')}</h2>
          <p>{t('terms.section.ip.body')}</p>
        </Card>

        <Card as='section' className='about-page__panel' padding='none'>
          <h2 className='ui-flow-heading'>{t('terms.section.dmca.title')}</h2>
          <p>{t('terms.section.dmca.body')}</p>
          <ol className='terms-ordered-list'>
            <li>{t('terms.section.dmca.step1')}</li>
            <li>{t('terms.section.dmca.step2')}</li>
            <li>{t('terms.section.dmca.step3')}</li>
            <li>{t('terms.section.dmca.step4')}</li>
          </ol>
          <p>{t('terms.section.dmca.footer')}</p>
        </Card>

        <Card as='section' className='about-page__panel' padding='none'>
          <h2 className='ui-flow-heading'>{t('terms.section.accounts.title')}</h2>
          <p>{t('terms.section.accounts.body')}</p>
        </Card>

        <Card as='section' className='about-page__panel' padding='none'>
          <h2 className='ui-flow-heading'>{t('terms.section.privacy.title')}</h2>
          <p>{t('terms.section.privacy.body')}</p>
        </Card>

        <Card as='section' className='about-page__panel' padding='none'>
          <h2 className='ui-flow-heading'>{t('terms.section.availability.title')}</h2>
          <p>{t('terms.section.availability.body')}</p>
        </Card>

        <Card as='section' className='about-page__panel' padding='none'>
          <h2 className='ui-flow-heading'>{t('terms.section.indemnity.title')}</h2>
          <p>{t('terms.section.indemnity.body')}</p>
        </Card>

        <Card as='section' className='about-page__panel' padding='none'>
          <h2 className='ui-flow-heading'>{t('terms.section.liability.title')}</h2>
          <p>{t('terms.section.liability.body')}</p>
        </Card>

        <Card as='section' className='about-page__panel' padding='none'>
          <h2 className='ui-flow-heading'>{t('terms.section.law.title')}</h2>
          <p>{lawBody}</p>
        </Card>

        <Card as='section' className='about-page__panel' padding='none'>
          <h2 className='ui-flow-heading'>{t('terms.section.changes.title')}</h2>
          <p>{t('terms.section.changes.body')}</p>
        </Card>

        <Card as='section' className='about-page__panel' padding='none'>
          <h2 className='ui-flow-heading'>{t('terms.section.misc.title')}</h2>
          <p>{t('terms.section.misc.body')}</p>
        </Card>
      </div>

      <nav className='about-page__actions' aria-label={t('terms.nav.actions')}>
        <Link to='/' className={cx('ui-button', 'ui-button--md', 'ui-button--primary')}>
          {t('terms.cta.home')}
        </Link>
        <Link to='/privacy' className={cx('ui-button', 'ui-button--md', 'ui-button--secondary')}>
          {t('terms.cta.policy')}
        </Link>
        <Link to='/settings' className={cx('ui-button', 'ui-button--md', 'ui-button--secondary')}>
          {t('terms.cta.privacy')}
        </Link>
      </nav>
    </article>
  );
}
