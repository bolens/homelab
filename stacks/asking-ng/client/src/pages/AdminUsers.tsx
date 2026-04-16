import {
  adminChangeRoleFormSchema,
  adminResetPasswordFormSchema,
  createUserBodySchema,
} from '@asking-ng/contracts/admin';
import { authLoginBodySchema } from '@asking-ng/contracts/auth';
import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useAdmin } from '../context/AdminContext';
import { useDocumentTitle } from '../hooks/useDocumentTitle';
import { useMaxWidth600 } from '../hooks/useMaxWidth600';
import { apiFetch } from '../http';
import { useLocaleTag, useT } from '../i18n/I18nContext';
import { formatLocaleInteger } from '../lib/formatLocaleDisplay';
import { clearStoredUserJwt, getStoredUserJwt, setStoredUserJwt } from '../lib/userSession';
import { Button, cx, VisuallyHidden } from '../ui';
import { errMsg } from '../utils/errMsg';
import { zodErrorSummary } from '../utils/zodForm';
import { useAdminWebSocket } from '../wsClient';

type AdminDirectoryUser = {
  id: number;
  homelab-user: string;
  role: string;
  active: boolean;
};

type SortKey = keyof AdminDirectoryUser;

function roleBadgeClass(role: string): string {
  if (role === 'superadmin') return 'admin-users-role admin-users-role--superadmin';
  if (role === 'admin') return 'admin-users-role admin-users-role--admin';
  return 'admin-users-role';
}

