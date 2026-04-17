import { expect, test } from '@playwright/test';
import { gotoAppPath } from './helpers/appReady';
import { ensureNavbarExpanded } from './helpers/nav';

test('login page is usable on small viewports', async ({ page }) => {
  await gotoAppPath(page, '/login');
  await expect(page.locator('#asking-auth-page__title')).toBeVisible();
  await expect(page.getByLabel(/homelab-user/i)).toBeVisible();
  await expect(page.getByLabel(/password/i)).toBeVisible();
  await expect(page.getByRole('button', { name: /(log in|sign in)/i })).toBeVisible();
});

test('register page is usable on small viewports', async ({ page }) => {
  await gotoAppPath(page, '/register');
  await expect(page.locator('#asking-auth-page__title')).toBeVisible();
  await expect(page.getByLabel(/homelab-user/i)).toBeVisible();
  await expect(page.getByLabel(/password/i)).toBeVisible();
  await expect(
    page.getByRole('checkbox', { name: /terms of use and privacy policy/i }),
  ).toBeVisible();
  await expect(page.getByRole('button', { name: /^register$/i })).toBeVisible();
});

test('my-polls prompts sign in when logged out', async ({ page }) => {
  await gotoAppPath(page, '/my-polls');
  await expect(page.locator('#asking-my-polls-page__login-required')).toBeVisible();
  await expect(
    page.locator('#asking-app__main').getByRole('link', { name: /sign in/i }),
  ).toBeVisible();
});

test('collapsed navbar exposes auth links', async ({ page }) => {
  await gotoAppPath(page, '/');
  await ensureNavbarExpanded(page);
  const nav = page.locator('#asking-app-navbar__drawer');
  await expect(nav.getByRole('link', { name: /sign in/i })).toBeVisible();
  await expect(nav.locator('#asking-app-navbar__about-link')).toBeVisible();
});
