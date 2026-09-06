# Tasks

- [x] T001 Trace media callers and reproduce missing-directory creation in fixtures.
- [x] T002 Implement the explicit policy and update media callers and guidance.
- [x] T003 Verify fixtures and source gates; retain hosted Compose validation evidence.
- [x] T004 Separately self-review helper ordering, all media callers, fixture assertions, and documentation.

Delivery follows hosted current-head validation through the PR.

PR #70 head `fec8c9d5bf511d737ab305bbaecf83d6b5821c2b` passed hosted repository/Compose and site-quality checks. That was the pre-merge observation. PR #70 subsequently merged at
`89996ff5f65cd4493a777ecbf5eb74d79bd5f1e7`, and all six observed workflows
on that exact revision passed, including repository/Compose and site validation.
The source implementation is complete; live preparation and service deployment
remain separate operator actions.
