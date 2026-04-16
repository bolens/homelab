import fs from 'node:fs';
import path from 'node:path';

/**
 * @param {string} clientRoot Absolute path to client package root
 */
export function readEnText(clientRoot) {
  const enPath = path.join(clientRoot, 'src/i18n/locales/en.ts');
  return { enText: fs.readFileSync(enPath, 'utf8'), enPath };
}

/** @param {string} enText */
export function parseEnCatalog(enText) {
  const match = enText.match(/export const en = \{([\s\S]*?)\} as const;/);
  if (!match) throw new Error('Could not parse en.ts');
  return Function(`return ({${match[1]}});`)();
}

/** Key order follows `en.ts` source (stable diffs vs `en`). */
export function listEnKeysInSourceOrder(enText) {
  const keyRe = /^\s+'([^']+)':\s/gm;
  const keys = [];
  let m;
  while ((m = keyRe.exec(enText)) !== null) keys.push(m[1]);
  return keys;
}

/**
 * @param {Record<string, string>} overrides
 * @param {Set<string>} enKeySet
 * @param {string} localeId
 */
export function assertOverrideKeysSubset(overrides, enKeySet, localeId) {
  for (const k of Object.keys(overrides)) {
    if (!enKeySet.has(k)) {
      throw new Error(`[${localeId}] Override key not in en.ts: ${k}`);
    }
  }
}

/**
 * @param {Record<string, string>} enCatalog
 * @param {Record<string, string>} overrides
 */
export function mergePartialCatalog(enCatalog, overrides) {
  /** @type {Record<string, string>} */
  const out = {};
  for (const k of Object.keys(enCatalog)) {
    out[k] = overrides[k] !== undefined ? overrides[k] : enCatalog[k];
  }
  return out;
}

function escapeTsSingleQuoted(s) {
  return String(s)
    .replace(/\\/g, '\\\\')
    .replace(/'/g, "\\'")
    .replace(/\r?\n/g, '\\n');
}

/**
 * @param {{ id: string, label: string, keysInOrder: string[], merged: Record<string, string> }} p
 */
export function formatLocaleTs({ id, label, keysInOrder, merged }) {
  const lines = [
    `/** ${label} UI strings (same keys as {@link ./en}). */`,
    "import { en } from './en';",
    '',
    `const ${id}Overrides = {`,
  ];
  for (const k of keysInOrder) {
    const v = merged[k];
    if (v === undefined) throw new Error(`Missing value for en key: ${k}`);
    const esc = escapeTsSingleQuoted(v);
    const keyLit = `'${k.replace(/'/g, "\\'")}'`;
    if (String(v).includes('\n')) {
      lines.push(`  ${keyLit}:`);
      lines.push(`    '${esc}',`);
    } else {
      lines.push(`  ${keyLit}: '${esc}',`);
    }
  }
  lines.push('} satisfies Record<keyof typeof en, string>;', '');
  lines.push(
    `export const ${id} = { ...en, ...${id}Overrides } satisfies Record<keyof typeof en, string>;`,
    '',
  );
  return lines.join('\n');
}
