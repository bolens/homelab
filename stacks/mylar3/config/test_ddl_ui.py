"""Fail closed on upstream template drift; retain empty-queue recovery controls."""
from pathlib import Path
import sys
import unittest
from patch_ddl_ui import template

SOURCE = Path(sys.argv.pop(1))


class QueueUITest(unittest.TestCase):
    def test_patch_is_repeatable_and_empty_queue_still_has_table(self):
        source = (SOURCE.parent/'data/interfaces/default/queue_management.html').read_text()
        result = template(source)
        self.assertEqual(template(result), result)
        self.assertNotIn('%if type(resultlist)', result)
        self.assertIn('id="queue_table"', result)
        self.assertNotIn('id="btn_container"', result)
        self.assertNotIn('setInterval(activecheck', result)

    def test_upstream_drift_is_not_silently_accepted(self):
        with self.assertRaises(ValueError):
            template('<html>Changed upstream template</html>')


if __name__ == '__main__':
    unittest.main()
