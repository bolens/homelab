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

// Execute the complete shipped script; ready is intentionally inert so each
// test controls request completion and time without initializing DataTables.
function preferencesHarness() {
  const fields = new Map(), requests = [], timers = new Map();
  let timerId = 0;
  function $(selector) {
    if (!fields.has(selector)) fields.set(selector, { props: {}, value: undefined, text: '' });
    const state = fields.get(selector);
    return {
      ready() {}, button() { return this; },
      val(value) { if (!arguments.length) return state.value; state.value = value; return this; },
      prop(name, value) { if (arguments.length === 1) return state.props[name]; state.props[name] = value; return this; },
      text(value) { if (!arguments.length) return state.text; state.text = value; return this; },
    };
  }
  $.ajax = options => {
    const callbacks = { done: [], fail: [], always: [] };
    const request = {
      options, aborted: false,
      done(callback) { callbacks.done.push(callback); return this; },
      fail(callback) { callbacks.fail.push(callback); return this; },
      always(callback) { callbacks.always.push(callback); return this; },
      resolve(data) { callbacks.done.forEach(callback => callback(data)); callbacks.always.forEach(callback => callback()); },
      reject(status = 503, textStatus = 'error') { callbacks.fail.forEach(callback => callback({ status }, textStatus)); callbacks.always.forEach(callback => callback()); },
      // Abort synchronously fires callbacks, as jQuery does. resolve/reject can
      // still be forced afterward to model a callback already queued at pause.
      abort() { this.aborted = true; this.reject(0); },
    };
    requests.push(request);
    return request;
  };
  const sandbox = vm.createContext({ document: { hidden: false }, $, setTimeout(callback, delay) {
    const id = ++timerId; timers.set(id, { callback, delay }); return id;
  }, clearTimeout(id) { timers.delete(id); } });
  vm.runInContext(readFileSync(new URL('./ddl_queue.js', import.meta.url), 'utf8'), sandbox);
  return {
    sandbox, requests, timers, $,
    tick(delay) {
      assert.equal(timers.size, 1, 'exactly one retry timer');
      const [id, timer] = timers.entries().next().value;
      assert.equal(timer.delay, delay); timers.delete(id); timer.callback();
    },
    edits() { $('#ddl_kind').val('alternate'); $('#ddl_order').val('newest'); $('#ddl_paused').prop('checked', false); },
    assertEdits() { assert.equal($('#ddl_kind').val(), 'alternate'); assert.equal($('#ddl_order').val(), 'newest'); assert.equal($('#ddl_paused').prop('checked'), false); },
  };
}

const validPreferences = () => ({ csrf: 'test-csrf', policy: { ddl_kind: 'packs', ddl_order: 'release_oldest', ddl_paused: true } });

test('preferences allow one GET and enable fields only after valid data', () => {
  const h = preferencesHarness();
  h.sandbox.ddlLoadPreferences(true); h.sandbox.ddlLoadPreferences(true);
  assert.equal(h.requests.length, 1);
  assert.equal(h.requests[0].options.url, 'workflowStatus');
  assert.ok(!h.requests[0].options.type || h.requests[0].options.type === 'GET');
  assert.equal(h.requests[0].options.dataType, 'json');
  h.requests[0].resolve(validPreferences());
  assert.equal(h.$('#ddl_kind').val(), 'packs');
  assert.equal(h.$('#ddl_order').val(), 'release_oldest');
  assert.equal(h.$('#ddl_paused').prop('checked'), true);
  assert.equal(h.$('#ddl_schedule :input').prop('disabled'), false);
  h.sandbox.ddlLoadPreferences(true);
  assert.equal(h.requests.length, 1, 'loaded token prevents redundant reads');
  assert.equal(h.timers.size, 0);
});

test('transient failures use bounded 2/4/8 second retries and explicit retry resets budget', () => {
  const h = preferencesHarness(); h.sandbox.ddlLoadPreferences(true);
  for (const delay of [2000, 4000, 8000]) {
    h.requests.at(-1).reject(); h.tick(delay);
  }
  h.requests.at(-1).reject();
  assert.equal(h.requests.length, 4); assert.equal(h.timers.size, 0);
  assert.match(h.$('#ddl_schedule_note').text(), /refresh status/i);
  h.sandbox.ddlLoadPreferences(true);
  assert.equal(h.requests.length, 5);
  h.requests.at(-1).reject(); h.tick(2000);
  assert.equal(h.requests.length, 6);
  assert.ok(h.requests.every(request => !request.options.type || request.options.type === 'GET'), 'no mutations');
});

