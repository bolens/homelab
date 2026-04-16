import AxeBuilder from '@axe-core/playwright';
import { expect, type Page, test } from '@playwright/test';
import { gotoAppPath } from './helpers/appReady';

async function expectNoA11yViolations(pageUrl: string, page: Page) {
  await gotoAppPath(page, pageUrl);
  const results = await new AxeBuilder({ page }).analyze();
  expect(results.violations, JSON.stringify(results.violations, null, 2)).toEqual([]);
}

test.describe('axe', () => {
  test('home', async ({ page }) => {
    await expectNoA11yViolations('/', page);
  });

  test('about', async ({ page }) => {
    await expectNoA11yViolations('/about', page);
  });
});
