import contextlib
import errno
import io
import json
import os
import tarfile
import tempfile
import unittest
import warnings
import wave
import zipfile
from pathlib import Path
from unittest import mock

import main


class UnpackMusicArchiveTest(unittest.TestCase):
    def setUp(self) -> None:
        self.enterContext(contextlib.redirect_stdout(io.StringIO()))
        self.enterContext(contextlib.redirect_stderr(io.StringIO()))

    def test_multidisc_releases_preserve_tracks_with_identical_names(self) -> None:
        disc_pairs = (
            ("CD1", "CD2"),
            ("CD 1 - Original Mixes", "CD 2 - Extended Mixes"),
            ("Disc 01 (Originals)", "Disc 02 (Remixes)"),
            ("Disk_1_Studio", "Disk_2_Live"),
            ("cd.001", "cd.002"),
        )
        for first, second in disc_pairs:
            for archive_kind in ("zip", "tar", "builtin"):
                with self.subTest(discs=(first, second), kind=archive_kind):
                    with tempfile.TemporaryDirectory() as temp:
                        root = Path(temp)
                        tracks = {
                            f"Release/{first}/Audio/01 - Song.flac": b"original mix",
                            f"Release/{second}/Audio/01 - Song.flac": b"alternate mix",
                        }
                        archive = root / f"release.{archive_kind}"
                        if archive_kind == "zip":
                            with zipfile.ZipFile(archive, "w") as output:
                                for name, payload in tracks.items():
                                    output.writestr(name, payload)
                        elif archive_kind == "tar":
                            with tarfile.open(archive, "w") as output:
                                for name, payload in tracks.items():
                                    member = tarfile.TarInfo(name)
                                    member.size = len(payload)
                                    output.addfile(member, io.BytesIO(payload))
                        else:
                            for name, payload in tracks.items():
                                path = root / name
                                path.parent.mkdir(parents=True, exist_ok=True)
                                path.write_bytes(payload)

                        environment = {"NZBPP_CATEGORY": "music", "NZBPP_FINALDIR": str(root)}
                        with mock.patch.dict(os.environ, environment, clear=True):
                            self.assertEqual(main.main(), main.SUCCESS)
                            # A repeated post-processing pass must keep both mixes.
                            self.assertEqual(main.main(), main.SUCCESS)

                        self.assertEqual((root / first / "01 - Song.flac").read_bytes(), b"original mix")
                        self.assertEqual((root / second / "01 - Song.flac").read_bytes(), b"alternate mix")
                        self.assertFalse((root / "01 - Song.flac").exists())
                        self.assertFalse((root / "Release").exists())
                        self.assertFalse(archive.exists())

    def test_same_disc_collisions_preserve_sources(self) -> None:
        for archive_kind in ("zip", "builtin"):
            with self.subTest(kind=archive_kind), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                tracks = {
                    "Release/Disc 1 (Mixes)/one/01.flac": b"one",
                    "Release/Disc 1 (Mixes)/two/01.flac": b"two",
                }
                archive = root / "release.zip"
                if archive_kind == "zip":
                    with zipfile.ZipFile(archive, "w") as output:
                        for name, payload in tracks.items():
                            output.writestr(name, payload)
                else:
                    for name, payload in tracks.items():
                        path = root / name
                        path.parent.mkdir(parents=True, exist_ok=True)
                        path.write_bytes(payload)
                environment = {"NZBPP_CATEGORY": "music", "NZBPP_FINALDIR": str(root)}
                with mock.patch.dict(os.environ, environment, clear=True):
                    self.assertEqual(main.main(), main.FAILURE)
                self.assertFalse((root / "Disc 1 (Mixes)/01.flac").exists())
                if archive_kind == "zip":
                    self.assertTrue(archive.exists())
                else:
                    for name, payload in tracks.items():
                        self.assertEqual((root / name).read_bytes(), payload)

    def test_extensionless_media_is_identified_and_unknown_text_is_retained(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            flac = root / "obfuscated-download"
            jpeg = root / "obfuscated-cover"
            sidecar = root / "obfuscated-sidecar"
            flac.write_bytes(b"fLaC" + b"\x00" * 32)
            jpeg.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 32)
            sidecar.write_text("01-track.flac\n02-track.flac\n")
            environment = {"NZBPP_CATEGORY": "music", "NZBPP_FINALDIR": str(root)}

            with mock.patch.dict(os.environ, environment, clear=True):
                self.assertEqual(main.main(), main.SUCCESS)

            self.assertTrue((root / "obfuscated-download.flac").exists())
            self.assertFalse(flac.exists())
            self.assertFalse(jpeg.exists())
            self.assertEqual(sidecar.read_text(), "01-track.flac\n02-track.flac\n")

    def test_cleanup_preserves_media_disguised_as_sidecars(self) -> None:
        stream = io.BytesIO()
        with wave.open(stream, "wb") as output:
            output.setnchannels(1)
            output.setsampwidth(2)
            output.setframerate(8000)
            output.writeframes(b"\x00\x00" * 800)
        payload = stream.getvalue()
        for archive_kind in ("zip", "tar", "builtin"):
            with self.subTest(kind=archive_kind), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                names = ("01.nfo", "02.txt", "03.log", "04.jpg", "05.cue", "Release.wav")
                archive = root / f"release.{archive_kind}"
                if archive_kind == "zip":
                    with zipfile.ZipFile(archive, "w") as output:
                        for name in names:
                            output.writestr(f"Release/{name}", payload)
                elif archive_kind == "tar":
                    with tarfile.open(archive, "w") as output:
                        for name in names:
                            member = tarfile.TarInfo(f"Release/{name}")
                            member.size = len(payload)
                            output.addfile(member, io.BytesIO(payload))
                else:
                    for name in names:
                        (root / name).write_bytes(payload)
                environment = {"NZBPP_CATEGORY": "music", "NZBPP_FINALDIR": str(root)}
                with mock.patch.dict(os.environ, environment, clear=True):
                    self.assertEqual(main.main(), main.SUCCESS)
                    self.assertEqual(main.main(), main.SUCCESS)
                for name in names:
                    target = root / (name if name.endswith(".wav") else name + ".wav")
                    self.assertEqual(target.read_bytes(), payload)
                self.assertFalse(archive.exists())

    def test_cleanup_preserves_unknown_binary_and_album_cue(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            files = {
                "unknown": b"A" * 4096 + b"\x00\xffbinary data",
                "unknown.txt": b"A" * 4096 + b"\x00\xffbinary data",
                "Release.flac": b"fLaC\x00audio",
                "Release.cue": b'FILE "Release.flac" WAVE\n  TRACK 01 AUDIO\n    INDEX 01 00:00:00\n  TRACK 02 AUDIO\n    INDEX 01 03:00:00\n',
            }
            for name, payload in files.items():
                (root / name).write_bytes(payload)
            (root / "notes.txt").write_text("Release notes\n")
            environment = {"NZBPP_CATEGORY": "music", "NZBPP_FINALDIR": str(root)}
            with mock.patch.dict(os.environ, environment, clear=True):
                self.assertEqual(main.main(), main.SUCCESS)
            for name, payload in files.items():
                self.assertEqual((root / name).read_bytes(), payload)
            self.assertFalse((root / "notes.txt").exists())

    def test_cleanup_alone_does_not_delete_disguised_media(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = root / "01.txt"
            payload = b"fLaC\x00audio"
            path.write_bytes(payload)
            main.remove_unwanted_files(root)
            self.assertEqual(path.read_bytes(), payload)

    def test_duplicate_archive_members_fail_before_overwriting_tracks(self) -> None:
        for archive_kind in ("zip", "tar"):
            for second_name in ("Release/01.flac", "Release/./01.flac"):
                with self.subTest(kind=archive_kind, second=second_name), tempfile.TemporaryDirectory() as temp:
                    root = Path(temp)
                    archive = root / f"release.{archive_kind}"
                    tracks = (("Release/01.flac", b"first mix"), (second_name, b"second mix"))
                    if archive_kind == "zip":
                        with warnings.catch_warnings():
                            warnings.simplefilter("ignore", UserWarning)
                            with zipfile.ZipFile(archive, "w") as output:
                                for name, payload in tracks:
                                    output.writestr(name, payload)
                    else:
                        with tarfile.open(archive, "w") as output:
                            for name, payload in tracks:
                                member = tarfile.TarInfo(name)
                                member.size = len(payload)
                                output.addfile(member, io.BytesIO(payload))
                    original = archive.read_bytes()
                    with self.assertRaisesRegex(ValueError, "duplicate path"):
                        main.unpack(archive)
                    self.assertEqual(archive.read_bytes(), original)
                    self.assertEqual(list(root.iterdir()), [archive])

    def test_extension_detection_refuses_to_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "track").write_bytes(b"fLaC" + b"\x00" * 8)
            (root / "track.flac").write_bytes(b"existing")

            with self.assertRaises(FileExistsError):
                main.add_missing_extensions(root)

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
            self.assertEqual((root / "release.cue").read_bytes(), b"cue")
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
                output.writestr("one/01.flac", b"one")
                output.writestr("two/01.flac", b"two")

            with self.assertRaises(FileExistsError):
                main.unpack(archive)

            self.assertTrue(archive.exists())
            self.assertFalse((root / "01.flac").exists())

class MusicProcessingSeamTest(unittest.TestCase):
    def setUp(self) -> None:
        self.enterContext(contextlib.redirect_stdout(io.StringIO()))
        self.enterContext(contextlib.redirect_stderr(io.StringIO()))

    def run_main(self, root: Path) -> int:
        with mock.patch.dict(os.environ, {"NZBPP_CATEGORY": "music", "NZBPP_FINALDIR": str(root)}, clear=True):
            return main.main()

    def snapshot(self, root: Path) -> dict[str, bytes]:
        return {path.relative_to(root).as_posix(): path.read_bytes()
                for path in root.rglob("*") if path.is_file() and not path.is_symlink()}

    def test_cue_references_follow_flattening_and_extension_repair(self) -> None:
        for kind in ("zip", "tar", "builtin"):
            for encoding in ("utf-8-sig", "cp1252"):
                with self.subTest(kind=kind, encoding=encoding), tempfile.TemporaryDirectory() as temp:
                    root = Path(temp)
                    cue = 'FILE "Audio\\Café.nfo" WAVE\r\n  TRACK 01 AUDIO\r\n    INDEX 01 00:00:00\r\n'
                    files = {"Release/Disc 1 (Mixes)/Album.cue": cue.encode(encoding),
                             "Release/Disc 1 (Mixes)/Audio/Café.nfo": b"fLaC\x00audio"}
                    archive = root / f"release.{kind}"
                    if kind == "zip":
                        with zipfile.ZipFile(archive, "w") as output:
                            for name, payload in files.items():
                                output.writestr(name, payload)
                    elif kind == "tar":
                        with tarfile.open(archive, "w") as output:
                            for name, payload in files.items():
                                member = tarfile.TarInfo(name)
                                member.size = len(payload)
                                output.addfile(member, io.BytesIO(payload))
                    else:
                        for name, payload in files.items():
                            path = root / name
                            path.parent.mkdir(parents=True, exist_ok=True)
                            path.write_bytes(payload)
                    self.assertEqual(self.run_main(root), main.SUCCESS)
                    expected = cue.replace('Audio\\Café.nfo', 'Café.nfo.flac').encode(encoding)
                    self.assertEqual((root / "Disc 1 (Mixes)/Album.cue").read_bytes(), expected)
                    self.assertEqual((root / "Disc 1 (Mixes)/Café.nfo.flac").read_bytes(), b"fLaC\x00audio")
                    before = self.snapshot(root)
                    self.assertEqual(self.run_main(root), main.SUCCESS)
                    self.assertEqual(self.snapshot(root), before)

    def test_cue_protects_unrecognized_track_named_like_text_sidecar(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "Release/Audio").mkdir(parents=True)
            (root / "Release/Audio/01.txt").write_bytes(b"unknown track content")
            (root / "Release/Album.cue").write_text('FILE Audio/01.txt WAVE\n  TRACK 01 AUDIO\n')
            self.assertEqual(self.run_main(root), main.SUCCESS)
            self.assertEqual((root / "01.txt").read_bytes(), b"unknown track content")
            self.assertIn('FILE "01.txt" WAVE', (root / "Album.cue").read_text())

    def test_invalid_cue_reference_preserves_release(self) -> None:
        for name in ("missing.flac", "../../outside.flac", "/outside.flac", "C:\\outside.flac"):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                (root / "Album.flac").write_bytes(b"fLaC\x00audio")
                (root / "Album.cue").write_text(f'FILE "{name}" WAVE\n')
                before = self.snapshot(root)
                self.assertEqual(self.run_main(root), main.FAILURE)
                self.assertEqual(self.snapshot(root), before)

    def test_duplicate_disposable_sidecars_do_not_block_music(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with zipfile.ZipFile(root / "release.zip", "w") as output:
                output.writestr("Release/CD1/Artwork/cover.jpg", b"first cover")
                output.writestr("Release/CD1/Scans/cover.jpg", b"second cover")
                output.writestr("Release/CD1/01.flac", b"fLaC\x00audio")
            self.assertEqual(self.run_main(root), main.SUCCESS)
            self.assertEqual(self.snapshot(root), {"CD1/01.flac": b"fLaC\x00audio"})

    def test_failed_repair_is_unchanged_and_can_be_retried(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            existing = root / "01.nfo.flac"
            existing.write_bytes(b"fLaC\x00existing")
            with zipfile.ZipFile(root / "release.zip", "w") as output:
                output.writestr("Release/01.nfo", b"fLaC\x00new")
            before = self.snapshot(root)
            self.assertEqual(self.run_main(root), main.FAILURE)
            self.assertEqual(self.snapshot(root), before)
            existing.rename(root / "previous.flac")
            self.assertEqual(self.run_main(root), main.SUCCESS)
            self.assertEqual((root / "01.nfo.flac").read_bytes(), b"fLaC\x00new")
            self.assertEqual((root / "previous.flac").read_bytes(), b"fLaC\x00existing")

    def test_symlink_and_special_file_inputs_are_rejected(self) -> None:
        for kind in ("directory", "broken", "archive", "fifo"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as temp:
                base = Path(temp)
                root = base / "release"
                outside = base / "outside"
                root.mkdir()
                outside.mkdir()
                (outside / "sentinel.flac").write_bytes(b"outside")
                with zipfile.ZipFile(root / "release.zip", "w") as output:
                    output.writestr("Release/CD1/01.flac", b"fLaC\x00audio")
                if kind == "directory":
                    (root / "CD1").symlink_to(outside, target_is_directory=True)
                elif kind == "broken":
                    (root / "CD1").symlink_to(outside / "missing", target_is_directory=True)
                elif kind == "archive":
                    (root / "linked.zip").symlink_to(root / "release.zip")
                else:
                    os.mkfifo(root / "input")
                original = (root / "release.zip").read_bytes()
                self.assertEqual(self.run_main(root), main.FAILURE)
                self.assertEqual((root / "release.zip").read_bytes(), original)
                self.assertEqual(self.snapshot(outside), {"sentinel.flac": b"outside"})
                self.assertFalse(any(root.glob(".unpack-music-*")))

    def test_publication_failure_rolls_back_every_original(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "Release/Audio").mkdir(parents=True)
            for name in ("01.flac", "02.flac"):
                (root / "Release/Audio" / name).write_bytes(b"fLaC\x00" + name.encode())
            (root / "Release/Album.cue").write_text('FILE "Audio/01.flac" WAVE\n')
            (root / "notes.txt").write_text("notes")
            before = self.snapshot(root)
            rename = Path.rename

            def fail_second(source: Path, target: Path) -> Path:
                if source.parent.name == "release" and target == root / "02.flac":
                    raise OSError("injected publication failure")
                return rename(source, target)

            with mock.patch.object(Path, "rename", fail_second):
                self.assertEqual(self.run_main(root), main.FAILURE)
            self.assertEqual(self.snapshot(root), before)
            self.assertFalse(any(root.glob(".unpack-music-*")))
            self.assertEqual(self.run_main(root), main.SUCCESS)

    def test_failed_rollback_retains_private_recovery_and_blocks_retry(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "Release").mkdir()
            for name in ("01.flac", "02.flac"):
                (root / "Release" / name).write_bytes(b"fLaC\x00" + name.encode())
            before = self.snapshot(root)
            rename = Path.rename

            def fail_install_and_restore(source: Path, target: Path) -> Path:
                if source.parent.name == "originals" or (source.parent.name == "release" and target == root / "02.flac"):
                    raise OSError("injected rollback failure")
                return rename(source, target)

            with mock.patch.object(Path, "rename", fail_install_and_restore):
                self.assertEqual(self.run_main(root), main.FAILURE)
            recovery = list(root.glob(".unpack-music-*"))
            self.assertEqual(len(recovery), 1)
            self.assertEqual(recovery[0].stat().st_mode & 0o777, 0o700)
            journal = json.loads((recovery[0] / "recovery.json").read_text())
            for index, name in enumerate(journal["originals"]):
                self.assertEqual((recovery[0] / "originals" / str(index)).read_bytes(), before[name])
            self.assertEqual(self.run_main(root), main.FAILURE)
            self.assertTrue(recovery[0].exists())

    def test_changed_input_aborts_without_reverting_the_other_writer(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "Release").mkdir()
            original = root / "Release/01.flac"
            original.write_bytes(b"fLaC\x00original")
            normalize = main.normalize_tree

            def other_writer(*args, **kwargs):
                normalize(*args, **kwargs)
                original.write_bytes(b"fLaC\x00updated elsewhere")

            with mock.patch.object(main, "normalize_tree", other_writer):
                self.assertEqual(self.run_main(root), main.FAILURE)
            self.assertEqual(self.snapshot(root), {"Release/01.flac": b"fLaC\x00updated elsewhere"})

    def test_concurrent_script_instance_fails_without_changes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "01.flac").write_bytes(b"fLaC\x00audio")
            before = self.snapshot(root)
            descriptor = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
            try:
                main.fcntl.flock(descriptor, main.fcntl.LOCK_EX | main.fcntl.LOCK_NB)
                self.assertEqual(self.run_main(root), main.FAILURE)
                self.assertEqual(self.snapshot(root), before)
            finally:
                os.close(descriptor)

    def test_nested_archives_are_processed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            nested = io.BytesIO()
            with zipfile.ZipFile(nested, "w") as output:
                output.writestr("Release/CD2/01.flac", b"fLaC\x00audio")
            with zipfile.ZipFile(root / "release.zip", "w") as output:
                output.writestr("inside.zip", nested.getvalue())
            self.assertEqual(self.run_main(root), main.SUCCESS)
            self.assertEqual(self.snapshot(root), {"CD2/01.flac": b"fLaC\x00audio"})

    def test_later_bad_archive_keeps_all_original_archives(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with zipfile.ZipFile(root / "a.zip", "w") as output:
                output.writestr("01.flac", b"fLaC\x00audio")
            (root / "b.zip").write_bytes(b"invalid archive")
            before = self.snapshot(root)
            self.assertEqual(self.run_main(root), main.FAILURE)
            self.assertEqual(self.snapshot(root), before)

    def test_limits_and_path_conflicts_preserve_archives(self) -> None:
        for kind in ("size", "members", "space", "path-conflict", "traversal", "nested"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                with zipfile.ZipFile(root / "release.zip", "w") as output:
                    output.writestr("01.flac", b"fLaC\x00audio")
                    output.writestr("01.flac/02.flac" if kind == "path-conflict" else
                                    "../02.flac" if kind == "traversal" else "02.flac", b"fLaC\x00audio")
                before = self.snapshot(root)
                patch = mock.patch.object(main, "MAX_EXPANDED_BYTES", 1) if kind == "size" else (
                    mock.patch.object(main, "MAX_MEMBERS", 1) if kind == "members" else
                    mock.patch.object(main.shutil, "disk_usage", return_value=mock.Mock(free=0)) if kind == "space" else
                    mock.patch.object(main, "MAX_ARCHIVES", 0) if kind == "nested" else contextlib.nullcontext())
                with patch:
                    self.assertEqual(self.run_main(root), main.FAILURE)
                self.assertEqual(self.snapshot(root), before)

    def test_missing_directory_and_cleanup_to_empty_fail(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.assertEqual(self.run_main(root / "missing"), main.FAILURE)
            with zipfile.ZipFile(root / "release.zip", "w") as output:
                output.writestr("notes.txt", b"only notes")
            before = self.snapshot(root)
            self.assertEqual(self.run_main(root), main.FAILURE)
            self.assertEqual(self.snapshot(root), before)

    def test_video_containers_are_not_mislabelled_as_audio(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "movie").write_bytes(b"\x00\x00\x00\x18ftypisom\x00video")
            (root / "movie2").write_bytes(b"\x1aE\xdf\xa3matroska\x00video")
            (root / "song").write_bytes(b"\x00\x00\x00\x18ftypM4A \x00audio")
            main.add_missing_extensions(root)
            self.assertTrue((root / "movie.mp4").exists())
            self.assertTrue((root / "movie2.mkv").exists())
            self.assertTrue((root / "song.m4a").exists())

    def test_zip_special_files_and_encryption_are_rejected(self) -> None:
        import stat
        for mode, flags in ((stat.S_IFLNK, 0), (stat.S_IFIFO, 0), (stat.S_IFREG, 1)):
            with self.subTest(mode=mode, flags=flags), tempfile.TemporaryDirectory() as temp:
                member = zipfile.ZipInfo("01.flac")
                member.external_attr = mode << 16
                member.flag_bits = flags
                archive = mock.Mock()
                archive.infolist.return_value = [member]
                with self.assertRaises(ValueError):
                    main.validate_zip_members(archive, Path(temp))

    def test_directory_conflict_is_found_before_publication(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "01.flac").mkdir()
            with zipfile.ZipFile(root / "release.zip", "w") as output:
                output.writestr("Release/01.flac", b"fLaC\x00audio")
            before = self.snapshot(root)
            self.assertEqual(self.run_main(root), main.FAILURE)
            self.assertEqual(self.snapshot(root), before)
            self.assertTrue((root / "01.flac").is_dir())

    def test_reserved_workspace_name_is_not_published(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with zipfile.ZipFile(root / "release.zip", "w") as output:
                output.writestr(".unpack-music-fake.flac", b"fLaC\x00audio")
            before = self.snapshot(root)
            self.assertEqual(self.run_main(root), main.FAILURE)
            self.assertEqual(self.snapshot(root), before)

    def test_tar_links_are_rejected_and_original_archive_is_preserved(self) -> None:
        for kind in (tarfile.SYMTYPE, tarfile.LNKTYPE, tarfile.FIFOTYPE):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                with tarfile.open(root / "release.tar", "w") as output:
                    member = tarfile.TarInfo("01.flac")
                    member.type = kind
                    member.linkname = "../../outside"
                    output.addfile(member)
                before = self.snapshot(root)
                self.assertEqual(self.run_main(root), main.FAILURE)
                self.assertEqual(self.snapshot(root), before)

    def test_repeated_archive_directory_entries_remain_supported(self) -> None:
        for kind in ("zip", "tar"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                if kind == "zip":
                    with warnings.catch_warnings():
                        warnings.simplefilter("ignore", UserWarning)
                        with zipfile.ZipFile(root / "release.zip", "w") as output:
                            output.writestr("Release/", b"")
                            output.writestr("Release/", b"")
                            output.writestr("Release/01.flac", b"fLaC\x00audio")
                else:
                    with tarfile.open(root / "release.tar", "w") as output:
                        member = tarfile.TarInfo("Release")
                        member.type = tarfile.DIRTYPE
                        output.addfile(member)
                        output.addfile(member)
                        member = tarfile.TarInfo("Release/01.flac")
                        member.size = 10
                        output.addfile(member, io.BytesIO(b"fLaC\x00audio"))
                self.assertEqual(self.run_main(root), main.SUCCESS)
                self.assertEqual(self.snapshot(root), {"01.flac": b"fLaC\x00audio"})

    def test_interrupted_publication_keeps_recoverable_originals(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "Release").mkdir()
            (root / "Release/01.flac").write_bytes(b"fLaC\x00audio")
            rename = Path.rename

            def interrupted(source: Path, target: Path) -> Path:
                if source.parent.name == "release" and target.parent == root:
                    raise KeyboardInterrupt()
                return rename(source, target)

            with mock.patch.object(Path, "rename", interrupted), self.assertRaises(KeyboardInterrupt):
                main.process_release(root)
            recovery = list(root.glob(".unpack-music-*"))
            self.assertEqual(len(recovery), 1)
            self.assertEqual((recovery[0] / "originals/0").read_bytes(), b"fLaC\x00audio")
            self.assertEqual(json.loads((recovery[0] / "recovery.json").read_text())["originals"], ["Release/01.flac"])
            self.assertEqual(self.run_main(root), main.FAILURE)

    def test_staging_on_filesystems_without_hard_links(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "Release").mkdir()
            (root / "Release/01.flac").write_bytes(b"fLaC\x00audio")
            with mock.patch.object(main.os, "link", side_effect=OSError(errno.EOPNOTSUPP, "no hard links")):
                self.assertEqual(self.run_main(root), main.SUCCESS)
            self.assertEqual(self.snapshot(root), {"01.flac": b"fLaC\x00audio"})

    def test_nested_disc_labels_are_all_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with zipfile.ZipFile(root / "release.zip", "w") as output:
                output.writestr("Release/CD1/Disc 1/01.flac", b"fLaC\x00first")
                output.writestr("Release/CD1/Disc 2/01.flac", b"fLaC\x00second")
            self.assertEqual(self.run_main(root), main.SUCCESS)
            self.assertEqual(self.snapshot(root), {"CD1/Disc 1/01.flac": b"fLaC\x00first",
                                                  "CD1/Disc 2/01.flac": b"fLaC\x00second"})

    def test_cue_encodings_and_line_endings_preserve_references(self) -> None:
        for encoding, bom in (("utf-8", b""), ("utf-16-le", b"\xff\xfe"), ("utf-16-be", b"\xfe\xff")):
            for newline in ("\r", "\n", "\r\n"):
                with self.subTest(encoding=encoding, newline=newline), tempfile.TemporaryDirectory() as temp:
                    root = Path(temp)
                    (root / "Release/Audio").mkdir(parents=True)
                    (root / "Release/Audio/01.flac").write_bytes(b"fLaC\x00one")
                    (root / "Release/Audio/02.flac").write_bytes(b"fLaC\x00two")
                    cue = newline.join(('FILE "Audio/01.flac" WAVE', '  TRACK 01 AUDIO',
                                        'FILE "Audio/02.flac" WAVE', '  TRACK 02 AUDIO', ''))
                    (root / "Release/Album.cue").write_bytes(bom + cue.encode(encoding))
                    self.assertEqual(self.run_main(root), main.SUCCESS)
                    expected = cue.replace("Audio/", "")
                    self.assertEqual((root / "Album.cue").read_bytes(), bom + expected.encode(encoding))
                    before = self.snapshot(root)
                    self.assertEqual(self.run_main(root), main.SUCCESS)
                    self.assertEqual(self.snapshot(root), before)

    def test_duplicate_sidecars_across_archives_are_discarded(self) -> None:
        for protected in (False, True):
            with self.subTest(protected=protected), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                for index in (1, 2):
                    with zipfile.ZipFile(root / f"{index}.zip", "w") as output:
                        output.writestr("Release/cover.jpg", b"cover")
                        output.writestr(f"Release/CD{index}/01.flac", b"fLaC\x00" + bytes([index]))
                        if protected and index == 2:
                            output.writestr("Release/Album.cue", b'FILE "cover.jpg" WAVE\n')
                before = self.snapshot(root)
                self.assertEqual(self.run_main(root), main.FAILURE if protected else main.SUCCESS)
                if protected:
                    self.assertEqual(self.snapshot(root), before)
                else:
                    self.assertEqual(self.snapshot(root), {"CD1/01.flac": b"fLaC\x00\x01",
                                                          "CD2/01.flac": b"fLaC\x00\x02"})

    def test_rollback_does_not_delete_a_changed_output(self) -> None:
        for replaced in (False, True):
            with self.subTest(replaced=replaced), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                (root / "Release").mkdir()
                (root / "Release/01.flac").write_bytes(b"fLaC\x00original one")
                (root / "Release/02.flac").write_bytes(b"fLaC\x00original two")
                rename = Path.rename

                def other_writer(source: Path, target: Path) -> Path:
                    if source.parent.name == "release" and target == root / "02.flac":
                        output = root / "01.flac"
                        if replaced:
                            replacement = root / "replacement"
                            replacement.write_bytes(b"fLaC\x00changed by another writer")
                            os.replace(replacement, output)
                        else:
                            output.write_bytes(b"fLaC\x00changed by another writer")
                        raise OSError("injected publication failure")
                    return rename(source, target)

                with mock.patch.object(Path, "rename", other_writer):
                    self.assertEqual(self.run_main(root), main.FAILURE)
                self.assertEqual((root / "01.flac").read_bytes(), b"fLaC\x00changed by another writer")
                recovery = list(root.glob(".unpack-music-*"))
                self.assertEqual(len(recovery), 1)
                self.assertTrue((recovery[0] / "recovery.json").exists())
                self.assertEqual(self.run_main(root), main.FAILURE)

    def test_unknown_binary_cue_is_rejected_without_changes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "01.flac").write_bytes(b"fLaC\x00audio")
            (root / "Album.cue").write_bytes(b"unknown\x00binary cue")
            before = self.snapshot(root)
            self.assertEqual(self.run_main(root), main.FAILURE)
            self.assertEqual(self.snapshot(root), before)

    def test_tar_entry_limit_is_checked_while_reading(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            first = tarfile.TarInfo("one")
            second = tarfile.TarInfo("two")
            def entries():
                yield first
                yield second
                self.fail("tar validator read beyond its entry limit")
            with mock.patch.object(main, "MAX_MEMBERS", 1), self.assertRaisesRegex(ValueError, "too many"):
                main.validate_members(entries(), Path(temp))

    def test_negative_archive_size_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp, self.assertRaisesRegex(ValueError, "negative"):
            main.archive_members([("one", False, -1)], Path(temp))

    def test_pdf_booklets_are_removed_but_disguised_audio_survives(self) -> None:
        for kind in ("zip", "builtin"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                files = {"Digital Booklet.PDF": b"%PDF-1.7\n\x00booklet",
                         "obfuscated-booklet": b"%PDF-1.7\n\x00booklet",
                         "01.pdf": b"fLaC\x00audio",
                         "unknown.pdf": b"\x00unknown binary"}
                if kind == "zip":
                    with zipfile.ZipFile(root / "release.zip", "w") as output:
                        for name, payload in files.items():
                            output.writestr(name, payload)
                else:
                    for name, payload in files.items():
                        (root / name).write_bytes(payload)
                self.assertEqual(self.run_main(root), main.SUCCESS)
                self.assertEqual(self.snapshot(root), {"01.pdf.flac": b"fLaC\x00audio",
                                                      "unknown.pdf": b"\x00unknown binary"})
                before = self.snapshot(root)
                self.assertEqual(self.run_main(root), main.SUCCESS)
                self.assertEqual(self.snapshot(root), before)

    def test_cue_referenced_pdf_is_protected_from_cleanup(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "01.pdf").write_bytes(b"%PDF-1.7\n\x00possible data")
            (root / "Album.cue").write_text('FILE "01.pdf" WAVE\n')
            before = self.snapshot(root)
            self.assertEqual(self.run_main(root), main.SUCCESS)
            self.assertEqual(self.snapshot(root), before)

    def test_tagless_audio_requires_consecutive_frames(self) -> None:
        mp3 = b"\xff\xfb\x90\x00" + b"\x00" * 413
        aac = b"\xff\xf1\x50\x80\x01\x1f\xfc\x00"
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name, payload, suffix in (("mp3", mp3 * 3, ".mp3"), ("aac", aac * 3, ".aac"),
                                          ("aiff", b"FORM\x00\x00\x00\x20AIFF\x00audio", ".aiff"),
                                          ("single", mp3, None), ("fake", b"\xff\xffgarbage", None)):
                path = root / name
                path.write_bytes(payload)
                self.assertEqual(main.detected_suffix(path), suffix)
            self.assertEqual(self.run_main(root), main.SUCCESS)
            self.assertTrue((root / "mp3.mp3").exists())
            self.assertTrue((root / "aac.aac").exists())
            self.assertTrue((root / "aiff.aiff").exists())
            self.assertTrue((root / "single").exists())

    def test_preview_lists_changes_without_modifying_release(self) -> None:
        for archived in (False, True):
            with self.subTest(archived=archived), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                files = {"Release/Audio/01.nfo": b"fLaC\x00audio",
                         "Release/Album.cue": b'FILE "Audio/01.nfo" WAVE\n',
                         "Release/booklet.pdf": b"%PDF-1.7\n\x00booklet"}
                if archived:
                    with zipfile.ZipFile(root / "release.zip", "w") as output:
                        for name, content in files.items():
                            output.writestr(name, content)
                else:
                    for name, content in files.items():
                        target = root / name
                        target.parent.mkdir(parents=True, exist_ok=True)
                        target.write_bytes(content)
                before = self.snapshot(root)
                states = {path: main.file_state(path) for path in main.tree_files(root)}
                directory_time = root.stat().st_mtime_ns
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    self.assertEqual(main.cli(["--preview", str(root)]), 0)
                self.assertIn("Remove sidecar", output.getvalue())
                self.assertIn("01.nfo.flac", output.getvalue())
                self.assertIn("Update cue FILE", output.getvalue())
                self.assertEqual(self.snapshot(root), before)
                self.assertEqual({path: main.file_state(path) for path in main.tree_files(root)}, states)
                self.assertEqual(root.stat().st_mtime_ns, directory_time)
                self.assertFalse(any(root.glob(".unpack-music-*")))

    def test_unchanged_release_skips_staging_and_publication(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "01.flac").write_bytes(b"fLaC\x00audio")
            (root / "unknown").write_bytes(b"\x00binary")
            before = self.snapshot(root)
            output = io.StringIO()
            with mock.patch.object(main.tempfile, "mkdtemp", side_effect=AssertionError("unexpected staging")), \
                    mock.patch.object(main, "publish", side_effect=AssertionError("unexpected publication")), \
                    contextlib.redirect_stdout(output):
                self.assertEqual(self.run_main(root), main.SUCCESS)
            self.assertIn("Release unchanged", output.getvalue())
            self.assertIn("1 unidentified files retained", output.getvalue())
            self.assertEqual(self.snapshot(root), before)

    def test_completion_summary_counts_actual_changes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "Release").mkdir()
            (root / "Release/01").write_bytes(b"fLaC\x00audio")
            (root / "Release/cover.jpg").write_bytes(b"cover")
            (root / "Release/unknown").write_bytes(b"\x00unknown")
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(self.run_main(root), main.SUCCESS)
            for expected in ("1 media files retained", "1 sidecars removed", "1 extensions repaired",
                             "1 unidentified files retained", "2 total files retained"):
                self.assertIn(expected, output.getvalue())

    def interrupted_workspace(self, root: Path) -> tuple[Path, dict[str, bytes]]:
        (root / "Release/Audio").mkdir(parents=True)
        (root / "Release/Audio/01.flac").write_bytes(b"fLaC\x00original one")
        (root / "Release/Audio/02.flac").write_bytes(b"fLaC\x00original two")
        (root / "Release/Album.cue").write_bytes(b'FILE "Audio/01.flac" WAVE\n')
        before = self.snapshot(root)
        rename = Path.rename
        def interrupted(source: Path, target: Path) -> Path:
            if source.parent.name == "release" and target == root / "02.flac":
                raise KeyboardInterrupt()
            return rename(source, target)
        with mock.patch.object(Path, "rename", interrupted), self.assertRaises(KeyboardInterrupt):
            main.process_release(root)
        return next(root.glob(".unpack-music-*")), before

    def test_recovery_command_restores_and_verifies_originals(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace, before = self.interrupted_workspace(root)
            self.assertEqual(main.cli(["--recover", str(workspace)]), 0)
            self.assertEqual(self.snapshot(root), before)
            self.assertFalse(workspace.exists())
            self.assertEqual(self.run_main(root), main.SUCCESS)

    def test_recovery_refuses_corruption_and_changed_outputs(self) -> None:
        for kind in ("backup", "output", "traversal", "legacy", "symlink"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                workspace, _ = self.interrupted_workspace(root)
                record = workspace / "recovery.json"
                if kind == "backup":
                    (workspace / "originals/0").write_bytes(b"corrupted backup")
                elif kind == "output":
                    changed = root / "new-file"
                    changed.write_bytes(b"fLaC\x00external update")
                    os.replace(changed, root / "01.flac")
                elif kind == "symlink":
                    (workspace / "unsafe").symlink_to(root / "01.flac")
                else:
                    journal = json.loads(record.read_text())
                    if kind == "legacy":
                        journal.pop("version")
                    else:
                        journal["originals"][0] = "../../outside"
                    record.write_text(json.dumps(journal))
                before = self.snapshot(root)
                self.assertEqual(main.cli(["--recover", str(workspace)]), 1)
                self.assertTrue(workspace.exists())
                self.assertEqual(self.snapshot(root), before)

    def test_recovery_write_failure_is_retryable(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace, original = self.interrupted_workspace(root)
            before = self.snapshot(root)
            rename = Path.rename
            def fail_second_restore(source: Path, target: Path) -> Path:
                if source.parent.name == "originals" and target.name == "02.flac":
                    raise OSError("injected recovery failure")
                return rename(source, target)
            with mock.patch.object(Path, "rename", fail_second_restore):
                self.assertEqual(main.cli(["--recover", str(workspace)]), 1)
            after = self.snapshot(root)
            # The private, empty quarantine directory is the only added artifact.
            self.assertEqual(after, before)
            self.assertEqual(main.cli(["--recover", str(workspace)]), 0)
            self.assertEqual(self.snapshot(root), original)

    def test_interrupted_recovery_can_resume(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace, original = self.interrupted_workspace(root)
            rename = Path.rename
            def interrupt_second_restore(source: Path, target: Path) -> Path:
                if source.parent.name == "originals" and target.name == "02.flac":
                    raise KeyboardInterrupt()
                return rename(source, target)
            with mock.patch.object(Path, "rename", interrupt_second_restore), self.assertRaises(KeyboardInterrupt):
                main.recover(workspace)
            self.assertTrue(workspace.exists())
            self.assertEqual(main.cli(["--recover", str(workspace)]), 0)
            self.assertEqual(self.snapshot(root), original)

    def test_preview_and_recovery_cli_need_explicit_paths(self) -> None:
        with self.assertRaises(SystemExit) as result:
            main.cli(["--recover"])
        self.assertEqual(result.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
