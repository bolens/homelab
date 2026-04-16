import type { AppRequest, AppResponse } from '../../types/http';
import { jsonError } from '../../lib/jsonError';
import { loggerForRequest } from '../../lib/logger';
import type { ChatCompletionBody } from '../../schemas/llm';
import { presentLlmStatus, presentOpenAiModelList } from './llm.presenter';
import {
  buildLlmStatus,
  createChatCompletionsService,
  listLlmModelsService,
} from './llm.service';

export async function llmStatusHandler(_req: AppRequest, res: AppResponse): Promise<void> {
  res.json(presentLlmStatus(buildLlmStatus()));
}

export async function llmModelsHandler(req: AppRequest, res: AppResponse): Promise<void> {
  const result = await listLlmModelsService();

  if (result.kind === 'not_configured') {
    jsonError(
      res,
      req,
      503,
      'LLM_NOT_CONFIGURED',
      'Set LLM_PROVIDER to ollama or lmstudio (and base URLs if not default).',
    );
    return;
  }
  if (result.kind === 'ollama_upstream_error') {
    jsonError(res, req, result.status, 'OLLAMA_UPSTREAM', 'Ollama tags request failed');
    return;
  }
  if (result.kind === 'lmstudio_upstream_invalid_json') {
    jsonError(res, req, 502, 'LMSTUDIO_UPSTREAM', 'Invalid JSON from LM Studio');
    return;
  }
  if (result.kind === 'lmstudio_upstream_error') {
    jsonError(
      res,
      req,
      result.status,
      'LMSTUDIO_UPSTREAM',
      'LM Studio models request failed',
      result.details,
    );
    return;
  }
  if (result.kind === 'upstream_error') {
    loggerForRequest(req).error(
      { event: 'llm.models.upstream_error', err: result.message },
      'llm list models',
    );
    jsonError(res, req, 502, 'LLM_UPSTREAM', result.message);
    return;
  }
  if (result.kind === 'ollama_upstream_invalid_json') {
    jsonError(res, req, 502, 'OLLAMA_UPSTREAM', 'Invalid JSON from Ollama');
    return;
  }
  if (result.kind === 'ollama_ok') {
    res.json(presentOpenAiModelList({ models: result.models }));
    return;
  }

  res.json(result.data);
}

export async function llmChatCompletionsHandler(req: AppRequest, res: AppResponse): Promise<void> {
  const result = await createChatCompletionsService(req.body as ChatCompletionBody);

  if (result.kind === 'not_configured') {
    jsonError(res, req, 503, 'LLM_NOT_CONFIGURED', 'Set LLM_PROVIDER to ollama or lmstudio.');
    return;
  }
  if (result.kind === 'ollama_upstream_invalid_json') {
    jsonError(res, req, 502, 'OLLAMA_UPSTREAM', 'Invalid JSON from Ollama');
    return;
  }
  if (result.kind === 'ollama_upstream_error') {
    jsonError(res, req, result.status, 'OLLAMA_UPSTREAM', 'Ollama chat failed', result.details);
    return;
  }
  if (result.kind === 'lmstudio_upstream_invalid_json') {
    jsonError(res, req, 502, 'LMSTUDIO_UPSTREAM', 'Invalid JSON from LM Studio');
    return;
  }
  if (result.kind === 'lmstudio_upstream_error') {
    jsonError(res, req, result.status, 'LMSTUDIO_UPSTREAM', 'LM Studio chat failed', result.details);
    return;
  }
  if (result.kind === 'upstream_error') {
    loggerForRequest(req).error({ event: 'llm.chat.upstream_error', err: result.message }, 'llm chat');
    jsonError(res, req, 502, 'LLM_UPSTREAM', result.message);
    return;
  }

  res.json(result.data);
}
