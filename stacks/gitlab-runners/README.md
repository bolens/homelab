# GitLab Runners

GitLab Runners are CI/CD job execution agents that connect to a GitLab instance and run pipeline jobs in isolated containers.

**Docs:** https://docs.gitlab.com/runner/install/docker.html
**GitHub:** https://github.com/gitlabhq/gitlab-runner

## Usage

Registers one or more runners against the GitLab stack using a registration token. Each runner spawns Docker-in-Docker or shell executors for pipeline jobs. No web UI; managed entirely through the GitLab web interface.

## Setup

1. Copy `stack.env.example` to `stack.env` and fill in required values.
2. Set TZ to your local timezone.
3. Obtain a runner registration token from GitLab (Admin > CI/CD > Runners).
4. Register each runner: `docker compose run --rm gitlab-runner register`
5. Deploy: `docker compose up -d`

## Environment variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| TZ | No | America/New_York | Container timezone |

## Notes

- Runner config is persisted in a volume; re-registration is not needed after restarts.
- Docker-in-Docker executor requires privileged mode — review security implications.
- Runners must be able to reach the GitLab instance by hostname or IP.
