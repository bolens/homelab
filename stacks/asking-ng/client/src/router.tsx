import { parseAuditLogsSearch } from '@asking-ng/contracts/audit-logs';
import {
  createRootRoute,
  createRoute,
  createRouter,
  Link,
  lazyRouteComponent,
  Outlet,
  RouterProvider,
  redirect,
} from '@tanstack/react-router';
import React from 'react';
import AdminLayout from './components/AdminLayout';
import CookieConsentBanner from './components/CookieConsentBanner';
import Navbar from './components/Navbar';
import NetworkStatusBanner from './components/NetworkStatusBanner';
import SiteFooter from './components/SiteFooter';
import { apiFetch, isApiFetchError } from './http';
import { useT, useUILocale } from './i18n/I18nContext';
import { hasAdminRouteCredential } from './lib/jwtRole';
import { parsePollSearch } from './lib/pollRouteSearch';
import About from './pages/About';
import Home from './pages/Home';
import Poll from './pages/Poll';

const Developer = lazyRouteComponent(() => import('./pages/Developer'));
const Login = lazyRouteComponent(() => import('./pages/Login'));
const Register = lazyRouteComponent(() => import('./pages/Register'));
const MyPolls = lazyRouteComponent(() => import('./pages/MyPolls'));
const PollResults = lazyRouteComponent(() => import('./pages/PollResults'));
const Settings = lazyRouteComponent(() => import('./pages/Settings'));
const Terms = lazyRouteComponent(() => import('./pages/Terms'));
const Privacy = lazyRouteComponent(() => import('./pages/Privacy'));
const PublicStatus = lazyRouteComponent(() => import('./pages/PublicStatus'));
const AdminLogin = lazyRouteComponent(() => import('./pages/AdminLogin'));
const AdminDashboard = lazyRouteComponent(() => import('./pages/AdminDashboard'));
const AdminUsers = lazyRouteComponent(() => import('./pages/AdminUsers'));
const AdminPolls = lazyRouteComponent(() => import('./pages/AdminPolls'));
const AdminAuditLogs = lazyRouteComponent(() => import('./pages/AdminAuditLogs'));
const AdminExport = lazyRouteComponent(() => import('./pages/AdminExport'));
const AdminStatus = lazyRouteComponent(() => import('./pages/AdminStatus'));
const AdminImpersonate = lazyRouteComponent(() => import('./pages/AdminImpersonate'));
const AdminSetup = lazyRouteComponent(() => import('./pages/AdminSetup'));

function requireAdmin() {
  if (!hasAdminRouteCredential()) {
    throw redirect({ to: '/admin/login' });
  }
}

const reservedTopLevelPaths = new Set([
  'api-docs',
  'healthcheck',
  'ready',
  'info',
  'poll',
  'status',
  'privacy',
  'terms',
]);

function preventReservedPollRoute(id: string) {
  if (reservedTopLevelPaths.has(id.toLowerCase())) {
    throw redirect({ to: '/' });
  }
}

type AdminBootstrapStatus = {
  noAdminExists?: boolean;
  adminTokenIsDefault?: boolean;
};

async function maybeRedirectToAdminOnFirstRun() {
  try {
    const status = (await apiFetch('admin/bootstrap-status', {
      adminToken: false,
    })) as AdminBootstrapStatus;
    const needsBootstrap = Boolean(status?.noAdminExists) || Boolean(status?.adminTokenIsDefault);
    if (needsBootstrap) {
      throw redirect({ to: '/admin/setup' });
    }
  } catch (err: unknown) {
    if (isApiFetchError(err)) {
      // If the API is not ready yet, fall back to the normal route.
      return;
    }
    return;
  }
}

function RootLayout() {
  const t = useT();
  const { uiLocale } = useUILocale();
  return (
    <>
      <a href='#asking-app__main' className='asking-app__skip-to-main'>
        {t('nav.skipToMain')}
      </a>
      <div className='asking-app' id='asking-app' data-ui-locale={uiLocale}>
        <NetworkStatusBanner />
        <Navbar />
        <main id='asking-app__main' tabIndex={-1}>
          <Outlet />
        </main>
        <CookieConsentBanner />
        <SiteFooter />
      </div>
    </>
  );
}

