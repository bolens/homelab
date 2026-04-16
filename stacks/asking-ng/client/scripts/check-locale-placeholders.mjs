/**
 * Validate placeholder parity against `src/i18n/locales/en.ts`.
 *
 * Uses the same placeholder grammar as runtime interpolation in `en.ts`:
 *   /\{(\w+)\}/g
 *
 * Usage (from client/):
 *   node scripts/check-locale-placeholders.mjs
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

const PLACEHOLDER_RE = /\{(\w+)\}/g;

const load = async (file) => import(pathToFileURL(path.join(localesDir, file)).href);

const placeholders = (text) => new Set([...String(text).matchAll(PLACEHOLDER_RE)].map((m) => m[1]));

const setsEqual = (a, b) => a.size === b.size && [...a].every((x) => b.has(x));

const formatSet = (s) => [...s].sort().join(', ');

const enMod = await load('en.ts');
const en = enMod.en ?? enMod.default?.en;
if (!en) throw new Error('Could not load English catalog from en.ts');

let hasFailures = false;
const enKeys = Object.keys(en);

for (const [file, exportName] of LOCALES) {
  const mod = await load(file);
  const catalog = mod[exportName] ?? mod.default?.[exportName];
  if (!catalog) throw new Error(`Could not read export "${exportName}" from ${file}`);

  const mismatches = [];
  for (const key of enKeys) {
    const enSet = placeholders(en[key]);
    const localeSet = placeholders(catalog[key]);
    if (!setsEqual(enSet, localeSet)) {
      mismatches.push({ key, enSet, localeSet });
    }
  }

  console.log(`\n${file}`);
  console.log(`  placeholder mismatches: ${mismatches.length}`);
  for (const row of mismatches) {
    console.log(`    ${row.key}`);
    console.log(`      en:  ${formatSet(row.enSet) || '(none)'}`);
    console.log(`      loc: ${formatSet(row.localeSet) || '(none)'}`);
  }

  if (mismatches.length > 0) hasFailures = true;
}

if (hasFailures) process.exitCode = 1;
