# Tasks: Nodepad LiteLLM

## Phase 1: Setup

- [x] T001 Record requirements and source ownership in specs/032-nodepad-litellm/spec.md and research.md.
- [x] T002 Complete the constitution-checked design in specs/032-nodepad-litellm/plan.md, data-model.md, contracts/proxy.md, and quickstart.md.
- [x] T003 Prepare the pinned patched source with stacks/nodepad/clone-repo.sh in the isolated worktree.

## Phase 2: Shared prerequisite

- [x] T004 Record exact route/model/origin/body/token/time boundaries in specs/032-nodepad-litellm/contracts/proxy.md before the proxy implementation.

## Phase 3: US1 - Choose shared models

Independent acceptance: Discover the three allowed models and complete a synthetic request through the selected LiteLLM provider.

- [x] T005 [US1] Add the fixed-route server proxy and focused rejection/streaming tests through stacks/nodepad/patches/0008-homelab-litellm-provider.patch.
- [x] T006 [US1] Wire the key-free provider, choices, URL/header helpers, and settings UI through stacks/nodepad/patches/0008-homelab-litellm-provider.patch.

## Phase 4: US2 - Preserve existing choices

Independent acceptance: Existing saved provider/model/key fixtures and the recorded empty first-visit build overrides retain their behavior.

- [x] T007 [US2] Add client helper and saved-settings preservation tests to stacks/nodepad/patches/0008-homelab-litellm-provider.patch, with focused checks in stacks/nodepad/verify-litellm.sh.

## Phase 5: US3 - Keep shared access private

Independent acceptance: All rejection cases pass, the canary is absent from browser assets, and existing full-site owner access is verified before deployment.

- [x] T008 [US3] Update stacks/nodepad/README.md, stack.env.example, docker-compose.yml, prepare-stack.sh, stack.yaml, and caddy_snippet.conf.example as one optional protected-connection contract.
- [x] T009 [US3] Apply the full patch sequence, run focused tests/type checking and a canary production build, and record results in specs/032-nodepad-litellm/acceptance.md.

## Phase 6: Validation and rollout

- [x] T010 Regenerate affected generated documentation, review the full diff, and run focused repository checks plus make validate.
- [ ] T011 Build and deploy only Nodepad with private scoped settings and preserved defaults, recording source/image/native acceptance in specs/032-nodepad-litellm/acceptance.md without private values.
- [ ] T012 Verify preservation and rollback readiness, clean only operation-owned temporary resources after acceptance, and record the final scope in specs/032-nodepad-litellm/acceptance.md.

## Dependencies

T001 -> T002 -> T003 -> T004 -> T005 -> T006 -> T007 -> T008 -> T009 -> T010 -> T011 -> T012.

## Independent work opportunities

US1 proxy and client analysis can be reviewed independently. Operational updates to existing apps use their own private backups and do not modify the Nodepad source contract. Execute source writes serially in this worktree.

## Implementation strategy

First establish the bounded proxy and its tests, then add the selectable client option, preserve old settings, complete operator documentation, and prove the built and deployed result. No public policy change or automatic provider switch is included.
