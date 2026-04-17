import React from 'react';
import { useOnline } from '../context/OnlineContext';
import { useT } from '../i18n/I18nContext';
import { IconWifiOff } from './icons/UiIcons';

/** Announces connectivity; pausing refetch is handled where queries run (e.g. Poll page). */
export default function NetworkStatusBanner() {
  const online = useOnline();
  const t = useT();

  if (online) return null;

  return (
    <div
      className='asking-network-banner asking-network-banner--offline'
      id='asking-app__network-status'
      role='status'
      aria-live='polite'
    >
      <IconWifiOff className='asking-network-banner__icon' aria-hidden />
      <span>{t('app.offlineBanner')}</span>
    </div>
  );
}
