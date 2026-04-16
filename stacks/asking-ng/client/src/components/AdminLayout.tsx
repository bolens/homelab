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
      className='admin-app-sidenav-link'
      aria-current={current ? 'page' : undefined}
    >
      {icon ? <span className='admin-app-sidenav-icon'>{icon}</span> : null}
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
      <main id='admin-main' aria-label={t('admin.chrome.mainAria')}>
        <Outlet />
      </main>
    );
  }

  return (
    <div className='admin-app'>
      <aside className='admin-app-sidebar' aria-label={t('admin.chrome.sidebarAria')}>
        <div className='admin-app-brand'>
          <Link to='/admin' className='admin-app-brand-link'>
            {t('admin.chrome.brandShort')}
          </Link>
        </div>
        <nav className='admin-app-sidenav' aria-label={t('admin.chrome.navAria')}>
          <div className='admin-app-nav-group'>
            <div className='admin-app-nav-group-label'>{t('admin.chrome.nav.group.overview')}</div>
            <AdminSidenavLink
              to='/admin'
              pathname={pathname}
              exact
              icon={<IconLayoutDashboard aria-hidden />}
            >
              {t('admin.chrome.dashboard')}
            </AdminSidenavLink>
          </div>
          <div className='admin-app-nav-group'>
            <div className='admin-app-nav-group-label'>
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
          <div className='admin-app-nav-group'>
            <div className='admin-app-nav-group-label'>
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
          <div className='admin-app-nav-group'>
            <div className='admin-app-nav-group-label'>{t('admin.chrome.nav.group.system')}</div>
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
        <div className='admin-app-sidebar-footer'>
          <Link to='/' className='admin-app-sidenav-link admin-app-sidenav-link--footer'>
            <span className='admin-app-sidenav-icon' aria-hidden>
              <IconHouse />
            </span>
            {t('admin.chrome.public')}
          </Link>
          <Button
            type='button'
            variant='ghost'
            className={cx('admin-users-btn', 'admin-app-logout')}
            onClick={handleLogout}
          >
            <IconLogOut aria-hidden />
            {t('admin.chrome.logout')}
          </Button>
        </div>
      </aside>
      <div className='admin-app-stage'>
        <main id='admin-main' className='admin-app-content' aria-label={t('admin.chrome.mainAria')}>
          <Outlet />
        </main>
      </div>
    </div>
  );
}
