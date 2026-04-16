import { authLoginBodySchema } from '@asking-ng/contracts/auth';
import { Link, useNavigate } from '@tanstack/react-router';
import { useState, type FormEvent } from 'react';
import { useDocumentTitle } from '../hooks/useDocumentTitle';
import { apiFetch } from '../http';
import { useT } from '../i18n/I18nContext';
import { setStoredUserJwt } from '../lib/userSession';
import { Button, Container, Input, Stack, VisuallyHidden } from '../ui';
import { errMsg } from '../utils/errMsg';

export default function Login() {
  const t = useT();
  const navigate = useNavigate();
  useDocumentTitle(t('login.docTitle'));
  const [homelab-user, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    setError('');
    const parsed = authLoginBodySchema.safeParse({ homelab-user: homelab-user.trim(), password });
    if (!parsed.success) {
      setError(t('login.err.invalid'));
      return;
    }
    setSubmitting(true);
    void apiFetch('auth/login', {
      method: 'POST',
      body: parsed.data,
      adminToken: false,
    })
      .then((data) => {
        const d = data as { token?: string };
        if (!d.token) {
          setError(t('login.err.noToken'));
          return;
        }
        setStoredUserJwt(d.token);
        void navigate({ to: '/my-polls' });
      })
      .catch((err: unknown) => {
        setError(errMsg(err, t('login.err.fail')));
      })
      .finally(() => setSubmitting(false));
  };

  return (
    <Container size='sm' className='ui-page-shell'>
      <h1 className='ui-page-heading ui-page-heading--center'>{t('login.title')}</h1>
      <p className='ui-copy-muted auth-links'>
        <Link to='/register'>{t('login.registerCta')}</Link>
        {' · '}
        <Link to='/'>{t('login.backHome')}</Link>
      </p>
      <form onSubmit={handleSubmit} aria-label={t('login.formAria')} className='auth-form'>
        <Stack gap='md'>
          <VisuallyHidden as='label' htmlFor='login-homelab-user'>
            {t('login.homelab-user')}
          </VisuallyHidden>
          <Input
            id='login-homelab-user'
            className='ui-input--stack'
            autoComplete='homelab-user'
            value={homelab-user}
            onChange={(e) => setUsername(e.target.value)}
            placeholder={t('login.homelab-user')}
          />
          <VisuallyHidden as='label' htmlFor='login-password'>
            {t('login.password')}
          </VisuallyHidden>
          <Input
            id='login-password'
            type='password'
            className='ui-input--stack'
            autoComplete='current-password'
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder={t('login.password')}
          />
          <Button
            type='submit'
            variant='primary'
            size='lg'
            fullWidth
            className='ui-button--lane-primary'
            disabled={submitting}
            aria-busy={submitting}
          >
            {submitting ? t('login.submitting') : t('login.submit')}
          </Button>
          {error ? (
            <p className='error-message' role='alert'>
              {error}
            </p>
          ) : null}
        </Stack>
      </form>
    </Container>
  );
}
