import { Link } from '@tanstack/react-router';
import PrivacySettingsSection from '../components/PrivacySettingsSection';
import UserSettingsForm from '../components/UserSettingsForm';
import { useDocumentTitle } from '../hooks/useDocumentTitle';
import { useT } from '../i18n/I18nContext';
import { Container, Stack } from '../ui';

export default function Settings() {
  const t = useT();
  useDocumentTitle(t('settings.docTitle'));
  return (
    <Container size='md' className='ui-page-shell page-narrow settings-page'>
      <Stack gap='lg'>
        <header>
          <h1 className='poll-header'>{t('nav.settingsTitle')}</h1>
          <p className='settings-page-lead'>
            <Link to='/'>{t('settings.backHome')}</Link>
          </p>
        </header>
        <UserSettingsForm className='settings-page-form app-settings-modal-body' />
        <PrivacySettingsSection />
      </Stack>
    </Container>
  );
}
