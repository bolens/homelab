import { promises as fs } from 'node:fs';
import path from 'node:path';

const ROOT = path.resolve(import.meta.dirname, '..');
const SRC_DIR = path.join(ROOT, 'src');
const EXTS = new Set(['.tsx', '.ts', '.css']);
const SKIP_DIRS = new Set(['node_modules', 'dist', 'coverage', '.turbo']);

const LEGACY_EXACT = new Set([
  'btn',
  'form-control',
  'form-select',
  'input-group',
  'container',
  'row',
  'card',
  'navbar',
  'dropdown-menu',
  'dropdown-item',
  'alert',
  'badge',
]);

const LEGACY_PREFIXES = ['col-', 'btn-', 'navbar-'];
const LEGACY_UTILITY_PREFIXES = [
  'm-',
  'mt-',
  'mb-',
  'ms-',
  'me-',
  'mx-',
  'my-',
  'p-',
  'pt-',
  'pb-',
  'ps-',
  'pe-',
  'px-',
  'py-',
  'd-',
  'text-',
  'fw-',
  'justify-content-',
  'align-items-',
  'gap-',
];

const CLASS_NAME_PATTERN = /className\s*=\s*['"`]([^'"`]+)['"`]/g;
const BOOTSTRAP_IMPORT_PATTERN = /bootstrap\/dist\/css\/bootstrap\.min\.css/;

function hasLegacyClass(token) {
  return (
    LEGACY_EXACT.has(token) ||
    LEGACY_PREFIXES.some((prefix) => token.startsWith(prefix)) ||
    LEGACY_UTILITY_PREFIXES.some((prefix) => token.startsWith(prefix))
  );
}

async function walk(dir) {
  const entries = await fs.readdir(dir, { withFileTypes: true });
  const out = [];
  for (const entry of entries) {
    if (SKIP_DIRS.has(entry.name)) continue;
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      out.push(...(await walk(fullPath)));
      continue;
    }
    if (entry.isFile() && EXTS.has(path.extname(entry.name))) {
      out.push(fullPath);
    }
  }
  return out;
}

async function main() {
  const files = await walk(SRC_DIR);
  const failures = [];

  for (const file of files) {
    const rel = path.relative(ROOT, file);
    const content = await fs.readFile(file, 'utf8');

    if (BOOTSTRAP_IMPORT_PATTERN.test(content)) {
      failures.push(`${rel}: do not import Bootstrap CSS; use app tokens and ui-kit.css instead`);
    }

    for (const match of content.matchAll(CLASS_NAME_PATTERN)) {
      const classValue = match[1] ?? '';
      const classes = classValue
        .split(/\s+/)
        .map((v) => v.trim())
        .filter(Boolean);
      for (const token of classes) {
        if (!hasLegacyClass(token)) continue;
        failures.push(`${rel}: legacy class "${token}" in className="${classValue}"`);
      }
    }
  }

  if (failures.length > 0) {
    console.error('Legacy UI class migration check failed:\n');
    for (const line of failures) console.error(`- ${line}`);
    process.exit(1);
  }

  console.log(`Legacy UI class migration check passed (${files.length} files scanned).`);
}

void main();
