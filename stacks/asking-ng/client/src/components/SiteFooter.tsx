import { Link, useRouterState } from '@tanstack/react-router';
import { useT } from '../i18n/I18nContext';
import { parseAttributionUrl, parseSiteFooter } from '../lib/siteFooter';
import { Inline } from '../ui';

function isAdminPath(pathname: string): boolean {
  const b = String(import.meta.env.BASE_URL ?? '/');
  const normalized = b.endsWith('/') && b !== '/' ? b.slice(0, -1) : b.replace(/\/$/, '');
  if (!normalized || normalized === '/') return pathname.startsWith('/admin');
  return pathname.startsWith(`${normalized}/admin`);
}

/** Site-wide footer: default “Powered by” link, custom plain text, or hidden (see `VITE_SITE_FOOTER`). */
export default function SiteFooter() {
  const t = useT();
  const mode = parseSiteFooter();
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  if (isAdminPath(pathname)) return null;
  if (mode.kind === 'hidden') return null;

  if (mode.kind === 'custom') {
    return (
      <footer className='site-footer'>
        <p className='site-footer__text'>{mode.text}</p>
      </footer>
    );
  }

  const href = parseAttributionUrl();
  return (
    <footer className='site-footer'>
      <Inline gap='sm' wrap align='center' className='site-footer__text'>
        <span>{t('footer.poweredBy')}</span>
        <a className='site-footer__link' href={href} rel='noopener noreferrer' target='_blank'>
          {t('footer.brandName')}
        </a>
        <span aria-hidden>·</span>
        <Link className='site-footer__link' to='/privacy'>
          {t('footer.privacy')}
        </Link>
        <span aria-hidden>·</span>
        <Link className='site-footer__link' to='/terms'>
          {t('footer.terms')}
        </Link>
      </Inline>
    </footer>
  );
}
