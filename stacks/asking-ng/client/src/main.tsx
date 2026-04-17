import { QueryClientProvider } from '@tanstack/react-query';
import React, { Suspense } from 'react';
import ReactDOM from 'react-dom/client';
import 'leaflet/dist/leaflet.css';
import './index.css';
import './ui/ui-kit.css';
import './theme/color-palettes.css';
import './theme/reading-comfort.css';
import { subscribeColorTheme } from './theme/colorTheme';
import { subscribeHighContrast } from './theme/highContrast';
import { subscribeReadingComfort } from './theme/readingComfort';

subscribeColorTheme();
subscribeHighContrast();
subscribeReadingComfort();

import AppSuspenseFallback from './components/AppSuspenseFallback';
import { AdminProvider } from './context/AdminContext';
import { OnlineProvider } from './context/OnlineContext';
import { I18nProvider } from './i18n/I18nContext';
import {
  COOKIE_CONSENT_CHANGED_EVENT,
  type CookieConsentChangedDetail,
  shouldLoadAnalytics,
} from './lib/cookieConsent';
import { initAnalyticsIntegrations } from './lib/umami';
import { queryClient } from './queryClient';
import { reportWebVitals } from './reportWebVitals';
import { AppRouter } from './router';

if (shouldLoadAnalytics()) {
  initAnalyticsIntegrations();
}

if (typeof window !== 'undefined') {
  window.addEventListener(COOKIE_CONSENT_CHANGED_EVENT, (event: Event) => {
    const detail = (event as CustomEvent<CookieConsentChangedDetail>).detail;
    if (detail?.analyticsEnabled) {
      initAnalyticsIntegrations();
    }
  });
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <I18nProvider>
      <OnlineProvider>
        <QueryClientProvider client={queryClient}>
          <AdminProvider>
            <Suspense fallback={<AppSuspenseFallback />}>
              <AppRouter />
            </Suspense>
          </AdminProvider>
        </QueryClientProvider>
      </OnlineProvider>
    </I18nProvider>
  </React.StrictMode>,
);

reportWebVitals();
