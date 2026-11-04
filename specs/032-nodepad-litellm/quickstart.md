# Validation guide

1. In an isolated checkout, run `stacks/nodepad/clone-repo.sh` to prepare the pinned upstream with all maintained patches.
2. Run the focused Nodepad LiteLLM verification script and the native production build. Explicit type checking is required because existing Next configuration ignores build type errors.
3. Configure a fake canary server credential for mock-upstream tests; verify it is absent from browser assets and responses.
4. Verify forbidden routes, origins, overrides, models, and oversized requests, plus safe failures, streaming and cancellation.
5. Configure a model-only key restricted to the three chosen aliases, private gateway URL, and exact site origins. Verify the whole public hostname and API paths retain owner-only access.
6. Rebuild with the recorded first-visit build defaults. Preserve old image/environment, deploy only Nodepad, and verify health, model discovery, and a synthetic request.
7. Open existing browser settings without saving changes and confirm the prior provider/model and notes remain. The added LiteLLM option must not select itself.

Follow the stack README for the operator contract and the proxy contract for allowed actions. Record executed checks and any unverified or unavailable checks in acceptance evidence.
