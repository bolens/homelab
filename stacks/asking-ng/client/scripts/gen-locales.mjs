/**
 * Merge `scripts/locale-data/<id>.mjs` partial overrides into the English catalog and emit
 * `src/i18n/locales/<id>.ts` (same shape as `fr.ts`: `{id}Overrides` + spread export).
 *
 * French: edit `src/i18n/locales/fr.ts` directly (full catalog). The old `gen-fr-overrides.mjs`
 * duplicated translations and drifted from `en.ts`; it was removed.
 *
 * Usage (from `client/`):
 *   node scripts/gen-locales.mjs           # validate only
 *   node scripts/gen-locales.mjs --write   # overwrite es, ga, de, it
 *
 * `--write` replaces those files with partial translations + English fallbacks — only use when
 * you mean to refresh stub catalogs, not when you already have full hand translations.
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import de from './locale-data/de.mjs';
import es from './locale-data/es.mjs';
import ga from './locale-data/ga.mjs';
import it from './locale-data/it.mjs';
import {
  assertOverrideKeysSubset,
  formatLocaleTs,
  listEnKeysInSourceOrder,
  mergePartialCatalog,
  parseEnCatalog,
  readEnText,
} from './lib/locale-gen.mjs';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const clientRoot = path.join(__dirname, '..');

const SPECS = [de, es, ga, it];

function main() {
  const write = process.argv.includes('--write');
  const { enText } = readEnText(clientRoot);
  const enCatalog = parseEnCatalog(enText);
  const keysInOrder = listEnKeysInSourceOrder(enText);
  const enKeySet = new Set(keysInOrder);

  if (keysInOrder.length !== Object.keys(enCatalog).length) {
    throw new Error(
      `en.ts key count mismatch: source order ${keysInOrder.length}, parsed object ${Object.keys(enCatalog).length}`,
    );
  }

  for (const spec of SPECS) {
    if (!spec?.id || !spec?.label || spec.overrides === undefined) {
      throw new Error('Each locale module must export default { id, label, overrides }');
    }
    assertOverrideKeysSubset(spec.overrides, enKeySet, spec.id);
    const merged = mergePartialCatalog(enCatalog, spec.overrides);
    const ts = formatLocaleTs({
      id: spec.id,
      label: spec.label,
      keysInOrder,
      merged,
    });
    const outPath = path.join(clientRoot, `src/i18n/locales/${spec.id}.ts`);
    if (write) {
      fs.writeFileSync(outPath, ts, 'utf8');
      console.log('Wrote', outPath);
    } else {
      console.log(`OK ${spec.id} (${keysInOrder.length} keys) -> ${outPath}`);
    }
  }

  if (!write) {
    console.log(
      '\nFrench (fr): maintain src/i18n/locales/fr.ts directly (not generated from locale-data).',
    );
    console.log('Re-run with --write to apply es, ga, de, it.');
  }
}

main();
