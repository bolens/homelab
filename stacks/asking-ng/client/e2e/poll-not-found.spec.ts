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
  await expect(page.getByRole('heading', { name: /poll not found/i })).toBeVisible();
  await expect(page.getByRole('link', { name: /create a new poll/i })).toBeVisible();
});
