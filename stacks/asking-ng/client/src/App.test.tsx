import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import React, { Suspense } from 'react';
import { AdminProvider } from './context/AdminContext';
import { OnlineProvider } from './context/OnlineContext';
import { I18nProvider } from './i18n/I18nContext';
import { AppRouter } from './router';

function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
}

test('renders app shell', async () => {
  const queryClient = createTestQueryClient();
  render(
    <I18nProvider>
      <OnlineProvider>
        <QueryClientProvider client={queryClient}>
          <AdminProvider>
            <Suspense fallback={null}>
              <AppRouter />
            </Suspense>
          </AdminProvider>
        </QueryClientProvider>
      </OnlineProvider>
    </I18nProvider>,
  );
  expect(await screen.findByRole('navigation')).toBeInTheDocument();
});