export default function AdminUsers() {
  const t = useT();
  const localeTag = useLocaleTag();
  useDocumentTitle(t('admin.docTitleUsers'));
  const { admin } = useAdmin();
  const [users, setUsers] = useState<AdminDirectoryUser[]>([]);
  const [selected, setSelected] = useState<number[]>([]);
  const [search, setSearch] = useState('');
  const [roleFilter, setRoleFilter] = useState('');
  const [activeFilter, setActiveFilter] = useState('');
  const [sortBy, setSortBy] = useState<SortKey>('id');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [refresh, setRefresh] = useState(0);
  const [newUser, setNewUser] = useState({ homelab-user: '', password: '', role: 'user' });
  const [resetPw, setResetPw] = useState({ id: '', password: '' });
  const [roleEdit, setRoleEdit] = useState({ id: '', role: 'user' });
  const [appProfile, setAppProfile] = useState<{ homelab-user: string; role: string } | null>(null);
  const [appLoginUser, setAppLoginUser] = useState('');
  const [appLoginPass, setAppLoginPass] = useState('');
  const [appLoginSubmitting, setAppLoginSubmitting] = useState(false);
  const hasAutoRevealedBulkActionsRef = useRef(false);

  const clearMessages = useCallback(() => {
    setError('');
    setSuccess('');
  }, []);

  const onDirectoryWebSocketUpdate = useCallback((data: unknown) => {
    if (Array.isArray(data)) setUsers(data as AdminDirectoryUser[]);
  }, []);

  useAdminWebSocket({ onUserUpdate: onDirectoryWebSocketUpdate });

  useEffect(() => {
    apiFetch('admin/users')
      .then((data) => setUsers((data as { users: AdminDirectoryUser[] }).users ?? []))
      .catch((err) => setError(errMsg(err, t('admin.users.errLoad'))));
  }, [refresh, t]);

  const superadminExists = users.some((u) => u.role === 'superadmin');

  const refreshAppSession = useCallback(async () => {
    const jwt = getStoredUserJwt();
    if (!jwt) {
      setAppProfile(null);
      return;
    }
    try {
      const data = (await apiFetch('profile', {
        adminToken: false,
        bearerToken: jwt,
      })) as { user: { homelab-user: string; role: string } };
      if (data.user.role !== 'superadmin') {
        clearStoredUserJwt();
        setAppProfile(null);
        setError(t('admin.users.appSessionErrNotSuperadmin'));
        return;
      }
      setAppProfile(data.user);
    } catch {
      clearStoredUserJwt();
      setAppProfile(null);
    }
  }, [t]);

  useEffect(() => {
    void refreshAppSession();
  }, [refreshAppSession, refresh]);

  useEffect(() => {
    if (!superadminExists || appProfile?.role === 'superadmin') return;
    setNewUser((prev) => (prev.role === 'superadmin' ? { ...prev, role: 'user' } : prev));
    setRoleEdit((prev) => (prev.role === 'superadmin' ? { ...prev, role: 'user' } : prev));
  }, [superadminExists, appProfile?.role]);

  useEffect(() => {
    if (selected.length === 0) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key !== 'Escape') return;
      setSelected([]);
    };
    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [selected.length]);

  const handleSortClick = (key: SortKey) => {
    if (sortBy === key) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortBy(key);
      setSortDir('asc');
    }
  };

  const sortAriaValue = (key: SortKey): 'ascending' | 'descending' | 'none' => {
    if (sortBy !== key) return 'none';
    return sortDir === 'asc' ? 'ascending' : 'descending';
  };

  const sortIndicator = (key: SortKey) => {
    if (sortBy !== key) return '';
    return sortDir === 'asc' ? ' ▲' : ' ▼';
  };

  const handleAppLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    clearMessages();
    const parsed = authLoginBodySchema.safeParse({
      homelab-user: appLoginUser.trim(),
      password: appLoginPass,
    });
    if (!parsed.success) {
      setError(zodErrorSummary(parsed.error));
      return;
    }
    setAppLoginSubmitting(true);
    try {
      const data = (await apiFetch('auth/login', {
        method: 'POST',
        body: parsed.data,
        adminToken: false,
      })) as { token: string; user: { homelab-user: string; role: string } };
      if (data.user.role !== 'superadmin') {
        setError(t('admin.users.appSessionErrLoginNotSuperadmin'));
        return;
      }
      setStoredUserJwt(data.token);
      setAppProfile(data.user);
      setAppLoginPass('');
    } catch (err) {
      setError(errMsg(err, t('admin.users.appSessionErrLogin')));
    } finally {
      setAppLoginSubmitting(false);
    }
  };

  const handleCreateUser = async (e: React.FormEvent) => {
    e.preventDefault();
    clearMessages();
    const parsed = createUserBodySchema.safeParse({
      homelab-user: newUser.homelab-user,
      password: newUser.password,
      role: newUser.role,
    });
    if (!parsed.success) {
      setError(zodErrorSummary(parsed.error));
      return;
    }
    try {
      const needsJwt = parsed.data.role === 'superadmin' && superadminExists;
      if (needsJwt) {
        const jwt = getStoredUserJwt();
        if (!jwt) {
          setError(t('admin.users.errNeedAppSession'));
          return;
        }
        await apiFetch('users', {
          method: 'POST',
          body: parsed.data,
          adminToken: false,
          bearerToken: jwt,
        });
      } else {
        await apiFetch('admin/users', { method: 'POST', body: parsed.data });
      }
      setNewUser({ homelab-user: '', password: '', role: 'user' });
      setSuccess(t('admin.users.successCreated'));
      setRefresh((r) => r + 1);
    } catch (err) {
      setError(errMsg(err, t('admin.users.errCreate')));
    }
  };

  const handleResetPassword = async (e: React.FormEvent) => {
    e.preventDefault();
    clearMessages();
    const parsed = adminResetPasswordFormSchema.safeParse({
      id: resetPw.id,
      password: resetPw.password,
    });
    if (!parsed.success) {
      setError(zodErrorSummary(parsed.error));
      return;
    }
    try {
      await apiFetch(`admin/users/${parsed.data.id}/reset-password`, {
        method: 'POST',
        body: { password: parsed.data.password },
      });
      setResetPw({ id: '', password: '' });
      setSuccess(t('admin.users.successPasswordReset'));
      setRefresh((r) => r + 1);
    } catch (err) {
      setError(errMsg(err, t('admin.users.errResetPw')));
    }
  };

  const handleChangeRole = async (e: React.FormEvent) => {
    e.preventDefault();
    clearMessages();
    const parsed = adminChangeRoleFormSchema.safeParse({
      id: roleEdit.id,
      role: roleEdit.role,
    });
    if (!parsed.success) {
      setError(zodErrorSummary(parsed.error));
      return;
    }
    try {
      const target = users.find((u) => u.id === parsed.data.id);
      const priorRole = target?.role;
      const promoteToSuperadmin =
        parsed.data.role === 'superadmin' && superadminExists && priorRole !== 'superadmin';
      if (promoteToSuperadmin) {
        const jwt = getStoredUserJwt();
        if (!jwt) {
          setError(t('admin.users.errNeedAppSession'));
          return;
        }
        await apiFetch(`users/${parsed.data.id}/role`, {
          method: 'PATCH',
          body: { role: parsed.data.role },
          adminToken: false,
          bearerToken: jwt,
        });
      } else {
        await apiFetch(`admin/users/${parsed.data.id}/role`, {
          method: 'PATCH',
          body: { role: parsed.data.role },
        });
      }
      setRoleEdit({ id: '', role: 'user' });
      setSuccess(t('admin.users.successRoleChanged'));
      setRefresh((r) => r + 1);
    } catch (err) {
      setError(errMsg(err, t('admin.users.errRole')));
    }
  };

  const handleDeleteUser = async (id: number) => {
    if (!window.confirm(t('admin.users.confirmDelete', { id }))) return;
    clearMessages();
    try {
      await apiFetch(`admin/users/${id}`, { method: 'DELETE' });
      setSuccess(t('admin.users.successDeleted'));
      setRefresh((r) => r + 1);
    } catch (err) {
      setError(errMsg(err, t('admin.users.errDelete')));
    }
  };

  const handleSelect = (id: number) => {
    const selectingFirst = selected.length === 0 && !selected.includes(id);
    setSelected((sel) => (sel.includes(id) ? sel.filter((x) => x !== id) : [...sel, id]));
    if (!selectingFirst || hasAutoRevealedBulkActionsRef.current || typeof window === 'undefined')
      return;
    const coarsePointer = window.matchMedia('(pointer: coarse)').matches;
    const narrowViewport = window.matchMedia('(max-width: 900px)').matches;
    if (!coarsePointer && !narrowViewport) return;
    hasAutoRevealedBulkActionsRef.current = true;
    window.requestAnimationFrame(() => {
      window.scrollBy({ top: 120, behavior: 'smooth' });
    });
  };

  const handleBulk = async (action: 'suspend' | 'activate' | 'delete') => {
    if (action === 'delete' && !window.confirm(t('admin.users.confirmBulkDelete'))) return;
    clearMessages();
    for (const id of selected) {
      try {
        if (action === 'suspend') {
          await apiFetch(`admin/users/${id}/suspend`, { method: 'PATCH', body: {} });
        }
        if (action === 'activate') {
          await apiFetch(`admin/users/${id}/activate`, { method: 'PATCH', body: {} });
        }
        if (action === 'delete') {
          await apiFetch(`admin/users/${id}`, { method: 'DELETE' });
        }
      } catch (err) {
        setError(errMsg(err, t('admin.users.errBulk', { id })));
        setRefresh((r) => r + 1);
        setSelected([]);
        return;
      }
    }
    setSelected([]);
    setSuccess(t('admin.users.successBulkDone'));
    setRefresh((r) => r + 1);
  };

  const handleSuspend = async (id: number) => {
    clearMessages();
    try {
      await apiFetch(`admin/users/${id}/suspend`, { method: 'PATCH', body: {} });
      setSuccess(t('admin.users.successSuspended'));
      setRefresh((r) => r + 1);
    } catch (err) {
      setError(errMsg(err, t('admin.users.errSuspend')));
    }
  };

  const handleActivate = async (id: number) => {
    clearMessages();
    try {
      await apiFetch(`admin/users/${id}/activate`, { method: 'PATCH', body: {} });
      setSuccess(t('admin.users.successActivated'));
      setRefresh((r) => r + 1);
    } catch (err) {
      setError(errMsg(err, t('admin.users.errActivate')));
    }
  };

  let filteredUsers = users.filter(
    (u) =>
      (u.homelab-user.toLowerCase().includes(search.toLowerCase()) || String(u.id) === search) &&
      (roleFilter ? u.role === roleFilter : true) &&
      (activeFilter ? (activeFilter === 'active' ? u.active : !u.active) : true),
  );

  filteredUsers = filteredUsers.sort((a, b) => {
    if (sortBy === 'active') {
      const diff = Number(a.active) - Number(b.active);
      if (diff !== 0) return sortDir === 'asc' ? diff : -diff;
    } else {
      const raw1 = a[sortBy];
      const raw2 = b[sortBy];
      const v1 = typeof raw1 === 'string' ? raw1.toLowerCase() : String(raw1);
      const v2 = typeof raw2 === 'string' ? raw2.toLowerCase() : String(raw2);
      if (v1 < v2) return sortDir === 'asc' ? -1 : 1;
      if (v1 > v2) return sortDir === 'asc' ? 1 : -1;
    }
    return a.id - b.id;
  });

  if (!admin || (admin.role !== 'admin' && admin.role !== 'superadmin')) {
    return (
      <div className='polls-page-container-error' role='alert'>
        {t('admin.users.accessDenied')}
      </div>
    );
  }

  const canJwtManageSuperadmin =
    admin.role === 'superadmin' && (!superadminExists || appProfile?.role === 'superadmin');

  const narrow600 = useMaxWidth600();
  const mobileStickyBulkActive = narrow600 && selected.length > 0;

  const shownStr = formatLocaleInteger(filteredUsers.length, localeTag);
  const totalStr = formatLocaleInteger(users.length, localeTag);

  return (
    <div
      className={`polls-page-container admin-cq-root${selected.length > 0 ? ' has-mobile-bulk-actions' : ''}`}
    >
      <header className='admin-page-header'>
        <h1 className='admin-page-title'>{t('admin.users.heading')}</h1>
        <p className='admin-page-subtitle'>
          {t('admin.users.pageSubtitle', { shown: shownStr, total: totalStr })}
        </p>
      </header>

      {selected.length > 0 ? (
        <a
          href={mobileStickyBulkActive ? '#admin-users-mobile-bulk' : '#admin-users-bulk-actions'}
          className='admin-jump-link'
        >
          {t('admin.users.skipToBulk')}
        </a>
      ) : null}

      {success ? (
        <div className='poll-status poll-status-success' role='status' aria-live='polite'>
          {success}
        </div>
      ) : null}
      {error ? (
        <div className='poll-status poll-status-error' role='alert'>
          {error}
        </div>
      ) : null}

      {admin.role === 'superadmin' && superadminExists ? (
        <section
          className='admin-users-app-session'
          aria-labelledby='admin-users-app-session-title'
        >
          <h2 id='admin-users-app-session-title' className='admin-users-app-session-title'>
            {t('admin.users.appSessionTitle')}
          </h2>
          <p className='admin-users-app-session-intro'>{t('admin.users.appSessionIntro')}</p>
          {appProfile ? (
            <div className='admin-users-inline-actions'>
              <span>
                {t('admin.users.appSessionSignedIn', {
                  user: appProfile.homelab-user,
                  role: appProfile.role,
                })}
              </span>
              <Button
                type='button'
                variant='secondary'
                className='admin-users-btn'
                onClick={() => {
                  clearStoredUserJwt();
                  setAppProfile(null);
                }}
              >
                {t('admin.users.appSessionSignOut')}
              </Button>
            </div>
          ) : (
            <form onSubmit={handleAppLogin} className='admin-users-form admin-users-form--session'>
              <VisuallyHidden as='label' htmlFor='admin-users-app-homelab-user'>
                {t('admin.users.appSessionUsername')}
              </VisuallyHidden>
              <input
                id='admin-users-app-homelab-user'
                className='admin-users-input'
                autoComplete='homelab-user'
                placeholder={t('admin.users.appSessionUsername')}
                value={appLoginUser}
                onChange={(e) => setAppLoginUser(e.target.value)}
              />
              <VisuallyHidden as='label' htmlFor='admin-users-app-password'>
                {t('admin.users.appSessionPassword')}
              </VisuallyHidden>
              <input
                id='admin-users-app-password'
                type='password'
                className='admin-users-input'
                autoComplete='current-password'
                placeholder={t('admin.users.appSessionPassword')}
                value={appLoginPass}
                onChange={(e) => setAppLoginPass(e.target.value)}
              />
              <Button
                type='submit'
                variant='primary'
                className='poll-btn'
                style={{ marginInlineStart: 0 }}
                disabled={appLoginSubmitting}
              >
                {appLoginSubmitting
                  ? t('admin.users.appSessionSigningIn')
                  : t('admin.users.appSessionSignIn')}
              </Button>
            </form>
          )}
        </section>
      ) : null}

      <form
        onSubmit={handleCreateUser}
        className='poll-form poll-form--tight'
        aria-label={t('admin.users.createFormAria')}
      >
        <b>{t('admin.users.createLabel')}</b>
        <VisuallyHidden as='label' htmlFor='admin-users-new-homelab-user'>
          {t('admin.users.newUsername')}
        </VisuallyHidden>
        <input
          id='admin-users-new-homelab-user'
          placeholder={t('admin.users.placeholderUsername')}
          value={newUser.homelab-user}
          onChange={(e) => setNewUser({ ...newUser, homelab-user: e.target.value })}
          className='poll-input-question'
        />
        <VisuallyHidden as='label' htmlFor='admin-users-new-password'>
          {t('admin.users.newPassword')}
        </VisuallyHidden>
        <input
          id='admin-users-new-password'
          type='password'
          placeholder={t('admin.users.placeholderPassword')}
          value={newUser.password}
          onChange={(e) => setNewUser({ ...newUser, password: e.target.value })}
          className='poll-input-wide'
        />
        <VisuallyHidden as='label' htmlFor='admin-users-new-role'>
          {t('admin.users.newUserRole')}
        </VisuallyHidden>
        <select
          id='admin-users-new-role'
          value={newUser.role}
          onChange={(e) => setNewUser({ ...newUser, role: e.target.value })}
          className='poll-input-wide'
        >
          <option value='user'>{t('admin.users.roleValueUser')}</option>
          <option value='mod'>{t('admin.users.roleValueMod')}</option>
          <option value='admin'>{t('admin.users.roleValueAdmin')}</option>
          {canJwtManageSuperadmin && (
            <option value='superadmin'>{t('admin.users.roleValueSuperadmin')}</option>
          )}
        </select>
        <Button type='submit' variant='secondary' className='poll-btn'>
          {t('admin.users.create')}
        </Button>
      </form>

      <div className='polls-search-bar polls-search-bar--tight'>
        <VisuallyHidden as='label' htmlFor='admin-users-search'>
          {t('admin.users.searchLabel')}
        </VisuallyHidden>
        <input
          id='admin-users-search'
          placeholder={t('admin.users.searchPlaceholder')}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <VisuallyHidden as='label' htmlFor='admin-users-role-filter'>
          {t('admin.users.filterRoleLabel')}
        </VisuallyHidden>
        <select
          id='admin-users-role-filter'
          value={roleFilter}
          onChange={(e) => setRoleFilter(e.target.value)}
        >
          <option value=''>{t('admin.users.roleAll')}</option>
          <option value='user'>{t('admin.users.roleUser')}</option>
          <option value='mod'>{t('admin.users.roleMod')}</option>
          <option value='admin'>{t('admin.users.roleAdmin')}</option>
          <option value='superadmin'>{t('admin.users.roleSuperadmin')}</option>
        </select>
        <VisuallyHidden as='label' htmlFor='admin-users-active-filter'>
          {t('admin.users.filterStatusLabel')}
        </VisuallyHidden>
        <select
          id='admin-users-active-filter'
          value={activeFilter}
          onChange={(e) => setActiveFilter(e.target.value)}
        >
          <option value=''>{t('admin.users.statusAll')}</option>
          <option value='active'>{t('admin.users.statusActive')}</option>
          <option value='inactive'>{t('admin.users.statusInactive')}</option>
        </select>
        <Button
          type='button'
          variant='secondary'
          className='poll-btn'
          aria-label={t('admin.users.clearFilters')}
          onClick={() => {
            setSearch('');
            setRoleFilter('');
            setActiveFilter('');
          }}
        >
          {t('admin.users.clear')}
        </Button>
        <Button type='button' variant='secondary' className='poll-btn' onClick={() => setRefresh((r) => r + 1)}>
          {t('admin.users.refresh')}
        </Button>
      </div>

      <section
        className='admin-users-tools'
        aria-label={
          admin.role === 'superadmin'
            ? t('admin.users.sectionTools')
            : t('admin.users.resetPasswordCardTitle')
        }
      >
        {admin.role === 'superadmin' ? (
          <div className='admin-users-tool-card'>
            <h3 className='admin-users-tool-card-title'>{t('admin.users.changeRoleCardTitle')}</h3>
            <form onSubmit={handleChangeRole} className='admin-users-tool-form'>
              <div className='admin-users-tool-form-row'>
                <VisuallyHidden as='label' htmlFor='admin-users-role-user-id'>
                  {t('admin.users.userIdRole')}
                </VisuallyHidden>
                <input
                  id='admin-users-role-user-id'
                  placeholder={t('admin.users.placeholderUserId')}
                  value={roleEdit.id}
                  onChange={(e) => setRoleEdit({ ...roleEdit, id: e.target.value })}
                  className='poll-input-question'
                />
                <VisuallyHidden as='label' htmlFor='admin-users-role-select'>
                  {t('admin.users.newRole')}
                </VisuallyHidden>
                <select
                  id='admin-users-role-select'
                  value={roleEdit.role}
                  onChange={(e) => setRoleEdit({ ...roleEdit, role: e.target.value })}
                  className='poll-input-wide'
                >
                  <option value='user'>{t('admin.users.roleValueUser')}</option>
                  <option value='mod'>{t('admin.users.roleValueMod')}</option>
                  <option value='admin'>{t('admin.users.roleValueAdmin')}</option>
                  {canJwtManageSuperadmin && (
                    <option value='superadmin'>{t('admin.users.roleValueSuperadmin')}</option>
                  )}
                </select>
                <Button type='submit' variant='secondary' className='poll-btn'>
                  {t('admin.users.change')}
                </Button>
              </div>
            </form>
          </div>
        ) : null}

        <div className='admin-users-tool-card'>
          <h3 className='admin-users-tool-card-title'>{t('admin.users.resetPasswordCardTitle')}</h3>
          <form onSubmit={handleResetPassword} className='admin-users-tool-form'>
            <div className='admin-users-tool-form-row'>
              <VisuallyHidden as='label' htmlFor='admin-users-reset-user-id'>
                {t('admin.users.resetUserId')}
              </VisuallyHidden>
              <input
                id='admin-users-reset-user-id'
                placeholder={t('admin.users.placeholderUserId')}
                value={resetPw.id}
                onChange={(e) => setResetPw({ ...resetPw, id: e.target.value })}
                className='poll-input-question'
              />
              <VisuallyHidden as='label' htmlFor='admin-users-reset-password'>
                {t('admin.users.resetPassword')}
              </VisuallyHidden>
              <input
                id='admin-users-reset-password'
                type='password'
                placeholder={t('admin.users.placeholderNewPassword')}
                value={resetPw.password}
                onChange={(e) => setResetPw({ ...resetPw, password: e.target.value })}
                className='poll-input-wide'
              />
              <Button type='submit' variant='secondary' className='poll-btn'>
                {t('admin.users.reset')}
              </Button>
            </div>
          </form>
        </div>
      </section>

      <section
        id='admin-users-bulk-actions'
        role='region'
        aria-labelledby='admin-users-bulk-heading'
        className='polls-bulk-actions polls-bulk-actions--tight'
        inert={mobileStickyBulkActive}
      >
        <b id='admin-users-bulk-heading'>{t('admin.users.bulkLabel')}</b>
        <Button
          type='button'
          variant='secondary'
          className='poll-btn'
          onClick={() => void handleBulk('suspend')}
          disabled={selected.length === 0}
          aria-label={t('admin.users.voiceSuspendBulk')}
        >
          {t('admin.users.suspend')}
        </Button>
        <Button
          type='button'
          variant='secondary'
          className='poll-btn'
          onClick={() => void handleBulk('activate')}
          disabled={selected.length === 0}
          aria-label={t('admin.users.voiceActivateBulk')}
        >
          {t('admin.users.activate')}
        </Button>
        <Button
          type='button'
          variant='secondary'
          onClick={() => void handleBulk('delete')}
          disabled={selected.length === 0}
          className={cx('poll-btn', 'poll-delete-btn')}
          aria-label={t('admin.users.voiceDeleteBulk')}
        >
          {t('admin.users.delete')}
        </Button>
        <span className='poll-bulk-selected' role='status' aria-live='polite' aria-atomic='true'>
          {t('admin.users.selected', { count: formatLocaleInteger(selected.length, localeTag) })}
        </span>
      </section>

      <div className='admin-data-table-wrap'>
        <table className='admin-users-table'>
          <thead>
            <tr>
              <th scope='col' aria-sort={sortAriaValue('id')}>
                <button
                  type='button'
                  className='table-sort-btn'
                  onClick={() => handleSortClick('id')}
                >
                  {t('admin.users.colId')}
                  {sortIndicator('id')}
                </button>
              </th>
              <th scope='col' aria-sort={sortAriaValue('homelab-user')}>
                <button
                  type='button'
                  className='table-sort-btn'
                  onClick={() => handleSortClick('homelab-user')}
                >
                  {t('admin.users.colUsername')}
                  {sortIndicator('homelab-user')}
                </button>
              </th>
              <th scope='col' aria-sort={sortAriaValue('role')}>
                <button
                  type='button'
                  className='table-sort-btn'
                  onClick={() => handleSortClick('role')}
                >
                  {t('admin.users.colRole')}
                  {sortIndicator('role')}
                </button>
              </th>
              <th scope='col' aria-sort={sortAriaValue('active')}>
                <button
                  type='button'
                  className='table-sort-btn'
                  onClick={() => handleSortClick('active')}
                >
                  {t('admin.users.colActive')}
                  {sortIndicator('active')}
                </button>
              </th>
              <th scope='col'>{t('admin.users.colActions')}</th>
            </tr>
          </thead>
          <tbody>
            {filteredUsers.map((u) => (
              <tr key={u.id}>
                <td>
                  <input
                    type='checkbox'
                    checked={selected.includes(u.id)}
                    onChange={() => handleSelect(u.id)}
                    onKeyDown={(e) => {
                      if ((e.key === ' ' || e.key === 'Spacebar') && e.shiftKey) {
                        e.preventDefault();
                        handleSelect(u.id);
                      }
                    }}
                    aria-label={t('admin.users.selectUser', { homelab-user: u.homelab-user })}
                  />{' '}
                  {formatLocaleInteger(u.id, localeTag)}
                </td>
                <td>{u.homelab-user}</td>
                <td>
                  <span className={roleBadgeClass(u.role)}>{u.role}</span>
                </td>
                <td>{u.active ? t('admin.users.yes') : t('admin.users.no')}</td>
                <td>
                  <div className='admin-users-actions-cell'>
                    {u.active ? (
                      <Button
                        type='button'
                        variant='secondary'
                        className='poll-btn'
                        onClick={() => void handleSuspend(u.id)}
                        aria-label={t('admin.users.voiceSuspendRow', { homelab-user: u.homelab-user })}
                      >
                        {t('admin.users.suspend')}
                      </Button>
                    ) : (
                      <Button
                        type='button'
                        variant='secondary'
                        className='poll-btn'
                        onClick={() => void handleActivate(u.id)}
                        aria-label={t('admin.users.voiceActivateRow', { homelab-user: u.homelab-user })}
                      >
                        {t('admin.users.activate')}
                      </Button>
                    )}
                    <Button
                      type='button'
                      variant='secondary'
                      onClick={() => void handleDeleteUser(u.id)}
                      className={cx('poll-btn', 'poll-delete-btn')}
                      aria-label={t('admin.users.voiceDeleteRow', { homelab-user: u.homelab-user })}
                    >
                      {t('admin.users.delete')}
                    </Button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {selected.length > 0 ? (
        <section
          id='admin-users-mobile-bulk'
          role='region'
          aria-labelledby='admin-users-mobile-bulk-heading'
          className='admin-mobile-bulk-actions'
        >
          <VisuallyHidden as='h2' id='admin-users-mobile-bulk-heading'>
            {t('admin.users.bulkLabel')}
          </VisuallyHidden>
          <span
            className='admin-mobile-bulk-selected'
            role='status'
            aria-live='polite'
            aria-atomic='true'
          >
            {t('admin.users.selected', { count: formatLocaleInteger(selected.length, localeTag) })}
          </span>
          <div className='admin-mobile-bulk-buttons'>
            <Button
              type='button'
              variant='secondary'
              onClick={() => void handleBulk('suspend')}
              className='admin-users-btn'
              aria-label={t('admin.users.voiceSuspendBulk')}
            >
              {t('admin.users.suspend')}
            </Button>
            <Button
              type='button'
              variant='secondary'
              onClick={() => void handleBulk('activate')}
              className='admin-users-btn'
              aria-label={t('admin.users.voiceActivateBulk')}
            >
              {t('admin.users.activate')}
            </Button>
            <Button
              type='button'
              variant='secondary'
              onClick={() => void handleBulk('delete')}
              className={cx('admin-users-btn', 'admin-users-btn-delete')}
              aria-label={t('admin.users.voiceDeleteBulk')}
            >
              {t('admin.users.delete')}
            </Button>
          </div>
        </section>
      ) : null}
    </div>
  );
}
