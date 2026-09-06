"""Exercise mirror synchronization against disposable local Git remotes."""

import os
from pathlib import Path
import subprocess
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "sync-gitea-from-github.sh"


class MirrorSyncTests(unittest.TestCase):
    def setUp(self):
        # Hooks export index/worktree state that must not reach fixture repos.
        self.env = {key: value for key, value in os.environ.items()
                    if not key.startswith("GIT_")}
        self.env.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.seed = self.root / "seed"
        self.source = self.root / "source.git"
        self.mirror = self.root / "mirror.git"
        self.caller = self.root / "caller"
        self.git(self.root, "init", "-q", "-b", "main", str(self.seed))
        self.commit(self.seed, "initial")
        self.git(self.root, "clone", "-q", "--bare", str(self.seed), str(self.source))
        self.git(self.root, "clone", "-q", "--bare", str(self.seed), str(self.mirror))
        self.git(self.root, "clone", "-q", str(self.source), str(self.caller))
        self.git(self.caller, "remote", "add", "backup", str(self.mirror))

    def git(self, path, *args, check=True):
        return subprocess.run(["git", "-C", str(path), *args], check=check,
                              capture_output=True, text=True, env=self.env)

    def commit(self, path, message):
        self.git(path, "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
                 "commit", "--allow-empty", "-qm", message)
        return self.git(path, "rev-parse", "HEAD").stdout.strip()

    def advance_source(self):
        head = self.commit(self.seed, "source update")
        self.git(self.seed, "push", str(self.source), "main")
        return head

    def sync(self, **extra):
        env = dict(self.env, SOURCE_REMOTE="origin", MIRROR_REMOTE="backup", **extra)
        return subprocess.run(["bash", str(SCRIPT), "main"], cwd=self.caller,
                              env=env, capture_output=True, text=True, timeout=30)

    def ref(self, repository, name):
        result = self.git(repository, "rev-parse", "--verify", name, check=False)
        return result.stdout.strip() if result.returncode == 0 else None

    def test_fast_forward_ignores_dirty_checkout_and_its_push_hook(self):
        expected = self.advance_source()
        marker = self.root / "hook-ran"
        hook = self.caller / ".git/hooks/pre-push"
        hook.write_text(f"#!/bin/sh\ntouch '{marker}'\nexit 9\n")
        hook.chmod(0o755)
        dirty = self.caller / "unrelated.txt"
        dirty.write_text("user work\n")
        before = self.ref(self.caller, "HEAD")
        result = self.sync()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.ref(self.mirror, "main"), expected)
        self.assertEqual(self.ref(self.caller, "HEAD"), before)
        self.assertEqual(dirty.read_text(), "user work\n")
        self.assertFalse(marker.exists())

    def test_bare_repository_is_supported(self):
        expected = self.advance_source()
        self.caller = self.root / "bare.git"
        self.git(self.root, "clone", "-q", "--bare", str(self.source), str(self.caller))
        self.git(self.caller, "remote", "add", "backup", str(self.mirror))
        result = self.sync()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.ref(self.mirror, "main"), expected)

    def test_linked_worktree_is_supported(self):
        expected = self.advance_source()
        linked = self.root / "linked"
        self.git(self.caller, "worktree", "add", "--detach", str(linked))
        self.caller = linked
        result = self.sync()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.ref(self.mirror, "main"), expected)

    def test_relative_remotes_from_nested_directory(self):
        expected = self.advance_source()
        self.git(self.caller, "remote", "set-url", "origin", "../source.git")
        self.git(self.caller, "remote", "set-url", "backup", "../mirror.git")
        self.caller = self.caller / "nested"
        self.caller.mkdir()
        result = self.sync()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.ref(self.mirror, "main"), expected)

    def test_runner_rejects_parent_discovery_and_continues(self):
        nested = self.caller / "nested"
        nested.mkdir()
        runner = SCRIPT.with_name("sync-gitea-mirrors.sh").read_text()
        start = runner.index("repositories=(")
        end = runner.index("\n)", start) + 2
        runner = runner[:start] + (
            f'repositories=(\n"wrong|{nested}|origin|backup|wrong-main|"\n'
            f'"valid|{self.caller}|origin|backup|github-main|"\n)'
        ) + runner[end:]
        runner = runner.replace('SYNC_HELPER="$SCRIPT_DIR/sync-gitea-from-github.sh"',
                                f'SYNC_HELPER="{SCRIPT}"')
        script = self.root / "runner.sh"
        script.write_text(runner)
        result = subprocess.run(["bash", str(script)], capture_output=True,
                                text=True, timeout=30, env=self.env)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("not a repository root", result.stderr)
        self.assertIsNone(self.ref(self.mirror, "wrong-main"))
        self.assertEqual(self.ref(self.mirror, "github-main"), self.ref(self.source, "main"))

    def test_only_source_tags_are_published(self):
        self.git(self.seed, "tag", "published")
        self.git(self.seed, "push", str(self.source), "refs/tags/published")
        self.git(self.caller, "tag", "local-only")
        result = self.sync()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIsNotNone(self.ref(self.mirror, "refs/tags/published"))
        self.assertIsNone(self.ref(self.mirror, "refs/tags/local-only"))

    def test_separate_destination_preserves_gitea_main(self):
        fork = self.commit(self.seed, "Gitea-only work")
        self.git(self.seed, "push", str(self.mirror), "main")
        expected = self.ref(self.source, "main")
        result = self.sync(MIRROR_BRANCH="github-main")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.ref(self.mirror, "main"), fork)
        self.assertEqual(self.ref(self.mirror, "github-main"), expected)

    def test_prefixed_annotated_tags_preserve_existing_gitea_tags(self):
        self.git(self.seed, "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
                 "tag", "-a", "v1", "-m", "published tag")
        self.git(self.seed, "push", str(self.source), "refs/tags/v1")
        expected = self.ref(self.source, "refs/tags/v1")
        self.git(self.mirror, "tag", "v1", "main")
        original = self.ref(self.mirror, "refs/tags/v1")
        result = self.sync(MIRROR_BRANCH="github-main", MIRROR_TAG_PREFIX="github/")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.ref(self.mirror, "refs/tags/github/v1"), expected)
        self.assertEqual(self.ref(self.mirror, "refs/tags/v1"), original)

    def test_conflicting_destination_tag_is_never_replaced(self):
        original = self.ref(self.mirror, "main")
        self.git(self.mirror, "tag", "v1", original)
        self.advance_source()
        self.git(self.seed, "tag", "v1")
        self.git(self.seed, "push", str(self.source), "refs/tags/v1")
        result = self.sync()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.ref(self.mirror, "refs/tags/v1"), original)

    def test_divergence_is_checked_after_fetching_mirror_objects(self):
        fork = self.commit(self.seed, "Gitea-only work")
        self.git(self.seed, "push", str(self.mirror), "main")
        result = self.sync()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("divergent", result.stderr)
        self.assertNotIn("Not a valid commit", result.stderr)
        self.assertEqual(self.ref(self.mirror, "main"), fork)

    def test_unavailable_remote_does_not_look_like_missing_branch(self):
        self.git(self.caller, "remote", "set-url", "backup", str(self.root / "missing.git"))
        result = self.sync()
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("fast-forwarding", result.stdout)


if __name__ == "__main__":
    unittest.main()
