.PHONY: monitoring-validate monitoring-reload monitoring-smoke-check monitoring-iterate monitoring-quick monitoring-sync-blackbox

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
	python3 scripts/sync_blackbox_targets_from_monitoring.py stacks/prometheus/prometheus.yml.example
