export function presentCreatePollResponse(data: {
  id: string;
  api_key: string;
  webhook_secrets?: Array<{ url: string; secret: string }>;
  embed_read_token?: string;
}): Record<string, unknown> {
  return {
    status: 'success',
    data,
  };
}
