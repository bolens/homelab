import { positiveUserIdSchema } from '@asking-ng/contracts/admin';
import { Link } from '@tanstack/react-router';
import React, { useState } from 'react';
import CopyFeedbackButton from '../components/CopyFeedbackButton';
import { useAdmin } from '../context/AdminContext';
import { useDocumentTitle } from '../hooks/useDocumentTitle';
import { apiFetch } from '../http';
import { useT } from '../i18n/I18nContext';
import { Button } from '../ui';
import { errMsg } from '../utils/errMsg';

type ImpersonateResponse = { token: string };

export default function AdminImpersonate() {
  const t = useT();
  useDocumentTitle(t('admin.docTitleImpersonate'));
  const { admin } = useAdmin();
  const [userId, setUserId] = useState('');
  const [token, setToken] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const handleImpersonate = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setToken('');
    const parsed = positiveUserIdSchema.safeParse(userId);
    if (!parsed.success) {
      setError(t('admin.impersonate.errUserId'));
      return;
    }
    setSubmitting(true);
    try {
      const data = (await apiFetch(`admin/impersonate/${parsed.data}`, {
        method: 'POST',
        body: {},
      })) as ImpersonateResponse;
      setToken(data.token);
    } catch (err) {
      setError(errMsg(err, t('admin.impersonate.errFail')));
    } finally {
      setSubmitting(false);
    }
  };

  if (!admin || admin.role !== 'superadmin') {
    return (
      <div className='polls-page-container-error' role='alert'>
        {t('admin.impersonate.accessDenied')}
      </div>
    );
  }

  return (
    <div className='admin-users-container admin-impersonate-page'>
      <header className='admin-page-header'>
        <h1 className='admin-page-title'>{t('admin.impersonate.title')}</h1>
        <p className='admin-page-subtitle'>{t('admin.impersonate.subtitle')}</p>
      </header>

      <p className='admin-impersonate-intro'>{t('admin.impersonate.intro')}</p>

      <section
        className='admin-impersonate-section'
        aria-labelledby='admin-impersonate-request-heading'
      >
        <h2 id='admin-impersonate-request-heading' className='admin-export-section-title'>
          {t('admin.impersonate.sectionRequest')}
        </h2>
        <p className='admin-help-text admin-status-section-hint'>
          {t('admin.impersonate.sectionRequestHint')}
        </p>

        <div className='admin-export-card'>
          <form
            onSubmit={(e) => void handleImpersonate(e)}
            aria-label={t('admin.impersonate.ariaForm')}
          >
            <div className='admin-impersonate-form-row'>
              <label htmlFor='impersonate-user-id' className='admin-impersonate-label'>
                {t('admin.impersonate.labelUserId')}
              </label>
              <input
                id='impersonate-user-id'
                type='number'
                inputMode='numeric'
                min={1}
                placeholder={t('admin.impersonate.placeholderUserId')}
                value={userId}
                onChange={(e) => setUserId(e.target.value)}
                className='admin-users-input admin-impersonate-input'
                aria-label={t('admin.impersonate.ariaUserId')}
                required
                disabled={submitting}
              />
            </div>
            <div className='admin-export-card-actions admin-impersonate-form-actions'>
              <Button
                type='submit'
                variant='secondary'
                className='admin-users-btn admin-export-dl-btn'
                disabled={submitting}
                aria-label={t('admin.impersonate.submitAria')}
              >
                {submitting ? t('admin.impersonate.generating') : t('admin.impersonate.submit')}
              </Button>
            </div>
          </form>

          {error ? (
            <div className='admin-banner-error admin-impersonate-form-error' role='alert'>
              {error}
            </div>
          ) : null}

          <p className='admin-impersonate-footer-link'>
            <Link to='/admin/users' className='admin-jump-link'>
              {t('admin.impersonate.linkUsers')}
            </Link>
          </p>
        </div>
      </section>

      {token ? (
        <section
          className='admin-impersonate-section'
          aria-labelledby='admin-impersonate-token-heading'
        >
          <h2 id='admin-impersonate-token-heading' className='admin-export-section-title'>
            {t('admin.impersonate.tokenTitle')}
          </h2>
          <p className='admin-help-text admin-status-section-hint'>
            {t('admin.impersonate.tokenHint')}
          </p>
          <div className='admin-export-success admin-impersonate-token-panel'>
            <textarea
              value={token}
              readOnly
              className='admin-impersonate-token'
              aria-label={t('admin.impersonate.jwtAria')}
            />
            <div className='admin-impersonate-token-actions'>
              <CopyFeedbackButton
                disabled={submitting}
                onCopy={async () => {
                  try {
                    await navigator.clipboard.writeText(token);
                    return true;
                  } catch {
                    return false;
                  }
                }}
              >
                {t('admin.impersonate.copyToken')}
              </CopyFeedbackButton>
              <Button
                type='button'
                variant='secondary'
                className='admin-users-btn admin-export-dismiss'
                onClick={() => {
                  setToken('');
                  setError('');
                }}
              >
                {t('admin.impersonate.dismissToken')}
              </Button>
            </div>
          </div>
        </section>
      ) : null}
    </div>
  );
}
