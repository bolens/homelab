import AxeBuilder from '@axe-core/playwright';
import { expect, type Page, test } from '@playwright/test';
import { gotoAppPath } from './helpers/appReady';

async function expectNoA11yViolations(pageUrl: string, page: Page) {
  await gotoAppPath(page, pageUrl);
  const results = await new AxeBuilder({ page }).analyze();
  expect(results.violations, JSON.stringify(results.violations, null, 2)).toEqual([]);
}

test.describe('axe', () => {
  test.beforeEach(async ({ page }) => {
    await page.route('**/admin/bootstrap-status', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ bootstrapRequired: false }),
      });
    });
    await page.route('**/telemetry/consent-region', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ region: 'unknown' }),
      });
    });
    await page.route('**/llm/status', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ provider: 'none', gatewayAuth: false }),
      });
    });
    await page.addInitScript(() => {
      try {
        localStorage.setItem(
          'asking-ng-cookie-consent',
          JSON.stringify({
            v: 2,
            analytics: true,
            functional: true,
            marketing: false,
          }),
        );
      } catch {
        // noop in constrained contexts
      }
    });
  });

  test('home', async ({ page }) => {
    await expectNoA11yViolations('/', page);
  });

  test('about', async ({ page }) => {
    await expectNoA11yViolations('/about', page);
  });
});
