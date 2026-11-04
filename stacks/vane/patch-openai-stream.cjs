'use strict';

const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');

const bundlePath = '.next/server/chunks/136.js';
// Source fingerprint from the exact upstream image pinned in Dockerfile.
const sourceSha256 = 'e0e4d54cead921e33871a1311a3225e5591bca21f75e9e1bf690f1b1fa1b8d20';
const before = 'arguments:(0,n.parse)(b.arguments)';
const after = 'arguments:(0,n.parse)(b.arguments||"{}")';

function patchBundle(source) {
  assert.equal(crypto.createHash('sha256').update(source).digest('hex'), sourceSha256,
    'Upstream bundle changed: review the patch against the new image before building');
  assert.equal(source.split(before).length - 1, 1, 'Expected one unguarded argument parser');
  const patched = source.replace(before, after);
  assert.equal(patched.includes(before), false);
  return patched;
}

if (require.main === module) {
  const target = path.join(process.argv[2] || '/home/vane', bundlePath);
  fs.writeFileSync(target, patchBundle(fs.readFileSync(target, 'utf8')));
  console.log('Patched repeated empty OpenAI tool-call argument deltas.');
}

module.exports = { bundlePath, patchBundle };
