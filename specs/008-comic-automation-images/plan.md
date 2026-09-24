# Plan

Build Mylar from its pinned LinuxServer base, apply checked patches and run the
native-image tests during a build stage, then copy patched application files and
health helper into the runtime stage. Build the maintenance worker from its pinned
converter base, test in a build stage, and copy only runtime Python modules.

Register homelab-mylar3 and homelab-comic-normalizer in the existing custom-image
matrix. Deny build-context inputs by default, explicitly allowing public source.
Use image overrides in Compose and remove runtime source/hook binds. Keep runtime
configuration and persistent mounts unchanged. Existing ingress needs no change.

Review all transferred work in an isolated branch, scan the publication boundary,
run native gates and make ci-local, push a feature branch, inspect PR feedback and
checks, and squash-merge without bypass. Verify GitHub/Gitea and Pages delivery and
GHCR artifacts before an authorized backed-up live transition. Finish with local
checkout synchronization and task-branch cleanup.

Constitution: portable examples, explicit image choices, unchanged exposure,
read-only CI, and separately authorized backed-up deployment remain intact.
