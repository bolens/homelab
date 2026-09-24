"""Failed-release recovery must never target an imported issue or a newer release."""
import hashlib
import json
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from reliability import report_failed


class FailedRecoveryTest(unittest.TestCase):
    def setUp(self):
        self.database = Mock()
        self.database.selectone.return_value.fetchone.return_value = {'ComicID': '2', 'Status': 'Snatched'}
        self.database.select.return_value = [{'ID': 'release-id', 'PROVIDER': 'provider', 'NZBName': 'Comic 001'}]
        self.token = hashlib.sha256(json.dumps(['release-id', 'provider', 'Comic 001']).encode()).hexdigest()
        self.queueit = Mock()
        self.factory = Mock(side_effect=self.processor)
        self.mylar = SimpleNamespace(CONFIG=SimpleNamespace(FAILED_DOWNLOAD_HANDLING=True, FAILED_AUTO=True),
                                     db=SimpleNamespace(DBConnection=lambda: self.database), workflow=SimpleNamespace(release_failed=Mock()),
                                     Failed=SimpleNamespace(FailedProcessor=self.factory),
                                     webserve=SimpleNamespace(WebInterface=lambda: SimpleNamespace(queueit=self.queueit)))
        self.patch = patch.dict(sys.modules, {'mylar': self.mylar})
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def processor(self, **kwargs):
        def process():
            kwargs['queue'].put([{'mode': 'retry', 'annchk': 'no', 'issueid': '1', 'comicid': '2',
                                  'comicname': 'Comic', 'issuenumber': '1'}])
        return SimpleNamespace(Process=process)

    def test_native_failure_processing_precedes_replacement_search(self):
        self.assertEqual(report_failed('1', '2', self.token), {'mode': 'retry'})
        self.factory.assert_called_once()
        self.queueit.assert_called_once_with(mode='want', ComicID='2', IssueID='1', ComicName='Comic', ComicIssue='1', manualsearch=True)

    def test_downloaded_issue_is_never_marked_failed(self):
        self.database.selectone.return_value.fetchone.return_value['Status'] = 'Downloaded'
        with self.assertRaises(ValueError):
            report_failed('1', '2', self.token)
        self.factory.assert_not_called()

    def test_new_release_or_ambiguous_history_is_not_retried(self):
        with self.assertRaises(ValueError):
            report_failed('1', '2', 'outdated-release')
        self.database.select.return_value *= 2
        with self.assertRaises(ValueError):
            report_failed('1', '2', self.token)
        self.factory.assert_not_called()


if __name__ == '__main__':
    unittest.main()
