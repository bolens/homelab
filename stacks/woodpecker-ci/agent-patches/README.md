# CI-only cgroup parent repair

This optional Woodpecker 3.20.1 agent fork preserves the existing Docker workflow
network-create repair and adds one administrator configuration field:
`WOODPECKER_BACKEND_DOCKER_CGROUP_PARENT` (`--backend-docker-cgroup-parent`).
The default is empty, preserving Docker's existing parent selection. No pipeline
schema or per-step option accepts this field. Every backend-created container,
including cold-image pull retries and service steps, receives the administrator's
parent through Docker `HostConfig.CgroupParent`.

The source pin, archive checksum, patch order, exact Go version and official base
image are recorded in `source.json`. The base stack stays unchanged. This repair
adds no ports, privileges, socket mounts, ingress routes or aggregate RAM budget.
The pipeline's existing RAM, swap, CPU and shared-memory limits remain intact.
The upstream mechanism is documented in [opencontainers/cgroups issue74](https://github.com/opencontainers/cgroups/issues/74):
the affected systemd backend omits an explicit zero swap property, so a manager
reload can reset a child's kernel swap ceiling while Docker metadata stays equal.
Docker-socket or privileged jobs can escape backend policy and remain trusted-only.

## Build and qualify before deployment

Run `build-agent.sh NEW_EMPTY_OUTPUT_DIRECTORY` with Go 1.27.3 available. It
verifies public upstream source and patches, runs the Docker backend unit tests,
and builds a static linux/amd64 agent. It does not invoke Docker. The build needs
public HTTPS access to the pinned source archive, Go proxy and checksum service.
The private output owns its HOME and caches. Do not supply credentials or reuse a
live repository as its output. Review the test log, binary hash and build metadata.

The Dockerfile copies only that binary onto the immutable official 3.20.1 image.
After source review, an administrator may build the image from the generated
`image` directory with fixed build limits, record its actual image ID, and transfer
that same image to each runner host. Verify the received ID and binary version.
Use an immutable reviewed local tag or digest. Never silently substitute an
official image: official 3.20.1 does not implement this new option. Build/publish is
a separate operational action. No shared custom-image publication policy is
changed by this proposal. The existing Docker dependency-update inventory owns
this Dockerfile. Any proposed base refresh must be reviewed together with the
source version, immutable archive, tests and source.json before acceptance.

## Host prerequisite and explicit selection

First inspect each target's actual Docker cgroup driver/version and unified
cgroup-v2 mount. The example requires Docker's `systemd` cgroup driver and host
systemd. Stop on another driver. Do not change global Docker or runc policy.
Install the reviewed `woodpecker-ci.slice.example` as the administrator-owned
`woodpecker-ci.slice` unit through the host's normal unit-management process.
Do not use a global manager reload as a validation experiment. If installing the
new unit requires a reload, plan that separately after draining CI and assessing
other services. The repair's correctness does not require inducing a reload.

Verify the loaded unit's `MemoryAccounting=yes` and `MemorySwapMax=0`, its actual
`ControlGroup`, and that ancestor's kernel `memory.swap.max` is zero. The unit has
no `MemoryMax` or CPU setting. Preserve the existing per-container limits.
A descendant's effective ceiling is the minimum along its ancestor chain, so a
child reset to `max` still cannot obtain swap beneath this zero ancestor.

Set `WOODPECKER_CGROUP_AGENT_IMAGE` in the operator's private `stack.env` to the
reviewed image. Select the example override explicitly:

```bash
docker compose --env-file stack.env -f docker-compose.yml \
  -f docker-compose.cgroup-parent.yml.example config --quiet
```

Rendering is read-only. Preparation prints guidance and never installs or starts
a unit, activates the override or recreates an agent. Configuring only the agent
container's own Compose `cgroup_parent` would leave its sibling build containers
unprotected. The backend field must be used.

## Scoped operational admission

1. Disable scheduling on each affected agent and wait for its actual active jobs
   to reach zero. Keep the server and unrelated services running. Record the
   agent image, resource policy, identity volume/config path and server-assigned
   ID. Use the existing verified recovery point without repeated app-data copies.
2. Install and verify the dedicated slice prerequisite. Preserve all existing
   network fixes, mounts, secrets, IDs and host-specific resource/concurrency
   overrides. Recreate only the drained agent with the reviewed image and explicit
   override, using `--no-deps --pull never`. Reenable it only after its original
   ID reconnects. Never wipe, share or clone `agent.conf`.
3. Run one disposable unprivileged backend step under the existing budget. Bind
   its exact source, step UUID, Docker container ID and initial PID. Inspect only
   its HostConfig, State and `/proc/PID/cgroup`. Verify `CgroupParent`, unchanged
   limits and actual membership beneath the dedicated slice. Read the child and
   every ancestor's `memory.max`/`memory.swap.max` and observe effective swap zero.
   Record memory.current/peak/events, swap.current and terminal exit/OOM state.
   Do not inspect Env/secrets or exec into unrelated containers.
4. Verify a current native job uses that same ancestry and retains its full test
   coverage. Report configured Docker limits separately from observed kernel
   enforcement. No host-wide default change, global reload experiment, periodic
   cgroup writer or limit increase is part of this validation.

Rollback drains only these agents, restores their previous image and optional
parent setting, and preserves their identity mounts. Remove the slice only after
its membership and children are empty. Do not restart Docker, alter server data,
prune shared images or delete volumes. Retain compact source/build/probe receipts
and the previous supplier until operational acceptance.

## Regression contract

`cgroup_parent_test.go` exercises actual CLI registration, configuration and
Docker create requests: empty default, administrator environment, flag precedence,
an attempted pipeline override, missing-image pull/retry and unchanged resource
and primary-network fields. The existing network-create regressions are retained.
Unit tests do not prove host cgroup ancestry. The scoped real probe above remains
required before deployment is reported complete.
