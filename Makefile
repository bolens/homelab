.PHONY: help doctor validate validate-strict ci-local hooks-install mirror-sync prepare-audit metadata-audit hygiene-audit docs-generate docs-check secrets secrets-files monitoring-validate monitoring-reload monitoring-smoke-check monitoring-iterate monitoring-quick monitoring-sync-blackbox

help:
	@echo "Homelab repository targets:"
	@echo "  doctor             Read-only host and repository checks"
	@echo "  validate           Python, Compose YAML, and shell validation"
	@echo "  validate-strict    Validate and require every lint dependency"
	@echo "  ci-local           Run all pre-commit and history secret checks"
	@echo "  hooks-install      Install repository pre-commit hooks"
	@echo "  mirror-sync        Fast-forward Gitea from authoritative GitHub"
	@echo "  prepare-audit      Audit stack preparation scripts and prerequisites"
	@echo "  metadata-audit     Validate stack.yaml catalog metadata"
	@echo "  hygiene-audit      Validate examples, docs, and cross-file basics"
	@echo "  docs-generate      Regenerate topology and stack catalog documents"
	@echo "  docs-check         Fail when generated documentation is stale"
	@echo "  secrets            Scan the full Git history with Gitleaks"
	@echo "  secrets-files      Scan files on disk, including ignored runtime files"
	@echo "  monitoring-iterate Validate, reload, and smoke-test monitoring"
	@echo "  monitoring-quick   Reload and smoke-test monitoring"

doctor:
	bash scripts/homelab-doctor.sh

validate:
	bash scripts/validate-repo.sh

validate-strict:
	bash scripts/validate-repo.sh --strict

ci-local:
	pre-commit run --all-files
	bash scripts/scan-secrets-gitleaks.sh git

hooks-install:
	pre-commit install --install-hooks

mirror-sync:
	bash scripts/sync-gitea-from-github.sh main

prepare-audit:
	python3 scripts/audit-prepare-scripts.py

metadata-audit:
	python3 scripts/audit-stack-metadata.py

hygiene-audit:
	python3 scripts/audit-repo-hygiene.py

docs-generate:
	python3 scripts/build-stack-catalog.py
	python3 scripts/build-topology.py --in-place

docs-check:
	python3 scripts/build-stack-catalog.py --check
	python3 scripts/build-topology.py --check

secrets:
	bash scripts/scan-secrets-gitleaks.sh git

secrets-files:
	bash scripts/scan-secrets-gitleaks.sh dir

monitoring-validate:
	bash scripts/validate-monitoring-config.sh

monitoring-reload:
	docker exec prometheus wget -qO- --post-data='' http://localhost:9090/-/reload
	docker exec alertmanager wget -qO- --post-data='' http://localhost:9093/-/reload

monitoring-smoke-check:
	bash scripts/monitoring-smoke-check.sh

# Full inner loop while tuning monitoring config.
monitoring-iterate: monitoring-validate monitoring-reload monitoring-smoke-check

# Fast path during query/rule tuning: reload + smoke only.
monitoring-quick: monitoring-reload monitoring-smoke-check

# Rebuild blackbox_nonalert + blackbox_http_paths_nonalert from documents/MONITORING-TARGETS.md (example.com only).
monitoring-sync-blackbox:
	python3 scripts/sync-blackbox-targets-from-monitoring.py stacks/prometheus/prometheus.yml.example
