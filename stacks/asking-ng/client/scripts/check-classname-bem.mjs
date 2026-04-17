import { readdir, readFile } from 'node:fs/promises';
import path from 'node:path';
import process from 'node:process';

const SRC_DIR = path.resolve(process.cwd(), 'src');
const FILE_EXTENSIONS = new Set(['.ts', '.tsx']);
const CLASS_TOKEN_PATTERN =
  /^(?:ui|asking|leaflet)(?:-[a-z0-9]+)*(?:__(?:[a-z0-9]+(?:-[a-z0-9]+)*))?(?:--[a-z0-9]+(?:-[a-z0-9]+)*)*$/;
const ALLOWED_LITERAL_CLASSES = new Set(['']);

/**
 * @param {string} input
 * @returns {string[]}
 */
function splitClassTokens(input) {
  return input
    .split(/\s+/)
    .map((v) => v.trim())
    .filter(Boolean);
}

/**
 * @param {string} classToken
 * @returns {boolean}
 */
function isValidClassToken(classToken) {
  // Ignore non-class string literals (enum values, prop variants) in cx(...) calls.
  if (!classToken.includes('-')) return true;
  if (ALLOWED_LITERAL_CLASSES.has(classToken)) return true;
  return CLASS_TOKEN_PATTERN.test(classToken);
}

/**
 * @param {string} filePath
 * @returns {Promise<string[]>}
 */
async function collectSourceFiles(filePath) {
  const entries = await readdir(filePath, { withFileTypes: true });
  /** @type {string[]} */
  const files = [];
  for (const entry of entries) {
    const fullPath = path.join(filePath, entry.name);
    if (entry.isDirectory()) {
      files.push(...(await collectSourceFiles(fullPath)));
      continue;
    }
    if (FILE_EXTENSIONS.has(path.extname(entry.name))) {
      files.push(fullPath);
    }
  }
  return files;
}

/**
 * @param {string} filePath
 * @param {string} content
 * @param {Map<string, Set<string>>} errors
 */
function validateClassTokens(filePath, content, errors) {
  /**
   * Record invalid token for a file.
   * @param {string} token
   */
  const addError = (token) => {
    const relative = path.relative(process.cwd(), filePath);
    const current = errors.get(relative) ?? new Set();
    current.add(token);
    errors.set(relative, current);
  };

  const classAttrRegex = /className\s*=\s*(?:'([^']+)'|"([^"]+)"|`([^`]+)`)/g;
  for (const match of content.matchAll(classAttrRegex)) {
    const literal = match[1] ?? match[2] ?? match[3] ?? '';
    if (literal.includes('${')) continue;
    for (const token of splitClassTokens(literal)) {
      if (!isValidClassToken(token)) addError(token);
    }
  }

  const cxRegex = /\bcx\(([\s\S]*?)\)/g;
  for (const match of content.matchAll(cxRegex)) {
    const args = match[1] ?? '';
    const stringRegex = /'([^']*)'|"([^"]*)"|`([^`]+)`/g;
    for (const stringMatch of args.matchAll(stringRegex)) {
      const literal = stringMatch[1] ?? stringMatch[2] ?? stringMatch[3] ?? '';
      if (literal.includes('${')) continue;
      for (const token of splitClassTokens(literal)) {
        if (!isValidClassToken(token)) addError(token);
      }
    }
  }
}

async function main() {
  const files = await collectSourceFiles(SRC_DIR);
  /** @type {Map<string, Set<string>>} */
  const errors = new Map();
  for (const filePath of files) {
    const content = await readFile(filePath, 'utf8');
    validateClassTokens(filePath, content, errors);
  }

  if (errors.size === 0) {
    console.log('BEM class token check passed.');
    return;
  }

  console.error('Found invalid class tokens in TS/TSX literals:');
  for (const [filePath, tokens] of [...errors.entries()].sort(([a], [b]) => a.localeCompare(b))) {
    const tokenList = [...tokens].sort((a, b) => a.localeCompare(b)).join(', ');
    console.error(`- ${filePath}: ${tokenList}`);
  }
  process.exitCode = 1;
}

void main();
