'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { bundlePath, patchBundle } = require('./patch-openai-stream.cjs');

const root = process.argv[2] || '/home/vane';
const { parse } = require(require.resolve('partial-json', { paths: [root] }));
const source = fs.readFileSync(path.join(root, bundlePath), 'utf8');

function harness(bundle, chunks) {
  const parser = source.indexOf('arguments:(0,n.parse)(b.arguments)');
  const start = [...source.matchAll(/async\s*\*\s*streamText\s*\(/g)]
    .filter((match) => match.index < parser).at(-1)?.index ?? -1;
  const end = [...bundle.matchAll(/async\s+generateObject\s*\(/g)]
    .find((match) => match.index > parser)?.index ?? -1;
  assert(start >= 0 && end > start, 'Cannot locate the actual upstream stream method');
  const Harness = vm.runInNewContext(`(class {${bundle.slice(start, end)}})`, { n: { parse } });
  const instance = new Harness();
  instance.config = { model: 'fixture' };
  instance.convertToOpenAIMessages = (messages) => messages;
  instance.openAIClient = {
    chat: { completions: { create: async () => (async function* fixture() {
      for (const chunk of chunks) yield chunk;
    }()) } },
  };
  return instance;
}

const chunk = (toolCalls, finish = null, content = '') => ({
  choices: [{ delta: { tool_calls: toolCalls, content }, finish_reason: finish }],
});

async function collect(bundle, chunks) {
  const results = [];
  for await (const item of harness(bundle, chunks).streamText({ messages: [] })) results.push(item);
  return JSON.parse(JSON.stringify(results));
}

async function main() {
  const patched = patchBundle(source);
  const calls = [
    chunk([{ index: 0, id: 'call-0', function: { name: 'search', arguments: '' } }]),
    chunk([{ index: 0, function: { arguments: '' } }]),
    chunk([{ index: 0, function: { arguments: '{"queries":["vane"]}' } }]),
    chunk([{ index: 1, id: 'call-1', function: { name: 'calculate', arguments: '' } }]),
    chunk([{ index: 0, function: { arguments: '' } }, { index: 1, function: { arguments: '' } }]),
    chunk([{ index: 1, function: { arguments: '{"value":4}' } }]),
    chunk(undefined, 'tool_calls'),
  ];
  // Reproduce the failure in the exact shipped method before applying the patch.
  await assert.rejects(collect(source, calls), /is empty/);
  const results = await collect(patched, calls);
  assert.deepEqual(results[1].toolCallChunk[0].arguments, {});
  assert.deepEqual(results[2].toolCallChunk[0], {
    name: 'search', id: 'call-0', arguments: { queries: ['vane'] },
  });
  assert.deepEqual(results[4].toolCallChunk[1].arguments, {});
  assert.deepEqual(results[5].toolCallChunk[0], {
    name: 'calculate', id: 'call-1', arguments: { value: 4 },
  });
  assert.equal(results.at(-1).done, true);
  const text = [chunk(undefined, null, 'hello'), chunk(undefined, 'stop')];
  assert.deepEqual(await collect(patched, text), await collect(source, text));
  await assert.rejects(collect(patched, [chunk([
    { index: 0, id: 'invalid', function: { name: 'search', arguments: '@' } },
  ])]));
  assert.throws(() => patchBundle(`${source}\n`), /Upstream bundle changed/);
  console.log('Native stream regression passed: empty deltas, two calls, text, malformed JSON and source drift.');
}

main().catch((error) => { console.error(error); process.exit(1); });
