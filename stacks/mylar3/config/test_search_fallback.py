"""Prove year-free searches retain the native candidate-validation boundary."""
import ast
from operator import itemgetter
from pathlib import Path
import re
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock

SOURCE=Path(sys.argv.pop(1))


class SearchTest(unittest.TestCase):
    def search(self, priority, accept=False):
        tree=ast.parse((SOURCE/'getcomics.py').read_text())
        node=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='search')
        formats=next(ast.literal_eval(n.value) for n in ast.walk(tree) if isinstance(n,ast.Assign)
                     and any(isinstance(t,ast.Attribute) and t.attr=='search_format' for t in n.targets))
        calls=[]; info={'chktpb':0}
        obj=SimpleNamespace(cookie_receipt=lambda:None,search_format=formats,
                            query={'comicname':'Pokemon The Electric Tale of Pikachu','issue':'1','year':'1998'})
        def queries(value):calls.append(value);return iter([{'pack':True,'title':'verified candidate'}])
        obj.perform_search_queries=queries
        checker=MagicMock()
        def check(results, actual, **kw):
            self.assertIs(actual,info)
            return next(results) if accept and '1998' not in calls[-1] else None
        checker.check_for_first_result.side_effect=check
        namespace={'mylar':SimpleNamespace(CONFIG=SimpleNamespace(PACK_PRIORITY=priority,DDL_QUERY_DELAY=5)),
                   'logger':MagicMock(),'time':MagicMock(),'re':re,'itemgetter':itemgetter,
                   'search_filer':SimpleNamespace(search_check=lambda:checker),
                   'requests':SimpleNamespace(exceptions=SimpleNamespace(Timeout=TimeoutError,ConnectionError=ConnectionError))}
        exec(compile(ast.Module(body=[node],type_ignores=[]),'<search>','exec'),namespace)
        result=namespace['search'](obj,info)
        return calls,result,checker

    def test_year_free_fallback_exists_with_and_without_pack_priority(self):
        for priority in (True,False):
            calls,result,checker=self.search(priority)
            self.assertTrue(any('1998' not in query and '#1' in query for query in calls))
            self.assertEqual(checker.check_for_first_result.call_count,len(calls))
            self.assertEqual(result,[])

    def test_fallback_result_still_requires_native_validation(self):
        calls,result,_=self.search(True,True)
        self.assertNotIn('1998',calls[-1])
        self.assertEqual(result,[{'pack':True,'title':'verified candidate'}])


if __name__=='__main__':unittest.main()
