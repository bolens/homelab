import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests/site',
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  timeout: 30_000,
  use: {
    baseURL: 'http://127.0.0.1:4173/homelab/',
    browserName: 'chromium',
    channel: 'chrome',
    trace: 'retain-on-failure',
    // CI supplies a checksum-verified Google Chrome for Testing executable.
    // Keep the existing Chrome channel and hosted default when no override is set.
    ...(process.env.HOMELAB_CHROME_EXECUTABLE_PATH ? {
      launchOptions: { executablePath: process.env.HOMELAB_CHROME_EXECUTABLE_PATH },
    } : {}),
  },
  webServer: {
    command: 'python3 scripts/serve-pages-site.py --port 4173',
    url: 'http://127.0.0.1:4173/homelab/',
    reuseExistingServer: !process.env.CI,
  },
});
