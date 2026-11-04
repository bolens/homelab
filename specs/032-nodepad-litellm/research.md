# Research: Nodepad LiteLLM

- Decision: Add a separate LiteLLM provider and same-origin server proxy. Existing `ai-settings.ts` URL/header helpers already serve enrichment and ghost requests. Preserve their behavior for all existing providers.
- Rationale: Browser calls cannot resolve the Docker service address, and a server-held restricted key avoids distributing provider credentials. Reusing the existing Ollama proxy would expose arbitrary paths/methods and forward browser credentials.
- Alternatives: Direct browser calls to the public gateway depend on separate origin/auth access and distribute a key. Repointing Ollama would change existing defaults and protocol behavior. Both are rejected.
- Decision: Maintain patch 0008 after the seven existing patches, with a plain testable server module and route adapters.
- Rationale: `clone-repo.sh` owns the pinned source and applies patches in lexical order. Run it only in the isolated worktree; it resets the nested checkout.
- Decision: Use native Node tests, explicit focused type checking, and a production build. The existing Next configuration ignores build type errors, so build success alone is insufficient.
- Deployment evidence: The current browser bundle contains empty first-visit provider and Ollama-model build overrides. Keep both arguments empty, preserving OpenRouter and `openai/gpt-4o` fallbacks. No browser-storage migration is needed.
- Access prerequisite: Inspect the exact full-host application and its attached owner allow rule in the authenticated Cloudflare dashboard; a generic HTTP403 does not prove the policy. Existing documented DNS/tunnel tokens do not establish Access read permissions. No Access policy changes are part of this feature.

Read-only research source locations: `lib/ai-settings.ts:15-54,184-221,306-355`, `components/project-sidebar.tsx:115-146,367-458,653-678`, `app/page.tsx:937-951`, `app/api/ollama/[[...path]]/route.ts`, and `next.config.mjs:42` in the pinned patched checkout. Research delegated under the Spec Kit plan skill; no research agent accessed live data or changed files.