test('invalid successful JSON cannot enable preferences and is retried', () => {
  for (const data of [null, {}, { csrf: '', policy: validPreferences().policy },
    { csrf: 'token', policy: { ...validPreferences().policy, ddl_paused: 'false' } },
    { csrf: 'token', policy: { ...validPreferences().policy, ddl_kind: 'bogus' } },
    { csrf: 'token', policy: { ...validPreferences().policy, ddl_order: 'bogus' } }]) {
    const h = preferencesHarness(); h.sandbox.ddlLoadPreferences(true); h.requests[0].resolve(data);
    assert.notEqual(h.$('#ddl_schedule :input').prop('disabled'), false);
    assert.equal(h.sandbox.ddlCsrf, null); h.tick(2000);
    h.requests[1].resolve(validPreferences());
    assert.equal(h.$('#ddl_schedule :input').prop('disabled'), false);
  }
});

test('authentication failures stop automatic retries', () => {
  for (const status of [401, 403]) {
    const h = preferencesHarness(); h.sandbox.ddlLoadPreferences(true); h.requests[0].reject(status);
    assert.equal(h.timers.size, 0); assert.equal(h.sandbox.ddlCsrf, null);
    assert.notEqual(h.$('#ddl_schedule :input').prop('disabled'), false);
    h.sandbox.ddlPausePreferences(); h.sandbox.ddlResumePreferences();
    assert.equal(h.requests.length, 1, 'resume retains authentication refusal');
    h.sandbox.ddlLoadPreferences(false);
    assert.equal(h.requests.length, 1);
    h.sandbox.ddlLoadPreferences(true);
    assert.equal(h.requests.length, 2, 'explicit refresh may retry after signing in');
    h.requests[1].resolve(validPreferences());
    assert.equal(h.$('#ddl_schedule :input').prop('disabled'), false);
  }
});

test('initial HTTP or parser failure recovers on the first retry and stops retrying', () => {
  for (const [status, textStatus] of [[503, 'error'], [200, 'parsererror']]) {
    const h = preferencesHarness(); h.sandbox.ddlLoadPreferences(true);
    h.requests[0].reject(status, textStatus);
    assert.equal(h.sandbox.ddlCsrf, null);
    assert.notEqual(h.$('#ddl_schedule :input').prop('disabled'), false);
    h.tick(2000); h.requests[1].resolve(validPreferences());
    assert.equal(h.requests.length, 2); assert.equal(h.timers.size, 0);
    assert.equal(h.sandbox.ddlCsrf, 'test-csrf');
    assert.equal(h.$('#ddl_schedule :input').prop('disabled'), false);
    assert.equal(h.$('#ddl_kind').val(), 'packs');
    assert.equal(h.$('#ddl_order').val(), 'release_oldest');
    assert.equal(h.$('#ddl_paused').prop('checked'), true);
    h.sandbox.ddlResumePreferences(); h.sandbox.ddlLoadPreferences(true);
    assert.equal(h.requests.length, 2, 'successful token suppresses further reads');
  }
});

test('token recovery preserves previously loaded user drafts', () => {
  const h = preferencesHarness(); h.sandbox.ddlLoadPreferences(true); h.requests[0].resolve(validPreferences());
  h.edits(); h.sandbox.ddlCsrf = null; h.sandbox.ddlLoadPreferences(true);
  h.requests[1].resolve(validPreferences()); h.assertEdits();
  assert.equal(h.sandbox.ddlCsrf, 'test-csrf');
});

test('pause aborts and invalidates old callbacks without clearing resumed request', () => {
  const h = preferencesHarness(); h.sandbox.ddlLoadPreferences(true);
  const old = h.requests[0]; h.sandbox.ddlPausePreferences();
  assert.equal(old.aborted, true); assert.equal(h.timers.size, 0);
  h.sandbox.ddlResumePreferences(); assert.equal(h.requests.length, 2);
  old.resolve({ ...validPreferences(), csrf: 'old-token' });
  assert.equal(h.sandbox.ddlCsrf, null);
  h.sandbox.ddlLoadPreferences(true); assert.equal(h.requests.length, 2, 'old completion cannot clear new in-flight request');
  h.requests[1].resolve(validPreferences()); h.edits(); old.resolve(validPreferences()); old.reject(); h.assertEdits();
  assert.equal(h.sandbox.ddlCsrf, 'test-csrf'); assert.equal(h.timers.size, 0);
});

test('pause clears retry timer and resume retains the consumed retry budget', () => {
  const h = preferencesHarness(); h.sandbox.ddlLoadPreferences(true); h.requests[0].reject();
  h.tick(2000); h.requests[1].reject();
  h.sandbox.ddlPausePreferences(); assert.equal(h.timers.size, 0);
  h.sandbox.ddlResumePreferences(); assert.equal(h.requests.length, 3);
  h.requests[2].reject(); h.tick(8000); h.requests[3].reject();
  assert.equal(h.requests.length, 4); assert.equal(h.timers.size, 0);
  h.sandbox.ddlPausePreferences(); h.sandbox.ddlResumePreferences();
  assert.equal(h.requests.length, 4, 'resume cannot replenish an exhausted budget');
});