function NotFoundView() {
  const t = useT();
  return (
    <div className='ui-page-shell asking-not-found-page' id='asking-not-found-page'>
      <h1
        className='ui-alert ui-alert--danger asking-not-found-page__title'
        id='asking-not-found-page__title'
      >
        {t('notFound.title')}
      </h1>
      <p>
        <Link to='/'>{t('notFound.back')}</Link>
      </p>
    </div>
  );
}

const rootRoute = createRootRoute({
  component: RootLayout,
  notFoundComponent: NotFoundView,
});

const indexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/',
  beforeLoad: () => maybeRedirectToAdminOnFirstRun(),
  component: Home,
});

const aboutRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: 'about',
  component: About,
});

const developerRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: 'developer',
  component: Developer,
});

const loginRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: 'login',
  beforeLoad: () => maybeRedirectToAdminOnFirstRun(),
  component: Login,
});

const registerRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: 'register',
  beforeLoad: () => maybeRedirectToAdminOnFirstRun(),
  component: Register,
});

const myPollsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: 'my-polls',
  component: MyPolls,
});

const settingsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: 'settings',
  component: Settings,
});

const statusRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: 'status',
  component: PublicStatus,
});

const termsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: 'terms',
  component: Terms,
});

const privacyRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: 'privacy',
  component: Privacy,
});

const adminRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: 'admin',
  component: AdminLayout,
});

const adminLoginRoute = createRoute({
  getParentRoute: () => adminRoute,
  path: 'login',
  component: AdminLogin,
});

const adminSetupRoute = createRoute({
  getParentRoute: () => adminRoute,
  path: 'setup',
  component: AdminSetup,
});

const adminDashboardRoute = createRoute({
  getParentRoute: () => adminRoute,
  path: '/',
  beforeLoad: requireAdmin,
  component: AdminDashboard,
});

const adminUsersRoute = createRoute({
  getParentRoute: () => adminRoute,
  path: 'users',
  beforeLoad: requireAdmin,
  component: AdminUsers,
});

const adminPollsRoute = createRoute({
  getParentRoute: () => adminRoute,
  path: 'polls',
  beforeLoad: requireAdmin,
  component: AdminPolls,
});

const adminAuditLogsRoute = createRoute({
  getParentRoute: () => adminRoute,
  path: 'audit-logs',
  validateSearch: parseAuditLogsSearch,
  beforeLoad: requireAdmin,
  component: AdminAuditLogs,
});

const adminExportRoute = createRoute({
  getParentRoute: () => adminRoute,
  path: 'export',
  beforeLoad: requireAdmin,
  component: AdminExport,
});

const adminStatusRoute = createRoute({
  getParentRoute: () => adminRoute,
  path: 'status',
  beforeLoad: requireAdmin,
  component: AdminStatus,
});

const adminImpersonateRoute = createRoute({
  getParentRoute: () => adminRoute,
  path: 'impersonate',
  beforeLoad: requireAdmin,
  component: AdminImpersonate,
});

const pollRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '$id',
  validateSearch: parsePollSearch,
  beforeLoad: ({ params }) => preventReservedPollRoute(params.id),
  component: Poll,
});

const pollResultsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '$id/results',
  validateSearch: parsePollSearch,
  beforeLoad: ({ params }) => preventReservedPollRoute(params.id),
  component: PollResults,
});

const routeTree = rootRoute.addChildren([
  indexRoute,
  aboutRoute,
  developerRoute,
  loginRoute,
  registerRoute,
  myPollsRoute,
  settingsRoute,
  statusRoute,
  termsRoute,
  privacyRoute,
  adminRoute.addChildren([
    adminLoginRoute,
    adminSetupRoute,
    adminDashboardRoute,
    adminUsersRoute,
    adminPollsRoute,
    adminAuditLogsRoute,
    adminExportRoute,
    adminStatusRoute,
    adminImpersonateRoute,
  ]),
  pollResultsRoute,
  pollRoute,
]);

const basepath = String(import.meta.env.BASE_URL ?? '/').replace(/\/$/, '') || '/';

const router = createRouter({
  routeTree,
  ...(basepath === '/' ? {} : { basepath }),
});

export function AppRouter() {
  return <RouterProvider router={router} />;
}

declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router;
  }
}
