// Run inside the pinned Paperclip container. The printed invite grants admin access.
import { mkdtempSync, writeFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { spawnSync } from 'node:child_process';

if (!process.env.DATABASE_URL || !process.env.PAPERCLIP_PUBLIC_URL) {
  throw new Error('Run this helper inside the configured Paperclip container');
}
const directory = mkdtempSync(join(tmpdir(), 'paperclip-bootstrap-'));
try {
  const config = join(directory, 'config.json');
  writeFileSync(config, JSON.stringify({
    $meta: { version: 1, updatedAt: new Date().toISOString(), source: 'configure' },
    database: { mode: 'postgres' },
    logging: { mode: 'file' },
    server: { deploymentMode: 'authenticated', exposure: 'public', host: '0.0.0.0', bind: 'lan' },
    auth: { baseUrlMode: 'explicit', publicBaseUrl: process.env.PAPERCLIP_PUBLIC_URL },
  }), { mode: 0o600 });
  const result = spawnSync(process.execPath, [
    'cli/node_modules/tsx/dist/cli.mjs', 'cli/src/index.ts',
    'auth', 'bootstrap-ceo', '--config', config, '--expires-hours', '24',
  ], { cwd: '/app', stdio: 'inherit' });
  if (result.error) throw result.error;
  process.exitCode = result.status ?? 1;
} finally {
  rmSync(directory, { recursive: true });
}
