"""Builder-only command contract using a disposable executable CLI fixture."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]
SCRIPT=ROOT/'stacks/docker-gc/builder-cache-guard.sh'

class BuilderCacheGuardTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.log=self.root/'calls'
        self.docker=self.root/'docker'
        self.docker.write_text('''#!/usr/bin/env bash
printf '%s\\0' "$@" >> "$CALL_LOG";printf '\\n' >> "$CALL_LOG"
if [[ ${*: -1} == --help ]];then
 if [[ ${MISSING_FLAGS:-0} == 1 ]];then echo 'legacy CLI';else echo '--max-used-space --min-free-space --reserved-space';fi
 exit 0
fi
exit "${PRUNE_EXIT:-0}"
''');self.docker.chmod(0o700)
    def invoke(self,**extra):
        env={'PATH':os.environ['PATH'],'DOCKER':str(self.docker),'CALL_LOG':str(self.log),**extra}
        result=subprocess.run(['bash',str(SCRIPT)],env=env,capture_output=True,text=True)
        calls=[line.rstrip(b'\0').decode().split('\0') for line in self.log.read_bytes().splitlines()] if self.log.exists() else []
        return result,calls
    def test_default_dry_run_never_prunes_or_enters_generic_gc(self):
        result,calls=self.invoke();self.assertEqual(result.returncode,0,result.stderr);self.assertEqual(calls,[['buildx','prune','--help']]);self.assertIn('DRY RUN:',result.stdout)
    def test_opt_in_is_only_selected_private_old_builder_cache(self):
        result,calls=self.invoke(BUILDER_CACHE_DRY_RUN='false',BUILDER_CACHE_BUILDER='fixture-builder')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(calls[-1],['buildx','--builder','fixture-builder','prune','--force','--filter','private=""','--filter','until=168h','--max-used-space','20GiB','--min-free-space','40GiB','--reserved-space','4GiB'])
        self.assertNotIn('--all',calls[-1]);self.assertNotIn('immutable=""',calls[-1])
    def test_existing_generic_cleanup_opt_in_does_not_enable_builder_prune(self):
        result,calls=self.invoke(DRY_RUN='false');self.assertEqual(result.returncode,0);self.assertEqual(len(calls),1)
    def test_per_resource_dry_run_overrides_global(self):
        result,calls=self.invoke(DRY_RUN='false',BUILDER_CACHE_DRY_RUN='true');self.assertEqual(result.returncode,0);self.assertEqual(len(calls),1)
    def test_invalid_limits_and_selector_refuse_before_cli(self):
        for changes in ({'BUILDER_CACHE_MAX_GIB':'0'},{'BUILDER_CACHE_MAX_GIB':'4'},{'BUILDER_CACHE_MAX_GIB':'4097'},{'BUILDER_CACHE_MIN_FREE_GIB':'1.5'},{'BUILDER_CACHE_RESERVED_GIB':'-1'},{'BUILDER_CACHE_MIN_AGE_HOURS':'0'},{'BUILDER_CACHE_BUILDER':'--all'},{'BUILDER_CACHE_DRY_RUN':'maybe'}):
            with self.subTest(changes=changes):
                result,calls=self.invoke(**changes);self.assertEqual(result.returncode,2);self.assertEqual(calls,[])
    def test_missing_flags_refuses_without_prune_fallback(self):
        result,calls=self.invoke(BUILDER_CACHE_DRY_RUN='false',MISSING_FLAGS='1');self.assertEqual(result.returncode,2);self.assertEqual(len(calls),1)
    def test_backend_refusal_propagates_without_second_command(self):
        result,calls=self.invoke(BUILDER_CACHE_DRY_RUN='false',PRUNE_EXIT='7');self.assertEqual(result.returncode,7);self.assertEqual(len(calls),2);self.assertNotIn('completed',result.stdout)
    def test_profile_cannot_fall_through_to_generic_entrypoint(self):
        body=(ROOT/'stacks/docker-gc/docker-compose.yml').read_text();service=body.split('  builder-cache:\n',1)[1].split('\nvolumes:',1)[0]
        self.assertIn('profiles: ["builder-cache"]',service);self.assertIn('entrypoint: ["/builder-cache-guard.sh"]',service);self.assertNotIn('privileged:',service)

if __name__=='__main__':unittest.main()
