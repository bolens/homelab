import assert from 'node:assert/strict';
import test from 'node:test';
import { createOpenAI } from '@ai-sdk/openai';
import {
  DEFAULT_MAX_DOWNLOAD_SIZE,
  DownloadError,
  createJsonErrorResponseHandler,
  createJsonResponseHandler,
  createStatusCodeErrorResponseHandler,
  readResponseWithSizeLimit,
} from '@ai-sdk/provider-utils';
import { generateText, streamText } from 'ai';
import { z } from 'zod';

const schema = z.object({ ok: z.boolean() });
const handlers = {
  json: createJsonResponseHandler(schema),
  'json error': createJsonErrorResponseHandler({ errorSchema: schema, errorToMessage: () => 'test' }),
  'status error': createStatusCodeErrorResponseHandler(),
};

for (const [name, handler] of Object.entries(handlers)) {
  test(`${name} handler rejects an oversized advertised body and cancels it`, async () => {
    let cancelled = false;
    const body = new ReadableStream({
      start(controller) {
        controller.enqueue(new TextEncoder().encode('{"ok":true}'));
        controller.close();
      },
      cancel() { cancelled = true; },
    });
    const response = new Response(body, {
      headers: { 'content-length': String(DEFAULT_MAX_DOWNLOAD_SIZE + 1) },
    });
    await assert.rejects(handler({ response, url: 'https://example.test/', requestBodyValues: {} }),
      error => DownloadError.isInstance(error));
    assert.equal(cancelled, true);
    assert.equal(body.locked, false);
  });
}

test('an unadvertised oversized body is cancelled and releases its reader', async () => {
  let cancelled = false;
  const body = new ReadableStream({
    start(controller) {
      controller.enqueue(new Uint8Array(2));
      controller.enqueue(new Uint8Array(2));
      controller.enqueue(new Uint8Array(1));
      controller.close();
    },
    cancel() { cancelled = true; },
  });
  await assert.rejects(readResponseWithSizeLimit({
    response: new Response(body), url: 'https://example.test/', maxBytes: 3,
  }), error => DownloadError.isInstance(error));
  assert.equal(cancelled, true);
  assert.equal(body.locked, false);
});

const completion = {
  id: 'test', object: 'chat.completion', created: 1, model: 'test',
  choices: [{ index: 0, message: { role: 'assistant', content: 'ok' }, finish_reason: 'stop' }],
  usage: { prompt_tokens: 1, completion_tokens: 1, total_tokens: 2 },
};

test('the pinned AI SDK still accepts a non-streaming completion', async () => {
  let requests = 0;
  const provider = createOpenAI({ apiKey: 'test', fetch: async (url) => {
    requests++;
    assert.equal(String(url), 'https://api.openai.com/v1/chat/completions');
    return Response.json(completion);
  } });
  const result = await generateText({ model: provider.chat('test'), prompt: 'test', maxRetries: 0 });
  assert.equal(result.text, 'ok');
  assert.equal(requests, 1);
});

test('the pinned AI SDK still consumes a chunked UTF-8 event stream', async () => {
  const chunk = { id: 'test', object: 'chat.completion.chunk', created: 1, model: 'test' };
  const events = [
    { ...chunk, choices: [{ index: 0, delta: { role: 'assistant', content: 'héllo' }, finish_reason: null }] },
    { ...chunk, choices: [{ index: 0, delta: {}, finish_reason: 'stop' }] },
  ];
  const bytes = new TextEncoder().encode(events.map(event => `data: ${JSON.stringify(event)}\n\n`).join('') + 'data: [DONE]\n\n');
  let requests = 0;
  const provider = createOpenAI({ apiKey: 'test', fetch: async (url) => {
    requests++;
    assert.equal(String(url), 'https://api.openai.com/v1/chat/completions');
    const body = new ReadableStream({ start(controller) {
      for (let i = 0; i < bytes.length; i += 7) controller.enqueue(bytes.slice(i, i + 7));
      controller.close();
    } });
    return new Response(body, { headers: { 'content-type': 'text/event-stream' } });
  } });
  const result = streamText({ model: provider.chat('test'), prompt: 'test', maxRetries: 0 });
  assert.equal(await result.text, 'héllo');
  assert.equal(requests, 1);
});
