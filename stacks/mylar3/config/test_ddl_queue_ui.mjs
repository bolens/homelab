import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';

const context = vm.createContext({
  document: {},
  $: () => ({ ready() {} }),
});
vm.runInContext(readFileSync(new URL('./ddl_queue.js', import.meta.url), 'utf8'), context);

test('progress ages are readable and unknown observations remain unknown', () => {
  for (const [seconds, expected] of [[null, 'Unknown'], [undefined, 'Unknown'],
    ['bad', 'Unknown'], [0, '0s ago'], [59, '59s ago'], [60, '1m ago'],
    [3600, '1h ago'], [468719, '5d ago'], [-1, '0s ago']]) {
    assert.equal(context.ddlAge(seconds), expected);
  }
});

test('review destinations distinguish download completion from import', () => {
  for (const [state, label, href] of [
    ['Completed', 'Review import', 'postProcessing#pp_work'],
    ['Failed', 'Review problems', 'importProblems'],
    ['NZB handoff', 'Review handoff', 'activity#wf_handoff'],
  ]) {
    const row = [];
    row[3] = state;
    const link = context.ddlReviewLink(row);
    assert.equal(link.label, label);
    assert.equal(link.href, href);
  }
  for (const state of ['Queued', 'Downloading', 'Incomplete']) {
    const row = [];
    row[3] = state;
    assert.equal(context.ddlReviewLink(row), null);
  }
});
