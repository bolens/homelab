import { expect, test } from '@playwright/test';
import { gotoAppPath } from './helpers/appReady';
import { ensureNavbarExpanded } from './helpers/nav';

test('home shows navigation', async ({ page }) => {
  await gotoAppPath(page, '/');
  await ensureNavbarExpanded(page);
  await expect(page.locator('#asking-app-navbar__about-link')).toBeVisible();
});
