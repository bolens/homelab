"""Legacy grammar and child isolation controls; real SDK runs in the image gate."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import tagger_legacy as legacy
from tagger_runtime import ProcessResult


class LegacyTests(unittest.TestCase):
    def test_ambiguous_or_lossy_values_are_refused_before_child_execution(self):
        for metadata in ({'series':'Literal ^ caret'}, {'series':'<_~_>'},
                         {'unknown':'value'}, {'year':True},
                         {'credits':[{'role':'Translator','person':'Person'}]},
                         {'credits':[{'role':'Writer','person':'Surname, First'}]},
                         {'credits':[{'role':'Writer','person':'Person:alias'}]},
                         {'web_links':['https://example.invalid/a','https://example.invalid/b']}):
            with self.subTest(metadata=metadata),self.assertRaises(ValueError):legacy.metadata_argument(metadata)

    def test_exact_legacy_fork_is_required(self):
        banner=b'ComicTagger 1.3.5 [ninjas.walk.alone / SHURIKEN]\n'
        self.assertTrue(legacy.version_supported(ProcessResult('ok',0,banner,b'')))
        for output in (b'ComicTagger 1.6.0b11.dev0\n',banner.replace(b'SHURIKEN',b'other')):
            self.assertFalse(legacy.version_supported(ProcessResult('ok',0,output,b'')))

    def test_child_receives_only_owned_archive_and_private_offline_configuration(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);archive=root/'tagged.cbz'
            with zipfile.ZipFile(archive,'w') as output:output.writestr('01.jpg',b'page')
            results=[ProcessResult('ok',0,b'ComicTagger 1.3.5 [ninjas.walk.alone / SHURIKEN]\n',b''),
                     ProcessResult('ok',0,b'',b'Save complete.\n')]
            with patch.object(legacy,'run',side_effect=results) as child:
                self.assertEqual(legacy.save(archive,{'series':'Series, = title','issue':'1'},workdir=root).state,'saved')
            args=child.call_args.args[0]
            self.assertEqual(args[-1],str(archive));self.assertEqual(args[args.index('--type')+1],'cr')
            self.assertEqual(Path(args[args.index('--configfolder')+1]).parent,root)
            self.assertFalse(set(args)&{'-o','--online','-e','--delete-rar','--rename','--cv-api-key'})
            self.assertFalse(list(root.glob('.legacy-*')))

    @unittest.skipUnless(Path('/app/mylar3/lib/comictaggerlib/options.py').is_file(),
                         'bundled Legacy SDK required; custom image gate')
    def test_actual_pinned_parser_preserves_scalar_lists_and_credits(self):
        sys.path.insert(0,'/app/mylar3')
        try:
            from lib.comictaggerlib.options import Options
            metadata=Options().parseMetadataFromString(legacy.metadata_argument(
                dict(series='Series, = title',issue='1',description='Description, = detail',year=2025,
                     characters=['One','Two'],credits=[dict(role='Writer',person='A Person')],
                     web_links=['https://example.invalid/issue'])) )
            self.assertEqual(metadata.series,'Series, = title');self.assertEqual(metadata.comments,'Description, = detail')
            self.assertEqual(metadata.year,'2025');self.assertEqual(metadata.characters,'One, Two')
            self.assertEqual(metadata.credits[0]['person'],'A Person')
            self.assertEqual(metadata.webLink,'https://example.invalid/issue')
        finally:sys.path.remove('/app/mylar3')


if __name__=='__main__':unittest.main()
