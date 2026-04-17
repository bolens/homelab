import { Link, Outlet, useNavigate, useRouterState } from '@tanstack/react-router';
import React from 'react';
import { useAdmin } from '../context/AdminContext';
import { useT } from '../i18n/I18nContext';
import { clearStoredUserJwt } from '../lib/userSession';
import { Button, cx } from '../ui';
import {
  IconActivity,
  IconBarChart,
  IconCircleUser,
  IconDownload,
  IconFileText,
  IconHouse,
  IconLayoutDashboard,
  IconLogOut,
  IconUsers,
} from './icons/UiIcons';

function sidenavActive(pathname: string, to: string, exact: boolean): boolean {
  if (exact) {
    return pathname === to || (to === '/admin' && pathname === '/admin/');
  }
  return pathname === to || pathname.startsWith(`${to}/`);
}

function AdminSidenavLink({
  to,
  search,
  children,
  pathname,
  exact = false,
  icon,
}: {
  to: string;
  search?: Record<string, undefined>;
  children: React.ReactNode;
  pathname: string;
  exact?: boolean;
  icon?: React.ReactNode;
}) {
  const current = sidenavActive(pathname, to, exact);
  return (
    <Link
      to={to}
      {...(search ? { search } : {})}
      // Router default is prefix match; `/admin` would otherwise stay "active" on every child route.
      {...(exact ? { activeOptions: { exact: true } } : {})}
      className='asking-admin-app__sidenav-link'
      aria-current={current ? 'page' : undefined}
    >
      {icon ? <span className='asking-admin-app__sidenav-icon'>{icon}</span> : null}
      {children}
    </Link>
  );
}

export default function AdminLayout() {
  const t = useT();
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const { admin, setAdmin } = useAdmin();
  const navigate = useNavigate();

  const isLogin = pathname.includes('/admin/login');

  const handleLogout = () => {
    localStorage.removeItem('adminToken');
    clearStoredUserJwt();
    setAdmin(null);
    navigate({ to: '/admin/login' });
  };

  if (isLogin) {
    return (
      <main id='asking-admin-app__main' aria-label={t('admin.chrome.mainAria')}>
        <Outlet />
      </main>
    );
  }

  return (
    <div className='asking-admin-app'>
      <aside
        className='asking-admin-app__sidebar'
        id='asking-admin-app__sidebar'
        aria-label={t('admin.chrome.sidebarAria')}
      >
        <div className='asking-admin-app__brand'>
          <Link to='/admin' className='asking-admin-app__brand-link'>
            {t('admin.chrome.brandShort')}
          </Link>
        </div>
        <nav
          className='asking-admin-app__sidenav'
          id='asking-admin-app__sidenav'
          aria-label={t('admin.chrome.navAria')}
        >
          <div className='asking-admin-app__nav-group'>
            <div className='asking-admin-app__nav-group-label'>
              {t('admin.chrome.nav.group.overview')}
            </div>
            <AdminSidenavLink
              to='/admin'
              pathname={pathname}
              exact
              icon={<IconLayoutDashboard aria-hidden />}
            >
              {t('admin.chrome.dashboard')}
            </AdminSidenavLink>
          </div>
          <div className='asking-admin-app__nav-group'>
            <div className='asking-admin-app__nav-group-label'>
              {t('admin.chrome.nav.group.operations')}
            </div>
            {admin?.role === 'admin' || admin?.role === 'superadmin' ? (
              <AdminSidenavLink
                to='/admin/users'
                pathname={pathname}
                icon={<IconUsers aria-hidden />}
              >
                {t('admin.dashboard.users')}
              </AdminSidenavLink>
            ) : null}
            <AdminSidenavLink
              to='/admin/polls'
              pathname={pathname}
              icon={<IconBarChart aria-hidden />}
            >
              {t('admin.dashboard.polls')}
            </AdminSidenavLink>
          </div>
          <div className='asking-admin-app__nav-group'>
            <div className='asking-admin-app__nav-group-label'>
              {t('admin.chrome.nav.group.compliance')}
            </div>
            <AdminSidenavLink
              to='/admin/audit-logs'
              search={{ limit: undefined }}
              pathname={pathname}
              icon={<IconFileText aria-hidden />}
            >
              {t('admin.dashboard.audit')}
            </AdminSidenavLink>
            {admin?.role === 'admin' || admin?.role === 'superadmin' ? (
              <AdminSidenavLink
                to='/admin/export'
                pathname={pathname}
                icon={<IconDownload aria-hidden />}
              >
                {t('admin.dashboard.export')}
              </AdminSidenavLink>
            ) : null}
          </div>
          <div className='asking-admin-app__nav-group'>
            <div className='asking-admin-app__nav-group-label'>
              {t('admin.chrome.nav.group.system')}
            </div>
            <AdminSidenavLink
              to='/admin/status'
              pathname={pathname}
              icon={<IconActivity aria-hidden />}
            >
              {t('admin.dashboard.status')}
            </AdminSidenavLink>
            {admin?.role === 'superadmin' ? (
              <AdminSidenavLink
                to='/admin/impersonate'
                pathname={pathname}
                icon={<IconCircleUser aria-hidden />}
              >
                {t('admin.dashboard.impersonate')}
              </AdminSidenavLink>
            ) : null}
          </div>
        </nav>
        <div className='asking-admin-app__sidebar-footer'>
          <Link
            to='/'
            className='asking-admin-app__sidenav-link asking-admin-app__sidenav-link--footer'
          >
            <span className='asking-admin-app__sidenav-icon' aria-hidden>
              <IconHouse />
            </span>
            {t('admin.chrome.public')}
          </Link>
          <Button
            type='button'
            variant='ghost'
            className={cx('asking-admin-page__btn', 'asking-admin-app__logout')}
            onClick={handleLogout}
          >
            <IconLogOut aria-hidden />
            {t('admin.chrome.logout')}
          </Button>
        </div>
      </aside>
      <div className='asking-admin-app__stage'>
        <main
          id='asking-admin-app__main'
          className='asking-admin-app__content'
          aria-label={t('admin.chrome.mainAria')}
        >
          <Outlet />
        </main>
      </div>
    </div>
  );
}
