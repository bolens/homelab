import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';

const pages = ['', 'apps/', 'architecture/', 'safety/', 'apps/immich/'];

for (const path of pages) {
  test(`${path || 'home'} has no serious accessibility violations`, async ({ page }) => {
    await page.goto(path);
    const results = await new AxeBuilder({ page }).analyze();
    const violations = results.violations.filter(({ impact }) => ['serious', 'critical'].includes(impact));
    expect(violations).toEqual([]);
  });
}

test('catalog search and category filters work', async ({ page }) => {
  const errors = [];
  page.on('pageerror', (error) => errors.push(error.message));
  await page.goto('apps/');
  await page.getByLabel('Search applications').fill('photo and video backup');
  await expect(page.getByRole('link', { name: 'Immich' })).toBeVisible();
  await expect(page.getByRole('status')).not.toHaveText(/Showing all/);
  await page.getByLabel('Search applications').fill('');
  await page.getByLabel('Category').selectOption({ label: 'Media' });
  await expect(page.getByRole('status')).toHaveText(/Showing \d+ of 217 applications/);
  expect(errors).toEqual([]);
});

test('keyboard users can skip to the main content', async ({ page }) => {
  await page.goto('');
  await page.keyboard.press('Tab');
  await expect(page.getByRole('link', { name: 'Skip to main content' })).toBeFocused();
  await page.keyboard.press('Enter');
  await expect(page.locator('#main')).toBeFocused();
});

test('mobile pages do not overflow horizontally', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  for (const path of ['', 'apps/', 'apps/immich/']) {
    await page.goto(path);
    const dimensions = await page.evaluate(() => ({
      client: document.documentElement.clientWidth,
      scroll: document.documentElement.scrollWidth,
    }));
    expect(dimensions.scroll).toBeLessThanOrEqual(dimensions.client);
  }
});
