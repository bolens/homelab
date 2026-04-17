import { authRegisterBodySchema } from '@asking-ng/contracts/auth';
import { Link, useNavigate } from '@tanstack/react-router';
import { useState, type FormEvent } from 'react';
import { useDocumentTitle } from '../hooks/useDocumentTitle';
import { apiFetch } from '../http';
import { useT } from '../i18n/I18nContext';
import { setStoredUserJwt } from '../lib/userSession';
import { Alert, Button, Checkbox, Container, Input, Stack, VisuallyHidden } from '../ui';
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
    <Container size='sm' className='ui-page-shell asking-register-page' id='asking-register-page'>
      <h1 className='ui-page-heading ui-page-heading--center' id='asking-auth-page__title'>
        {t('register.title')}
      </h1>
      <p className='ui-copy-muted asking-auth-page__links'>
        <Link to='/login'>{t('register.loginCta')}</Link>
        {' · '}
        <Link to='/'>{t('register.backHome')}</Link>
      </p>
      <form
        id='asking-register-page__form'
        onSubmit={handleSubmit}
        aria-label={t('register.formAria')}
        className='asking-auth-page__form'
      >
        <Stack gap='md'>
          <VisuallyHidden as='label' htmlFor='asking-auth-page__homelab-user'>
            {t('register.homelab-user')}
          </VisuallyHidden>
          <Input
            id='asking-auth-page__homelab-user'
            className='ui-input--stack'
            autoComplete='homelab-user'
            value={homelab-user}
            onChange={(e) => setUsername(e.target.value)}
            placeholder={t('register.homelab-user')}
          />
          <VisuallyHidden as='label' htmlFor='asking-auth-page__password'>
            {t('register.passwordHint')}
          </VisuallyHidden>
          <Input
            id='asking-auth-page__password'
            type='password'
            className='ui-input--stack'
            autoComplete='new-password'
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder={t('register.passwordHint')}
          />
          <Checkbox
            id='asking-auth-page__accept-terms'
            checked={acceptTermsAndPrivacy}
            onChange={(e) => setAcceptTermsAndPrivacy(e.target.checked)}
            aria-label={t('register.acceptAria')}
            label={termsLabel}
            containerClassName='asking-auth-page__terms-checkbox'
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
          {error ? <Alert>{error}</Alert> : null}
        </Stack>
      </form>
    </Container>
  );
}
