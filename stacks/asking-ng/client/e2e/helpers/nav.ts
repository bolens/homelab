import { expect, type Page } from '@playwright/test';

/** Opens the collapsed app nav (small viewports) and the "More" menu when needed so About is visible. */
export async function ensureNavbarExpanded(page: Page): Promise<void> {
  const about = page.locator('#asking-app-navbar__about-link');
  if (await about.isVisible().catch(() => false)) {
    return;
  }

  const nav = page.locator('#asking-app-navbar');
  const toggler = nav.locator('.asking-app-navbar__toggler');
  await toggler.waitFor({ state: 'attached', timeout: 15_000 });
  const box = await toggler.boundingBox();
  if (box && box.width > 1 && box.height > 1) {
    await toggler.click();
  }

  const moreBtn = page.getByRole('button', { name: /^more$/i });
  if (await moreBtn.isVisible().catch(() => false)) {
    await moreBtn.click();
  }

  await expect(about).toBeVisible({ timeout: 15_000 });
}
