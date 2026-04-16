#!/usr/bin/env node

import { readdir, readFile } from 'node:fs/promises';
import path from 'node:path';
import process from 'node:process';

const apiRoot = process.cwd();
const routesRoot = path.join(apiRoot, 'src', 'routes');

const routeImportLegacyAllowlist = new Set();

const importPattern =
  /(?:import\s+[\s\S]*?\s+from\s+['"]([^'"]+)['"]|import\s*\(\s*['"]([^'"]+)['"]\s*\)|require\(\s*['"]([^'"]+)['"]\s*\))/gm;

function isForbiddenResolvedTarget(targetAbsPath) {
  const normalized = targetAbsPath.split(path.sep).join('/');
  return (
    normalized.includes('/src/model/') ||
    normalized.includes('/src/models/') ||
    normalized.includes('/src/connections/')
  );
}

async function listTsFilesRecursively(rootDir) {
  const out = [];
  const queue = [rootDir];
  while (queue.length > 0) {
    const current = queue.pop();
    const entries = await readdir(current, { withFileTypes: true });
    for (const entry of entries) {
      const full = path.join(current, entry.name);
      if (entry.isDirectory()) {
        queue.push(full);
      } else if (entry.isFile() && full.endsWith('.ts')) {
        out.push(full);
      }
    }
  }
  return out.sort();
}

async function main() {
  const files = await listTsFilesRecursively(routesRoot);
  const violations = [];

  for (const filePath of files) {
    const rel = path.relative(apiRoot, filePath).split(path.sep).join('/');
    if (routeImportLegacyAllowlist.has(rel)) continue;

    const source = await readFile(filePath, 'utf8');
    let match;
    while ((match = importPattern.exec(source)) !== null) {
      const specifier = match[1] ?? match[2] ?? match[3];
      if (!specifier || !specifier.startsWith('.')) continue;
      const resolved = path.resolve(path.dirname(filePath), specifier);
      if (isForbiddenResolvedTarget(resolved)) {
        violations.push({ file: rel, importPath: specifier });
      }
    }
  }

  if (violations.length === 0) {
    console.log('Route boundary check passed.');
    return;
  }

  console.error('Route boundary check failed. Routes must not import model/connections directly.');
  for (const v of violations) {
    console.error(`- ${v.file}: ${v.importPath}`);
  }
  process.exitCode = 1;
}

await main();
