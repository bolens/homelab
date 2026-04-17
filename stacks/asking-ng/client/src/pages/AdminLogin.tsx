import { adminLoginTokenSchema, createUserBodySchema } from '@asking-ng/contracts/admin';
import { useForm } from '@tanstack/react-form';
import { Link, useNavigate } from '@tanstack/react-router';
import React, { useEffect, useState } from 'react';
import { useAdmin } from '../context/AdminContext';
import { useDocumentTitle } from '../hooks/useDocumentTitle';
import { apiFetch, isApiFetchError } from '../http';
import { useT } from '../i18n/I18nContext';
import type { AdminUser } from '../types/admin';
import { Alert, Button, Card, Container, cx, Field, Input, Stack } from '../ui';
import { errMsg } from '../utils/errMsg';

type AdminMeResponse = { admin: AdminUser };
type CreateUserResponse = { user: AdminUser };
type AdminBootstrapStatus = {
  noAdminExists?: boolean;
  adminTokenIsDefault?: boolean;
};

export default function AdminLogin() {
  const t = useT();
  useDocumentTitle(t('admin.docTitleLogin'));
  const [error, setError] = useState('');
  const [loggingIn, setLoggingIn] = useState(false);
  const [bootstrapping, setBootstrapping] = useState(false);
  const [bootstrapStatus, setBootstrapStatus] = useState<AdminBootstrapStatus | null>(null);
  const [bootstrapToken, setBootstrapToken] = useState('');
  const [bootstrapUsername, setBootstrapUsername] = useState('');
  const [bootstrapPassword, setBootstrapPassword] = useState('');
  const navigate = useNavigate();
  const { admin, adminSessionReady, setAdmin } = useAdmin();

  useEffect(() => {
    if (!adminSessionReady || !admin) return;
    void navigate({ to: '/admin' });
  }, [admin, adminSessionReady, navigate]);

  useEffect(() => {
    let cancelled = false;
    async function loadBootstrapStatus() {
      try {
        const status = (await apiFetch('admin/bootstrap-status', {
          adminToken: false,
        })) as AdminBootstrapStatus;
        if (!cancelled) {
          setBootstrapStatus(status);
        }
      } catch (err: unknown) {
        if (isApiFetchError(err)) {
          return;
        }
      }
    }
    void loadBootstrapStatus();
    return () => {
      cancelled = true;
    };
  }, []);

  const form = useForm({
    defaultValues: {
      token: '',
    },
    onSubmit: async ({ value }) => {
      const parsed = adminLoginTokenSchema.safeParse(value.token);
      if (!parsed.success) {
        setError(t('admin.login.errRequired'));
        return;
      }
      const token = parsed.data;
      setError('');
      setLoggingIn(true);
      try {
        const data = (await apiFetch('admin/me', { adminToken: token })) as AdminMeResponse;
        localStorage.setItem('adminToken', token);
        setAdmin(data.admin);
        navigate({ to: '/admin' });
      } catch (err: unknown) {
        if (
          isApiFetchError(err) &&
          err.status === 404 &&
          err.message.includes('No user with role admin or superadmin')
        ) {
          setBootstrapToken(token);
          setError(t('admin.login.bootstrap.noAdmin'));
          return;
        }
        setError(errMsg(err, t('admin.login.errInvalid')));
      } finally {
        setLoggingIn(false);
      }
    },
  });

  async function handleBootstrapCreate(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const homelab-user = bootstrapUsername.trim();
    const password = bootstrapPassword;
    const parsed = createUserBodySchema.safeParse({ homelab-user, password, role: 'superadmin' });
    if (!parsed.success) {
      setError(t('admin.login.bootstrap.errInvalidInput'));
      return;
    }
    setBootstrapping(true);
    setError('');
    try {
      const created = (await apiFetch('admin/users', {
        method: 'POST',
        adminToken: bootstrapToken,
        body: parsed.data,
      })) as CreateUserResponse;
      const me = (await apiFetch('admin/me', { adminToken: bootstrapToken })) as AdminMeResponse;
      localStorage.setItem('adminToken', bootstrapToken);
      setAdmin(me.admin);
      navigate({ to: '/admin' });
      void created;
    } catch (err: unknown) {
      setError(errMsg(err, t('admin.login.bootstrap.errCreateFail')));
    } finally {
      setBootstrapping(false);
    }
  }

  if (!adminSessionReady) {
    return (
      <Container size='sm' className='asking-admin-page asking-admin-login-page' id='asking-admin-login-page'>
        <Card role='status' aria-live='polite' className='asking-admin-login-page__hint' tone='muted'>
          {t('admin.login.sessionCheck')}
        </Card>
      </Container>
    );
  }

  if (admin) {
    return (
      <Container size='sm' className='asking-admin-page asking-admin-login-page' id='asking-admin-login-page'>
        <Card role='status' aria-live='polite' className='asking-admin-login-page__hint' tone='muted'>
          {t('admin.login.redirecting')}
        </Card>
      </Container>
    );
  }

  return (
    <Container size='md' className='asking-admin-page asking-admin-login-page' id='asking-admin-login-page'>
      <section className='asking-admin-login-page__layout'>
        <header className='asking-admin-page__header'>
          <h1 className='asking-admin-page__title' id='asking-admin-login-page__title'>
            {t('admin.login.title')}
          </h1>
          <p className='asking-admin-login-page__hint'>
            Use the admin token from your stack configuration. If this is your first visit, complete
            the guided checklist after signing in.
          </p>
        </header>

        <Card
          as='section'
          className='asking-admin-page__setup-card asking-admin-page__setup-card--compact asking-admin-login-page__guide-card'
          aria-labelledby='asking-admin-login-page__setup-cta-heading'
          tone='muted'
        >
          <h2 className='asking-admin-page__setup-title' id='asking-admin-login-page__setup-cta-heading'>
            New instance?
          </h2>
          <p className='asking-admin-login-page__hint'>
            If you&apos;re starting a fresh Asking instance, you can use the guided setup wizard to
            walk through securing the admin token and creating the first admin account.
          </p>
          <p>
            <Link to='/admin/setup'>Open guided admin setup</Link>
          </p>
        </Card>

        {bootstrapStatus && (bootstrapStatus.noAdminExists || bootstrapStatus.adminTokenIsDefault) ? (
          <Card
            role='status'
            aria-live='polite'
            className='asking-admin-login-page__hint'
            tone='accent'
          >
            <Stack gap='xs'>
              {bootstrapStatus.adminTokenIsDefault ? (
                <p>
                  For security, update your admin token in the stack environment (for example in
                  your `STACK_ENV` or Docker compose secrets) and restart the API before creating
                  an admin user.
                </p>
              ) : null}
              {bootstrapStatus.noAdminExists ? (
                <p>
                  No admin user exists yet. After setting the admin token, sign in below and follow
                  the “Create first admin account” section to bootstrap your instance.
                </p>
              ) : null}
            </Stack>
          </Card>
        ) : null}

        <Card
          as='section'
          padding='none'
          className={cx('ui-card--form-panel', 'asking-admin-login-page__card')}
          aria-labelledby='asking-admin-login-page__title'
        >
          <form
            id='asking-admin-login-page__token-form'
            className='asking-admin-login-page__form'
            onSubmit={(e) => {
              e.preventDefault();
              void form.handleSubmit();
            }}
            aria-label={t('admin.login.ariaForm')}
          >
            <form.Field
              name='token'
              validators={{
                onBlur: ({ value }) =>
                  adminLoginTokenSchema.safeParse(value).success
                    ? undefined
                    : t('admin.login.errRequired'),
              }}
            >
              {(field) => (
                <Field
                  className='asking-admin-login-page__field'
                  label={t('admin.login.tokenLabel')}
                  htmlFor='asking-admin-login-page__token'
                  error={
                    field.state.meta.errors.length > 0 ? String(field.state.meta.errors[0]) : undefined
                  }
                >
                  <Input
                    id='asking-admin-login-page__token'
                    type='password'
                    placeholder={t('admin.login.placeholder')}
                    value={field.state.value}
                    onChange={(e) => field.handleChange(e.target.value)}
                    onBlur={field.handleBlur}
                    className='asking-admin-login-page__token ui-input--stack'
                    aria-label={t('admin.login.tokenLabel')}
                    aria-invalid={Boolean(field.state.meta.errors.length)}
                    autoComplete='current-password'
                  />
                </Field>
              )}
            </form.Field>
            <div className='asking-admin-login-page__actions'>
              <Button
                type='submit'
                aria-label={t('admin.login.submitAria')}
                title={t('admin.login.submitAria')}
                disabled={loggingIn}
                aria-busy={loggingIn}
              >
                {loggingIn ? t('admin.login.submitting') : t('admin.login.submit')}
              </Button>
            </div>
          </form>
          {error ? <Alert className='asking-admin-login-page__error'>{error}</Alert> : null}
        </Card>

        <Card
          as='section'
          className='asking-admin-page__setup-card asking-admin-page__setup-card--compact asking-admin-login-page__guide-card'
          aria-labelledby='asking-admin-login-page__first-run-guide-heading'
          tone='muted'
        >
          <h2 className='asking-admin-page__setup-title' id='asking-admin-login-page__first-run-guide-heading'>
            {t('admin.login.firstRunGuide.title')}
          </h2>
          <ol className='asking-admin-page__setup-list'>
            <li>{t('admin.login.firstRunGuide.step1')}</li>
            <li>{t('admin.login.firstRunGuide.step2')}</li>
            <li>{t('admin.login.firstRunGuide.step3')}</li>
            <li>{t('admin.login.firstRunGuide.step4')}</li>
            <li>{t('admin.login.firstRunGuide.step5')}</li>
          </ol>
          <p className='ui-copy-muted'>
            {t('admin.login.firstRunGuide.diagnosticsPrefix')}{' '}
            <Link to='/developer'>{t('admin.login.firstRunGuide.diagnosticsLink')}</Link>.
          </p>
        </Card>

        {bootstrapToken ? (
          <Card
            as='section'
            className='asking-admin-page__setup-card asking-admin-page__setup-card--compact asking-admin-login-page__bootstrap-card'
            aria-labelledby='asking-admin-login-page__bootstrap-heading'
            tone='accent'
          >
            <h2 className='asking-admin-page__setup-title' id='asking-admin-login-page__bootstrap-heading'>
              {t('admin.login.bootstrap.title')}
            </h2>
            <p className='asking-admin-login-page__hint'>{t('admin.login.bootstrap.intro')}</p>
            <form
              id='asking-admin-login-page__bootstrap-form'
              className='asking-admin-login-page__form'
              onSubmit={(e) => void handleBootstrapCreate(e)}
              aria-label={t('admin.login.bootstrap.ariaForm')}
            >
              <Stack gap='md'>
                <Field
                  className='asking-admin-login-page__field'
                  label={t('admin.login.bootstrap.homelab-userPlaceholder')}
                  htmlFor='asking-admin-login-page__bootstrap-homelab-user'
                >
                <Input
                  id='asking-admin-login-page__bootstrap-homelab-user'
                  type='text'
                  placeholder={t('admin.login.bootstrap.homelab-userPlaceholder')}
                  value={bootstrapUsername}
                  onChange={(e) => setBootstrapUsername(e.target.value)}
                  className='asking-admin-login-page__token ui-input--stack'
                  autoComplete='homelab-user'
                  disabled={bootstrapping}
                />
                </Field>
                <Field
                  className='asking-admin-login-page__field'
                  label={t('admin.login.bootstrap.passwordPlaceholder')}
                  htmlFor='asking-admin-login-page__bootstrap-password'
                >
                <Input
                  id='asking-admin-login-page__bootstrap-password'
                  type='password'
                  placeholder={t('admin.login.bootstrap.passwordPlaceholder')}
                  value={bootstrapPassword}
                  onChange={(e) => setBootstrapPassword(e.target.value)}
                  className='asking-admin-login-page__token ui-input--stack'
                  autoComplete='new-password'
                  disabled={bootstrapping}
                />
                </Field>
              </Stack>
              <div className='asking-admin-login-page__actions'>
                <Button
                  type='submit'
                  disabled={bootstrapping}
                  aria-busy={bootstrapping}
                >
                  {bootstrapping
                    ? t('admin.login.bootstrap.creating')
                    : t('admin.login.bootstrap.create')}
                </Button>
              </div>
            </form>
          </Card>
        ) : null}
      </section>
    </Container>
  );
}
