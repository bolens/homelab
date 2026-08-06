# Stack metadata

Each top-level `stacks/<name>/` directory uses `stack.yaml` as its catalog
record. `stack.yml` is not supported. Metadata documents intended deployment
and operational characteristics; `docker-compose.yml` remains authoritative
for container behavior.

Required top-level fields are:

```text
name, default_port, databases, health, monitoring, shared_resources,
type, category, exposure, data_profile, host_requirements, links,
backup, volumes, auth, resources, placement, lifecycle, runtime_security
```

The directory name and `name` must match. `default_port` is either `null` or a
container port. Resource profiles use `small`, `medium`, or `large`; GPU profile
uses `none` or `required`. Valid types are `api`, `cli_tool`, `service`, and
`web_app`.

Run:

```bash
make metadata-audit
make validate
```

For a newly cataloged stack, maintainers can create a conservative draft with:

```bash
python3 scripts/audit-stack-metadata.py --fix-missing
git diff
```

Inferred metadata is only a draft. Review application type, ports, exposure,
PII, authentication, backup priority, volumes, resource sizing, links, and
placement against the README and Compose file. The audit warns when metadata
describes a deployable service but its `docker-compose.yml` is absent.

`runtime_security` records service names that use privileged mode, host
networking, the Docker socket, or a floating image tag. These lists make
security-sensitive exceptions reviewable and must exactly match Compose:

```bash
python3 scripts/audit-stack-metadata.py --sync-runtime-security
```

Review every resulting change. Prefer removing an exception—especially a
floating image tag—before accepting it in metadata.
