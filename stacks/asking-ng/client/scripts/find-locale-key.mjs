/**
 * Find translation keys quickly across locale catalogs.
 *
 * Usage (from client/):
 *   pnpm exec tsx scripts/find-locale-key.mjs --key admin.status.heading
 *   pnpm exec tsx scripts/find-locale-key.mjs --prefix admin.status.
 */
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const localesDir = path.join(__dirname, '..', 'src', 'i18n', 'locales');

const LOCALES = [
  ['en.ts', 'en'],
  ['en-gb.ts', 'enGb'],
  ['fr.ts', 'fr'],
  ['es.ts', 'es'],
  ['ga.ts', 'ga'],
  ['de.ts', 'de'],
  ['it.ts', 'it'],
];

function parseArgs(argv) {
  let key = '';
  let prefix = '';
  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg === '--key') key = argv[i + 1] ?? '';
    if (arg === '--prefix') prefix = argv[i + 1] ?? '';
  }
  if ((key === '' && prefix === '') || (key !== '' && prefix !== '')) {
    throw new Error('Provide exactly one of --key <k> or --prefix <p>.');
  }
  return { key, prefix };
}

const load = async (file) => import(pathToFileURL(path.join(localesDir, file)).href);

const { key, prefix } = parseArgs(process.argv.slice(2));
const enMod = await load('en.ts');
const en = enMod.en ?? enMod.default?.en;
if (!en) throw new Error('Could not load English catalog from en.ts');

const targetKeys = key !== '' ? [key] : Object.keys(en).filter((k) => k.startsWith(prefix));
if (targetKeys.length === 0) {
  console.log('No matching keys found.');
  process.exit(0);
}

for (const k of targetKeys) {
  console.log(`\n${k}`);
  for (const [file, exportName] of LOCALES) {
    const mod = await load(file);
    const catalog = mod[exportName] ?? mod.default?.[exportName];
    if (!catalog) {
      console.log(`  ${file}: <missing export ${exportName}>`);
      continue;
    }
    if (!(k in catalog)) {
      console.log(`  ${file}: <missing key>`);
      continue;
    }
    console.log(`  ${file}: ${String(catalog[k])}`);
  }
}
