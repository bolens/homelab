"""Mandatory source/compile controls; does not run Docker or establish reader authority."""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

HERE = Path(__file__).parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--java-home', required=True)
    args = parser.parse_args()
    java_home = Path(args.java_home).resolve(strict=True)
    env = {k: v for k, v in os.environ.items() if k not in {'JAVA_TOOL_OPTIONS', 'JDK_JAVA_OPTIONS', '_JAVA_OPTIONS'}}
    env['KOMGA_TEST_JAVA_HOME'] = str(java_home)
    for name in ('test_parent.py', 'test_target_runner.py', 'test_class_transport.py'):
        subprocess.run([sys.executable, '-I', '-B', str(HERE / name)], env=env, check=True)
    with tempfile.TemporaryDirectory(prefix='komga-source-gate-') as directory:
        destination = Path(directory) / 'compiled'
        subprocess.run([sys.executable, '-I', '-B', str(HERE / 'build.py'), '--output', str(destination), '--java-home', str(java_home)], env=env, check=True)
        artifacts = json.loads((destination / 'artifacts.json').read_bytes())
        parent_ast = ast.parse((HERE / 'parent.py').read_text())
        suppliers = next(n for n in parent_ast.body if isinstance(n, ast.ClassDef) and n.name == 'Suppliers')
        expected = next(ast.literal_eval(n) for n in ast.walk(suppliers) if isinstance(n, ast.Set) and all(isinstance(v, ast.Constant) for v in n.elts))
        assert set(artifacts['supplier_pins']) == expected, 'owning-supplier-schema'
        assert all(hashlib.sha256((destination / n).read_bytes()).hexdigest() == pin for n, pin in artifacts['supplier_pins'].items()), 'actual-supplier-byte-map'
        env['KOMGA_COMPILED_CLASSES'] = str(destination)
        subprocess.run([sys.executable, '-I', '-B', str(HERE / 'test_compiled_effective_projection.py')], env=env, check=True)
        with tempfile.TemporaryDirectory(prefix='komga-jdk-closure-') as classes:
            subprocess.run([str(java_home / 'bin/javac'), '--release', '17', '-d', classes, *[str(HERE / name) for name in ('KomgaClasspathMetadata.java', 'KomgaEffectiveScope.java', 'TargetEffectiveScopeCase.java', 'TestEffectiveScope.java')]], env=env, check=True)
            subprocess.run([str(java_home / 'bin/java'), '-XX:-UsePerfData', '-cp', classes, 'TestEffectiveScope'], env=env, check=True)
    print('SOURCE_AND_COMPILE_CONTROLS_PASS; SPRING_CASES_UNRUN; CONFIGURED_ACCEPTANCE_FALSE')


if __name__ == '__main__':
    main()
