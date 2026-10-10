import contextlib
import errno
import io
import json
import os
import shutil
import subprocess
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
                output.writestr("Release/release.m3u", b"CD 1/Audio/01.flac\nCD2/02.flac\n")
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
            (release / "release.m3u").write_bytes(b"01.flac\n")
            (release / "stream.M3U8").write_bytes(b"Disc 01/Audio/02.flac\n")
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

    @staticmethod
    def tagged_flac(tags: dict[str, str], *, embedded_cue: bool = False) -> bytes:
        def field(value: bytes) -> bytes:
            return len(value).to_bytes(4, "little") + value
        comments = field(b"fixture") + len(tags).to_bytes(4, "little")
        comments += b"".join(field(f"{key}={value}".encode()) for key, value in tags.items())
        streaminfo = b"\x00\x00\x00\x22" + bytes(34)
        comment_header = bytes([4 if embedded_cue else 132]) + len(comments).to_bytes(3, "big")
        cue = b"\x85\x00\x00\x01\x00" if embedded_cue else b""
        return b"fLaC" + streaminfo + comment_header + comments + cue + b"audio fixture"

    def test_lone_track_from_album_fails_before_cleanup_or_publication(self) -> None:
        for tags in ({"TRACK": "9", "TRACKTOTAL": "10"}, {"TRACKNUMBER": "09/10"},
                     {"TRACKNUMBER": "1", "TOTALTRACKS": "10"}):
            with self.subTest(tags=tags), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                (root / "Release.flac").write_bytes(self.tagged_flac(tags))
                (root / "notes.nfo").write_text("release notes")
                before = self.snapshot(root)
                with mock.patch.object(main, "publish") as publish:
                    self.assertEqual(self.run_main(root), main.FAILURE)
                    publish.assert_not_called()
                self.assertEqual(self.snapshot(root), before)
                self.assertFalse(any(root.glob(".unpack-music-*")))
                with self.assertRaisesRegex(ValueError, "track .* of 10"):
                    main.preview(root)

    def test_complete_obfuscated_album_retains_all_ten_tracks(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for track in range(1, 11):
                (root / f"{track:032x}.flac").write_bytes(self.tagged_flac({"TRACK": str(track), "TRACKTOTAL": "10"}))
            before = self.snapshot(root)
            self.assertEqual(self.run_main(root), main.SUCCESS)
            self.assertEqual(self.snapshot(root), before)

    def test_numbered_flac_gaps_and_duplicates_fail_without_totals(self) -> None:
        for numbers in ((11,), (10, 10), (1, 3), (1, 1)):
            with self.subTest(numbers=numbers), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                for index, number in enumerate(numbers):
                    (root / f"track-{index}.flac").write_bytes(self.tagged_flac(
                        {"ALBUM": "Fixture", "TRACKNUMBER": str(number)}))
                (root / "notes.nfo").write_text("preserved notes")
                before = self.snapshot(root)
                with mock.patch.object(main, "publish") as publish:
                    self.assertEqual(self.run_main(root), main.FAILURE)
                    publish.assert_not_called()
                self.assertEqual(self.snapshot(root), before)

    def test_contiguous_flac_numbers_without_totals_remain_valid(self) -> None:
        for numbers in ((1,), (1, 2, 3)):
            with self.subTest(numbers=numbers), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                for number in numbers:
                    (root / f"{number}.flac").write_bytes(self.tagged_flac(
                        {"ALBUM": "Fixture", "TRACKNUMBER": str(number)}))
                before = self.snapshot(root)
                self.assertEqual(self.run_main(root), main.SUCCESS)
                self.assertEqual(self.snapshot(root), before)

    def test_totalless_numbered_discs_and_album_image_keep_their_exceptions(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for disc in ("CD1", "CD2"):
                folder = root / disc
                folder.mkdir()
                for number in (1, 2):
                    (folder / f"{number}.flac").write_bytes(self.tagged_flac(
                        {"ALBUM": "Fixture", "TRACKNUMBER": str(number)}))
            self.assertEqual(self.run_main(root), main.SUCCESS)
            self.assertEqual(len(list(root.rglob('*.flac'))), 4)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "Image.flac").write_bytes(self.tagged_flac({"TRACKNUMBER": "11"}))
            (root / "Image.cue").write_text('FILE "Image.flac" WAVE\n TRACK 01 AUDIO\n')
            before = self.snapshot(root)
            self.assertEqual(self.run_main(root), main.SUCCESS)
            self.assertEqual(self.snapshot(root), before)

    def test_single_tracks_and_album_images_are_not_rejected(self) -> None:
        for kind in ("single", "untagged", "cue", "embedded", "comment-cue"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                tags = {} if kind == "untagged" else {"TRACK": "1", "TRACKTOTAL": "1" if kind == "single" else "10"}
                if kind == "comment-cue":
                    tags["CUESHEET"] = 'FILE "Release.flac" WAVE'
                (root / "Release.flac").write_bytes(self.tagged_flac(tags, embedded_cue=kind == "embedded"))
                if kind == "cue":
                    (root / "Release.cue").write_text('FILE "Release.flac" WAVE\n TRACK 01 AUDIO\n')
                self.assertEqual(self.run_main(root), main.SUCCESS)
                self.assertTrue((root / "Release.flac").exists())

    def test_metadata_aliases_cannot_mask_missing_tracks_or_conflicts(self) -> None:
        variants = [
            {"TRACKNUMBER": "1", "TRACKTOTAL": "1", "TOTALTRACKS": "11"},
            {"TRACKNUMBER": "1/11", "TRACKTOTAL": ""},
            {"TRACKNUMBER": "", "TRACK": "11"},
            {"TRACKNUMBER": "1", "TRACK": "2", "TRACKTOTAL": "1"},
            {"TRACKNUMBER": "1", "TRACKTOTAL": "1", "tracktotal": "11"},
            {"TRACKNUMBER": "1", "TRACKTOTAL": "1", "DISCNUMBER": "1", "DISC": "2"},
        ]
        for tags in variants:
            with self.subTest(tags=tags), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                (root / "track.flac").write_bytes(self.tagged_flac(tags))
                (root / "notes.nfo").write_text("retained notes")
                before = self.snapshot(root)
                with mock.patch.object(main, "publish") as publish:
                    self.assertEqual(self.run_main(root), main.FAILURE)
                    publish.assert_not_called()
                self.assertEqual(self.snapshot(root), before)

    def test_blank_and_equivalent_aliases_fall_through(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "one.flac").write_bytes(self.tagged_flac({
                "TRACKNUMBER": "", "TRACK": "01/01", "TRACKTOTAL": "", "TOTALTRACKS": "1",
                "DISCNUMBER": "", "DISC": "01/01", "DISCTOTAL": "", "TOTALDISCS": "1",
                "tracktotal": "01"}))
            main.process_release(root, require_completeness=True)
            before = self.snapshot(root)
            main.process_release(root, require_completeness=True)
            self.assertEqual(self.snapshot(root), before)

    def test_declared_disc_totals_reject_missing_or_conflicting_discs(self) -> None:
        variants = [
            {"DISCNUMBER": "1", "DISCTOTAL": "2"},
            {"DISCNUMBER": "1/2"}, {"DISC": "1/2", "DISCTOTAL": ""},
            {"DISCNUMBER": "1", "TOTALDISCS": "2"},
            {"DISCNUMBER": "1/1", "DISCTOTAL": "2"},
            {"DISCNUMBER": "1", "DISCTOTAL": "1", "TOTALDISCS": "2"},
        ]
        for disc_tags in variants:
            with self.subTest(tags=disc_tags), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                (root / "one.flac").write_bytes(self.tagged_flac({
                    "ALBUM": "Fixture", "TRACKNUMBER": "1", "TRACKTOTAL": "1", **disc_tags}))
                (root / "notes.nfo").write_text("retained notes")
                before = self.snapshot(root)
                self.assertEqual(self.run_main(root), main.FAILURE)
                self.assertEqual(self.snapshot(root), before)

    def test_declared_disc_sets_keep_edition_boundaries(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for edition, total in (("original", 2), ("deluxe", 3)):
                for disc in range(1, total + 1):
                    folder = root / edition / f"CD{disc}"
                    folder.mkdir(parents=True)
                    (folder / f"{edition}-{disc}.flac").write_bytes(self.tagged_flac({
                        "ALBUM": "Fixture", "TRACKNUMBER": "1/1", "DISCNUMBER": f"{disc}/{total}"}))
            main.preview(root, require_completeness=True)
            main.process_release(root, require_completeness=True)
            before = self.snapshot(root)
            main.process_release(root, require_completeness=True)
            self.assertEqual(self.snapshot(root), before)

    def test_unknown_album_folder_groups_survive_repeated_processing(self) -> None:
        for total in (False, True):
            with self.subTest(total=total), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                for name in ("one", "two"):
                    folder = root / name
                    folder.mkdir()
                    tags = {"TRACKNUMBER": "1"}
                    if total:
                        tags["TRACKTOTAL"] = "1"
                    (folder / f"{name}.flac").write_bytes(self.tagged_flac(tags))
                    (folder / "notes.nfo").write_text("disposable notes")
                main.process_release(root)
                before = self.snapshot(root)
                main.process_release(root)
                self.assertEqual(self.snapshot(root), before)
                self.assertEqual(set(before), {"one/one.flac", "two/two.flac"})

    def test_strict_completeness_rejects_unproven_tail_and_preserves_archives(self) -> None:
        for archive in (False, True):
            with self.subTest(archive=archive), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                content = {f"Release/{track}.flac": self.tagged_flac({"ALBUM": "Fixture", "TRACKNUMBER": str(track)})
                           for track in (1, 2)}
                content["Release/notes.nfo"] = b"retained notes"
                if archive:
                    with zipfile.ZipFile(root / "release.zip", "w") as output:
                        for name, payload in content.items():
                            output.writestr(name, payload)
                else:
                    for name, payload in content.items():
                        path = root / name
                        path.parent.mkdir(exist_ok=True)
                        path.write_bytes(payload)
                before = self.snapshot(root)
                with self.assertRaisesRegex(ValueError, "unproven"), mock.patch.object(main, "publish") as publish:
                    main.process_release(root, require_completeness=True)
                publish.assert_not_called()
                self.assertEqual(self.snapshot(root), before)
                with self.assertRaisesRegex(ValueError, "unproven"):
                    main.preview(root, require_completeness=True)
                self.assertEqual(self.snapshot(root), before)

    def test_strict_playlist_evidence_survives_repairs_flattening_and_retries(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            folder = root / "Release" / "Audio"
            folder.mkdir(parents=True)
            (folder / "one").write_bytes(self.tagged_flac({"TRACKNUMBER": "1"}))
            (folder / "two").write_bytes(self.tagged_flac({"TRACKNUMBER": "2"}))
            (folder.parent / "tracks.m3u").write_bytes(b"\xef\xbb\xbf# fixture\r\nAudio/one.flac\r\nAudio/two.flac\r\n")
            (folder / "notes.nfo").write_text("disposable notes")
            main.process_release(root, require_completeness=True)
            before = self.snapshot(root)
            self.assertEqual(before["tracks.m3u"], b"\xef\xbb\xbf# fixture\r\none.flac\r\ntwo.flac\r\n")
            main.process_release(root, require_completeness=True)
            self.assertEqual(self.snapshot(root), before)

    def test_strict_playlist_must_cover_every_unproven_audio_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name in ("one", "two"):
                (root / f"{name}.mp3").write_bytes(b"ID3audio fixture")
            (root / "tracks.m3u").write_text("one.mp3\n")
            before = self.snapshot(root)
            with self.assertRaisesRegex(ValueError, "unproven"):
                main.process_release(root, cleanup=False, require_completeness=True)
            self.assertEqual(self.snapshot(root), before)
            (root / "tracks.m3u").write_text("one.mp3\ntwo.mp3\n")
            main.process_release(root, require_completeness=True)

    def test_strict_cue_image_and_known_track_total_are_supported(self) -> None:
        for kind in ("cue", "embedded", "total"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                tags = {"TRACKNUMBER": "1/1"} if kind == "total" else {"TRACKNUMBER": "11"}
                (root / "image.flac").write_bytes(self.tagged_flac(tags, embedded_cue=kind == "embedded"))
                if kind == "cue":
                    (root / "image.cue").write_text('FILE "image.flac" WAVE\n TRACK 01 AUDIO\n')
                main.process_release(root, require_completeness=True)
                before = self.snapshot(root)
                main.process_release(root, require_completeness=True)
                self.assertEqual(self.snapshot(root), before)

    def test_strict_nzbget_option_preview_cli_and_invalid_values(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for value, status in (("yes", main.SUCCESS), ("invalid", main.FAILURE)):
                with mock.patch.dict(os.environ, {"NZBPP_CATEGORY": "music", "NZBPP_FINALDIR": str(root),
                                                  "NZBPO_REQUIRECOMPLETENESS": value}, clear=True), \
                     mock.patch.object(main, "process_release") as process:
                    self.assertEqual(main.main(), status)
                    if value == "yes":
                        process.assert_called_once_with(root, verify_audio=False, require_completeness=True)
                    else:
                        process.assert_not_called()
            with mock.patch.object(main, "preview") as preview:
                self.assertEqual(main.cli(["--preview", str(root), "--require-completeness"]), 0)
                preview.assert_called_once_with(root, verify_audio=False, require_completeness=True)
            with self.assertRaises(SystemExit):
                main.cli(["--recover", str(root), "--require-completeness"])

    def test_playlist_entries_must_resolve_to_distinct_audio_files(self) -> None:
        for strict in (False, True):
            with self.subTest(strict=strict), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                (root / "one.flac").write_bytes(self.tagged_flac({"ALBUM": "Fixture", "TRACKNUMBER": "1"}))
                (root / "tracks.m3u").write_text("one.flac\none.FLAC\n")
                (root / "notes.nfo").write_text("retained notes")
                before = self.snapshot(root)
                with self.assertRaisesRegex(ValueError, "distinct audio"), mock.patch.object(main, "publish") as publish:
                    main.process_release(root, require_completeness=strict)
                publish.assert_not_called()
                self.assertEqual(self.snapshot(root), before)
                with self.assertRaisesRegex(ValueError, "distinct audio"):
                    main.preview(root, require_completeness=strict)
                self.assertEqual(self.snapshot(root), before)

    def test_obfuscated_playlist_uses_reconciled_blank_and_disc_aliases(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for track in (1, 2):
                (root / f"hash-{track}.flac").write_bytes(self.tagged_flac({
                    "ALBUM": "Fixture", "ALBUMARTIST": "", "ALBUM ARTIST": "Artist", "ARTIST": "Artist",
                    "TITLE": f"Song {track}", "TRACKNUMBER": "", "TRACK": str(track),
                    "DISCNUMBER": "01/01" if track == 1 else "", "DISC": "1/1"}))
            (root / "tracks.m3u").write_text("01 Artist Song 1.flac\n02 Artist Song 2.flac\n")
            main.preview(root, require_completeness=True)
            main.process_release(root, require_completeness=True)
            before = self.snapshot(root)
            main.process_release(root, require_completeness=True)
            self.assertEqual(self.snapshot(root), before)
            self.assertEqual(before["tracks.m3u"], b"hash-1.flac\nhash-2.flac\n")

    def test_disc_ancestry_stops_at_selected_release_root(self) -> None:
        for ancestor in ("normal", "CD1", "Disc 2 - Remixes"):
            with self.subTest(ancestor=ancestor), tempfile.TemporaryDirectory() as temp:
                root = Path(temp) / ancestor / "release"
                root.mkdir(parents=True)
                for edition in ("original", "remaster"):
                    folder = root / edition
                    folder.mkdir()
                    (folder / f"{edition}.flac").write_bytes(self.tagged_flac({
                        "ALBUM": "Fixture", "TRACKNUMBER": "1/1", "DISCNUMBER": "1/1"}))
                before = self.snapshot(root)
                main.preview(root, require_completeness=True)
                main.process_release(root, require_completeness=True)
                main.process_release(root, require_completeness=True)
                self.assertEqual(self.snapshot(root), before)

    def test_compatible_repeated_positions_merge_nonempty_totals(self) -> None:
        for first, second in (("1", "01/01"), ("01/01", "1")):
            with self.subTest(first=first), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                (root / "one.flac").write_bytes(self.tagged_flac({
                    "TRACKNUMBER": first, "tracknumber": second,
                    "DISCNUMBER": first, "discnumber": second}))
                main.process_release(root, require_completeness=True)
                before = self.snapshot(root)
                main.process_release(root, require_completeness=True)
                self.assertEqual(self.snapshot(root), before)

    def test_strict_playlist_rewrite_rejects_unreadable_references_before_publication(self) -> None:
        for name in ("hash:one.flac", "hash\\one.flac"):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                (root / name).write_bytes(self.tagged_flac({
                    "ALBUM": "Fixture", "ARTIST": "Artist", "TITLE": "Song", "TRACKNUMBER": "1"}))
                (root / "tracks.m3u").write_text("01 Artist Song.flac\n")
                before = self.snapshot(root)
                with self.assertRaisesRegex(ValueError, "represented in a playlist"), mock.patch.object(main, "publish") as publish:
                    main.process_release(root, require_completeness=True)
                publish.assert_not_called()
                self.assertEqual(self.snapshot(root), before)

    def test_strict_playlist_references_escape_leading_space_and_comment_marker(self) -> None:
        for name in (" one.mp3", "#one.mp3"):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                folder = root / "Audio"
                folder.mkdir()
                (folder / name).write_bytes(b"ID3audio fixture")
                (root / "tracks.m3u").write_text(f"Audio/{name}\n")
                main.process_release(root, require_completeness=True)
                before = self.snapshot(root)
                self.assertEqual(before["tracks.m3u"], f"./{name}\n".encode())
                main.process_release(root, require_completeness=True)
                self.assertEqual(self.snapshot(root), before)

    def test_independent_editions_with_distinct_disc_labels_remain_repeatable(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for edition, label, disc in (("original", "CD1 - Original Mixes", "1/1"),
                                         ("deluxe", "CD1 - Extended Mixes", "1/2"),
                                         ("deluxe", "CD2 - Bonus Mixes", "2/2")):
                folder = root / edition / label
                folder.mkdir(parents=True)
                (folder / "one.flac").write_bytes(self.tagged_flac({
                    "ALBUM": "Fixture", "TRACKNUMBER": "1/1", "DISCNUMBER": disc}))
            before = self.snapshot(root)
            main.process_release(root, require_completeness=True)
            main.process_release(root, require_completeness=True)
            self.assertEqual(self.snapshot(root), before)

    def test_invalid_flac_metadata_does_not_invent_missing_tracks(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for payload in (b"fLaC", b"fLaC\x84\xff\xff\xff", self.tagged_flac({"TRACK": "9", "TRACKTOTAL": "unknown"})):
                (root / "Release.flac").write_bytes(payload)
                self.assertEqual(self.run_main(root), main.SUCCESS)

    def test_unsuccessful_downloads_skip_before_any_processing(self) -> None:
        statuses = [
            {"NZBPP_TOTALSTATUS": status} for status in ("FAILURE", "WARNING", "DELETED")
        ] + [{"NZBPP_STATUS": "FAILURE/PAR"}, {"NZBPP_PARSTATUS": "1", "NZBPP_UNPACKSTATUS": "2"},
             {"NZBPP_PARSTATUS": "3"}, {"NZBPP_PARSTATUS": "4"}, {"NZBPP_UNPACKSTATUS": "1"},
             {"NZBPP_UNPACKSTATUS": "3"}, {"NZBPP_UNPACKSTATUS": "4"}]
        for status in statuses:
            with self.subTest(status=status), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                (root / "notes.nfo").write_text("diagnostic notes")
                before = self.snapshot(root)
                environment = {"NZBPP_CATEGORY": "music", "NZBPP_FINALDIR": str(root), **status}
                with mock.patch.dict(os.environ, environment, clear=True), mock.patch.object(main, "process_release") as process:
                    self.assertEqual(main.main(), main.SKIPPED)
                    process.assert_not_called()
                self.assertEqual(self.snapshot(root), before)

    def test_successful_and_unspecified_statuses_keep_processing(self) -> None:
        for status in ({}, {"NZBPP_TOTALSTATUS": "SUCCESS", "NZBPP_STATUS": "SUCCESS/ALL",
                            "NZBPP_PARSTATUS": "2", "NZBPP_UNPACKSTATUS": "0", "NZBPP_SCRIPTSTATUS": "FAILURE"}):
            with self.subTest(status=status), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                (root / "track.flac").write_bytes(b"fLaC\x00audio")
                with mock.patch.dict(os.environ, {"NZBPP_CATEGORY": "music", "NZBPP_FINALDIR": str(root), **status}, clear=True):
                    self.assertEqual(main.main(), main.SUCCESS)

    def test_partial_duplicate_and_conflicting_albums_fail_without_cleanup(self) -> None:
        variants = [((1, 10), (9, 10)), ((1, 2), (1, 2)), ((1, 2), (2, 3)), ((1, 2), (0, 2))]
        for tracks in variants:
            with self.subTest(tracks=tracks), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                for index, (track, total) in enumerate(tracks):
                    (root / f"hash-{index}.flac").write_bytes(self.tagged_flac(
                        {"TRACK": str(track), "TRACKTOTAL": str(total), "ALBUM": "Album"}))
                (root / "notes.nfo").write_text("diagnostic notes")
                before = self.snapshot(root)
                self.assertEqual(self.run_main(root), main.FAILURE)
                self.assertEqual(self.snapshot(root), before)

    def test_partial_album_archive_is_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with zipfile.ZipFile(root / "release.zip", "w") as output:
                for track in (1, 9):
                    output.writestr(f"Release/{track}.flac", self.tagged_flac(
                        {"TRACK": str(track), "TRACKTOTAL": "10", "ALBUM": "Album"}))
                output.writestr("Release/notes.nfo", "diagnostic notes")
            before = self.snapshot(root)
            self.assertEqual(self.run_main(root), main.FAILURE)
            self.assertEqual(self.snapshot(root), before)
            self.assertFalse(any(root.glob(".unpack-music-*")))

    def test_completeness_keeps_separate_discs_albums_and_artists(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for album, artist, disc in (("Same Album", "A", "01/2"), ("Same Album", "A", "2/2"),
                                        ("Same Album", "B", "1"), ("Other Album", "A", "1")):
                for track in (1, 2):
                    name = f"{album}-{artist}-{disc.replace('/', '-')}-{track}.flac"
                    (root / name).write_bytes(self.tagged_flac({"TRACKNUMBER": str(track), "TRACKTOTAL": "2",
                                                               "ALBUM": album, "ALBUMARTIST": artist, "DISCNUMBER": disc}))
            before = self.snapshot(root)
            self.assertEqual(self.run_main(root), main.SUCCESS)
            self.assertEqual(self.snapshot(root), before)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for disc in ("CD 1 - Originals", "CD 2 - Remixes"):
                (root / disc).mkdir()
                for track in (1, 2):
                    (root / disc / f"{track}.flac").write_bytes(self.tagged_flac({"TRACK": str(track), "TRACKTOTAL": "2"}))
            self.assertEqual(self.run_main(root), main.SUCCESS)
            self.assertEqual(len(list(root.rglob("*.flac"))), 4)

    def test_verification_failure_missing_tool_and_timeout_preserve_release(self) -> None:
        for kind in ("missing", "failure", "timeout"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                (root / "obfuscated.nfo").write_bytes(b"fLaC\x00damaged audio")
                (root / "notes.nfo").write_text("diagnostic notes")
                before = self.snapshot(root)
                result = subprocess.CompletedProcess([], 1 if kind == "failure" else 0)
                side_effect = subprocess.TimeoutExpired("ffmpeg", 600) if kind == "timeout" else None
                with mock.patch.object(main.shutil, "which", return_value=None if kind == "missing" else "/ffmpeg"), \
                     mock.patch.object(main.subprocess, "run", return_value=result, side_effect=side_effect), \
                     self.assertRaises(ValueError):
                    main.process_release(root, verify_audio=True)
                self.assertEqual(self.snapshot(root), before)
                self.assertFalse(any(root.glob(".unpack-music-*")))

    def test_verification_checks_unchanged_release_once_and_maps_all_audio(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "track.flac").write_bytes(b"fLaC\x00audio")
            with mock.patch.object(main.shutil, "which", return_value="/ffmpeg"), \
                 mock.patch.object(main.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)) as run, \
                 mock.patch.object(main, "publish") as publish:
                main.process_release(root, verify_audio=True)
                publish.assert_not_called()
                run.assert_called_once()
                command = run.call_args.args[0]
                self.assertEqual(command[command.index("-map") + 1], "0:a")
                self.assertIn("-xerror", command)
                self.assertIn("-nostdin", command)
                self.assertEqual(command[command.index("-protocol_whitelist") + 1], "file,pipe")

    def test_cp437_scene_nfo_cleanup_preserves_media_and_unknown_binary(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            art = "┌─────┐\r\n│ ■ Artist: Fixture ■ │\r\n└─────┘\r\n".encode("cp437")
            (root / "release.nfo").write_bytes(art)
            (root / "unknown.nfo").write_bytes(art + b"\xffbinary")
            (root / "control.nfo").write_bytes(art + b"\x00binary")
            (root / "audio.nfo").write_bytes(b"fLaC\x00audio")
            (root / "art.txt").write_bytes(art)
            self.assertTrue(main.disposable(root / "release.nfo"))
            self.assertEqual(self.run_main(root), main.SUCCESS)
            self.assertFalse((root / "release.nfo").exists())
            for name in ("unknown.nfo", "control.nfo", "art.txt"):
                self.assertTrue((root / name).exists())
            self.assertEqual((root / "audio.nfo.flac").read_bytes(), b"fLaC\x00audio")

    def test_empty_audio_without_totals_preserves_release(self) -> None:
        for suffix in sorted(main.AUDIO_SUFFIXES):
            with self.subTest(suffix=suffix), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                (root / f"empty{suffix.upper()}").write_bytes(b"")
                (root / "release.nfo").write_text("evidence")
                before = {path.name: path.read_bytes() for path in root.iterdir()}
                self.assertEqual(self.run_main(root), main.FAILURE)
                self.assertEqual(before, {path.name: path.read_bytes() for path in root.iterdir()})
                with self.assertRaisesRegex(ValueError, "empty audio file"):
                    main.plan_tree(root, cleanup=False, extensions=False, flatten=False)

    def test_empty_audio_archive_and_cue_remain_untouched(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive = root / "release.zip"
            with zipfile.ZipFile(archive, "w") as output:
                output.writestr("Release/image.flac", b"")
                output.writestr("Release/image.cue", 'FILE "image.flac" WAVE\n')
            (root / "release.nfo").write_text("evidence")
            before = {path.name: path.read_bytes() for path in root.iterdir()}
            self.assertEqual(self.run_main(root), main.FAILURE)
            self.assertEqual(before, {path.name: path.read_bytes() for path in root.iterdir()})

    def test_empty_unknown_and_sidecar_files_do_not_trigger_audio_guard(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "audio.flac").write_bytes(b"fLaC\x00audio")
            (root / "unknown").write_bytes(b"")
            (root / "empty.nfo").write_bytes(b"")
            self.assertEqual(self.run_main(root), main.SUCCESS)
            self.assertTrue((root / "unknown").exists())
            self.assertFalse((root / "empty.nfo").exists())

    def test_playlist_without_track_totals_detects_obfuscated_partial_album(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for track in (1, 2, 5):
                (root / f"hash-{track}.flac").write_bytes(self.tagged_flac({
                    "ALBUM": "Fixture", "ARTIST": "Artist", "TITLE": f"Song {track}", "TRACKNUMBER": str(track)}))
            (root / "hashed-list").write_text("".join(f"{track:02d}-artist-song_{track}.flac\n" for track in range(1, 15)))
            (root / "release.nfo").write_text("evidence")
            before = {path.name: path.read_bytes() for path in root.iterdir()}
            self.assertEqual(self.run_main(root), main.FAILURE)
            self.assertEqual(before, {path.name: path.read_bytes() for path in root.iterdir()})

    def test_complete_obfuscated_playlist_is_cleaned_without_renaming_audio(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for track, title in ((1, "Song (Mix - Edit)"), (2, "Song (A & B Remix)")):
                (root / f"hash-{track}.flac").write_bytes(self.tagged_flac({
                    "ALBUM": "Fixture", "ARTIST": "Artist", "TITLE": title, "TRACKNUMBER": str(track)}))
            (root / "hashed-list").write_text("01-artist-song_(mix_edit).flac\n02-artist-song_(a_and_b_remix).flac\n")
            self.assertEqual(self.run_main(root), main.SUCCESS)
            self.assertEqual({path.name for path in root.iterdir()}, {"hash-1.flac", "hash-2.flac"})

    def test_hashed_scene_playlist_and_repeated_musicbrainz_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for track in (1, 2):
                tags = {"ALBUM": "Fixture", "ALBUMARTIST": "Artist", "ARTIST": "Artist feat. Guest",
                        "TITLE": f"Song {track}", "TRACKNUMBER": str(track), "TRACKTOTAL": "2"}
                # Build valid separate comments for the multi-valued field.
                values = [f"{key}={value}".encode() for key, value in tags.items() if key != "MUSICBRAINZ_ARTISTID"]
                values += [b"MUSICBRAINZ_ARTISTID=first", b"MUSICBRAINZ_ARTISTID=second", b"ARTISTS=Artist", b"ARTISTS=Guest"]
                data = (4).to_bytes(4, "little") + b"test" + len(values).to_bytes(4, "little")
                data += b"".join(len(value).to_bytes(4, "little") + value for value in values)
                payload = b"fLaC\x84" + len(data).to_bytes(3, "big") + data
                (root / f"hash-{track}.flac").write_bytes(payload)
                self.assertEqual(main.flac_album_metadata(root / f"hash-{track}.flac")[0]['TRACKTOTAL'], '2')
            (root / "release.m3u").write_text("01-artist_guest-song_1-1234abcd.flac\n02-artist_guest-song_2-deadbeef.flac\n")
            self.assertEqual(self.run_main(root), main.SUCCESS)
            self.assertFalse((root / "release.m3u").exists())

    def test_partial_playlist_inside_archive_preserves_original_archive_and_sidecars(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive = root / "release.zip"
            with zipfile.ZipFile(archive, "w") as output:
                output.writestr("Release/01.flac", b"fLaC\x00audio")
                output.writestr("Release/release.m3u", "01.flac\n02.flac\n")
            (root / "release.nfo").write_text("evidence")
            before = {path.name: path.read_bytes() for path in root.iterdir()}
            self.assertEqual(self.run_main(root), main.FAILURE)
            self.assertEqual(before, {path.name: path.read_bytes() for path in root.iterdir()})

    def test_exact_playlist_multidisc_and_missing_reference(self) -> None:
        for missing in (False, True):
            with self.subTest(missing=missing), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                for disc in (1, 2):
                    (root / f"CD{disc}").mkdir()
                    if disc == 1 or not missing:
                        (root / f"CD{disc}" / "01.flac").write_bytes(b"fLaC\x00audio")
                (root / "release.m3u8").write_text("#EXTM3U\nCD1\\01.flac\nCD2/01.flac\n", encoding="utf-8-sig")
                before = {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()}
                self.assertEqual(self.run_main(root), main.FAILURE if missing else main.SUCCESS)
                if missing:
                    self.assertEqual(before, {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()})
                else:
                    self.assertFalse((root / "release.m3u8").exists())

    def test_unsafe_or_unrelated_playlists_are_retained(self) -> None:
        cases = ("https://example.invalid/one.flac\n", "../one.flac\n", "/one.flac\n",
                 "one.flac\none.flac\n", "one.flac\nunknown text\n", "missing.flac\n")
        for text in cases:
            with self.subTest(text=text), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                (root / "audio.flac").write_bytes(b"fLaC\x00audio")
                for name in ("list", "list.m3u"):
                    (root / name).write_text(text)
                self.assertEqual(self.run_main(root), main.SUCCESS)
                for name in ("list", "list.m3u"):
                    self.assertEqual((root / name).read_text(), text)

    def test_conflicting_archive_playlists_preserve_both_original_archives(self) -> None:
        for suffix in (".m3u", ".m3u8", ".txt"):
            with self.subTest(suffix=suffix), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                for index, text in enumerate(("unrelated.flac\n", "one.flac\nmissing.flac\n")):
                    with tarfile.open(root / f"release-{index}.tar", "w") as output:
                        payloads = {f"Release/list{suffix}": text.encode(), f"Release/{index}.flac": b"fLaC\x00audio"}
                        if index == 1:
                            payloads['Release/one.flac'] = b"fLaC\x00audio"
                        for name, payload in payloads.items():
                            member = tarfile.TarInfo(name)
                            member.size = len(payload)
                            output.addfile(member, io.BytesIO(payload))
                before = self.snapshot(root)
                self.assertEqual(self.run_main(root), main.FAILURE)
                self.assertEqual(self.snapshot(root), before)

    def test_aif_extension_and_disguised_image_remain_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            payloads = {'song.aif': b'FORM\x00\x00\x00\x00AIFFaudio', 'cover.aif': b'\x89PNG\r\n\x1a\nimage'}
            for name, payload in payloads.items():
                (root / name).write_bytes(payload)
            self.assertEqual(self.run_main(root), main.SUCCESS)
            self.assertEqual(self.snapshot(root), payloads)

    def test_cue_referenced_playlist_text_stays_protected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "list").write_text("missing1.flac\nmissing2.flac\n")
            (root / "release.cue").write_text('FILE "list" BINARY\n')
            self.assertEqual(self.run_main(root), main.SUCCESS)
            self.assertTrue((root / "list").exists())

    def test_binary_srr_header_cleanup_preserves_unknown_and_disguised_audio(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            name = b"pyReScene Auto 0.5"
            header = b"iii\x01\x00" + (9 + len(name)).to_bytes(2, "little") + len(name).to_bytes(2, "little") + name
            (root / "release.SRR").write_bytes(header + b"\x00binary metadata")
            (root / "minimal.srr").write_bytes(b"iii\x00\x00\x07\x00")
            (root / "unknown.srr").write_bytes(b"\x00unknown binary")
            (root / "truncated.srr").write_bytes(header[:-1])
            (root / "bad-size.srr").write_bytes(b"iii\x01\x00\x09\x00\x01\x00")
            (root / "bad-flags.srr").write_bytes(b"iii\x02\x00\x07\x00")
            (root / "audio.srr").write_bytes(b"fLaC\x00audio")
            self.assertEqual(self.run_main(root), main.SUCCESS)
            for filename in ("release.SRR", "minimal.srr"):
                self.assertFalse((root / filename).exists())
            for filename in ("unknown.srr", "truncated.srr", "bad-size.srr", "bad-flags.srr"):
                self.assertTrue((root / filename).exists())
            self.assertEqual((root / "audio.srr.flac").read_bytes(), b"fLaC\x00audio")

    def test_cue_referenced_binary_srr_stays_protected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            payload = b"iii\x00\x00\x07\x00"
            (root / "release.srr").write_bytes(payload)
            (root / "release.cue").write_text('FILE "release.srr" BINARY\n')
            self.assertEqual(self.run_main(root), main.SUCCESS)
            self.assertEqual((root / "release.srr").read_bytes(), payload)

    def test_cp437_nfo_cue_reference_stays_protected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            payload = "┌──┐\r\n│ Fixture │\r\n└──┘".encode("cp437")
            (root / "release.nfo").write_bytes(payload)
            (root / "release.cue").write_text('FILE "release.nfo" BINARY\n')
            self.assertEqual(self.run_main(root), main.SUCCESS)
            self.assertEqual((root / "release.nfo").read_bytes(), payload)

    def test_nzbget_verification_option_and_preview_cli(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with mock.patch.dict(os.environ, {"NZBPP_CATEGORY": "music", "NZBPP_FINALDIR": str(root),
                                              "NZBPO_VERIFYAUDIO": "yes"}, clear=True), \
                 mock.patch.object(main, "process_release") as process:
                self.assertEqual(main.main(), main.SUCCESS)
                process.assert_called_once_with(root, verify_audio=True, require_completeness=False)
            with mock.patch.object(main, "preview") as preview:
                self.assertEqual(main.cli(["--preview", str(root), "--verify-audio"]), 0)
                preview.assert_called_once_with(root, verify_audio=True, require_completeness=False)
            with self.assertRaises(SystemExit):
                main.cli(["--recover", str(root), "--verify-audio"])

    @unittest.skipUnless(shutil.which("ffmpeg"), "optional ffmpeg unavailable")
    def test_real_audio_verification_rejects_damaged_archive_without_changes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            good = root / "generated.flac"
            subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-f", "lavfi", "-i", "sine=duration=0.1", str(good)], check=True)
            payload = good.read_bytes()
            main.process_release(root, verify_audio=True)
            self.assertEqual(good.read_bytes(), payload)
            main.preview(root, verify_audio=True)
            good.unlink()
            archive = root / "release.zip"
            with zipfile.ZipFile(archive, "w") as output:
                output.writestr("Release/01.flac", b"fLaC" + bytes(64))
                output.writestr("Release/notes.nfo", "diagnostic notes")
            before = self.snapshot(root)
            with self.assertRaisesRegex(ValueError, "decoding verification failed"):
                main.process_release(root, verify_audio=True)
            self.assertEqual(self.snapshot(root), before)
            with self.assertRaisesRegex(ValueError, "decoding verification failed"):
                main.preview(root, verify_audio=True)
            self.assertEqual(self.snapshot(root), before)

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
