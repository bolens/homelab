import { cpus } from 'node:os';
import { defineConfig, devices } from '@playwright/test';

const webkitExtraLibs =
  process.env['PLAYWRIGHT_WEBKIT_EXTRA_LIBS'] ??
  (process.env['HOME'] ? `${process.env['HOME']}/.local/lib/playwright-webkit-extras` : '');
const webkitLdLibraryPath = [webkitExtraLibs, process.env['LD_LIBRARY_PATH'] ?? '']
  .filter((v) => v.length > 0)
  .join(':');

/**
 * iPhone / WebKit project (opt-in locally via `PLAYWRIGHT_WEBKIT=1` or `pnpm run e2e:webkit`).
 *
 * - **Ubuntu / CI:** `playwright install --with-deps webkit` satisfies ICU 74, WPE, flite, jxl, etc.
 * - **Arch / CachyOS:** after AUR `icu74` + repo `libjxl`, typical gaps are:
 *   - **WPE (GTK WebKit pulls these):** `paru -S --needed wpewebkit libwpe wpebackend-fdo`
 *   - **`libjxl.so.0.8`:** if `ls /usr/lib/libjxl.so*` has no `*.0.8`, either symlink the repo `.so`
 *     (risky) or add Ubuntu’s `libjxl0.8` `.so` into an extras dir (same idea as flite below).
 *   - **`libflite_cmu_*` + `libjxl.so.0.8`:** run `bash e2e/scripts/sync-webkit-ubuntu-libs.sh` (needs podman or docker),
 *     then `LD_LIBRARY_PATH=$HOME/.local/lib/playwright-webkit-extras:$LD_LIBRARY_PATH pnpm run e2e:webkit`.
 *   Check: `ldd ~/.cache/ms-playwright/webkit-*\/minibrowser-gtk/lib/libwebkitgtk-6.0.so* | rg 'not found'`
 */
const webkitProject =
  process.env['PLAYWRIGHT_WEBKIT'] === '1'
    ? ([
        {
          name: 'mobile-webkit',
          use: {
            ...devices['iPhone 12'],
            launchOptions: {
              env: {
                ...process.env,
                LD_LIBRARY_PATH: webkitLdLibraryPath,
              },
            },
          },
        },
      ] as const)
    : [];

export default defineConfig({
  testDir: 'e2e',
  fullyParallel: true,
  forbidOnly: !!process.env['CI'],
  retries: process.env['CI'] ? 2 : 0,
  workers: process.env['CI'] ? 1 : Math.min(4, Math.max(1, cpus().length)),
  reporter: 'list',
  timeout: 60_000,
  use: {
    baseURL: 'http://127.0.0.1:5179',
    trace: 'on-first-retry',
  },
  projects: [
    {
      name: 'desktop-chrome',
      use: { ...devices['Desktop Chrome'] },
    },
    {
      name: 'mobile-chrome',
      use: { ...devices['Pixel 7'] },
    },
    ...webkitProject,
  ],
  webServer: {
    command: 'pnpm exec vp dev -- --host 127.0.0.1 --port 5179',
    url: 'http://127.0.0.1:5179',
    reuseExistingServer: !process.env['CI'],
  },
});
