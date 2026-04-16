import { expect, type Page } from '@playwright/test';

/** Opens the collapsed Bootstrap nav (small viewports) and the "More" menu when needed so About is visible. */
export async function ensureNavbarExpanded(page: Page): Promise<void> {
  const about = page.getByRole('link', { name: /^about$/i });
  if (await about.isVisible().catch(() => false)) {
    return;
  }

  const toggler = page.locator('.navbar-toggler');
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
