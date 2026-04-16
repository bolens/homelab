import { authRegisterBodySchema } from '@asking-ng/contracts/auth';
import { Link, useNavigate } from '@tanstack/react-router';
import { useState, type FormEvent } from 'react';
import { useDocumentTitle } from '../hooks/useDocumentTitle';
import { apiFetch } from '../http';
import { useT } from '../i18n/I18nContext';
import { setStoredUserJwt } from '../lib/userSession';
import { Button, Checkbox, Container, Input, Stack } from '../ui';
import { errMsg } from '../utils/errMsg';

export default function Register() {
  const t = useT();
  const navigate = useNavigate();
  useDocumentTitle(t('register.docTitle'));
  const [homelab-user, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [acceptTermsAndPrivacy, setAcceptTermsAndPrivacy] = useState(false);
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    setError('');
    const parsed = authRegisterBodySchema.safeParse({
      homelab-user: homelab-user.trim(),
      password,
      acceptTermsAndPrivacy,
    });
    if (!parsed.success) {
      const issue = parsed.error.issues[0];
      setError(issue?.message || t('register.err.invalid'));
      return;
    }
    setSubmitting(true);
    void apiFetch('auth/register', {
      method: 'POST',
      body: parsed.data,
      adminToken: false,
    })
      .then((data) => {
        const d = data as { token?: string };
        if (!d.token) {
          setError(t('register.err.noToken'));
          return;
        }
        setStoredUserJwt(d.token);
        void navigate({ to: '/my-polls' });
      })
      .catch((err: unknown) => {
        setError(errMsg(err, t('register.err.fail')));
      })
      .finally(() => setSubmitting(false));
  };

  const termsLabel = (
    <>
      {t('register.acceptTermsBefore')}{' '}
      <Link to='/terms'>{t('nav.terms')}</Link>
      {t('register.acceptTermsMiddle')}{' '}
      <Link to='/privacy'>{t('nav.privacy')}</Link>
      {t('register.acceptTermsAfter')}
    </>
  );

  return (
    <Container size='sm' className='ui-page-shell'>
      <h1 className='ui-page-heading ui-page-heading--center'>{t('register.title')}</h1>
      <p className='ui-copy-muted auth-links'>
        <Link to='/login'>{t('register.loginCta')}</Link>
        {' · '}
        <Link to='/'>{t('register.backHome')}</Link>
      </p>
      <form onSubmit={handleSubmit} aria-label={t('register.formAria')} className='auth-form'>
        <Stack gap='md'>
          <label htmlFor='reg-homelab-user' className='visually-hidden'>
            {t('register.homelab-user')}
          </label>
          <Input
            id='reg-homelab-user'
            className='ui-input--stack'
            autoComplete='homelab-user'
            value={homelab-user}
            onChange={(e) => setUsername(e.target.value)}
            placeholder={t('register.homelab-user')}
          />
          <label htmlFor='reg-password' className='visually-hidden'>
            {t('register.passwordHint')}
          </label>
          <Input
            id='reg-password'
            type='password'
            className='ui-input--stack'
            autoComplete='new-password'
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder={t('register.passwordHint')}
          />
          <Checkbox
            id='reg-accept-terms'
            checked={acceptTermsAndPrivacy}
            onChange={(e) => setAcceptTermsAndPrivacy(e.target.checked)}
            aria-label={t('register.acceptAria')}
            label={termsLabel}
            containerClassName='auth-terms-checkbox'
          />
          <Button
            type='submit'
            variant='primary'
            size='lg'
            fullWidth
            className='ui-button--lane-primary'
            disabled={submitting || !acceptTermsAndPrivacy}
            aria-busy={submitting}
          >
            {submitting ? t('register.submitting') : t('register.submit')}
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
