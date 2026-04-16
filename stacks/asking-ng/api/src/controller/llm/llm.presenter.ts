export function presentLlmStatus(payload: {
  provider: string;
  gatewayAuth: boolean;
  ollamaAuth?: boolean;
  ollamaBaseUrl?: string;
  lmStudioBaseUrl?: string;
}): Record<string, unknown> {
  return payload;
}

export function presentOpenAiModelList(payload: {
  models: Array<{ name: string }>;
}): Record<string, unknown> {
  return {
    object: 'list',
    data: payload.models.map((m) => ({
      id: m.name,
      object: 'model',
      owned_by: 'ollama',
    })),
  };
}
