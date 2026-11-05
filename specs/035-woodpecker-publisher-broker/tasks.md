# Tasks and evidence

- [x] Establish exact Woodpecker signature and pre-queue secret-fetch contracts.
- [x] Coordinate the queue-safe lease protocol with publisher helper owners.
- [x] Implement authenticated source policy, bounded leases and JIT redemption.
- [x] Exercise signature/ref/metadata/tag, replay and lease boundaries locally.
- [x] Verify isolated, preserving opt-in preparation with a stub Docker CLI.
- [x] Include actual compiled dependency notices and race/vet CI coverage.
- [ ] Complete target validators, full repository validation and image proof.
- [ ] Obtain independent security/integration review on the frozen candidate.
- [ ] Verify live signing key, private credentials, proxy and queued-helper fixtures.
- [ ] Verify backups, unchanged state and explicitly authorized deployment.

The current 3.20.1-aligned dependency graph reports no vulnerabilities with
Go vulnerability tooling. Source and dependency checks do not establish a
live deployment or an audit of unrelated upstream images.
