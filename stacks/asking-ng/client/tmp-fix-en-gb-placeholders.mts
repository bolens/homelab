import fs from 'node:fs';
import { en } from './src/i18n/locales/en.ts';
import { enGb } from './src/i18n/locales/en-gb.ts';

const file = '/home/youruser/dev/docker/stacks/asking-ng/client/src/i18n/locales/en-gb.ts';
let src = fs.readFileSync(file, 'utf8');

const re = /\{(\w+)\}/g;
const ph = (s: string) => new Set([...s.matchAll(re)].map((m) => m[1]));
const eq = (a: Set<string>, b: Set<string>) => a.size === b.size && [...a].every((x) => b.has(x));

const mismatches: string[] = [];
for (const k of Object.keys(en) as (keyof typeof en)[]) {
  if (!eq(ph(en[k]), ph(enGb[k]))) mismatches.push(String(k));
}

const quote = (s: string) => `'${s.replace(/\\/g, '\\\\').replace(/'/g, "\\'")}'`;

function findValueBounds(text: string, key: string): [number, number] | null {
  const marker = `'${key}':`;
  const i = text.indexOf(marker);
  if (i < 0) return null;
  let p = i + marker.length;
  while (p < text.length && /\s/.test(text[p])) p++;
  const start = p;

  let s: string | null = null;
  let esc = false;
  let paren = 0;
  let bracket = 0;
  let brace = 0;

  for (; p < text.length; p++) {
    const ch = text[p];
    if (s) {
      if (esc) { esc = false; continue; }
      if (ch === '\\') { esc = true; continue; }
      if (ch === s) s = null;
      continue;
    }
    if (ch === '\'' || ch === '"' || ch === '`') { s = ch; continue; }
    if (ch === '(') paren++;
    else if (ch === ')') paren--;
    else if (ch === '[') bracket++;
    else if (ch === ']') bracket--;
    else if (ch === '{') brace++;
    else if (ch === '}') brace--;
    else if (ch === ',' && paren === 0 && bracket === 0 && brace === 0) return [start, p];
  }
  return null;
}

let updated = 0;
for (const key of mismatches) {
  const bounds = findValueBounds(src, key);
  if (!bounds) continue;
  const [start, end] = bounds;
  const replacement = quote((en as Record<string, string>)[key]);
  src = src.slice(0, start) + replacement + src.slice(end);
  updated++;
}

fs.writeFileSync(file, src);
console.log('updated keys:', updated);
