import io
import os
import tarfile
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

import main


class UnpackMusicArchiveTest(unittest.TestCase):
    def test_zip_is_flattened_but_disc_directories_are_retained(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive = root / "b5DYhAXZ70hSHZ4OmAFwhYz3G.zip"
            (root / "old.NFO").write_bytes(b"old")
            with zipfile.ZipFile(archive, "w") as output:
                output.writestr("Release/Artwork/cover.jpg", b"cover")
                output.writestr("Release/release.cue", b"cue")
                output.writestr("Release/release.m3u", b"playlist")
                output.writestr("Release/release.sfv", b"checksums")
                output.writestr("Release/release.srr", b"metadata")
                output.writestr("Release/notes.TXT", b"notes")
                output.writestr("Release/rip.log", b"log")
                output.writestr("Release/video.mp4", b"video")
                output.writestr("Release/CD 1/Audio/01.flac", b"one")
                output.writestr("Release/CD2/02.flac", b"two")
                output.writestr("Release/CD 01/03.flac", b"three")
                output.writestr("Release/CD01/04.flac", b"four")
                output.writestr("Release/Disc 01/05.flac", b"five")
                output.writestr("Release/Disc 02/06.flac", b"six")

            main.unpack(archive)

            self.assertEqual((root / "CD 1/01.flac").read_bytes(), b"one")
            self.assertEqual((root / "video.mp4").read_bytes(), b"video")
            self.assertEqual((root / "CD2/02.flac").read_bytes(), b"two")
            self.assertEqual((root / "CD 01/03.flac").read_bytes(), b"three")
            self.assertEqual((root / "CD01/04.flac").read_bytes(), b"four")
            self.assertEqual((root / "Disc 01/05.flac").read_bytes(), b"five")
            self.assertEqual((root / "Disc 02/06.flac").read_bytes(), b"six")
            self.assertFalse((root / "cover.jpg").exists())
            self.assertFalse((root / "release.cue").exists())
            self.assertFalse((root / "release.m3u").exists())
            self.assertFalse((root / "release.sfv").exists())
            self.assertFalse((root / "release.srr").exists())
            self.assertFalse((root / "notes.TXT").exists())
            self.assertFalse((root / "rip.log").exists())
            self.assertFalse((root / "old.NFO").exists())
            self.assertFalse(archive.exists())

    def test_main_cleans_files_when_builtin_unpacker_removed_archive(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            release = root / "Three_Days_Grace-Outsider"
            release.mkdir()
            (release / "01.flac").write_bytes(b"audio")
            (release / "folder.jpg").write_bytes(b"cover")
            (release / "release.m3u").write_bytes(b"playlist")
            (release / "stream.M3U8").write_bytes(b"playlist")
            (release / "rip.LOG").write_bytes(b"log")
            (release / "art.PNG").write_bytes(b"art")
            (release / "rip.AccuRip").write_bytes(b"verification")
            (release / "checksums.MD5").write_bytes(b"checksums")
            (release / "checksums.SFV").write_bytes(b"checksums")
            (release / "disc.TOC").write_bytes(b"table of contents")
            (release / "source.NZB").write_bytes(b"source")
            (release / "playlist.PLS").write_bytes(b"playlist")
            (release / "website.URL").write_bytes(b"shortcut")
            disc = release / "Disc 01/Audio"
            disc.mkdir(parents=True)
            (disc / "02.flac").write_bytes(b"disc audio")
            environment = {
                "NZBPP_CATEGORY": "music",
                "NZBPP_FINALDIR": str(root),
            }

            with mock.patch.dict(os.environ, environment, clear=True):
                self.assertEqual(main.main(), main.SUCCESS)

            self.assertTrue((root / "01.flac").exists())
            self.assertTrue((root / "Disc 01/02.flac").exists())
            self.assertFalse((root / "folder.jpg").exists())
            self.assertFalse((root / "release.m3u").exists())
            self.assertFalse((root / "stream.M3U8").exists())
            self.assertFalse((root / "rip.LOG").exists())
            self.assertFalse((root / "art.PNG").exists())
            self.assertFalse((root / "rip.AccuRip").exists())
            self.assertFalse((root / "checksums.MD5").exists())
            self.assertFalse((root / "checksums.SFV").exists())
            self.assertFalse((root / "disc.TOC").exists())
            self.assertFalse((root / "source.NZB").exists())
            self.assertFalse((root / "playlist.PLS").exists())
            self.assertFalse((root / "website.URL").exists())
            self.assertFalse(release.exists())

    def test_tar_is_also_flattened(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive = root / "release.tar"
            payload = b"audio"
            with tarfile.open(archive, "w") as output:
                member = tarfile.TarInfo("Release/Nested/01.flac")
                member.size = len(payload)
                output.addfile(member, io.BytesIO(payload))

            main.unpack(archive)

            self.assertEqual((root / "01.flac").read_bytes(), payload)
            self.assertFalse(archive.exists())

    def test_flattening_refuses_duplicate_filenames(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive = root / "release.zip"
            with zipfile.ZipFile(archive, "w") as output:
                output.writestr("one/cover.jpg", b"one")
                output.writestr("two/cover.jpg", b"two")

            with self.assertRaises(FileExistsError):
                main.unpack(archive)

            self.assertTrue(archive.exists())
            self.assertFalse((root / "cover.jpg").exists())


if __name__ == "__main__":
    unittest.main()
