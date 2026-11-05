# Implementation plan

Extend the existing root `.woodpecker.yml` while retaining its single result.
Use Node, JDK, .NET and Go lanes with pinned existing runtimes. Install only
checksum-bound public tools into fresh task-local directories and validate an
exact committed full clone in each lane. This avoids shared Python/npm ABI state
and ignored checkout inputs. Docker CLI configuration rendering has no daemon.

Small wrappers own tool installation, mandatory default-CI compiler execution and
weekly-link policy reuse. Hermetic fixtures cover archive boundaries, failed
prerequisites, skipped tests, event coverage and hosted retirement guards. Include
these fixtures in normal repository validation as well as the native policy lane.

Keep existing hosted jobs until the operator proves native PR/main/cron and
migrates protection. Actual Docker/security/deployment jobs are exceptions rather
than credential expansion. Update source and delivery documentation together.

Constitution check: portable public examples and placeholders remain intact;
validation reads tracked source and isolated fixtures only; no stack deployment,
application data access, generated catalog edit or live configuration change.
