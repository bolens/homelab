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
      id='asking-settings-modal'
      open={show}
      onClose={onHide}
      titleId='asking-settings-modal__title'
      title={t('nav.settingsTitle')}
      closeAriaLabel={t('nav.closeDialog')}
      bodyClassName='asking-settings-modal__body'
    >
      <div id='asking-settings-modal__user-preferences'>
        <UserSettingsForm />
      </div>
    </Dialog>
  );
}
