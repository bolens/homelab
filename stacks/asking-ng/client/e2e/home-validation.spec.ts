import { expect, test } from '@playwright/test';
import { gotoAppPath } from './helpers/appReady';

test('create poll shows validation when answers are missing', async ({ page }) => {
  await gotoAppPath(page, '/');
  await page.locator('#asking-home-page__poll-title').fill('E2E validation question');
  await page.locator('#asking-home-page__create-poll-form').getByRole('button', { name: /create poll/i }).click();
  await expect(page.getByText(/at least 2 non-empty answers/i)).toBeVisible({ timeout: 15_000 });
});
