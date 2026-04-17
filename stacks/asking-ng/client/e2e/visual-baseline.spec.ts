import { expect, test } from '@playwright/test';
import { gotoAppPath } from './helpers/appReady';

const THEMES = ['default', 'tokyo-night'] as const;

const VIEWS = [
  { name: 'home', path: '/' },
  { name: 'about', path: '/about' },
  { name: 'privacy', path: '/privacy' },
  { name: 'terms', path: '/terms' },
  { name: 'developer', path: '/developer' },
] as const;

test.describe('visual baselines', () => {
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

  for (const theme of THEMES) {
    for (const view of VIEWS) {
      test(`${view.name} ${theme}`, async ({ page }) => {
        await gotoAppPath(page, view.path);

        if (theme === 'default') {
          await page.evaluate(() => {
            document.documentElement.removeAttribute('data-color-theme');
          });
        } else {
          await page.evaluate((t) => {
            document.documentElement.setAttribute('data-color-theme', t);
          }, theme);
        }

        await page.evaluate(async () => {
          await document.fonts.ready;
        });

        await expect(page).toHaveScreenshot(`visual-${view.name}-${theme}.png`, {
          fullPage: true,
          animations: 'disabled',
          caret: 'hide',
        });
      });
    }
  }
});
