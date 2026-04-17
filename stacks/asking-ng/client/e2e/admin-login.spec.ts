import { expect, test } from '@playwright/test';
import { gotoAppPath } from './helpers/appReady';

test('admin login reaches dashboard when E2E_ADMIN_TOKEN is set', async ({ page }) => {
  const token = process.env['E2E_ADMIN_TOKEN']?.trim();
  test.skip(!token, 'Set E2E_ADMIN_TOKEN to run admin login e2e');

  await gotoAppPath(page, '/admin/login');
  await page.locator('#asking-admin-login-page__token').fill(token!);
  await page.getByRole('button', { name: /^login$/i }).click();
  await expect(page).toHaveURL(/\/admin\/?$/);
  await expect(page.locator('#asking-admin-dashboard-page__title')).toBeVisible();
});
