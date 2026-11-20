# Woodpecker agents in virtual machines

Run the existing Docker backend inside one dedicated VM per agent. Each guest
owns the Docker engine, networks, volumes, and build cache used by its
workflows. The hypervisor imposes a CPU, RAM, and disk budget for the whole
guest. Use separate guests for untrusted PRs and any trusted job that needs
privileged execution or access to a Docker socket.

Keep the guest off the LAN bridge. A network boundary enforced outside the
guest must block the host management plane, private and link-local addresses,
and other guests. Allow the agent's existing control-plane destination and
port explicitly. Permit the forge, registries, dependency mirrors, and other
job dependencies through the chosen egress policy. Apply equivalent IPv6 rules
or disable guest IPv6. Host shares, devices other than the virtual machine's
own hardware, the hypervisor socket, and the hypervisor's Docker socket stay
outside the guest. QEMU user-mode networking can run without allocating a host
Docker network. With its `restrict=on` option, packages and the forge require
explicit forwarding or a controlled egress service.

## Prepare the guest

1. Give the guest its own virtual disk and install Docker Engine and the Compose
   plugin there. Size the guest for the sum of the existing job limits at the
   desired concurrency, including parallel test services. Preserve the per-step
   limits in the example and qualify higher concurrency with the full suite.
2. Copy the Compose example into the guest. Create a private environment file
   from `agent.env.example` and keep the per-agent token in the separate
   owner-readable file it points to. Use the existing reviewed agent image and verify
   its digest or image ID in the guest. The server endpoint must use trusted TLS
   or an existing authenticated private transport with a narrowly scoped
   firewall rule.
3. From inside the guest, use a dedicated Compose project and render the
   configuration without printing the credential.

   ```bash
   docker compose --env-file /path/to/private/agent.env \
     -f docker-compose.yml.example -p woodpecker-guest config --quiet
   ```

The socket in the example belongs to the guest. The agent has sole access to
it. The Compose project uses the guest's host network for the agent connection
while the backend creates and removes pipeline networks inside the guest.
Never attach an external network to all jobs. Each guest gets its own identity
volume.

## Qualify and switch one agent at a time

- Set a server-side required filter such as `!node=isolated-qualification`
  before the guest connects. Agent-reported labels alone do not confine the
  new agent to qualification workflows. Verify that the tagged job can clone
  and pull its real
  pinned tools, services resolve each other by name, and artifacts move between
  steps. Check that the workflow network appears only on the guest Docker
  engine and is removed after success, failure, and cancellation.
- Verify from the guest and a build step that a listening host canary and
  private destinations are unreachable. Check that the allowed forge and
  registry paths remain reachable. Keep publication disabled during
  qualification.
- Run representative browser, database, image and devcontainer builds, and
  scheduled or release checks that this agent will execute. Verify timeouts,
  cleanup, and aggregate limits on the actual hypervisor. Keep any platform or
  privileged lanes with their current provider until an isolated replacement
  runs the full workload.
- Disable scheduling on the old agent and wait for its active work to finish.
  Preserve the old agent image and identity volume. Give the replacement its
  own identity, move the scheduling labels only after qualification, and verify
  an exact PR and a genuine main push. For rollback, drain the replacement and
  restore the old scheduler entry from its original state.
