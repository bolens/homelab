import { adminLoginTokenSchema, createUserBodySchema } from '@asking-ng/contracts/admin';
import { Link, useNavigate } from '@tanstack/react-router';
import React, { useEffect, useState } from 'react';
import { useAdmin } from '../context/AdminContext';
import { useDocumentTitle } from '../hooks/useDocumentTitle';
import { apiFetch, isApiFetchError } from '../http';
import { useT } from '../i18n/I18nContext';
import type { AdminUser } from '../types/admin';
import { Alert, Button, Card, Container, Field, Input, Stack } from '../ui';
import { errMsg } from '../utils/errMsg';

type AdminMeResponse = { admin: AdminUser };
type CreateUserResponse = { user: AdminUser };

type AdminBootstrapStatus = {
  noAdminExists?: boolean;
  adminTokenIsDefault?: boolean;
};

export default function AdminSetup() {
  const t = useT();
  useDocumentTitle('Admin setup');
  const navigate = useNavigate();
  const { admin, adminSessionReady, setAdmin } = useAdmin();

  const [bootstrapStatus, setBootstrapStatus] = useState<AdminBootstrapStatus | null>(null);
  const [loadingStatus, setLoadingStatus] = useState(true);
  const [statusError, setStatusError] = useState('');

  const [adminTokenInput, setAdminTokenInput] = useState('');
  const [verifyingToken, setVerifyingToken] = useState(false);
  const [bootstrapToken, setBootstrapToken] = useState('');
  const [generatedToken, setGeneratedToken] = useState('');
  const [copyState, setCopyState] = useState<'idle' | 'copied' | 'failed'>('idle');
  const [copyRestartState, setCopyRestartState] = useState<'idle' | 'copied' | 'failed'>('idle');
  const [copyRecreateState, setCopyRecreateState] = useState<'idle' | 'copied' | 'failed'>('idle');
  const [showAdvancedRestart, setShowAdvancedRestart] = useState(false);

  const [bootstrapping, setBootstrapping] = useState(false);
  const [bootstrapUsername, setBootstrapUsername] = useState('');
  const [bootstrapPassword, setBootstrapPassword] = useState('');
  const [error, setError] = useState('');
  const stackDirectory = 'stacks/asking-ng';
  const restartCommand = 'docker compose restart asking-api';
  const recreateCommand = 'docker compose up -d --force-recreate asking-api';
  const restartFromRepoRootCommand = `cd ${stackDirectory} && ${restartCommand}`;
  const recreateFromRepoRootCommand = `cd ${stackDirectory} && ${recreateCommand}`;

  useEffect(() => {
    if (!adminSessionReady) return;
    if (admin) {
      void navigate({ to: '/admin' });
    }
  }, [admin, adminSessionReady, navigate]);

  async function refreshBootstrapStatus() {
    setLoadingStatus(true);
    setStatusError('');
    try {
      const status = (await apiFetch('admin/bootstrap-status', {
        adminToken: false,
      })) as AdminBootstrapStatus;
      setBootstrapStatus(status);
    } catch (err: unknown) {
      if (isApiFetchError(err)) {
        setStatusError(errMsg(err, 'Unable to load setup status.'));
      } else {
        setStatusError('Unable to load setup status.');
      }
    } finally {
      setLoadingStatus(false);
    }
  }

  useEffect(() => {
    void refreshBootstrapStatus();
  }, []);

  function generateAdminToken() {
    const bytes = new Uint8Array(24);
    crypto.getRandomValues(bytes);
    const token = Array.from(bytes, (byte) => byte.toString(16).padStart(2, '0')).join('');
    setGeneratedToken(token);
    setAdminTokenInput(token);
    setCopyState('idle');
    setError('');
  }

  async function copyGeneratedToken() {
    if (!generatedToken) return;
    try {
      await navigator.clipboard.writeText(generatedToken);
      setCopyState('copied');
    } catch {
      setCopyState('failed');
    }
  }

  async function copyRestartCommand() {
    try {
      await navigator.clipboard.writeText(restartFromRepoRootCommand);
      setCopyRestartState('copied');
    } catch {
      setCopyRestartState('failed');
    }
  }

  async function copyRecreateCommand() {
    try {
      await navigator.clipboard.writeText(recreateFromRepoRootCommand);
      setCopyRecreateState('copied');
    } catch {
      setCopyRecreateState('failed');
    }
  }

  async function handleVerifyToken(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const parsed = adminLoginTokenSchema.safeParse(adminTokenInput);
    if (!parsed.success) {
      setError(t('admin.login.errRequired'));
      return;
    }
    const token = parsed.data;
    setError('');
    setVerifyingToken(true);
    try {
      const data = (await apiFetch('admin/me', { adminToken: token })) as AdminMeResponse;
      localStorage.setItem('adminToken', token);
      setBootstrapToken(token);
      setAdmin(data.admin);
      await navigate({ to: '/admin' });
    } catch (err: unknown) {
      if (
        isApiFetchError(err) &&
        err.status === 404 &&
        err.message.includes('No user with role admin or superadmin')
      ) {
        setBootstrapToken(token);
        setError('');
        return;
      }
      setError(errMsg(err, t('admin.login.errInvalid')));
    } finally {
      setVerifyingToken(false);
    }
  }

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
      await navigate({ to: '/admin' });
      void created;
    } catch (err: unknown) {
      setError(errMsg(err, t('admin.login.bootstrap.errCreateFail')));
    } finally {
      setBootstrapping(false);
    }
  }

  const showBootstrapForm = Boolean(bootstrapToken);

  return (
    <Container
      size='md'
      className='asking-admin-page asking-admin-setup-page'
      id='asking-admin-setup-page'
    >
      <section className='asking-admin-login-page__layout'>
        <header className='asking-admin-page__header'>
          <h1 className='asking-admin-page__title' id='asking-admin-setup-page__title'>
            Secure your Asking instance
          </h1>
          <p className='asking-admin-login-page__hint'>
            This short checklist helps you protect the admin interface and create the first admin
            account.
          </p>
        </header>

        <Card
          as='section'
          className='asking-admin-page__setup-card asking-admin-page__setup-card--compact'
          aria-labelledby='asking-admin-setup-page__checklist-heading'
        >
          <h2
            className='asking-admin-page__setup-title'
            id='asking-admin-setup-page__checklist-heading'
          >
            Setup checklist
          </h2>
          <ol className='asking-admin-page__setup-list'>
            <li>Set a strong admin token in your stack configuration.</li>
            <li>
              If you do not have one yet, generate one in your browser and copy it into config.
            </li>
            <li>Verify the admin token below.</li>
            <li>Create the first admin account.</li>
          </ol>
          <p className='ui-copy-muted'>
            You can return to the normal <Link to='/admin/login'>admin login</Link> once setup is
            complete.
          </p>
        </Card>

        <Card
          as='section'
          className='asking-admin-page__setup-card asking-admin-page__setup-card--compact'
          aria-labelledby='asking-admin-setup-page__step-token-heading'
          tone='muted'
        >
          <h2
            className='asking-admin-page__setup-title'
            id='asking-admin-setup-page__step-token-heading'
          >
            Step 1 · Admin token
          </h2>
          {loadingStatus ? (
            <p>Checking current setup…</p>
          ) : statusError ? (
            <Alert>{statusError}</Alert>
          ) : (
            <Stack gap='sm'>
              {bootstrapStatus?.adminTokenIsDefault ? (
                <Alert tone='danger'>
                  Your admin token is still using the default value. Update it in your environment
                  (for example in your stack env file or Docker compose secrets) and restart the API
                  before proceeding.
                </Alert>
              ) : (
                <Alert tone='success'>
                  Admin token appears to be configured. You can now verify it below and create an
                  admin account.
                </Alert>
              )}
              {bootstrapStatus?.adminTokenIsDefault ? (
                <p>
                  If you have not chosen a token yet, generate one below. The token is generated
                  locally in your browser and is never sent anywhere until you paste it into your
                  stack config and use it to verify login.
                </p>
              ) : null}
              {bootstrapStatus?.noAdminExists ? (
                <p>
                  No admin account exists yet. After verifying the admin token, you will be able to
                  create the first superadmin.
                </p>
              ) : (
                <p>
                  An admin account may already exist. If so, you can sign in from the admin login.
                </p>
              )}
            </Stack>
          )}
        </Card>

        <Card
          as='section'
          padding='none'
          className='ui-card--form-panel asking-admin-page__setup-card asking-admin-page__setup-card--compact'
          aria-labelledby='asking-admin-setup-page__step-verify-heading'
        >
          <div className='asking-admin-login-page__form'>
            <h2
              className='asking-admin-page__setup-title'
              id='asking-admin-setup-page__step-verify-heading'
            >
              Step 2 · Verify admin token
            </h2>
            <p className='asking-admin-login-page__hint'>
              Paste the admin token you configured for this instance. We will verify it with the API
              and then let you create the first admin account.
            </p>
            <form
              id='asking-admin-setup-page__verify-token-form'
              onSubmit={(e) => void handleVerifyToken(e)}
            >
              <Field
                className='asking-admin-login-page__field'
                label='Generate a token'
                htmlFor='asking-admin-setup-page__generated-token'
              >
                <Input
                  id='asking-admin-setup-page__generated-token'
                  type='text'
                  value={generatedToken}
                  readOnly
                  placeholder='Click "Generate token" to create a strong admin token'
                  className='asking-admin-login-page__token ui-input--stack'
                />
              </Field>
              <div className='asking-admin-login-page__actions'>
                <Button type='button' onClick={generateAdminToken}>
                  {generatedToken ? 'Generate new token' : 'Generate token'}
                </Button>
                <Button
                  type='button'
                  variant='secondary'
                  onClick={() => void copyGeneratedToken()}
                  disabled={!generatedToken}
                >
                  Copy token
                </Button>
                {copyState === 'copied' ? (
                  <span className='ui-copy-muted'>Copied to clipboard.</span>
                ) : null}
                {copyState === 'failed' ? (
                  <span className='ui-copy-muted'>
                    Copy failed. You can still select and copy it manually.
                  </span>
                ) : null}
              </div>
              <p className='ui-copy-muted'>
                Save this token in your stack configuration, restart the API, then paste the same
                token below to continue.
              </p>
              <Field
                className='asking-admin-login-page__field'
                label='Restart API command'
                htmlFor='asking-admin-setup-page__restart-command'
              >
                <Input
                  id='asking-admin-setup-page__restart-command'
                  type='text'
                  value={restartFromRepoRootCommand}
                  readOnly
                  className='asking-admin-login-page__token ui-input--stack'
                />
              </Field>
              <p className='ui-copy-muted'>
                Run this from your repo root. It changes into `stacks/asking-ng` and restarts only
                the API service.
              </p>
              <div className='asking-admin-login-page__actions'>
                <Button type='button' variant='secondary' onClick={() => void copyRestartCommand()}>
                  Copy restart command
                </Button>
                <Button
                  type='button'
                  variant='secondary'
                  onClick={() => setShowAdvancedRestart((prev) => !prev)}
                >
                  {showAdvancedRestart ? 'Hide advanced command' : 'Show advanced command'}
                </Button>
                <Button
                  type='button'
                  variant='secondary'
                  onClick={() => void refreshBootstrapStatus()}
                  disabled={loadingStatus}
                >
                  {loadingStatus ? 'Checking…' : 'I restarted, re-check setup'}
                </Button>
                {copyRestartState === 'copied' ? (
                  <span className='ui-copy-muted'>Restart command copied.</span>
                ) : null}
                {copyRestartState === 'failed' ? (
                  <span className='ui-copy-muted'>
                    Copy failed. You can still select and copy the command manually.
                  </span>
                ) : null}
              </div>
              {showAdvancedRestart ? (
                <>
                  <Field
                    className='asking-admin-login-page__field'
                    label='Advanced restart (force recreate)'
                    htmlFor='asking-admin-setup-page__recreate-command'
                  >
                    <Input
                      id='asking-admin-setup-page__recreate-command'
                      type='text'
                      value={recreateFromRepoRootCommand}
                      readOnly
                      className='asking-admin-login-page__token ui-input--stack'
                    />
                  </Field>
                  <div className='asking-admin-login-page__actions'>
                    <Button
                      type='button'
                      variant='secondary'
                      onClick={() => void copyRecreateCommand()}
                    >
                      Copy advanced command
                    </Button>
                    {copyRecreateState === 'copied' ? (
                      <span className='ui-copy-muted'>Advanced command copied.</span>
                    ) : null}
                    {copyRecreateState === 'failed' ? (
                      <span className='ui-copy-muted'>
                        Copy failed. You can still select and copy the command manually.
                      </span>
                    ) : null}
                  </div>
                  <p className='ui-copy-muted'>
                    Use this if a normal restart does not pick up environment changes.
                  </p>
                </>
              ) : null}
              <Field
                className='asking-admin-login-page__field'
                label={t('admin.login.tokenLabel')}
                htmlFor='asking-admin-setup-page__verify-token'
              >
                <Input
                  id='asking-admin-setup-page__verify-token'
                  type='password'
                  placeholder={t('admin.login.placeholder')}
                  value={adminTokenInput}
                  onChange={(e) => setAdminTokenInput(e.target.value)}
                  className='asking-admin-login-page__token ui-input--stack'
                  aria-label={t('admin.login.tokenLabel')}
                  autoComplete='current-password'
                />
              </Field>
              <div className='asking-admin-login-page__actions'>
                <Button type='submit' disabled={verifyingToken} aria-busy={verifyingToken}>
                  {verifyingToken ? t('admin.login.submitting') : 'Verify token'}
                </Button>
              </div>
            </form>
            {error ? <Alert className='asking-admin-login-page__error'>{error}</Alert> : null}
          </div>
        </Card>

        {showBootstrapForm ? (
          <Card
            as='section'
            className='asking-admin-page__setup-card asking-admin-page__setup-card--compact asking-admin-login-page__bootstrap-card'
            aria-labelledby='asking-admin-setup-page__step-create-admin-heading'
            tone='accent'
          >
            <h2
              className='asking-admin-page__setup-title'
              id='asking-admin-setup-page__step-create-admin-heading'
            >
              Step 3 · Create first admin account
            </h2>
            <p className='asking-admin-login-page__hint'>{t('admin.login.bootstrap.intro')}</p>
            <form
              id='asking-admin-setup-page__bootstrap-account-form'
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
                <Button type='submit' disabled={bootstrapping} aria-busy={bootstrapping}>
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
