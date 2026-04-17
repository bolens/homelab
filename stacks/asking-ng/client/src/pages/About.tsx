import { Link } from '@tanstack/react-router';
import { useDocumentTitle } from '../hooks/useDocumentTitle';
import { useT } from '../i18n/I18nContext';
import { Card, cx } from '../ui';

export default function About() {
  const t = useT();
  useDocumentTitle(t('about.docTitle'));
  return (
    <article
      className='ui-page-shell asking-public-layout asking-about-page'
      id='asking-about-page'
    >
      <header className='ui-page-hero'>
        <h1 className='ui-page-hero-title' id='asking-about-page__title'>
          {t('about.title')}
        </h1>
        <p className='ui-page-hero-tagline asking-about-page__intro'>
          {t('about.p1')}{' '}
          <a href='https://github.com/jdleo/asking' target='_blank' rel='noopener noreferrer'>
            {t('about.p1.link')}
          </a>
          .
        </p>
      </header>

      <div className='asking-about-page__panels'>
        <Card
          as='section'
          className={cx('asking-about-page__panel', 'ui-card--form-panel')}
          padding='none'
          aria-labelledby='asking-about-page__stack-heading'
        >
          <h2 id='asking-about-page__stack-heading' className='ui-flow-heading'>
            {t('about.section.stack')}
          </h2>
          <ul className='asking-about-page__feature-list'>
            <li>{t('about.bullet.api')}</li>
            <li>{t('about.bullet.llm')}</li>
            <li>{t('about.bullet.admin')}</li>
            <li>{t('about.bullet.caddy')}</li>
          </ul>
        </Card>

        <Card
          as='section'
          className={cx(
            'asking-about-page__panel',
            'asking-about-page__panel--a11y',
            'ui-card--form-panel',
          )}
          padding='none'
          aria-labelledby='asking-about-page__a11y-heading'
        >
          <h2 id='asking-about-page__a11y-heading' className='ui-flow-heading'>
            {t('about.section.a11y')}
          </h2>
          <p className='asking-about-page__a11y-body'>{t('about.accessibility')}</p>
        </Card>
      </div>

      <nav
        className='asking-about-page__actions'
        id='asking-about-page__actions'
        aria-label={t('about.nav.actions')}
      >
        <Link to='/' className={cx('ui-button', 'ui-button--md', 'ui-button--primary')}>
          {t('about.cta.create')}
        </Link>
        <Link to='/developer' className={cx('ui-button', 'ui-button--md', 'ui-button--secondary')}>
          {t('about.cta.dev')}
        </Link>
      </nav>
    </article>
  );
}
