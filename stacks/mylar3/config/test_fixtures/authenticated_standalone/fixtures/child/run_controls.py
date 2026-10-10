"""Run only owning suites from this explicit public fixture closure."""
from pathlib import Path
import sys
import unittest
root=Path(__file__).resolve().parent/'source'
sys.path.insert(0,str(root))
suite=unittest.defaultTestLoader.loadTestsFromNames(['test_publication_retained_standalone','test_standalone_pack_report_deny','test_pack_records','test_standalone_resources'])
result=unittest.TextTestRunner(verbosity=2).run(suite)
raise SystemExit(not result.wasSuccessful())
