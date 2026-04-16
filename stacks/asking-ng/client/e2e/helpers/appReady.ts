import type { Page } from '@playwright/test';

/**
 * Navigate and wait until the shell has rendered. `Navbar` sits outside `<main>`, so we wait for
 * both to avoid racing collapsed-nav / axe runs on a half-mounted tree.
 */
export async function gotoAppPath(page: Page, path: string): Promise<void> {
  await page.goto(path);
  await page.getByRole('main').waitFor({ state: 'visible', timeout: 30_000 });
  await page.locator('nav.navbar').waitFor({ state: 'attached', timeout: 30_000 });
}
