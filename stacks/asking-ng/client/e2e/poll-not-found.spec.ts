import { expect, test } from '@playwright/test';
import { gotoAppPath } from './helpers/appReady';

const missingId = 'e2e-missing-poll-id';

test('poll page shows not found when API returns 404', async ({ page }) => {
  await page.route(`**/poll/${missingId}`, async (route) => {
    await route.fulfill({
      status: 404,
      contentType: 'application/json',
      body: JSON.stringify({
        error: { code: 'NOT_FOUND', message: 'Poll not found' },
        requestId: 'e2e',
      }),
    });
  });

  await gotoAppPath(page, `/${missingId}`);
  const pollShell = page.locator('#asking-poll-page');
  await expect(pollShell.locator('#asking-poll-page__title')).toContainText(/poll not found/i);
  await expect(pollShell.getByRole('link', { name: /create a new poll/i })).toBeVisible();
});
