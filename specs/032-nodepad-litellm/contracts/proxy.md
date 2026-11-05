# Nodepad LiteLLM proxy contract

- Client base: `/api/litellm/v1`, independent of saved custom URLs.
- GET `/models`: Return only models in the configured allowlist, without credentials, upstream headers, or errors containing provider details.
- POST `/chat/completions`: Require an exact permitted Origin, JSON object, permitted model, bounded messages/body/output tokens, and allowed chat options. Ignore no unsupported override fields: reject them.
- Other routes/methods: Reject without contacting the upstream.
- Missing or invalid private server configuration: Safe 503.
- Invalid origin/model/body: Safe 4xx, without contacting upstream.
- Redirect/upstream failure: Safe generic failure, without following redirects or returning raw upstream error bodies.
- Success: Preserve JSON/SSE content while excluding sensitive headers. Stop upstream work on cancellation or configured timeout.
- Access: Full-site owner authentication, including these paths, is an operator prerequisite. Origin checks are not authentication.

Concrete request, output token, and timeout bounds are documented with the implementation and exercised at their boundary values by focused tests.

## Concrete limits

- JSON request body: at most 1 MiB of actual UTF-8 bytes, enforced while reading regardless of Content-Length.
- Messages: 1 through 64, with string content and only system/user/assistant roles.
- Output: integer `max_tokens` from 1 through 8192, default 2048.
- Upstream wait and complete streamed response: at most 60 seconds; cancellation aborts upstream work.
- Accepted chat keys: `model`, `messages`, `max_tokens`, `temperature`, `response_format`, `stream`, `stream_options`, `top_p`, `seed`, and `stop`. Reject other fields, including credential, destination, provider, and retry overrides.
- Browser origins: exact normalized origins in `NODEPAD_ALLOWED_ORIGINS`, or the exact `NODEPAD_SITE_URL` origin when an explicit list is absent. Invalid or missing origin configuration fails closed for POST.
- Server base: HTTP(S), without URL credentials, query, or fragment. Only the fixed model/chat suffixes are appended. Redirects are disabled.
- Inbound body reading is separately bounded to 10 seconds before the upstream budget begins.

Copilot Gemini and the optional OpenRouter free router count reasoning against
output tokens. The client grants those LiteLLM synthesis requests 1200 tokens.
Other provider and model budgets remain at 220 tokens.
