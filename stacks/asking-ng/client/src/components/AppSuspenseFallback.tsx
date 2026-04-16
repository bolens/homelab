import React from 'react';
import { useT } from '../i18n/I18nContext';
import { Card, Container } from '../ui';

export default function AppSuspenseFallback() {
  const t = useT();
  return (
    <Container size='sm'>
      <Card role='status' aria-live='polite' className='ui-loading-fallback-card' padding='md'>
        {t('app.loading')}
      </Card>
    </Container>
  );
}
