import { Link, useNavigate } from '@tanstack/react-router';
import { useCallback, useEffect, useRef, useState } from 'react';
import { useRelativeLocationPath } from '../helpers/routerPath';
import { useBootstrapNavDark } from '../hooks/useBootstrapNavDark';
import { useNavbarAuth } from '../hooks/useNavbarAuth';
import { useT } from '../i18n/I18nContext';
import { clearStoredUserJwt } from '../lib/userSession';
import { cx, VisuallyHidden } from '../ui';
import { IconListPolls, IconSignOut } from './icons/UiIcons';
import UserSettingsModal from './UserSettingsModal';

function navRouteActive(active: boolean): string {
  return active ? 'asking-app-navbar__route--active' : '';
}

function GitHubMarkIcon() {
  return (
    <svg
      className='asking-app-navbar__icon'
      width={20}
      height={20}
      viewBox='0 0 24 24'
      fill='currentColor'
      xmlns='http://www.w3.org/2000/svg'
      aria-hidden
    >
      <path d='M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.113.825-.258.825-.577 0-.285-.01-1.04-.015-2.04-3.338.724-4.042-1.61-4.042-1.61C4.422 18.07 3.633 17.7 3.633 17.7c-1.087-.744.084-.729.084-.729 1.205.084 1.838 1.236 1.838 1.236 1.07 1.835 2.809 1.305 3.495.998.108-.775.417-1.305.76-1.605-2.665-.3-5.466-1.332-5.466-5.93 0-1.31.465-2.38 1.235-3.22-.135-.303-.54-1.523.105-3.176 0 0 1.005-.322 3.3 1.23.96-.267 1.98-.399 3-.405 1.02.006 2.04.138 3 .405 2.28-1.552 3.285-1.23 3.285-1.23.645 1.653.24 2.873.12 3.176.765.84 1.23 1.91 1.23 3.22 0 4.61-2.805 5.625-5.475 5.92.42.36.81 1.096.81 2.22 0 1.606-.015 2.896-.015 3.286 0 .315.21.69.825.57C20.565 21.795 24 17.295 24 12c0-6.63-5.37-12-12-12z' />
    </svg>
  );
}

function SettingsGearIcon() {
  return (
    <svg
      className='asking-app-navbar__icon'
      width={20}
      height={20}
      viewBox='0 0 24 24'
      fill='none'
      xmlns='http://www.w3.org/2000/svg'
      aria-hidden
    >
      <path
        d='M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z'
        stroke='currentColor'
        strokeWidth='2'
        strokeLinecap='round'
        strokeLinejoin='round'
      />
      <path
        d='M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1Z'
        stroke='currentColor'
        strokeWidth='2'
        strokeLinecap='round'
        strokeLinejoin='round'
      />
    </svg>
  );
}

