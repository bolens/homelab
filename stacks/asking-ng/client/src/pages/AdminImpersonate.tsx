import { positiveUserIdSchema } from '@asking-ng/contracts/admin';
import { Link } from '@tanstack/react-router';
import React, { useState } from 'react';
import CopyFeedbackButton from '../components/CopyFeedbackButton';
import { useAdmin } from '../context/AdminContext';
import { useDocumentTitle } from '../hooks/useDocumentTitle';
import { apiFetch } from '../http';
import { useT } from '../i18n/I18nContext';
import { Button, Notice, PageHeader, SectionPanel } from '../ui';
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
      <Notice tone='error' className='asking-admin-page__error'>
        {t('admin.impersonate.accessDenied')}
      </Notice>
    );
  }

  return (
    <div className='asking-admin-shell asking-admin-impersonate-page asking-admin-page__cq-root' id='asking-admin-impersonate-page'>
      <PageHeader
        className='asking-admin-page__header'
        titleId='asking-admin-impersonate-page__title'
        titleClassName='asking-admin-page__title'
        subtitleClassName='asking-admin-page__subtitle'
        title={t('admin.impersonate.title')}
        subtitle={t('admin.impersonate.subtitle')}
      />

      <p className='asking-admin-impersonate-page__intro'>{t('admin.impersonate.intro')}</p>

      <SectionPanel
        className='asking-admin-impersonate-page__section'
        titleId='asking-admin-impersonate-page__request-heading'
        title={<span className='asking-admin-page__section-title'>{t('admin.impersonate.sectionRequest')}</span>}
        hint={<span className='asking-admin-page__help-text asking-admin-status-page__section-hint'>{t('admin.impersonate.sectionRequestHint')}</span>}
      >
        <div className='asking-admin-page__card'>
          <form
            id='asking-admin-impersonate-page__request-form'
            onSubmit={(e) => void handleImpersonate(e)}
            aria-label={t('admin.impersonate.ariaForm')}
          >
            <div className='asking-admin-impersonate-page__form-row'>
              <label htmlFor='asking-admin-impersonate-page__user-id' className='asking-admin-impersonate-page__label'>
                {t('admin.impersonate.labelUserId')}
              </label>
              <input
                id='asking-admin-impersonate-page__user-id'
                type='number'
                inputMode='numeric'
                min={1}
                placeholder={t('admin.impersonate.placeholderUserId')}
                value={userId}
                onChange={(e) => setUserId(e.target.value)}
                className='asking-admin-users-page__input asking-admin-impersonate-page__input'
                aria-label={t('admin.impersonate.ariaUserId')}
                required
                disabled={submitting}
              />
            </div>
            <div className='asking-admin-page__card-actions asking-admin-impersonate-page__form-actions'>
              <Button
                type='submit'
                variant='secondary'
                className='asking-admin-page__btn asking-admin-page__download-btn'
                disabled={submitting}
                aria-label={t('admin.impersonate.submitAria')}
              >
                {submitting ? t('admin.impersonate.generating') : t('admin.impersonate.submit')}
              </Button>
            </div>
          </form>

          {error ? (
            <Notice tone='error' className='asking-admin-page__banner-error asking-admin-impersonate-page__form-error'>
              {error}
            </Notice>
          ) : null}

          <p className='asking-admin-impersonate-page__footer-link'>
            <Link to='/admin/users' className='asking-admin-page__jump-link'>
              {t('admin.impersonate.linkUsers')}
            </Link>
          </p>
        </div>
      </SectionPanel>

      {token ? (
        <SectionPanel
          className='asking-admin-impersonate-page__section'
          titleId='asking-admin-impersonate-page__token-heading'
          title={<span className='asking-admin-page__section-title'>{t('admin.impersonate.tokenTitle')}</span>}
          hint={<span className='asking-admin-page__help-text asking-admin-status-page__section-hint'>{t('admin.impersonate.tokenHint')}</span>}
        >
          <Notice tone='success' className='asking-admin-export-page__success asking-admin-impersonate-page__token-panel'>
            <textarea
              id='asking-admin-impersonate-page__jwt'
              value={token}
              readOnly
              className='asking-admin-impersonate-page__token'
              aria-label={t('admin.impersonate.jwtAria')}
            />
            <div className='asking-admin-impersonate-page__token-actions'>
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
                className='asking-admin-page__btn asking-admin-page__dismiss-btn'
                onClick={() => {
                  setToken('');
                  setError('');
                }}
              >
                {t('admin.impersonate.dismissToken')}
              </Button>
            </div>
          </Notice>
        </SectionPanel>
      ) : null}
    </div>
  );
}
