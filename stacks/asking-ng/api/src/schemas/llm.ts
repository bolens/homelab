import { z } from 'zod';
import { appEnv } from '../lib/env';

const MAX_LLM_MESSAGES = 128;
const MAX_LLM_MESSAGE_TEXT_CHARS = 16_000;
const MAX_LLM_TOTAL_TEXT_CHARS = 64_000;

function allowedLlmModels(): Set<string> {
  const raw = appEnv.llmAllowedModelsRaw;
  if (!raw) return new Set<string>();
  return new Set(
    raw
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean),
  );
}

const messageSchema = z.object({
  role: z.enum(['system', 'user', 'assistant']),
  content: z.union([z.string(), z.array(z.record(z.unknown()))]),
});

export const chatCompletionBodySchema = z
  .object({
    model: z.string().min(1).max(256),
    messages: z.array(messageSchema).min(1).max(MAX_LLM_MESSAGES),
    temperature: z.number().min(0).max(2).optional(),
    max_tokens: z.number().int().positive().max(8192).optional(),
    stream: z.boolean().optional(),
  })
  .passthrough()
  .superRefine((data, ctx) => {
    if (data.stream === true) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: 'Streaming is not supported; omit stream or set it to false.',
        path: ['stream'],
      });
    }

    const models = allowedLlmModels();
    if (models.size > 0 && !models.has(data.model)) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: 'Model is not allowed by server policy.',
        path: ['model'],
      });
    }

    let totalTextChars = 0;
    for (const [idx, message] of data.messages.entries()) {
      if (typeof message.content !== 'string') continue;
      const textChars = message.content.length;
      totalTextChars += textChars;

      if (textChars > MAX_LLM_MESSAGE_TEXT_CHARS) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          message: `Message content exceeds ${MAX_LLM_MESSAGE_TEXT_CHARS} characters.`,
          path: ['messages', idx, 'content'],
        });
      }
    }

    if (totalTextChars > MAX_LLM_TOTAL_TEXT_CHARS) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: `Total message text exceeds ${MAX_LLM_TOTAL_TEXT_CHARS} characters.`,
        path: ['messages'],
      });
    }
  });

export type ChatCompletionBody = z.infer<typeof chatCompletionBodySchema>;
