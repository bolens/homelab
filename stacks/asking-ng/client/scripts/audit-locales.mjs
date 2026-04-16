/**
 * Locale parity/coverage audit against `src/i18n/locales/en.ts`.
 *
 * Usage (from client/):
 *   node scripts/audit-locales.mjs
 *   node scripts/audit-locales.mjs --fail-on-untranslated
 */
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const localesDir = path.join(__dirname, '..', 'src', 'i18n', 'locales');

const LOCALES = [
  ['en-gb.ts', 'enGb'],
  ['fr.ts', 'fr'],
  ['es.ts', 'es'],
  ['ga.ts', 'ga'],
  ['de.ts', 'de'],
  ['it.ts', 'it'],
];

const PREFIXES = ['nav.', 'login.', 'register.', 'home.', 'myPolls.', 'poll.', 'about.', 'status.', 'admin.', 'developer.'];

const failOnUntranslated = process.argv.includes('--fail-on-untranslated');

const load = async (file) => import(pathToFileURL(path.join(localesDir, file)).href);

const enMod = await load('en.ts');
const en = enMod.en ?? enMod.default?.en;
if (!en) throw new Error('Could not load English catalog from en.ts');

const enKeys = Object.keys(en);
let hasCoverageFailures = false;

for (const [file, exportName] of LOCALES) {
  const mod = await load(file);
  const catalog = mod[exportName] ?? mod.default?.[exportName];
  if (!catalog) throw new Error(`Could not read export "${exportName}" from ${file}`);

  const keys = Object.keys(catalog);
  const missing = enKeys.filter((k) => !(k in catalog));
  const extra = keys.filter((k) => !(k in en));
  const untranslated = enKeys.filter((k) => catalog[k] === en[k]);

  console.log(`\n${file}`);
  console.log(`  missing: ${missing.length}`);
  console.log(`  extra: ${extra.length}`);
  console.log(`  untranslated: ${untranslated.length}`);

  for (const prefix of PREFIXES) {
    const count = untranslated.filter((k) => k.startsWith(prefix)).length;
    if (count > 0) console.log(`    ${prefix} ${count}`);
  }

  if (missing.length > 0 || extra.length > 0 || (failOnUntranslated && untranslated.length > 0)) {
    hasCoverageFailures = true;
  }
}

if (hasCoverageFailures) {
  process.exitCode = 1;
}
