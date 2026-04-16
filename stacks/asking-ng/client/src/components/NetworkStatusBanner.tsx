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
    <div className='network-offline-banner' role='status' aria-live='polite'>
      <IconWifiOff className='network-offline-banner__icon' aria-hidden />
      <span>{t('app.offlineBanner')}</span>
    </div>
  );
}