export default function NavbarWrapper() {
  const navigate = useNavigate();
  const t = useT();
  const navDark = useBootstrapNavDark();
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [navExpanded, setNavExpanded] = useState(false);
  const [moreOpen, setMoreOpen] = useState(false);
  const [accountOpen, setAccountOpen] = useState(false);
  const { userJwtPresent, admin, noAdminExists } = useNavbarAuth();

  const moreRef = useRef<HTMLDivElement>(null);
  const accountRef = useRef<HTMLDivElement>(null);

  const closeNav = useCallback(() => {
    setNavExpanded(false);
    setMoreOpen(false);
    setAccountOpen(false);
  }, []);

  useEffect(() => {
    if (!moreOpen && !accountOpen) return;
    const onPointerDown = (e: MouseEvent | PointerEvent) => {
      const node = e.target as Node | null;
      if (!node) return;
      if (moreOpen && moreRef.current && !moreRef.current.contains(node)) setMoreOpen(false);
      if (accountOpen && accountRef.current && !accountRef.current.contains(node))
        setAccountOpen(false);
    };
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setMoreOpen(false);
        setAccountOpen(false);
      }
    };
    document.addEventListener('mousedown', onPointerDown);
    document.addEventListener('keydown', onKeyDown);
    return () => {
      document.removeEventListener('mousedown', onPointerDown);
      document.removeEventListener('keydown', onKeyDown);
    };
  }, [moreOpen, accountOpen]);

  const p = useRelativeLocationPath();
  const isHome = p === '/';
  const isAbout = p === '/about';
  const isDeveloper = p === '/developer';
  const isTerms = p === '/terms';
  const isPrivacy = p === '/privacy';
  const isMyPolls = p === '/my-polls';
  const isLogin = p === '/login';
  const isRegister = p === '/register';
  const isAdmin = p.startsWith('/admin');
  const isSettings = p === '/settings';
  const moreActive = isAbout || isDeveloper || isTerms || isPrivacy;

  const handleUserSignOut = () => {
    clearStoredUserJwt();
    closeNav();
    if (p === '/my-polls') {
      void navigate({ to: '/' });
    }
  };

  const brand = import.meta.env.VITE_APP_NAME || t('nav.brandFallback');

  const navCollapseId = 'asking-app-navbar__drawer';

  const showAdminLink = admin != null || noAdminExists;
  const adminNavTo = admin != null ? '/admin' : '/admin/login';
  const adminNavLabel = admin != null ? t('nav.admin') : t('nav.adminLogin');
  const adminSignedInFull =
    admin != null ? t('nav.adminSignedIn', { user: admin.homelab-user }) : undefined;

  const openSettings = () => {
    setSettingsOpen(true);
    closeNav();
  };

  const navBarClass = cx(
    'asking-app-navbar',
    'asking-app-navbar__main',
    'asking-app-navbar--surface',
    navDark ? 'asking-app-navbar--dark' : 'asking-app-navbar--light',
  );

  return (
    <>
      <UserSettingsModal show={settingsOpen} onHide={() => setSettingsOpen(false)} />
      <nav className={navBarClass} id='asking-app-navbar'>
        <Link
          to='/'
          className={
            isHome
              ? 'asking-app-navbar__brand asking-app-navbar__brand-text asking-app-navbar__brand--active'
              : 'asking-app-navbar__brand asking-app-navbar__brand-text'
          }
          aria-current={isHome ? 'page' : undefined}
          onClick={closeNav}
        >
          {brand}
        </Link>
        <button
          type='button'
          className='asking-app-navbar__toggler'
          aria-controls={navCollapseId}
          aria-expanded={navExpanded}
          aria-label={t('nav.menuToggle')}
          onClick={() => setNavExpanded((v) => !v)}
        >
          <span className='asking-app-navbar__toggler-icon' />
        </button>
        <div
          id={navCollapseId}
          className={cx(
            'asking-app-navbar__collapse',
            'asking-app-navbar__links',
            navExpanded && 'asking-app-navbar__collapse--open',
          )}
        >
          <div className='asking-app-navbar__cluster'>
            <div ref={moreRef} className='asking-app-navbar__dropdown'>
              <button
                type='button'
                id='asking-app-navbar__more-trigger'
                className={cx(
                  'asking-app-navbar__link',
                  'asking-app-navbar__link--caret',
                  navRouteActive(moreActive),
                )}
                aria-expanded={moreOpen}
                aria-haspopup='menu'
                onClick={() => {
                  setAccountOpen(false);
                  setMoreOpen((o) => !o);
                }}
              >
                {t('nav.more')}
              </button>
              {moreOpen ? (
                <ul
                  className={cx(
                    'asking-app-navbar__menu',
                    'asking-app-navbar__menu--end',
                    navDark && 'asking-app-navbar__menu--dark',
                    'asking-app-navbar__menu--open',
                  )}
                  role='menu'
                  aria-labelledby='asking-app-navbar__more-trigger'
                >
                  <li role='none'>
                    <Link
                      role='menuitem'
                      to='/about'
                      id='asking-app-navbar__about-link'
                      className={cx(
                        'asking-app-navbar__menu-item',
                        isAbout && 'asking-app-navbar__menu-item--active',
                      )}
                      aria-current={isAbout ? 'page' : undefined}
                      onClick={closeNav}
                    >
                      {t('nav.about')}
                    </Link>
                  </li>
                  <li role='none'>
                    <Link
                      role='menuitem'
                      to='/developer'
                      className={cx(
                        'asking-app-navbar__menu-item',
                        isDeveloper && 'asking-app-navbar__menu-item--active',
                      )}
                      aria-current={isDeveloper ? 'page' : undefined}
                      onClick={closeNav}
                    >
                      {t('nav.developer')}
                    </Link>
                  </li>
                  <li role='none'>
                    <Link
                      role='menuitem'
                      to='/privacy'
                      className={cx(
                        'asking-app-navbar__menu-item',
                        isPrivacy && 'asking-app-navbar__menu-item--active',
                      )}
                      aria-current={isPrivacy ? 'page' : undefined}
                      onClick={closeNav}
                    >
                      {t('nav.privacy')}
                    </Link>
                  </li>
                  <li role='none'>
                    <Link
                      role='menuitem'
                      to='/terms'
                      className={cx(
                        'asking-app-navbar__menu-item',
                        isTerms && 'asking-app-navbar__menu-item--active',
                      )}
                      aria-current={isTerms ? 'page' : undefined}
                      onClick={closeNav}
                    >
                      {t('nav.terms')}
                    </Link>
                  </li>
                  <li role='none'>
                    <a
                      role='menuitem'
                      className='asking-app-navbar__menu-item'
                      href='https://github.com/homelab-user/asking-ng'
                      target='_blank'
                      rel='noopener noreferrer'
                      onClick={closeNav}
                      aria-label={t('nav.githubRepo')}
                    >
                      <span className='ui-nav-menu-row'>
                        <GitHubMarkIcon />
                        {t('nav.github')}
                      </span>
                    </a>
                  </li>
                </ul>
              ) : null}
            </div>
            {userJwtPresent ? (
              <div ref={accountRef} className='asking-app-navbar__dropdown'>
                <button
                  type='button'
                  id='asking-app-navbar__account-trigger'
                  className={cx(
                    'asking-app-navbar__link',
                    'asking-app-navbar__link--caret',
                    navRouteActive(isMyPolls),
                  )}
                  aria-expanded={accountOpen}
                  aria-haspopup='menu'
                  aria-label={t('nav.accountMenu')}
                  onClick={() => {
                    setMoreOpen(false);
                    setAccountOpen((o) => !o);
                  }}
                >
                  {t('nav.account')}
                </button>
                {accountOpen ? (
                  <ul
                    className={cx(
                      'asking-app-navbar__menu',
                      'asking-app-navbar__menu--end',
                      navDark && 'asking-app-navbar__menu--dark',
                      'asking-app-navbar__menu--open',
                    )}
                    role='menu'
                    aria-labelledby='asking-app-navbar__account-trigger'
                  >
                    <li role='none'>
                      <Link
                        role='menuitem'
                        to='/my-polls'
                        className={cx(
                          'asking-app-navbar__menu-item',
                          isMyPolls && 'asking-app-navbar__menu-item--active',
                        )}
                        aria-current={isMyPolls ? 'page' : undefined}
                        onClick={closeNav}
                      >
                        <span className='ui-nav-menu-row'>
                          <IconListPolls className='asking-app-navbar__icon' aria-hidden />
                          {t('nav.myPolls')}
                        </span>
                      </Link>
                    </li>
                    <li role='none'>
                      <button
                        type='button'
                        role='menuitem'
                        className='asking-app-navbar__menu-item'
                        onClick={() => {
                          handleUserSignOut();
                        }}
                      >
                        <span className='ui-nav-menu-row'>
                          <IconSignOut className='asking-app-navbar__icon' aria-hidden />
                          {t('nav.signOut')}
                        </span>
                      </button>
                    </li>
                  </ul>
                ) : null}
              </div>
            ) : (
              <Link
                to='/login'
                className={cx('asking-app-navbar__link', navRouteActive(isLogin || isRegister))}
                aria-current={isLogin || isRegister ? 'page' : undefined}
                onClick={closeNav}
              >
                {t('nav.signIn')}
              </Link>
            )}
            {showAdminLink ? (
              <Link
                to={adminNavTo}
                className={cx('asking-app-navbar__link', navRouteActive(isAdmin))}
                aria-current={isAdmin ? 'page' : undefined}
                title={admin != null ? adminSignedInFull : undefined}
                aria-label={admin != null ? adminSignedInFull : undefined}
                onClick={closeNav}
              >
                {adminNavLabel}
              </Link>
            ) : null}
            <button
              type='button'
              className={cx(
                'asking-app-navbar__link',
                'asking-app-navbar__settings-slot',
                'asking-app-navbar__settings-trigger',
                navRouteActive(isSettings || settingsOpen),
              )}
              onClick={openSettings}
              aria-haspopup='dialog'
              aria-expanded={settingsOpen}
            >
              <VisuallyHidden>{t('nav.settings')}</VisuallyHidden>
              <SettingsGearIcon />
              <span className='asking-app-navbar__settings-caption' aria-hidden>
                {t('nav.settings')}
              </span>
            </button>
          </div>
        </div>
      </nav>
    </>
  );
}
