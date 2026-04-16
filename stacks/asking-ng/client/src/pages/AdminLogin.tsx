import { adminLoginTokenSchema, createUserBodySchema } from '@asking-ng/contracts/admin';
import { useForm } from '@tanstack/react-form';
import { Link, useNavigate } from '@tanstack/react-router';
import React, { useEffect, useState } from 'react';
import { useAdmin } from '../context/AdminContext';
import { useDocumentTitle } from '../hooks/useDocumentTitle';
import { apiFetch, isApiFetchError } from '../http';
import { useT } from '../i18n/I18nContext';
import type { AdminUser } from '../types/admin';
import { Button, Card, Container, cx, Field, Input, Stack } from '../ui';
import { errMsg } from '../utils/errMsg';

type AdminMeResponse = { admin: AdminUser };
type CreateUserResponse = { user: AdminUser };

export default function AdminLogin() {
  const t = useT();
  useDocumentTitle(t('admin.docTitleLogin'));
  const [error, setError] = useState('');
  const [loggingIn, setLoggingIn] = useState(false);
  const [bootstrapping, setBootstrapping] = useState(false);
  const [bootstrapToken, setBootstrapToken] = useState('');
  const [bootstrapUsername, setBootstrapUsername] = useState('');
  const [bootstrapPassword, setBootstrapPassword] = useState('');
  const navigate = useNavigate();
  const { admin, adminSessionReady, setAdmin } = useAdmin();

  useEffect(() => {
    if (!adminSessionReady || !admin) return;
    void navigate({ to: '/admin' });
  }, [admin, adminSessionReady, navigate]);

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
      <Container size='sm' className='polls-page-container'>
        <Card role='status' aria-live='polite' className='admin-login-hint' tone='muted'>
          {t('admin.login.sessionCheck')}
        </Card>
      </Container>
    );
  }

  if (admin) {
    return (
      <Container size='sm' className='polls-page-container'>
        <Card role='status' aria-live='polite' className='admin-login-hint' tone='muted'>
          {t('admin.login.redirecting')}
        </Card>
      </Container>
    );
  }

  return (
    <Container size='md' className='polls-page-container'>
      <section className='admin-login-layout'>
        <header className='admin-page-header'>
          <h1 className='admin-page-title'>{t('admin.login.title')}</h1>
          <p className='admin-login-hint'>
            Use the admin token from your stack configuration. If this is your first visit, complete
            the guided checklist after signing in.
          </p>
        </header>

        <Card
          as='section'
          padding='none'
          className={cx('ui-card--form-panel', 'admin-login-card')}
          aria-label={t('admin.login.ariaForm')}
        >
          <form
            className='admin-login-form'
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
                  className='admin-login-field'
                  label={t('admin.login.tokenLabel')}
                  htmlFor='admin-login-token'
                  error={
                    field.state.meta.errors.length > 0 ? String(field.state.meta.errors[0]) : undefined
                  }
                >
                  <Input
                    id='admin-login-token'
                    type='password'
                    placeholder={t('admin.login.placeholder')}
                    value={field.state.value}
                    onChange={(e) => field.handleChange(e.target.value)}
                    onBlur={field.handleBlur}
                    className='admin-login-token ui-input--stack'
                    aria-label={t('admin.login.tokenLabel')}
                    aria-invalid={Boolean(field.state.meta.errors.length)}
                    autoComplete='current-password'
                  />
                </Field>
              )}
            </form.Field>
            <div className='admin-login-actions'>
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
          {error ? (
            <p className='error-message admin-login-error' role='alert'>
              {error}
            </p>
          ) : null}
        </Card>

        <Card
          as='section'
          className='admin-setup-card admin-setup-card--compact admin-login-guide-card'
          aria-label='First run guide'
          tone='muted'
        >
          <h2 className='admin-setup-title'>{t('admin.login.firstRunGuide.title')}</h2>
          <ol className='admin-setup-list'>
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
            className='admin-setup-card admin-setup-card--compact admin-login-bootstrap-card'
            aria-label={t('admin.login.bootstrap.ariaSection')}
            tone='accent'
          >
            <h2 className='admin-setup-title'>{t('admin.login.bootstrap.title')}</h2>
            <p className='admin-login-hint'>{t('admin.login.bootstrap.intro')}</p>
            <form
              className='admin-login-form'
              onSubmit={(e) => void handleBootstrapCreate(e)}
              aria-label={t('admin.login.bootstrap.ariaForm')}
            >
              <Stack gap='md'>
                <Field
                  className='admin-login-field'
                  label={t('admin.login.bootstrap.homelab-userPlaceholder')}
                  htmlFor='admin-bootstrap-homelab-user'
                >
                <Input
                  id='admin-bootstrap-homelab-user'
                  type='text'
                  placeholder={t('admin.login.bootstrap.homelab-userPlaceholder')}
                  value={bootstrapUsername}
                  onChange={(e) => setBootstrapUsername(e.target.value)}
                  className='admin-login-token ui-input--stack'
                  autoComplete='homelab-user'
                  disabled={bootstrapping}
                />
                </Field>
                <Field
                  className='admin-login-field'
                  label={t('admin.login.bootstrap.passwordPlaceholder')}
                  htmlFor='admin-bootstrap-password'
                >
                <Input
                  id='admin-bootstrap-password'
                  type='password'
                  placeholder={t('admin.login.bootstrap.passwordPlaceholder')}
                  value={bootstrapPassword}
                  onChange={(e) => setBootstrapPassword(e.target.value)}
                  className='admin-login-token ui-input--stack'
                  autoComplete='new-password'
                  disabled={bootstrapping}
                />
                </Field>
              </Stack>
              <div className='admin-login-actions'>
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
