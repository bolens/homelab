import { describe, expect, it } from 'vitest';
import { ollamaResponseToOpenAI, toOllamaChatPayload } from './llmOpenAiFormat';

describe('ollamaResponseToOpenAI', () => {
  it('maps message content and usage', () => {
    const out = ollamaResponseToOpenAI({
      model: 'llama3',
      message: { role: 'assistant', content: 'hello' },
      prompt_eval_count: 3,
      eval_count: 5,
      done_reason: 'stop',
    });
    expect(out.object).toBe('chat.completion');
    expect(out.model).toBe('llama3');
    expect((out.choices as { message: { content: string } }[])[0].message.content).toBe('hello');
    expect((out.usage as { prompt_tokens: number }).prompt_tokens).toBe(3);
    expect((out.usage as { completion_tokens: number }).completion_tokens).toBe(5);
  });

  it('uses length finish_reason when done_reason is length', () => {
    const out = ollamaResponseToOpenAI({
      model: 'm',
      message: { content: 'x' },
      done_reason: 'length',
    });
    expect((out.choices as { finish_reason: string }[])[0].finish_reason).toBe('length');
  });
});

describe('toOllamaChatPayload', () => {
  it('maps roles and options', () => {
    const body = {
      model: 'qwen',
      messages: [
        { role: 'developer' as const, content: 'sys' },
        { role: 'user' as const, content: 'hi' },
      ],
      temperature: 0.2,
      max_tokens: 64,
    };
    const payload = toOllamaChatPayload(body);
    expect(payload.model).toBe('qwen');
    expect((payload.messages as { role: string }[])[0].role).toBe('system');
    expect((payload.options as { temperature: number }).temperature).toBe(0.2);
    expect((payload.options as { num_predict: number }).num_predict).toBe(64);
    expect(payload.stream).toBe(false);
  });
});
