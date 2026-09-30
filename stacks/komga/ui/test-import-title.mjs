import assert from 'node:assert/strict'
import test from 'node:test'
import { importFilename, importBookTitle, resolveImportTitle } from './import-title.ts'
const source = '/normalizer-state/jobs/abcdef/prepared/Teenage Mutant Ninja Turtles - Shredder 001 (2025) (digital) (Raphael-Empire).cbz'
test('normalizer paths become readable titles without changing input', () => {
  assert.equal(importFilename(source), 'Teenage Mutant Ninja Turtles - Shredder #1 (2025)')
  assert.equal(importFilename('C:\\imports\\Comic 002 (2026).cbr'), 'Comic #2 (2026)')
  assert.equal(importFilename('/tmp/Été #½.cbz'), 'Été #½')
  assert.equal(importFilename('/tmp/Art Book (Deluxe).pdf'), 'Art Book (Deluxe)')
})
test('catalog identity takes precedence over staging filename', () => {
  assert.equal(importBookTitle({ seriesTitle: 'TMNT: Shredder', metadata: { number: '001', title: 'release group', releaseDate: '2025-08-13' } }, source), 'TMNT: Shredder #1 (2025)')
  assert.equal(importBookTitle({ seriesTitle: 'Series', metadata: { number: '½' } }, source), 'Series #½')
  assert.equal(importBookTitle({ oneshot: true, metadata: { title: 'The Art of Something' } }, source), 'The Art of Something')
})
test('missing or inaccessible metadata still produces a successful readable toast', async () => {
  assert.equal(await resolveImportTitle({ bookId: '42', sourceFile: source }, async (id, signal) => {
    assert.equal(id, '42'); assert.ok(signal instanceof AbortSignal); throw new Error('403')
  }), importFilename(source))
  assert.equal(await resolveImportTitle({ sourceFile: source }, async () => { throw new Error('must not call') }), importFilename(source))
  assert.equal(importBookTitle(undefined, source), importFilename(source))
  assert.equal(importBookTitle({ oneshot: true, metadata: { title: 'Batman/Superman' } }, source), 'Batman/Superman')
})
