/** Ollama `/api/chat` JSON response (non-stream). */
type OllamaChatResponse = {
  model?: string;
  created_at?: string;
  message?: { role?: string; content?: string | unknown[] };
  done_reason?: string;
  prompt_eval_count?: number;
  eval_count?: number;
};

export function ollamaResponseToOpenAI(data: OllamaChatResponse): Record<string, unknown> {
  const raw = data.message?.content;
  const content = typeof raw === 'string' ? raw : raw !== undefined ? JSON.stringify(raw) : '';
  const created = Math.floor(Date.now() / 1000);
  const promptTokens = data.prompt_eval_count ?? 0;
  const completionTokens = data.eval_count ?? 0;
  return {
    id: `chatcmpl-ollama-${created}`,
    object: 'chat.completion',
    created,
    model: data.model ?? 'unknown',
    choices: [
      {
        index: 0,
        message: { role: 'assistant' as const, content },
        finish_reason: data.done_reason === 'length' ? 'length' : 'stop',
      },
    ],
    usage: {
      prompt_tokens: promptTokens,
      completion_tokens: completionTokens,
      total_tokens: promptTokens + completionTokens,
    },
  };
}

export function toOllamaChatPayload(body: {
  model: string;
  messages: { role: string; content: string | unknown[] }[];
  temperature?: number;
  max_tokens?: number;
}): Record<string, unknown> {
  return {
    model: body.model,
    messages: body.messages.map((m) => ({
      role: m.role === 'developer' ? 'system' : m.role === 'tool' ? 'user' : m.role,
      content: typeof m.content === 'string' ? m.content : JSON.stringify(m.content),
    })),
    stream: false,
    options: {
      ...(body.temperature !== undefined ? { temperature: body.temperature } : {}),
      ...(body.max_tokens !== undefined ? { num_predict: body.max_tokens } : {}),
    },
  };
}
