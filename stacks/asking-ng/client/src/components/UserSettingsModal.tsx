import { useT } from '../i18n/I18nContext';
import { Dialog } from '../ui';
import UserSettingsForm from './UserSettingsForm';

type UserSettingsModalProps = {
  show: boolean;
  onHide: () => void;
};

export default function UserSettingsModal({ show, onHide }: UserSettingsModalProps) {
  const t = useT();
  return (
    <Dialog
      open={show}
      onClose={onHide}
      titleId='user-settings-title'
      title={t('nav.settingsTitle')}
      closeAriaLabel={t('nav.closeDialog')}
      bodyClassName='app-settings-modal-body'
    >
      <UserSettingsForm />
    </Dialog>
  );
}
