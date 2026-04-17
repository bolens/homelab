import { Link } from '@tanstack/react-router';
import PrivacySettingsSection from '../components/PrivacySettingsSection';
import UserSettingsForm from '../components/UserSettingsForm';
import { useDocumentTitle } from '../hooks/useDocumentTitle';
import { useT } from '../i18n/I18nContext';
import { Container, PageHeader, Stack } from '../ui';

export default function Settings() {
  const t = useT();
  useDocumentTitle(t('settings.docTitle'));
  return (
    <Container
      size='md'
      className='ui-page-shell asking-public-layout asking-public-layout--narrow asking-settings-page'
      id='asking-settings-page'
    >
      <Stack gap='lg'>
        <PageHeader
          title={t('nav.settingsTitle')}
          titleId='asking-settings-page__title'
          subtitle={
            <span className='asking-settings-page__lead'>
              <Link to='/'>{t('settings.backHome')}</Link>
            </span>
          }
        />
        <div id='asking-settings-page__user-preferences'>
          <UserSettingsForm className='asking-settings-page__form asking-settings-modal__body' />
        </div>
        <PrivacySettingsSection />
      </Stack>
    </Container>
  );
}
