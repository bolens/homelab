import contextlib
import errno
import io
import itertools
import json
import os
import shutil
import struct
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

    @staticmethod
    def classic_tiff(order: str = '<') -> bytes:
        prefix = b'II' if order == '<' else b'MM'
        entries = [(256, 1), (257, 1), (273, 62), (279, 1)]
        return (prefix + struct.pack(order + 'HIH', 42, 8, len(entries))
                + b''.join(struct.pack(order + 'HHII', tag, 4, 1, value) for tag, value in entries)
                + bytes(4) + b'\x00')

    @staticmethod
    def thumbnail_database() -> bytes:
        header = bytearray(512)
        header[:8] = bytes.fromhex('d0cf11e0a1b11ae1')
        struct.pack_into('<HHHHH', header, 24, 0x3e, 3, 0xfffe, 9, 6)
        for offset, value in ((44, 1), (48, 1), (56, 4096), (60, 0xfffffffe), (68, 0xfffffffe)):
            struct.pack_into('<I', header, offset, value)
        struct.pack_into('<109I', header, 76, 0, *([0xffffffff] * 108))
        jpeg = b'\xff\xd8\xff' + bytes(4091) + b'\xff\xd9'
        payload = struct.pack('<III', 24, 3, len(jpeg)) + bytes(12) + jpeg
        fat = [0xffffffff] * 128
        fat[0], fat[1] = 0xfffffffd, 0xfffffffe
        for index in range(2, 11):
            fat[index] = index + 1 if index < 10 else 0xfffffffe
        directory = bytearray(512)
        for offset in range(0, 512, 128):
            struct.pack_into('<III', directory, offset + 68, 0xffffffff, 0xffffffff, 0xffffffff)
        for offset, name, kind, start, size in ((0, 'Root Entry', 5, 0xfffffffe, 0),
                                               (128, '256_0123456789abcdef', 2, 2, len(payload))):
            encoded = (name + '\0').encode('utf-16-le')
            directory[offset:offset + len(encoded)] = encoded
            struct.pack_into('<H', directory, offset + 64, len(encoded))
            directory[offset + 66] = kind
            directory[offset + 67] = 1
            struct.pack_into('<III', directory, offset + 68, 0xffffffff, 0xffffffff, 1 if kind == 5 else 0xffffffff)
            struct.pack_into('<IQ', directory, offset + 116, start, size)
        return bytes(header) + struct.pack('<128I', *fat) + directory + payload.ljust(9 * 512, b'\0')

    def test_tiff_and_thumbnail_cleanup_protects_audio_unknowns_and_retries(self) -> None:
        for archive in (False, True):
            with self.subTest(archive=archive), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                audio = b'fLaC' + bytes(32)
                files = {'booklet.tif': self.classic_tiff(), 'disc.TIFF': self.classic_tiff('>'),
                         'obfuscated-image': self.classic_tiff(), 'Thumbs.db': self.thumbnail_database(),
                         'song.tiff': audio, 'song.db': audio, 'unknown.tiff': b'\0binary',
                         'unrelated.db': self.thumbnail_database()}
                if archive:
                    with zipfile.ZipFile(root / 'release.zip', 'w') as output:
                        for name, payload in files.items():
                            output.writestr(name, payload)
                else:
                    for name, payload in files.items():
                        (root / name).write_bytes(payload)
                main.process_release(root)
                expected = {'song.tiff.flac': audio, 'song.db.flac': audio,
                            'unknown.tiff': files['unknown.tiff'], 'unrelated.db': files['unrelated.db']}
                self.assertEqual({p.name: p.read_bytes() for p in root.iterdir()}, expected)
                main.process_release(root)
                self.assertEqual({p.name: p.read_bytes() for p in root.iterdir()}, expected)

    def test_tiff_and_thumbnail_cleanup_cue_disabled_and_empty_guards(self) -> None:
        for name, payload in (('booklet.tiff', self.classic_tiff()), ('Thumbs.db', self.thumbnail_database())):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                (root / name).write_bytes(payload)
                with self.assertRaisesRegex(ValueError, 'no files would remain'):
                    main.process_release(root)
                main.process_release(root, cleanup=False)
                self.assertEqual((root / name).read_bytes(), payload)
                cue = ('FILE "' + name + '" BINARY\n').encode()
                (root / 'release.cue').write_bytes(cue)
                main.process_release(root)
                self.assertEqual({p.name: p.read_bytes() for p in root.iterdir()}, {name: payload, 'release.cue': cue})

    def test_tiff_rejects_truncated_invalid_and_out_of_bounds_rasters(self) -> None:
        valid = self.classic_tiff()
        variants = [valid[:4], valid[:10], b'II*\0' + bytes(12)]
        for offset, value in ((4, 0xffffffff), (8, 4097), (18, 0), (42, 0xffffffff), (54, 0xffffffff), (58, 8), (58, 0xffffffff)):
            damaged = bytearray(valid)
            struct.pack_into('<I' if offset != 8 else '<H', damaged, offset, value)
            variants.append(bytes(damaged))
        for payload in variants:
            with self.subTest(payload=payload[:10]), tempfile.TemporaryDirectory() as temp:
                path = Path(temp) / 'booklet.tiff'
                path.write_bytes(payload)
                self.assertFalse(main.is_tiff_image(path))
                self.assertFalse(main.disposable(path))

    def test_thumbnail_cache_rejects_other_ole_streams_and_malformed_chains(self) -> None:
        valid = self.thumbnail_database()
        variants = [valid[:512], valid[:-1], b'fLaC' + valid[4:]]
        for offset, value in ((44, 110), (48, 0), (512 + 10 * 4, 2), (1024 + 128 + 116, 1),
                              (1024 + 128 + 120, 4000), (1536 + 8, 1), (1024 + 76, 0), (1024 + 76, 0x12345678),
                              (1152 + 68, 1), (1152 + 76, 0), (512 + 127 * 4, 0xfffffffe),
                              (1280 + 68, 0)):
            damaged = bytearray(valid)
            struct.pack_into('<I', damaged, offset, value)
            variants.append(bytes(damaged))
        damaged = bytearray(valid)
        name = 'WordDocument\0'.encode('utf-16-le')
        damaged[1152:1216] = name.ljust(64, b'\0')
        struct.pack_into('<H', damaged, 1216, len(name))
        variants.append(bytes(damaged))
        for payload in variants:
            with self.subTest(payload=payload[:8]), tempfile.TemporaryDirectory() as temp:
                path = Path(temp) / 'Thumbs.db'
                path.write_bytes(payload)
                self.assertFalse(main.is_windows_thumbnail_cache(path))
                self.assertFalse(main.disposable(path))

    def test_scene_nfo_nonbreaking_spaces_keep_other_controls_protected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            text = 'Artist : Example\nTitle : A\u00a0measure\nTracks : 1\n'.encode('utf-8')
            nfo = root / 'scene.nfo'
            nfo.write_bytes(text)
            self.assertTrue(main.disposable(nfo))
            nfo.write_bytes(text + b'\0')
            self.assertFalse(main.disposable(nfo))

    def test_jpeg_sidecar_extension_cleanup_protects_disguised_audio_and_binary(self) -> None:
        for archive in (False, True):
            with self.subTest(archive=archive), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                audio = b"fLaC" + bytes(32)
                files = {"cover.jpeg": b"\xff\xd8\xff" + bytes(32),
                         "cover.JPEG": b"\x89PNG\r\n\x1a\n" + bytes(32),
                         "song.jpeg": audio, "unknown.jpeg": b"\x00binary"}
                if archive:
                    with zipfile.ZipFile(root / "release.zip", "w") as output:
                        for name, payload in files.items():
                            output.writestr(name, payload)
                else:
                    for name, payload in files.items():
                        (root / name).write_bytes(payload)
                main.process_release(root)
                self.assertEqual({p.name: p.read_bytes() for p in root.iterdir()},
                                 {"song.jpeg.flac": audio, "unknown.jpeg": files["unknown.jpeg"]})
                main.process_release(root)

    def test_jpeg_sidecar_keeps_cue_empty_output_and_cleanup_disabled_guards(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            payload = b"\xff\xd8\xff" + bytes(32)
            (root / "cover.jpeg").write_bytes(payload)
            with self.assertRaisesRegex(ValueError, "no files would remain"):
                main.process_release(root)
            main.process_release(root, cleanup=False)
            self.assertEqual((root / "cover.jpeg").read_bytes(), payload)
            cue = b'FILE "cover.jpeg" BINARY\n'
            (root / "album.cue").write_bytes(cue)
            main.process_release(root)
            self.assertEqual({p.name: p.read_bytes() for p in root.iterdir()}, {"cover.jpeg": payload, "album.cue": cue})

    def test_html_and_website_sidecars_preserve_media_and_unknown_binary(self) -> None:
        for archive in (False, True):
            for suffix in (".htm", ".HTML", ".website"):
                with self.subTest(archive=archive, suffix=suffix), tempfile.TemporaryDirectory() as temp:
                    root = Path(temp)
                    audio = b"fLaC" + bytes(32)
                    text = ("<html><body>Newsletter</body></html>" if suffix.lower() != ".website"
                            else "[InternetShortcut]\r\nURL=https://example.com/release\r\n")
                    files = {"sidecar" + suffix: text.encode(), "unicode" + suffix: text.encode("utf-16"),
                             "song" + suffix: audio, "unknown" + suffix: b"\x00binary"}
                    if archive:
                        with zipfile.ZipFile(root / "release.zip", "w") as output:
                            for name, payload in files.items():
                                output.writestr(name, payload)
                    else:
                        for name, payload in files.items():
                            (root / name).write_bytes(payload)
                    main.process_release(root)
                    self.assertEqual({p.name: p.read_bytes() for p in root.iterdir()},
                                     {"song" + suffix + ".flac": audio, "unknown" + suffix: b"\x00binary"})
                    main.process_release(root)

    def test_html_and_website_sidecars_keep_cleanup_and_cue_guards(self) -> None:
        for suffix in (".htm", ".html", ".website"):
            with self.subTest(suffix=suffix), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                sidecar = root / ("sidecar" + suffix)
                payload = b"[InternetShortcut]\nURL=https://example.com/\n"
                sidecar.write_bytes(payload)
                with self.assertRaisesRegex(ValueError, "no files would remain"):
                    main.process_release(root)
                main.process_release(root, cleanup=False)
                self.assertEqual(sidecar.read_bytes(), payload)
                cue = ('FILE "' + sidecar.name + '" BINARY\n').encode()
                (root / "album.cue").write_bytes(cue)
                main.process_release(root)
                self.assertEqual({p.name: p.read_bytes() for p in root.iterdir()},
                                 {sidecar.name: payload, "album.cue": cue})

    @staticmethod
    def decorated_posting_nfo() -> str:
        return ("┌──────────────────────────────┐\n"
                "│ Artist : Fixture Künstler    │\n"
                "│ Album  : Example             │\n"
                "│ Source : CD                  │\n"
                "│ Encoder: FLAC                │\n"
                "│ 1. Example Song         3:00  │\n"
                "└──────────────────────────────┘\n")

    def test_alternate_posting_separator_and_framed_nfo_are_cleaned(self) -> None:
        for separator in ("___", "-_-_--_"):
            for tag in ("WtFnZb", "newzNZB"):
                for encoding in ("utf-8", "cp437"):
                    for archive in (False, True):
                        with self.subTest(separator=separator, tag=tag, encoding=encoding, archive=archive), tempfile.TemporaryDirectory() as temp:
                            root = Path(temp)
                            name = f"release.1234abcd{separator}123456abcdef_ [{tag}] [2_13] - yEnc  7533 (1_1)"
                            audio = b"fLaC" + bytes(32)
                            files = {name: self.decorated_posting_nfo().encode(encoding),
                                     name.replace("7533", "449"): b"01-song.flac 1234abcd\r\n", "01-song.flac": audio}
                            if archive:
                                with zipfile.ZipFile(root / "release.zip", "w") as output:
                                    for filename, payload in files.items():
                                        output.writestr(filename, payload)
                            else:
                                for filename, payload in files.items():
                                    (root / filename).write_bytes(payload)
                            main.process_release(root)
                            self.assertEqual({p.name: p.read_bytes() for p in root.iterdir()}, {"01-song.flac": audio})
                            main.process_release(root)

    def test_posting_art_cleanup_preserves_invalid_binary_and_empty_fields(self) -> None:
        name = "release.1234abcd-_-_--_123456abcdef_ [WtFnZb] [2_13] - yEnc  7533 (1_1)"
        art = self.decorated_posting_nfo()
        files = {name: art.encode("cp437") + b"\xffbinary",
                 name.replace("7533", "7534"): art.encode("cp437") + b"\x00",
                 name.replace("7533", "7535"): art.replace("Fixture Künstler", "                ").encode("cp437"),
                 name.replace("7533", "7536"): art.replace("│ 1. Example Song         3:00  │\n", "").encode("cp437"),
                 name.replace("7533", "7537"): art.replace("│ Source : CD                  │\n", "").encode("cp437"),
                 name.replace("-_-_--_", "-_-___-"): art.encode("cp437"),
                 name.replace("7533", "7538"): b"fLaC" + bytes(32),
                 name.replace("7533", "7539"): art.encode("cp437") + b"x" * 65536}
        for index, encoding in enumerate(("utf-8", "cp437")):
            files[name.replace("7533", str(7540 + index))] = art.replace("Example Song         3:00", "                        ").encode(encoding)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for filename, payload in files.items():
                (root / filename).write_bytes(payload)
            main.process_release(root)
            expected = {(filename + ".flac" if filename == name.replace("7533", "7538") else filename): payload for filename, payload in files.items()}
            self.assertEqual({p.name: p.read_bytes() for p in root.iterdir()}, expected)

    def test_modern_posting_title_fields_require_structured_nfo(self) -> None:
        name = "Fixture-Example.1234abcd___123456abcdef_ [newzNZB] [2_6] - yEnc  1451 (1_1)"
        text = "Artist.......: Fixture\nTitle........: Example\nGenre........: Rock\nSource.......: Vinyl\n01.Example Song 03:00\n"
        for archive in (False, True):
            with self.subTest(archive=archive), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                retained = {"song.flac": b"fLaC" + bytes(32),
                            name.replace("1451", "1452"): text.replace("Artist.......: Fixture", "Artist.......: ").encode(),
                            name.replace("1451", "1453"): text.replace("Genre........: Rock\n", "").encode(),
                            name.replace("1451", "1454"): text.replace("01.Example Song 03:00\n", "").encode(),
                            name.replace("1451", "1455"): text.encode() + b"\x00"}
                files = {**retained, name: text.encode()}
                if archive:
                    with zipfile.ZipFile(root / "release.zip", "w") as output:
                        for filename, payload in files.items():
                            output.writestr(filename, payload)
                else:
                    for filename, payload in files.items():
                        (root / filename).write_bytes(payload)
                main.process_release(root)
                self.assertEqual({p.name: p.read_bytes() for p in root.iterdir()}, retained)

    def test_posting_art_keeps_cue_empty_output_and_cleanup_disabled_guards(self) -> None:
        name = "release.1234abcd-_-_--_123456abcdef_ [WtFnZb] [2_13] - yEnc  7533 (1_1)"
        payload = self.decorated_posting_nfo().encode("cp437")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / name).write_bytes(payload)
            with self.assertRaisesRegex(ValueError, "no files would remain"):
                main.process_release(root)
            cue = f'FILE "{name}" BINARY\n'.encode()
            (root / "album.cue").write_bytes(cue)
            main.process_release(root)
            self.assertEqual({p.name: p.read_bytes() for p in root.iterdir()}, {name: payload, "album.cue": cue})
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / name).write_bytes(payload)
            (root / "song.flac").write_bytes(b"fLaC" + bytes(32))
            main.process_release(root, cleanup=False)
            self.assertEqual((root / name).read_bytes(), payload)

    def test_posting_dotted_and_arrow_fields_require_complete_structured_text(self) -> None:
        name = "Fixture-Example.1234abcd___123456abcdef_ [newzNZB] [2_6] - yEnc  1140 (1_1)"
        for text in ("artist....... Fixture\ntitle........ Example\nsource....... CD\ngenre........ Rock\n01 Example Song 03:00\n",
                     "||| Artist Name_____> Fixture |||\n||| Album Name______> Example |||\n||| Genre___________> Rock |||\n||| Encoder_________> FLAC |||\n| 1 Example Song 03:00 |\n"):
            for archive in (False, True):
                with self.subTest(text=text, archive=archive), tempfile.TemporaryDirectory() as temp:
                    root = Path(temp)
                    retained = {"song.flac": b"fLaC" + bytes(32),
                                "notes": text.encode(),
                                name + ".flac": text.encode(),
                                name.replace("1140", "1141"): text.encode() + b"\x00",
                                name.replace("1140", "1142"): text.replace("Fixture", "").encode(),
                                name.replace("1140", "1143"): text.replace("Rock", "").encode(),
                                name.replace("1140", "1144"): text.replace("1 Example Song 03:00", "").encode()}
                    files = {**retained, name: text.encode()}
                    if archive:
                        with zipfile.ZipFile(root / "release.zip", "w") as output:
                            for filename, payload in files.items():
                                output.writestr(filename, payload)
                    else:
                        for filename, payload in files.items():
                            (root / filename).write_bytes(payload)
                    main.process_release(root)
                    self.assertEqual({p.name: p.read_bytes() for p in root.iterdir()}, retained)
                    main.process_release(root)

    def test_about_album_requires_bounded_album_artist_and_tracklist(self) -> None:
        text = b"Album: Example\nArtist: Fixture\nTracklist:\n01 Example Song (3:00)\n"
        for archive in (False, True):
            with self.subTest(archive=archive), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                retained = {"song.flac": b"fLaC" + bytes(32), "notes": text,
                            "about_album.flac": text, "bad_about_album": text,
                            "post_album_info": text.replace(b"Artist: Fixture", b"Artist: ")}
                files = {**retained, "about_album": text}
                if archive:
                    with zipfile.ZipFile(root / "release.zip", "w") as output:
                        for filename, payload in files.items():
                            output.writestr(filename, payload)
                else:
                    for filename, payload in files.items():
                        (root / filename).write_bytes(payload)
                main.process_release(root)
                self.assertEqual({p.name: p.read_bytes() for p in root.iterdir()}, retained)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for payload in (text + b"\0", text + b"x" * 65536, text.replace(b"01 Example Song (3:00)\n", b""),
                            text.replace(b"Album: Example", b"Album: "), b"fLaC" + bytes(32)):
                (root / "about_album").write_bytes(payload)
                self.assertFalse(main.is_album_info_sidecar(root / "about_album"))

    def test_new_posting_layouts_keep_cleanup_cue_and_empty_output_guards(self) -> None:
        posting = "Fixture-Example.1234abcd___123456abcdef_ [newzNZB] [2_6] - yEnc  1140 (1_1)"
        payloads = {"about_album": b"Album: Example\nArtist: Fixture\nTracklist:\n01 Song\n",
                    posting: b"artist... Fixture\ntitle... Example\nsource... CD\ngenre... Rock\n01 Song\n"}
        for name, text in payloads.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                (root / name).write_bytes(text)
                with self.assertRaisesRegex(ValueError, "no files would remain"):
                    main.process_release(root)
                main.process_release(root, cleanup=False)
                self.assertEqual((root / name).read_bytes(), text)
                (root / "album.cue").write_text(f'FILE "{name}" BINARY\n')
                main.process_release(root)
                self.assertEqual((root / name).read_bytes(), text)

    def test_posting_info_requires_matching_release_date_and_footer(self) -> None:
        name = "Artist-Example-xpost.1234abcd-_-_--_123456abcdef_ [WtFnZb] [8_8] - yEnc 1515 (1_1)"
        payload = b"ASCII art\nRELEASE: Artist_Example\nUPLOADED DATE: 2024-February-29\n.::newz[NZB]::.\n"
        cases = ((payload, True),
                 (payload.replace(b"\n", b"\r\n"), True),
                 (payload.replace(b"\n", b"\r"), True),
                 (b"RELEASE:\r" + payload, False),
                 (b"UPLOADED DATE:\r" + payload, False),
                 (payload.replace(b"Artist_Example", b"Other_Example"), False),
                 (payload.replace(b"2024-February-29", b"2023-February-29"), False),
                 (payload.replace(b"2024-February-29", b"2024-Unknown-01"), False),
                 (payload.replace(b"2024-February-29", b"0000-January-01"), False),
                 (payload.replace(b"UPLOADED DATE:", b"DATE:"), False),
                 (payload.replace(b".::newz[NZB]::.", b"other marker"), False),
                 (payload.replace(b"ASCII art", b"RELEASE: Artist_Example"), False),
                 (payload.replace(b"ASCII art", b"RELEASE:"), False),
                 (payload.replace(b"ASCII art", b"UPLOADED DATE:"), False),
                 (payload.replace(b".::newz[NZB]::.", b".::NEWZ[nzb]::."), False),
                 (payload.replace(b"ASCII art", b"UPLOADED DATE: 2024-February-29"), False),
                 (payload + b"extra text", False),
                 (payload + b"\x00", False),
                 (payload + b" " * 65536, False))
        for raw, expected in cases:
            with self.subTest(raw=raw[:100]), tempfile.TemporaryDirectory() as temp:
                path = Path(temp) / name
                path.write_bytes(raw)
                self.assertEqual(main.disposable(path), expected)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / name).write_bytes(payload)
            before = {p.name: p.read_bytes() for p in root.iterdir()}
            with self.assertRaises(ValueError):
                main.process_release(root)
            self.assertEqual({p.name: p.read_bytes() for p in root.iterdir()}, before)
            (root / "audio.flac").write_bytes(b"fLaC\x00audio")
            main.process_release(root, cleanup=False)
            self.assertEqual((root / name).read_bytes(), payload)
            main.process_release(root)
            self.assertEqual({p.name: p.read_bytes() for p in root.iterdir()}, {"audio.flac": b"fLaC\x00audio"})
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / name).write_bytes(payload)
            (root / "album.cue").write_text(f'FILE "{name}" WAVE\n TRACK 01 AUDIO\n')
            main.process_release(root)
            self.assertEqual((root / name).read_bytes(), payload)

    def test_legacy_full_posting_sidecars_require_bounded_structured_content(self) -> None:
        wrapper = "[123]-[FULL]-[#a.b.flac@EFNet]-[ Artist-Example ]-[03_13] - _00-example.{}_ yEnc (1_1) (1_1)"
        nfo = b"Artist.......: Artist\nTitle........: Example\nGenre........: Rock\nSource.......: CDDA\n01.Song\n"
        sfv = b"01-song.flac 1234abcd\n"
        cases = ((wrapper.format("nfo"), nfo, True),
                 (wrapper.format("sfv"), sfv, True),
                 (wrapper.format("txt"), nfo, False),
                 (wrapper.format("nfo").replace("EFNet", "Other"), nfo, False),
                 (wrapper.format("nfo"), nfo + b"\x00", False),
                 (wrapper.format("nfo"), b"Artist: Artist\nAlbum: Example\nTitle: Example\nGenre: Rock\n01.Song\n", False),
                 ("release.1234abcd___123456abcdef_ [newzNZB] [1_2] - yEnc 123 (1_1)",
                  b"Artist: Artist\nAlbum: Example\nTitle: Example\nGenre: Rock\n01.Song\n", False),
                 (wrapper.format("nfo"), nfo.replace(b"Artist.......: Artist\n", b""), False),
                 (wrapper.format("nfo"), nfo + b" " * 65536, False),
                 (wrapper.format("sfv"), b"../outside.flac 1234abcd\n", False),
                 (wrapper.format("sfv"), b"01-song.flac invalid\n", False),
                 (wrapper.format("nfo"), b"fLaC\x00audio", False))
        for name, raw, expected in cases:
            with self.subTest(name=name, raw=raw[:70]), tempfile.TemporaryDirectory() as temp:
                path = Path(temp) / name
                path.write_bytes(raw)
                self.assertEqual(main.disposable(path), expected)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            audio = b"fLaC\x00audio"
            (root / "01-song.flac").write_bytes(audio)
            (root / wrapper.format("nfo")).write_bytes(nfo)
            protected = wrapper.format("sfv")
            (root / protected).write_bytes(sfv)
            (root / "album.cue").write_text(f'FILE "{protected}" WAVE\n TRACK 01 AUDIO\n')
            main.process_release(root)
            self.assertFalse((root / wrapper.format("nfo")).exists())
            self.assertEqual((root / protected).read_bytes(), sfv)
            self.assertEqual((root / "01-song.flac").read_bytes(), audio)

    def test_duplicate_decorated_posting_nfos_do_not_block_archive_audio(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            name = "release.1234abcd-_-_--_123456abcdef_ [WtFnZb] [2_13] - yEnc  7533 (1_1)"
            payload = self.decorated_posting_nfo().encode("cp437")
            audio = b"fLaC" + bytes(32)
            (root / name).write_bytes(payload)
            with zipfile.ZipFile(root / "release.zip", "w") as output:
                output.writestr(name, payload)
                output.writestr("song.flac", audio)
            main.process_release(root)
            self.assertEqual({p.name: p.read_bytes() for p in root.iterdir()}, {"song.flac": audio})


    @staticmethod
    def synology_metadata() -> bytes:
        # AppleDouble v2: FinderInfo/attributes followed by an empty resource fork.
        name = b"com.apple.provenance\x00"
        data = b"fixturedata"
        start = (131 + len(name) + 3) & ~3
        end = start + len(data)
        attributes = (bytes(2) + struct.pack(">IIIIIIIIHH", 0x41545452, 0, end, start, len(data), 0, 0, 0, 0, 1)
                      + struct.pack(">IIHB", start, len(data), 0, len(name)) + name
                      + bytes(start - 131 - len(name)) + data)
        finder = bytes(32) + attributes
        return (struct.pack(">II16sH", 0x00051607, 0x00020000, b"Mac OS X        ", 2)
                + struct.pack(">III", 9, 50, len(finder))
                + struct.pack(">III", 2, end, 0) + finder)

    def test_synology_metadata_cleanup_from_existing_and_archived_releases(self) -> None:
        for archive in (False, True):
            with self.subTest(archive=archive), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                audio = b"fLaC" + bytes(32)
                files = {"Release/one.flac": audio,
                         "Release/one.flac@SynoEAStream": self.synology_metadata(),
                         "Release/cover.jpg@SynoEAStream": self.synology_metadata()}
                if archive:
                    with zipfile.ZipFile(root / "release.zip", "w") as output:
                        for name, payload in files.items():
                            output.writestr(name, payload)
                else:
                    for name, payload in files.items():
                        path = root / name
                        path.parent.mkdir(parents=True, exist_ok=True)
                        path.write_bytes(payload)
                main.process_release(root)
                self.assertEqual({p.name: p.read_bytes() for p in root.iterdir()}, {"one.flac": audio})
                main.process_release(root)

    def test_synology_metadata_cleanup_preserves_unproven_data(self) -> None:
        raw = self.synology_metadata()
        def change(offset: int, value: int) -> bytes:
            return raw[:offset] + struct.pack(">I", value) + raw[offset + 4:]
        cases = [b"not metadata", raw[:49], change(0, 0x00051600), change(4, 0x00010000),
                 raw[:24] + b"\x00\x03" + raw[26:], change(38, 9), change(38, 1),
                 change(46, 1), change(30, 49), change(34, 31), change(42, len(raw) - 1),
                 raw + b"trailer", raw + bytes(65536)]
        for index, payload in enumerate(cases):
            with self.subTest(case=index), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                path = root / "one.flac@SynoEAStream"
                path.write_bytes(payload)
                (root / "song.flac").write_bytes(b"fLaC" + bytes(32))
                self.assertFalse(main.disposable(path))
                main.process_release(root)
                self.assertEqual(path.read_bytes(), payload)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            files = {"metadata.bin": raw, "named.flac": raw,
                     "audio.flac@SynoEAStream": b"fLaC" + bytes(32)}
            for name, payload in files.items():
                (root / name).write_bytes(payload)
            main.process_release(root)
            self.assertEqual({p.name: p.read_bytes() for p in root.iterdir()},
                             {"metadata.bin": raw, "named.flac": raw,
                              "audio.flac@SynoEAStream.flac": files["audio.flac@SynoEAStream"]})

    def test_synology_attribute_records_require_complete_known_structure(self) -> None:
        raw = self.synology_metadata()
        def change(offset: int, value: int) -> bytes:
            return raw[:offset] + struct.pack(">I", value) + raw[offset + 4:]
        cases = [change(84, 0), change(92, len(raw) - 1), change(96, 120), change(100, 10),
                 change(104, 1), raw[:118] + b"\x00\x02" + raw[120:],
                 change(120, 151), change(124, 12), raw[:128] + b"\x00\x01" + raw[130:],
                 raw[:130] + b"\xff" + raw[131:], raw[:131] + b"x" + raw[132:],
                 raw[:82] + b"\x00\x01" + raw[84:]]
        for index, payload in enumerate(cases):
            with self.subTest(case=index), tempfile.TemporaryDirectory() as temp:
                path = Path(temp) / "one.flac@SynoEAStream"
                path.write_bytes(payload)
                self.assertFalse(main.disposable(path))
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "one.flac@SynoEAStream"
            bare = (struct.pack(">II16sH", 0x00051607, 0x00020000, bytes(16), 2)
                    + struct.pack(">III", 9, 50, 32) + struct.pack(">III", 2, 82, 0) + bytes(32))
            path.write_bytes(bare)
            self.assertTrue(main.disposable(path))

    def test_synology_metadata_keeps_cue_and_empty_output_guards(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            name = "one.flac@SynoEAStream"
            payload = self.synology_metadata()
            (root / name).write_bytes(payload)
            with self.assertRaisesRegex(ValueError, "no files would remain"):
                main.process_release(root)
            cue = f'FILE "{name}" BINARY\n'.encode()
            (root / "album.cue").write_bytes(cue)
            main.process_release(root)
            self.assertEqual({p.name: p.read_bytes() for p in root.iterdir()}, {name: payload, "album.cue": cue})

    def test_synology_duplicate_metadata_does_not_block_audio(self) -> None:
        for protected in (False, True):
            with self.subTest(protected=protected), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                name = "one.flac@SynoEAStream"
                (root / name).write_bytes(self.synology_metadata())
                if protected:
                    (root / "album.cue").write_text(f'FILE "{name}" BINARY\n')
                audio = b"fLaC" + bytes(32)
                with zipfile.ZipFile(root / "release.zip", "w") as output:
                    output.writestr(name, self.synology_metadata())
                    output.writestr("song.flac", audio)
                before = {p.name: p.read_bytes() for p in root.iterdir()}
                if protected:
                    with self.assertRaises((FileExistsError, ValueError)):
                        main.process_release(root)
                    self.assertEqual({p.name: p.read_bytes() for p in root.iterdir()}, before)
                else:
                    main.process_release(root)
                    self.assertEqual({p.name: p.read_bytes() for p in root.iterdir()}, {"song.flac": audio})

    def test_padded_cp437_scene_nfo_cleanup_and_guards(self) -> None:
        art = "███\r\n▐▒▌Artist\x07\x07: Fixture\r\n▐▒▌Title\x07: Example\r\n▐▒▌Tracks\x07: 1\r\n███\r\n".encode("cp437")
        audio = b"fLaC" + bytes(32)
        for archive in (False, True):
            with self.subTest(archive=archive), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                retained = {"song.flac": audio, "drawing.txt": art, "unknown": art,
                            "trailing.nfo": art + b"\x07", "binary.nfo": art + b"\x00",
                            "control.nfo": art.replace(b"\x07", b"\x08"),
                            "missing.nfo": art.replace(b"Title", b"Notes"),
                            "empty.nfo": art.replace(b": Example", ":      ▐▒▌".encode("cp437")),
                            "unframed.nfo": b"Artist\x07: Fixture\nTitle\x07: Example\nTracks\x07: 1\n",
                            "oversize.nfo": art + b" " * 65536,
                            "audio.nfo": audio}
                files = {**retained, "release.NFO": art}
                if archive:
                    with zipfile.ZipFile(root / "release.zip", "w") as output:
                        for name, payload in files.items():
                            output.writestr(name, payload)
                else:
                    for name, payload in files.items():
                        (root / name).write_bytes(payload)
                main.process_release(root)
                expected = {k: v for k, v in retained.items() if k != "audio.nfo"}
                expected["audio.nfo.flac"] = audio
                self.assertEqual({p.name: p.read_bytes() for p in root.iterdir()}, expected)
                main.process_release(root)
                self.assertEqual({p.name: p.read_bytes() for p in root.iterdir()}, expected)

    def test_padded_cp437_scene_nfo_preserves_cue_and_empty_output_guards(self) -> None:
        art = "██\n▐▒▌Artist\x07: Fixture\n▐▒▌Title\x07: Example\n▐▒▌Tracks\x07: 1\n".encode("cp437")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "release.nfo").write_bytes(art)
            with self.assertRaisesRegex(ValueError, "no files would remain"):
                main.process_release(root)
            main.process_release(root, cleanup=False)
            cue = b'FILE "release.nfo" BINARY\n'
            (root / "album.cue").write_bytes(cue)
            main.process_release(root)
            self.assertEqual({p.name: p.read_bytes() for p in root.iterdir()}, {"release.nfo": art, "album.cue": cue})

    def test_cp437_art_row_syn_controls_are_bounded_and_scoped(self) -> None:
        art = "██\n\xa0\x16░█\n▐▒▌Artist...: Fixture\n▐▒▌Title....: Example\n▐▒▌Tracks...: 1\n".encode("cp437")
        audio = b"fLaC" + bytes(32)
        for archive in (False, True):
            with self.subTest(archive=archive), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                retained = {"song.flac": audio, "drawing.txt": art, "unknown": art,
                            "text.nfo": art + b"Some\x16text\n", "binary.nfo": art + b"\x00",
                            "no-title.nfo": art.replace(b"Title", b"Notes"),
                            "empty-title.nfo": art.replace(b": Example", ":      ▐▒▌".encode("cp437")),
                            "mixed-invalid.nfo": art.replace(b"....:", b"\x07:").replace(b"...:", b"\x07:") + b"text\x16row\n",
                            "oversize.nfo": art + b" " * 65536}
                files = {**retained, "release.nfo": art,
                         "mixed.nfo": art.replace(b"....:", b"\x07:").replace(b"...:", b"\x07:")}
                if archive:
                    with zipfile.ZipFile(root / "release.zip", "w") as output:
                        for filename, payload in files.items():
                            output.writestr(filename, payload)
                else:
                    for filename, payload in files.items():
                        (root / filename).write_bytes(payload)
                main.process_release(root)
                self.assertEqual({p.name: p.read_bytes() for p in root.iterdir()}, retained)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "release.nfo").write_bytes(art)
            with self.assertRaisesRegex(ValueError, "no files would remain"):
                main.process_release(root)
            main.process_release(root, cleanup=False)
            cue = b'FILE "release.nfo" BINARY\n'
            (root / "album.cue").write_bytes(cue)
            main.process_release(root)
            self.assertEqual({p.name: p.read_bytes() for p in root.iterdir()}, {"release.nfo": art, "album.cue": cue})

    def test_txt_direction_marks_preserve_other_controls_media_and_cues(self) -> None:
        for encoding in ("utf-8", "utf-16-le", "utf-16-be"):
            with self.subTest(encoding=encoding), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                def payload(text):
                    bom = b"\xff\xfe" if encoding == "utf-16-le" else b"\xfe\xff" if encoding == "utf-16-be" else b""
                    return bom + text.encode(encoding)
                text = payload("Artist: \u200eFixture\u200e\nAlbum: Example\n")
                files = {"song.flac": b"fLaC" + bytes(32), "protected.txt": text,
                         "drawing.nfo": text, "unknown": text,
                         "bidi.txt": payload("Artist: \u202eFixture\n"),
                         "binary.txt": payload("Artist: \u200eFixture\x00\n"),
                         "album.cue": b'FILE "protected.txt" BINARY\n'}
                for filename, raw in {**files, "release.txt": text}.items():
                    (root / filename).write_bytes(raw)
                main.process_release(root)
                self.assertEqual({p.name: p.read_bytes() for p in root.iterdir()}, files)

    def test_printable_cp437_scene_symbols_are_cleaned_without_binary_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            art = "┌───┐\n│ ¼ «Fixture» ∙ ⌐ │\n└───┘\n".encode("cp437")
            files = {"song.flac": b"fLaC" + bytes(32), "unknown.nfo": art + "∞".encode("cp437"),
                     "control.nfo": art + b"\x08binary", "drawing.txt": art}
            for name, payload in {**files, "scene.nfo": art}.items():
                (root / name).write_bytes(payload)
            main.process_release(root)
            self.assertEqual({p.name: p.read_bytes() for p in root.iterdir()}, files)

    def test_legacy_text_sidecars_from_existing_and_archived_releases(self) -> None:
        notes = "Vinyl notes: Artist’s album © 2017\r\n".encode("cp1252")
        art = "┌───┐\n│ ÷ ≤ Fixture  │\n└───┘\n".encode("cp437")
        for archive in (False, True):
            with self.subTest(archive=archive), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                audio = b"fLaC" + bytes(32)
                files = {"song.flac": audio, "notes.TXT": notes, "scene.nfo": art,
                         "binary.txt": notes + b"\x00", "undefined.txt": notes + b"\x81",
                         "control.nfo": art + b"\x08", "drawing.txt": art,
                         "unknown": notes, "audio.txt": audio}
                if archive:
                    with zipfile.ZipFile(root / "release.zip", "w") as output:
                        for name, payload in files.items():
                            output.writestr(name, payload)
                else:
                    for name, payload in files.items():
                        (root / name).write_bytes(payload)
                main.process_release(root)
                expected = {k: v for k, v in files.items() if k not in {"notes.TXT", "scene.nfo", "audio.txt"}}
                expected["audio.txt.flac"] = audio
                self.assertEqual({p.name: p.read_bytes() for p in root.iterdir()}, expected)
                main.process_release(root)

    def test_legacy_text_sidecar_guards_cover_cues_cleanup_and_empty_output(self) -> None:
        notes = "Artist’s notes © 2017\n".encode("cp1252")
        art = "┌──┐\n│ ÷ ≤  │\n└──┘\n".encode("cp437")
        for name, payload in (("notes.txt", notes), ("scene.nfo", art)):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                (root / name).write_bytes(payload)
                with self.assertRaisesRegex(ValueError, "no files would remain"):
                    main.process_release(root)
                main.process_release(root, cleanup=False)
                cue = ('FILE "' + name + '" BINARY\n').encode()
                (root / "album.cue").write_bytes(cue)
                main.process_release(root)
                self.assertEqual({p.name: p.read_bytes() for p in root.iterdir()},
                                 {name: payload, "album.cue": cue})

    def test_additional_sidecars_from_postings_are_removed(self) -> None:
        posting = "release.1234abcd___123456abcdef_ [newzNZB] [4_22] - yEnc  1393 (1_1)"
        files = {
            "lyrics.lrc": b"[00:01.00]Fixture lyrics\n",
            "windows.nfo": "Artist: Fixture\r\nAlbum: Artist’s album\r\n".encode("cp1252"),
            "scene.nfo": "█ Fixture café · █\r\n".encode("cp437"),
            posting: b"Artist...: Fixture\r\nAlbum....: Example\r\nSource...: CD\r\nEncoder..: FLAC\r\n01 Example Song\r\n",
            posting.replace("1393", "821"): b"01-song.flac 1234abcd\r\n02-song.flac ABCD1234\r\n",
            "obfuscated-recovery": b"iii\x01\x00\x0d\x00\x04\x00test" + b"recovery blocks",
        }
        for archive in (False, True):
            with self.subTest(archive=archive), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                audio = b"fLaC" + bytes(32)
                if archive:
                    with zipfile.ZipFile(root / "release.zip", "w") as output:
                        for name, payload in {**files, "song.flac": audio}.items():
                            output.writestr(name, payload)
                else:
                    for name, payload in {**files, "song.flac": audio}.items():
                        (root / name).write_bytes(payload)
                main.process_release(root)
                self.assertEqual({p.name: p.read_bytes() for p in root.iterdir()}, {"song.flac": audio})
                main.process_release(root)

    def test_posting_tags_and_windows_text_are_cleaned_with_audio(self) -> None:
        for tag in ("newzNZB", "WtFnZb", "wtfnzb"):
            for encoding in ("utf-8", "utf-8-sig", "cp1252"):
                for archive in (False, True):
                    with self.subTest(tag=tag, encoding=encoding, archive=archive), tempfile.TemporaryDirectory() as temp:
                        root = Path(temp)
                        name = f"release.1234abcd___123456abcdef_ [{tag}] [3_16] - yEnc  903 (1_1)"
                        info = "Artist: Fixture\r\nAlbum: 7800° Example\r\nSource: CD\r\nEncoder: FLAC\r\n01. Example Track\r\n"
                        files = {name: info.encode(encoding),
                                 name.replace("903", "553"): "01-artist’s-song.flac 1234abcd\r\n".encode(encoding),
                                 "01-artist’s-song.flac": b"fLaC" + bytes(32)}
                        if archive:
                            with zipfile.ZipFile(root / "release.zip", "w") as output:
                                for filename, payload in files.items():
                                    output.writestr(filename, payload)
                        else:
                            for filename, payload in files.items():
                                (root / filename).write_bytes(payload)
                        main.process_release(root)
                        self.assertEqual({p.name: p.read_bytes() for p in root.iterdir()},
                                         {"01-artist’s-song.flac": files["01-artist’s-song.flac"]})
                        main.process_release(root)

    def test_windows_posting_cleanup_keeps_cue_and_empty_output_guards(self) -> None:
        for tag in ("newzNZB", "WtFnZb"):
            with self.subTest(tag=tag), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                name = f"release.1234abcd___123456abcdef_ [{tag}] [3_16] - yEnc  903 (1_1)"
                payload = "Artist: Fixture\nAlbum: 7800° Example\nSource: CD\nEncoder: FLAC\n01. Example\n".encode("cp1252")
                (root / name).write_bytes(payload)
                with self.assertRaisesRegex(ValueError, "no files would remain"):
                    main.process_release(root)
                self.assertEqual((root / name).read_bytes(), payload)
                cue = f'FILE "{name}" BINARY\n'.encode()
                (root / "album.cue").write_bytes(cue)
                main.process_release(root)
                self.assertEqual({p.name: p.read_bytes() for p in root.iterdir()}, {name: payload, "album.cue": cue})

    def test_windows_posting_cleanup_preserves_malformed_unknown_and_media(self) -> None:
        name = "release.1234abcd___123456abcdef_ [WtFnZb] [3_16] - yEnc  903 (1_1)"
        info = "Artist: Fixture\nAlbum: 7800° Example\nSource: CD\nEncoder: FLAC\n01. Example\n".encode("cp1252")
        files = {name: info + b"\x00", name.replace("903", "904"): info + b"\x81",
                 name.replace("903", "905"): info + b"x" * 65536,
                 name.replace("903", "906"): b"unstructured text",
                 name.replace("WtFnZb", "AnotherTag"): info,
                 name.replace("903", "907"): "../artist’s-song.flac 1234abcd\n".encode("cp1252"),
                 name.replace("903", "908"): b"fLaC" + bytes(32), "named.flac": info}
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for filename, payload in files.items():
                (root / filename).write_bytes(payload)
            main.process_release(root)
            expected = {(filename + ".flac" if filename == name.replace("903", "908") else filename): payload
                        for filename, payload in files.items()}
            self.assertEqual({p.name: p.read_bytes() for p in root.iterdir()}, expected)

    def test_windows_posting_duplicates_do_not_block_archive_tracks(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            name = "release.1234abcd___123456abcdef_ [WtFnZb] [3_16] - yEnc  903 (1_1)"
            info = "Artist: Fixture\nAlbum: 7800° Example\nSource: CD\nEncoder: FLAC\n01. Example\n".encode("cp1252")
            (root / name).write_bytes(info)
            audio = b"fLaC" + bytes(32)
            with zipfile.ZipFile(root / "release.zip", "w") as output:
                output.writestr(name, info)
                output.writestr("song.flac", audio)
            main.process_release(root)
            self.assertEqual({p.name: p.read_bytes() for p in root.iterdir()}, {"song.flac": audio})

    def test_windows_nfo_accents_do_not_select_cp437_drawing_mode(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            audio = b"fLaC" + bytes(32)
            (root / "song.flac").write_bytes(audio)
            for name, text in {"accent.nfo": "Artist: Édith Fixture\r\nAlbum: Best Of\r\nCopyright © 1990\r\n",
                               "degree.nfo": "Copyright © 1990\r\nTemperature 20°\r\n"}.items():
                (root / name).write_bytes(text.encode("cp1252"))
            main.process_release(root)
            self.assertEqual({p.name: p.read_bytes() for p in root.iterdir()}, {"song.flac": audio})

    def test_windows_nfo_duplicates_do_not_block_archive_tracks(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            info = "Artist: Fixture\nAlbum: Große Fixture\nCopyright © 2026\n".encode("cp1252")
            (root / "release.nfo").write_bytes(info)
            audio = b"fLaC" + bytes(32)
            with zipfile.ZipFile(root / "release.zip", "w") as output:
                output.writestr("release.nfo", info)
                output.writestr("song.flac", audio)
            main.process_release(root)
            self.assertEqual({p.name: p.read_bytes() for p in root.iterdir()}, {"song.flac": audio})

    def test_additional_sidecar_recognition_preserves_unconfirmed_content(self) -> None:
        posting = "release.1234abcd___123456abcdef_ [newzNZB] [4_22] - yEnc  1393 (1_1)"
        info = b"Artist: Fixture\nAlbum: Example\nSource: CD\nEncoder: FLAC\n01 Example Song\n"
        files = {
            "notes": info, posting: b"unstructured text\n",
            posting.replace("1393", "822"): info + b"x" * 65536,
            posting.replace("1393", "823"): b"Artist: Fixture\nAlbum: Example\n01 Song\n",
            posting.replace("1393", "824"): b"01-song.flac 1234abcd\ninvalid checksum\n",
            posting.replace("1393", "825"): info + b"\x00",
            posting.replace("1393", "821"): b"../song.flac 1234abcd\n",
            "binary.lrc": b"\x00unknown binary", "audio.lrc": b"fLaC" + bytes(32),
            "truncated-recovery": b"iii\x01\x00\x0d\x00\x04\x00tes",
            "named.mp3": b"iii\x00\x00\x07\x00",
            "unknown.nfo": b"notes\x81", "control.nfo": b"notes\x00",
        }
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name, payload in files.items():
                (root / name).write_bytes(payload)
            main.process_release(root)
            expected = {("audio.lrc.flac" if name == "audio.lrc" else name): payload for name, payload in files.items()}
            self.assertEqual({p.name: p.read_bytes() for p in root.iterdir()}, expected)

    def test_additional_sidecars_remain_protected_by_cues_and_empty_output_guard(self) -> None:
        payloads = {"lyrics.lrc": b"[00:01.00]Fixture lyrics\n",
                    "obfuscated-recovery": b"iii\x00\x00\x07\x00",
                    "windows.nfo": "Artist’s notes\n".encode("cp1252")}
        for name, payload in payloads.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                (root / name).write_bytes(payload)
                with self.assertRaisesRegex(ValueError, "no files would remain"):
                    main.process_release(root)
                cue = f'FILE "{name}" BINARY\n'.encode()
                (root / "album.cue").write_bytes(cue)
                main.process_release(root)
                self.assertEqual((root / name).read_bytes(), payload)
                self.assertEqual((root / "album.cue").read_bytes(), cue)

    def test_windows_playlists_validate_completeness_and_keep_encoding(self) -> None:
        for missing in (False, True):
            for cleanup in (False, True):
                with self.subTest(missing=missing, cleanup=cleanup), tempfile.TemporaryDirectory() as temp:
                    root = Path(temp)
                    release = root / "Release"
                    (release / "Audio").mkdir(parents=True)
                    (release / "Audio/01 Artist’s Song.flac").write_bytes(b"fLaC" + bytes(32))
                    if not missing:
                        (release / "Audio/02 Artist’s Song.flac").write_bytes(b"fLaC" + bytes(32))
                    text = "#EXTM3U\r\nAudio/01 Artist’s Song.flac\r\nAudio/02 Artist’s Song.flac\r\n"
                    (release / "tracks.m3u").write_bytes(text.encode("cp1252"))
                    before = {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()}
                    if missing and cleanup:
                        with self.assertRaisesRegex(ValueError, "incomplete playlist"):
                            main.process_release(root)
                        self.assertEqual({str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()}, before)
                    elif not missing:
                        main.process_release(root, cleanup=cleanup)
                        if cleanup:
                            self.assertFalse(any(root.rglob("*.m3u")))
                        else:
                            self.assertEqual((root / "tracks.m3u").read_bytes(), text.replace("Audio/", "").encode("cp1252"))
                            main.process_release(root, cleanup=False)
                    else:
                        main.process_release(root, cleanup=False)
                        self.assertEqual({str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()}, before)

    def test_utf16_sidecars_are_cleaned_without_changing_audio_or_cues(self) -> None:
        for encoding, bom in (("utf-16-le", b"\xff\xfe"), ("utf-16-be", b"\xfe\xff")):
            with self.subTest(encoding=encoding), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                audio = b"fLaC" + bytes(32)
                (root / "album.flac").write_bytes(audio)
                cue = b'FILE "album.flac" WAVE\r\n'
                (root / "album.cue").write_bytes(cue)
                (root / "album.log").write_bytes(bom + "Exact Audio Copy\r\nAccurately ripped\r\n".encode(encoding))
                main.process_release(root)
                self.assertEqual({p.name: p.read_bytes() for p in root.iterdir()},
                                 {"album.flac": audio, "album.cue": cue})

    def test_utf16_cleanup_preserves_malformed_data_media_and_cue_references(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            text = b"\xff\xfe" + "rip notes\r\n".encode("utf-16-le")
            files = {"odd.log": text + b"x", "control.log": b"\xff\xfe" + "notes\x00".encode("utf-16-le"),
                     "no-bom.log": "notes".encode("utf-16-le"), "song.mp3": text,
                     "unknown.log": b"\x00unknown binary", "referenced.log": text,
                     "album.cue": b'FILE "referenced.log" BINARY\n'}
            for name, payload in files.items():
                (root / name).write_bytes(payload)
            main.process_release(root)
            self.assertEqual({p.name: p.read_bytes() for p in root.iterdir()}, files)

    def test_utf16_playlists_detect_incomplete_releases_and_preserve_encoding(self) -> None:
        for encoding, bom in (("utf-16-le", b"\xff\xfe"), ("utf-16-be", b"\xfe\xff")):
            for missing in (False, True):
                with self.subTest(encoding=encoding, missing=missing), tempfile.TemporaryDirectory() as temp:
                    root = Path(temp)
                    audio = root / "Release" / "Audio"
                    audio.mkdir(parents=True)
                    (audio / "one.flac").write_bytes(b"fLaC" + bytes(32))
                    if not missing:
                        (audio / "two.flac").write_bytes(b"fLaC" + bytes(32))
                    text = "# fixture\r\nAudio/one.flac\r\nAudio/two.flac\r\n"
                    (audio.parent / "tracks.log").write_bytes(bom + text.encode(encoding))
                    before = {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()}
                    if missing:
                        with self.assertRaisesRegex(ValueError, "incomplete playlist"):
                            main.process_release(root)
                        self.assertEqual({str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()}, before)
                    else:
                        main.process_release(root, cleanup=False)
                        expected = "# fixture\r\none.flac\r\ntwo.flac\r\n"
                        self.assertEqual((root / "tracks.log").read_bytes(), bom + expected.encode(encoding))
                        before = {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()}
                        main.process_release(root, cleanup=False)
                        self.assertEqual({str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()}, before)

    def test_multidisc_releases_preserve_tracks_with_identical_names(self) -> None:
        disc_pairs = (
            ("CD1", "CD2"),
            ("CDM-1", "CDM-2"),
            ("cdm.01 - UK", "CDM 02 (Remixes)"),
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

    def test_exact_posting_markers_are_cleaned_after_audio_is_retained(self) -> None:
        for ending in (b"", b"\n", b"\r\n"):
            for archive in (False, True):
                with self.subTest(ending=ending, archive=archive), tempfile.TemporaryDirectory() as temp:
                    root = Path(temp)
                    name = "Release.xpost.hash [newzNZB] [16_23] - yEnc 13 (1_1)"
                    files = {name: b"~^newz[NZB]~" + ending, "one.flac": b"fLaC" + bytes(32)}
                    if archive:
                        with zipfile.ZipFile(root / "release.zip", "w") as output:
                            for filename, payload in files.items():
                                output.writestr(filename, payload)
                    else:
                        for filename, payload in files.items():
                            (root / filename).write_bytes(payload)
                    main.process_release(root)
                    self.assertEqual({p.name: p.read_bytes() for p in root.iterdir()}, {"one.flac": files["one.flac"]})
                    main.process_release(root)

    def test_posting_marker_cleanup_preserves_near_matches_media_and_cues(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            exact = b"~^newz[NZB]~\n"
            files = {"prefix-only": exact + b"extra", "near-match": b"~^newz[NZB]~ \n",
                     "arbitrary-text": b"posting notes\n", "audio.mp3": exact,
                     "marker.cue": exact, "unknown.m3u": exact, "unknown.m3u8": exact,
                     "cue-target": exact, "protected.cue": b'FILE "cue-target" BINARY\n'}
            for filename, payload in files.items():
                (root / filename).write_bytes(payload)
            main.process_release(root)
            self.assertEqual({p.name: p.read_bytes() for p in root.iterdir()}, files)

    def test_marker_only_release_fails_without_deleting_original(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            marker = root / "obfuscated-posting-marker"
            marker.write_bytes(b"~^newz[NZB]~\n")
            with self.assertRaisesRegex(ValueError, "no files would remain"), mock.patch.object(main, "publish") as publish:
                main.process_release(root)
            publish.assert_not_called()
            self.assertEqual(marker.read_bytes(), b"~^newz[NZB]~\n")
            self.assertEqual(list(root.iterdir()), [marker])

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

    @classmethod
    def id3_flac(cls, tags: dict[str, str], *, version: int = 3, footer: bool = False) -> bytes:
        flac = bytearray(cls.tagged_flac(tags))
        streaminfo = struct.pack(">HH", 4096, 4096) + bytes(6)
        streaminfo += ((44100 << 44) | (1 << 41) | (15 << 36) | 44100).to_bytes(8, "big") + bytes(16)
        flac[8:42] = streaminfo
        title = b"\x00Fixture title"
        frame = ((b"TT2" + len(title).to_bytes(3, "big")) if version == 2
                 else b"TIT2" + len(title).to_bytes(4, "big") + bytes(2)) + title
        body = frame + (b"" if footer else bytes(5000))
        size = bytes((len(body) >> shift) & 127 for shift in (21, 14, 7, 0))
        header = b"ID3" + bytes((version, 0, 16 if footer else 128)) + size
        return header + body + (b"3DI" + header[3:] if footer else b"") + flac + b"TAG" + bytes(125)

    def test_id3_flac_is_repaired_without_changing_tags_artwork_or_payload(self) -> None:
        tags = {"ALBUM": "Example", "ARTIST": "Fixture", "TITLE": "Song", "TRACKNUMBER": "1", "TRACKTOTAL": "1"}
        for version, footer in ((2, False), (3, False), (4, False), (4, True)):
            for archive in (False, True):
                with self.subTest(version=version, footer=footer, archive=archive), tempfile.TemporaryDirectory() as temp:
                    root = Path(temp)
                    audio = self.id3_flac(tags, version=version, footer=footer)
                    cue = b'FILE "track.MP3" WAVE\n  TRACK 01 AUDIO\n    INDEX 01 00:00:00\n'
                    files = {"track.MP3": audio, "album.cue": cue, "tracks.m3u": b"track.MP3\r\n", "info.txt": b"posting info"}
                    if archive:
                        with zipfile.ZipFile(root / "release.zip", "w") as output:
                            for name, data in files.items():
                                output.writestr(name, data)
                    else:
                        for name, data in files.items():
                            (root / name).write_bytes(data)
                    main.process_release(root, require_completeness=True)
                    expected = {"track.flac": audio, "album.cue": cue.replace(b"track.MP3", b"track.flac"),
                                "tracks.m3u": b"track.flac\r\n"}
                    self.assertEqual({p.name: p.read_bytes() for p in root.iterdir()}, expected)
                    self.assertEqual(main.flac_album_metadata(root / "track.flac"), (tags, False))
                    main.process_release(root, require_completeness=True)
                    self.assertEqual({p.name: p.read_bytes() for p in root.iterdir()}, expected)

    def test_wave_cue_alias_uses_confirmed_flac_with_a_planned_mp3_rename(self) -> None:
        tags = {"ALBUM": "Example", "ARTIST": "Fixture", "TITLE": "Song", "TRACKNUMBER": "1", "TRACKTOTAL": "1"}
        for wrapped in (False, True):
            for archive in (False, True):
                for extensions in (False, True):
                    with self.subTest(wrapped=wrapped, archive=archive, extensions=extensions), tempfile.TemporaryDirectory() as temp:
                        root = Path(temp)
                        audio = self.id3_flac(tags) if wrapped else self.tagged_flac(tags)
                        cue = b'FILE "song.wav" WAVE\n  TRACK 01 AUDIO\n    INDEX 01 00:00:00\n'
                        if archive:
                            with zipfile.ZipFile(root / "release.zip", "w") as output:
                                output.writestr("song.mp3", audio)
                                output.writestr("album.cue", cue)
                        else:
                            (root / "song.mp3").write_bytes(audio)
                            (root / "album.cue").write_bytes(cue)
                        main.process_release(root, extensions=extensions, require_completeness=True)
                        target = "song.flac" if extensions else "song.mp3"
                        expected = {target: audio, "album.cue": cue.replace(b"song.wav", target.encode())}
                        self.assertEqual({p.name: p.read_bytes() for p in root.iterdir()}, expected)
                        main.process_release(root, extensions=extensions, require_completeness=True)
                        self.assertEqual({p.name: p.read_bytes() for p in root.iterdir()}, expected)

    def test_wave_cue_alias_keeps_ambiguous_planned_flac_targets(self) -> None:
        tags = {"ALBUM": "Example", "TRACKNUMBER": "1", "TRACKTOTAL": "1"}
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            files = {"song.mp3": self.id3_flac(tags), "song.flac": self.tagged_flac(tags),
                     "album.cue": b'FILE "song.wav" WAVE\n  TRACK 01 AUDIO\n'}
            for name, payload in files.items():
                (root / name).write_bytes(payload)
            with self.assertRaisesRegex(ValueError, "missing or ambiguous"):
                main.process_release(root)
            self.assertEqual({p.name: p.read_bytes() for p in root.iterdir()}, files)

    def test_id3_flac_keeps_disabled_repairs_and_target_collision_protection(self) -> None:
        tags = {"ALBUM": "Example", "ARTIST": "Fixture", "TITLE": "Song", "TRACKNUMBER": "1", "TRACKTOTAL": "1"}
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            audio = self.id3_flac(tags)
            (root / "track.mp3").write_bytes(audio)
            main.process_release(root, extensions=False, require_completeness=True)
            self.assertEqual((root / "track.mp3").read_bytes(), audio)
            other = self.tagged_flac({**tags, "ALBUM": "Other edition"})
            (root / "track.flac").write_bytes(other)
            with self.assertRaises(FileExistsError):
                main.process_release(root)
            self.assertEqual({p.name: p.read_bytes() for p in root.iterdir()}, {"track.mp3": audio, "track.flac": other})

    def test_id3_flac_recognition_rejects_malformed_or_unproven_headers(self) -> None:
        valid = self.id3_flac({"TITLE": "Song"})
        offset = 10 + sum(value << shift for value, shift in zip(valid[6:10], (21, 14, 7, 0)))
        core = valid[offset:]
        malformed = [b"ID3", b"ID3\x05" + valid[4:], valid[:4] + b"\xff" + valid[5:],
                     valid[:5] + b"\x01" + valid[6:], valid[:6] + b"\x80" + valid[7:],
                     valid[:6] + b"\x7f\x7f\x7f\x7f" + valid[10:],
                     valid[:offset] + b"fLaC" + bytes(38),
                     self.id3_flac({"TITLE": "Song"}, version=4, footer=True).replace(b"3DI", b"bad", 1),
                     b"ID3\x03\x00\x00" + bytes(4) + b"\xff\xfb\x90\x64" + bytes(413),
                     b"ID3\x03\x00\x00" + bytes((0, 0, 0, 4)) + b"fLaC" + b"not FLAC audio"]
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "track.mp3"
            for data in malformed:
                with self.subTest(header=data[:10]):
                    path.write_bytes(data)
                    self.assertEqual(main.detected_suffix(path), ".mp3")
                    self.assertEqual(main.flac_album_metadata(path), ({}, False))
            # A FLAC marker inside an ID3 payload does not identify the following MPEG stream.
            header = b"ID3\x03\x00\x00" + bytes((0, 0, 1, 0))
            path.write_bytes(header + core[:128].ljust(128, b"\x00") + b"\xff\xfb\x90\x64" + bytes(413))
            self.assertEqual(main.detected_suffix(path), ".mp3")
            self.assertEqual(main.extension_target(path), path)

    def test_raw_flac_with_mp3_suffix_is_repaired_and_disguised_sidecars_are_kept(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            raw = self.tagged_flac({"ALBUM": "Example", "TRACKNUMBER": "1", "TRACKTOTAL": "1"})
            tagged = self.id3_flac({"ALBUM": "Other", "TRACKNUMBER": "1", "TRACKTOTAL": "1"})
            (root / "song.mp3").write_bytes(raw)
            (root / "song.txt").write_bytes(tagged)
            main.process_release(root, require_completeness=True)
            self.assertEqual({p.name: p.read_bytes() for p in root.iterdir()}, {"song.flac": raw, "song.txt.flac": tagged})

    def test_modern_posting_audio_reports_need_known_header_and_structured_records(self) -> None:
        name = "Fixture-Example.1234abcd___123456abcdef_ [newzNZB] [2_6] - yEnc  2044 (1_1)"
        reports = [
            "foobar2000 1.4.3 / Dynamic Range Meter 1.1.1\nlog date: 2020-01-03 17:41:00\nAnalyzed: Fixture / Example\nDR         Peak         RMS     Duration Track\nDR6 -0.20 dB -7.26 dB 3:57 01-Song\nNumber of tracks: 1\nOfficial DR value: DR6\n",
            "AUDIOCHECKER v2.0 beta (build 457) - by Fixture\n-=== DO NOT EDIT THIS FILE! ===-\n001 -=- song.flac -=- CDDA (100%)\nSummary 99,93% CDDA\n",
            "DON'T MODIFY THIS FILE\nPERFORMER: auCDtect Task Manager, ver.1.6.0\nANALYZER: auCDtect: CD records authenticity detector\nFILE: song.flac\n  Size: 100 Hash: " + "A" * 32 + " Accuracy: -m8\n  Conclusion: CDDA 100%\n  Signature: " + "B" * 40 + "\n",
            "Torrent downloaded from Demonoid - https://www.demonoid.is",
        ]
        for report in reports:
            for encoding in ("utf-8", "utf-16"):
                with self.subTest(report=report[:30], encoding=encoding), tempfile.TemporaryDirectory() as temp:
                    root = Path(temp)
                    files = {"song.flac": b"fLaC" + bytes(32), name: report.encode(encoding),
                             "notes": report.encode(encoding), name + ".flac": report.encode(encoding),
                             name.replace("2044", "2045"): (report + "\x00").encode(encoding)}
                    for filename, payload in files.items():
                        (root / filename).write_bytes(payload)
                    main.process_release(root)
                    self.assertEqual({p.name: p.read_bytes() for p in root.iterdir()}, {k: v for k, v in files.items() if k != name})

    def test_posting_report_fragments_are_retained(self) -> None:
        name = "Fixture-Example.1234abcd___123456abcdef_ [newzNZB] [2_6] - yEnc  2044 (1_1)"
        reports = ["foobar2000 1.4.3 / Dynamic Range Meter 1.1.1\nAnalyzed: Fixture / Example\n",
                   "AUDIOCHECKER v2.0 beta (build 457) - by Fixture\nSummary 99,93% CDDA\n",
                   "DON'T MODIFY THIS FILE\nPERFORMER: auCDtect Task Manager, ver.1.6.0\nANALYZER: auCDtect: CD records authenticity detector\nFILE: song.flac\n",
                   "Torrent downloaded from Demonoid - https://example.com"]
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "song.flac").write_bytes(b"fLaC" + bytes(32))
            for report in reports:
                (root / name).write_text(report)
                main.process_release(root)
                self.assertEqual((root / name).read_text(), report)

    def test_printable_md5_audio_checksums_are_not_mistaken_for_playlists(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "song.flac").write_bytes(b"fLaC" + bytes(32))
            text = ("a" * 32 + " *01 Song.flac\r\n" + "b" * 32 + " *02 Song.flac\r\n").encode()
            (root / "album.md5").write_bytes(text)
            self.assertIsNone(main.playlist_entries(root / "album.md5"))
            main.process_release(root)
            self.assertEqual([p.name for p in root.iterdir()], ["song.flac"])

    def test_scene_nfo_art_controls_need_structured_headers_and_exact_placement(self) -> None:
        for control in ("\x10", "\x14"):
            with self.subTest(control=control), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                text = f"██\nArtist | Fixture\nTitle | Example\nGenre | Rock\n██{control}██\n"
                (root / "song.flac").write_bytes(b"fLaC" + bytes(32))
                (root / "scene.nfo").write_bytes(text.encode("cp437"))
                (root / "unstructured.nfo").write_bytes(text.replace("Artist | Fixture", "notes").encode("cp437"))
                (root / "payload.nfo").write_bytes((text + "metadata" + control + "payload").encode("cp437"))
                main.process_release(root)
                self.assertFalse((root / "scene.nfo").exists())
                self.assertTrue((root / "unstructured.nfo").exists())
                self.assertTrue((root / "payload.nfo").exists())

    def test_scene_nfo_backspace_frames_require_layout_credit_and_identity(self) -> None:
        text = "██\n\x08░ ARTIST.... Fixture ░\x08\n\x08░ TITLE..... Example ░\x08\n\x08░ TRACKS.... 2 ░\x08\n██ \x08\x08 ██\n\x0e\x07nfoLayoutBy■fixture\n"
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "song.flac").write_bytes(b"fLaC" + bytes(32))
            (root / "scene.nfo").write_bytes(text.encode("cp437"))
            for index, invalid in enumerate((text.replace("nfoLayoutBy", "other"), text.replace("Fixture", ""),
                                             text + "bad\x08\x08payload", text + "\x00", text + "payload \x08hidden", text + "payload \x08\x08hidden", text + "payload\x08 hidden")):
                (root / f"invalid{index}.nfo").write_bytes(invalid.encode("cp437"))
            main.process_release(root)
            self.assertFalse((root / "scene.nfo").exists())
            self.assertEqual(len(list(root.glob("invalid*.nfo"))), 7)

    @staticmethod
    def parenthesized_posting(name: str) -> str:
        return f'[PRiVATE]-[WtFnZb]-[{name}]-[1_20] - __ yEnc  1024 (1_1)'

    def test_parenthesized_disc_images_cues_reports_and_retries(self) -> None:
        for archive in (False, True):
            with self.subTest(archive=archive), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                files = {}
                for disc in (1, 2):
                    stem = f'Fixture.-.Example.(CD{disc})'
                    files[self.parenthesized_posting(stem + '.flac') + '.flac'] = self.tagged_flac({})
                    files[self.parenthesized_posting(stem + '.cue')] = (
                        f'FILE "Fixture - Example (CD{disc}).flac" WAVE\r\n TRACK 01 AUDIO\r\n INDEX 01 00:00:00\r\n'
                        ' TRACK 02 AUDIO\r\n INDEX 01 03:00:00\r\n').encode()
                    files[self.parenthesized_posting(stem + '.accurip')] = b'AccurateRip report\n'
                    files[self.parenthesized_posting('foo_dr.txt')] = b'Analysis report\n'
                if archive:
                    with zipfile.ZipFile(root / 'release.zip', 'w') as output:
                        for name, payload in files.items():
                            output.writestr(name, payload)
                else:
                    for name, payload in files.items():
                        (root / name).write_bytes(payload)
                main.process_release(root, require_completeness=True)
                expected = {}
                for disc in (1, 2):
                    stem = f'Fixture.-.Example.(CD{disc})'
                    expected[f'CD{disc}/{stem}.flac'] = files[self.parenthesized_posting(stem + '.flac') + '.flac']
                    cue = (root / f'CD{disc}/{stem}.cue').read_bytes()
                    self.assertIn(f'FILE "{stem}.flac" WAVE'.encode(), cue)
                    expected[f'CD{disc}/{stem}.cue'] = cue
                self.assertEqual({p.relative_to(root).as_posix(): p.read_bytes() for p in main.tree_files(root)}, expected)
                main.process_release(root, require_completeness=True)
                self.assertEqual({p.relative_to(root).as_posix(): p.read_bytes() for p in main.tree_files(root)}, expected)

    def test_parenthesized_wrappers_reject_ambiguous_discs_and_cross_disc_cues(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name in ('Fixture.(CD1).(CD2).flac', '_Fixture_CD1_image.(CD2).flac'):
                path = root / (self.parenthesized_posting(name) + '.flac')
                path.write_bytes(self.tagged_flac({}))
                self.assertIsNone(main.wrapped_posting_target(path))
            cue = root / self.parenthesized_posting('Fixture.(CD1).cue')
            cue.write_text('FILE "Fixture.(CD2).flac" WAVE\n')
            audio = root / (self.parenthesized_posting('Fixture.(CD2).flac') + '.flac')
            audio.write_bytes(self.tagged_flac({}))
            before = {p.name: p.read_bytes() for p in root.iterdir()}
            with self.assertRaisesRegex(ValueError, 'FILE reference'):
                main.process_release(root)
            self.assertEqual({p.name: p.read_bytes() for p in root.iterdir()}, before)

    def test_wrapped_text_reports_preserve_binary_media_playlists_and_cues(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            report = root / self.parenthesized_posting('Report.txt')
            report.write_text('Analysis report\n')
            self.assertTrue(main.disposable(report))
            for name, payload in (('Report.txt', b'\0binary'), ('Report.log', b'fLaC' + bytes(32)),
                                  ('Report.cue', b'FILE "track.flac" WAVE\n'),
                                  ('Report.m3u', b'track.flac\n')):
                path = root / self.parenthesized_posting(name)
                path.write_bytes(payload)
                self.assertFalse(main.disposable(path))
            report.write_text('Analysis report\n')
            (root / 'track.flac').write_bytes(self.tagged_flac({'TRACKNUMBER': '1', 'TRACKTOTAL': '1'}))
            main.process_release(root, cleanup=False, extensions=False)
            self.assertTrue(report.exists())

    def test_conflicting_wrapped_text_playlists_keep_archive_and_sources(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            name = self.parenthesized_posting('Report.txt')
            (root / name).write_bytes(b'01.flac\n02.flac\n')
            self.assertFalse(main.disposable(root / name))
            for track in (1, 2):
                (root / f'{track:02}.flac').write_bytes(self.tagged_flac({'TRACKNUMBER': str(track), 'TRACKTOTAL': '2'}))
            with zipfile.ZipFile(root / 'release.zip', 'w') as archive:
                archive.writestr(name, b'01.flac\n03-missing.flac\n')
            before = {p.name: p.read_bytes() for p in root.iterdir()}
            with self.assertRaises((FileExistsError, ValueError)):
                main.process_release(root)
            self.assertEqual({p.name: p.read_bytes() for p in root.iterdir()}, before)

    def test_encryptnzb_wrapped_reports_require_verified_text_and_preserve_references(self) -> None:
        def posting(name: str) -> str:
            return f'[PRiVATE]-[EnCrYpTnZb]-[{name}]-[37_91] - __ yEnc  4946 (1_1)'

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            audio = self.tagged_flac({'TRACKNUMBER': '1', 'TRACKTOTAL': '1'})
            (root / 'track.flac').write_bytes(audio)
            report = root / posting('Album.log')
            report.write_text('Exact Audio Copy V1.0\nExtraction report\n')
            self.assertTrue(main.disposable(report))
            retained = {}
            for name, payload in (('binary.log', b'Exact Audio Copy\0'),
                                  ('audio.log', audio), ('playlist.txt', b'01.flac\n02.flac\n'),
                                  ('Album.cue', b'FILE "track.flac" WAVE\n')):
                path = root / posting(name)
                path.write_bytes(payload)
                retained[path.name] = payload
                self.assertFalse(main.disposable(path))
            (root / posting('audio.log')).unlink()
            del retained[posting('audio.log')]
            unknown = root / posting('Unknown.log').replace('EnCrYpTnZb', 'Unknown')
            unknown.write_text('Extraction report\n')
            self.assertFalse(main.disposable(unknown))
            main.process_release(root, extensions=False, cleanup=False)
            self.assertTrue(report.exists())
            cue = root / 'protected.cue'
            cue.write_text(f'FILE "{report.name}" WAVE\n')
            main.process_release(root, extensions=False)
            self.assertTrue(report.exists())
            cue.unlink()
            main.process_release(root, extensions=False)
            self.assertFalse(report.exists())
            self.assertEqual((root / 'track.flac').read_bytes(), audio)
            for name, payload in retained.items():
                self.assertEqual((root / name).read_bytes(), payload)

    def test_windows_audiochecker_log_text_validation_is_complete(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'audiochecker.log'
            payload = 'AUDIOCHECKER v2.0 beta\n01 -=- 01. Móige.flac -=- CDDA (100%)\n'.encode('cp1252')
            path.write_bytes(payload)
            self.assertTrue(main.disposable(path))
            path.write_bytes(payload + b'\0')
            self.assertFalse(main.disposable(path))
            path.write_bytes(payload.replace(b'AUDIOCHECKER', b'Unknown tool'))
            self.assertFalse(main.disposable(path))

    @staticmethod
    def wrapped_disc_name(name: str, disc: int = 1) -> str:
        return f"[PRiVATE]-[WtFnZb]-[_Fixture_FLAC_CD{disc}_{name}]-[1_20] - __ yEnc  1024 (1_1)"

    def test_wrapped_disc_cues_and_images_restore_together_without_changing_audio(self) -> None:
        for archive in (False, True):
            with self.subTest(archive=archive), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                files = {}
                for disc in (1, 2):
                    audio = self.tagged_flac({"ALBUM": f"Example CD{disc}"})
                    cue = f'FILE "Fixture - Example CD{disc}.flac" WAVE\r\n TRACK 01 AUDIO\r\n INDEX 01 00:00:00\r\n TRACK 02 AUDIO\r\n INDEX 01 03:00:00\r\n'.encode()
                    files[self.wrapped_disc_name(f"Fixture.-.Example.CD{disc}.flac", disc) + ".flac"] = audio
                    files[self.wrapped_disc_name(f"Fixture.-.Example.CD{disc}.cue", disc)] = cue
                    files[self.wrapped_disc_name("Technical_FLAC.txt", disc)] = b"Encoding info\n"
                if archive:
                    with zipfile.ZipFile(root / "release.zip", "w") as output:
                        for name, payload in files.items():
                            output.writestr(name, payload)
                else:
                    for name, payload in files.items():
                        (root / name).write_bytes(payload)
                main.process_release(root, require_completeness=True)
                for disc in (1, 2):
                    name = self.wrapped_disc_name(f"Fixture.-.Example.CD{disc}.flac", disc) + ".flac"
                    self.assertEqual((root / f"CD{disc}/Fixture.-.Example.CD{disc}.flac").read_bytes(), files[name])
                    cue = (root / f"CD{disc}/Fixture.-.Example.CD{disc}.cue").read_bytes()
                    self.assertIn(f'FILE "Fixture.-.Example.CD{disc}.flac" WAVE'.encode(), cue)
                self.assertEqual(len(main.tree_files(root)), 4)
                before = {p.relative_to(root): p.read_bytes() for p in main.tree_files(root)}
                main.process_release(root, require_completeness=True)
                self.assertEqual({p.relative_to(root): p.read_bytes() for p in main.tree_files(root)}, before)

    def test_wrapped_cues_resolve_only_within_their_restored_disc(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for disc in (1, 2):
                (root / (self.wrapped_disc_name("song.flac", disc) + ".flac")).write_bytes(self.tagged_flac({"ALBUM": "Example"}))
                (root / self.wrapped_disc_name("album.cue", disc)).write_text('FILE "song.flac" WAVE\n TRACK 01 AUDIO\n TRACK 02 AUDIO\n')
            main.process_release(root, require_completeness=True)
            for disc in (1, 2):
                self.assertIn('FILE "song.flac" WAVE', (root / f"CD{disc}/album.cue").read_text())
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / (self.wrapped_disc_name("song.flac", 2) + ".flac")).write_bytes(self.tagged_flac({"ALBUM": "Example"}))
            (root / self.wrapped_disc_name("album.cue", 1)).write_text('FILE "song.flac" WAVE\n TRACK 01 AUDIO\n TRACK 02 AUDIO\n')
            before = {p.name: p.read_bytes() for p in root.iterdir()}
            with self.assertRaisesRegex(ValueError, "missing or ambiguous"):
                main.process_release(root, require_completeness=True)
            self.assertEqual({p.name: p.read_bytes() for p in root.iterdir()}, before)

    def test_wrapped_track_completeness_uses_verified_disc_folders(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for disc in (1, 2):
                (root / (self.wrapped_disc_name("song.flac", disc) + ".flac")).write_bytes(self.tagged_flac({"ALBUM": "Example", "TRACKNUMBER": "1", "TRACKTOTAL": "1"}))
            main.process_release(root, require_completeness=True)
            self.assertEqual({str(p.relative_to(root)) for p in main.tree_files(root)}, {"CD1/song.flac", "CD2/song.flac"})
            main.process_release(root, require_completeness=True)

    def test_wrapped_cue_retries_with_optional_suffix_and_repair_cleanup_switches(self) -> None:
        for appended, extensions, cleanup in itertools.product((False, True), repeat=3):
            with self.subTest(appended=appended, extensions=extensions, cleanup=cleanup), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                name = self.wrapped_disc_name("song.flac") + (".flac" if appended else "")
                cue_name = self.wrapped_disc_name("album.cue")
                audio = self.tagged_flac({"ALBUM": "Example"})
                (root / name).write_bytes(audio)
                (root / cue_name).write_text('FILE "song.flac" WAVE\n TRACK 01 AUDIO\n TRACK 02 AUDIO\n')
                main.process_release(root, extensions=extensions, cleanup=cleanup, require_completeness=True)
                expected = {p.relative_to(root): p.read_bytes() for p in main.tree_files(root)}
                self.assertEqual(len(expected), 2)
                main.process_release(root, extensions=extensions, cleanup=cleanup, require_completeness=True)
                self.assertEqual({p.relative_to(root): p.read_bytes() for p in main.tree_files(root)}, expected)
                self.assertEqual([p.read_bytes() for p in main.tree_files(root) if main.detected_suffix(p) == ".flac"], [audio])

    def test_wrapped_cues_cannot_be_referenced_as_audio(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            name = self.wrapped_disc_name("other.cue")
            (root / name).write_text('FILE "song.flac" WAVE\n TRACK 01 AUDIO\n')
            (root / "CD1").mkdir()
            (root / "CD1/song.flac").write_bytes(self.tagged_flac({"ALBUM": "Example"}))
            (root / "album.cue").write_text(f'FILE "{name}" WAVE\n TRACK 01 AUDIO\n')
            before = {p.relative_to(root): p.read_bytes() for p in main.tree_files(root)}
            with self.assertRaisesRegex(ValueError, "invalid FILE reference"):
                main.process_release(root)
            self.assertEqual({p.relative_to(root): p.read_bytes() for p in main.tree_files(root)}, before)

    def test_ambiguous_wrapped_disc_markers_are_not_unwrapped(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name in (self.wrapped_disc_name("session_CD2_song.flac", 1) + ".flac",
                         self.wrapped_disc_name("CD2_song.flac", 1) + ".flac",
                         self.wrapped_disc_name("song.flac", 1).replace("Fixture_", "Fixture_CD2_") + ".flac"):
                path = root / name
                audio = self.tagged_flac({"ALBUM": name})
                path.write_bytes(audio)
                self.assertIsNone(main.wrapped_posting_target(path))
                self.assertEqual(main.extension_target(path), path)
            before = {p.name: p.read_bytes() for p in root.iterdir()}
            main.process_release(root)
            self.assertEqual({p.name: p.read_bytes() for p in root.iterdir()}, before)

    def test_wrapped_postings_preserve_malformed_binary_controls_and_cleanup_switch(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            audio = self.tagged_flac({"ALBUM": "Example"})
            text = b"Metadata\n"
            files = {"song.flac": audio, self.wrapped_disc_name("info.txt"): text,
                     self.wrapped_disc_name("bad.log"): b"Exact Audio Copy \x00",
                     self.wrapped_disc_name("bad.cue"): b"no cue entries\n",
                     self.wrapped_disc_name("fake.flac"): text,
                     self.wrapped_disc_name("bad.txt") + ".flac": text,
                     self.wrapped_disc_name("../bad.txt"): text,
                     self.wrapped_disc_name("unknown.bin"): text}
            for name, payload in files.items():
                if "/" in name:
                    continue
                (root / name).write_bytes(payload)
            main.process_release(root, cleanup=False, extensions=False)
            self.assertEqual({p.name: p.read_bytes() for p in root.iterdir()}, {k: v for k, v in files.items() if "/" not in k})
            main.process_release(root)
            self.assertFalse(any(p.name == self.wrapped_disc_name("info.txt") for p in root.rglob("*")))
            self.assertEqual((root / self.wrapped_disc_name("bad.log")).read_bytes(), b"Exact Audio Copy \x00")

    def test_wrapped_postings_collision_or_missing_cue_reference_preserves_source(self) -> None:
        for collision in (False, True):
            with self.subTest(collision=collision), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                name = self.wrapped_disc_name("song.flac") + ".flac"
                (root / name).write_bytes(self.tagged_flac({"ALBUM": "Example"}))
                if collision:
                    (root / "CD1").mkdir()
                    (root / "CD1/song.flac").write_bytes((root / name).read_bytes())
                else:
                    (root / self.wrapped_disc_name("album.cue")).write_text('FILE "missing.flac" WAVE\n TRACK 01 AUDIO\n')
                before = {p.relative_to(root): p.read_bytes() for p in main.tree_files(root)}
                with self.assertRaises((ValueError, FileExistsError)):
                    main.process_release(root)
                self.assertEqual({p.relative_to(root): p.read_bytes() for p in main.tree_files(root)}, before)

    def test_windows_eac_logs_require_known_header_and_complete_printable_text(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            files = {"song.flac": b"fLaC" + bytes(32),
                     "ripping.log": "Exact Audio Copy V0.99\nBenutztes Laufwerk: Gerät\n".encode("cp1252"),
                     "unknown.log": b"unknown \xff payload", "binary.log": b"Exact Audio Copy \x00\xff"}
            for name, payload in files.items():
                (root / name).write_bytes(payload)
            main.process_release(root)
            self.assertEqual({p.name: p.read_bytes() for p in root.iterdir()}, {k: v for k, v in files.items() if k != "ripping.log"})

    def test_cue_space_to_dot_flac_references_preserve_bytes_and_encoding(self) -> None:
        for extension in ("wav", "flac"):
            for encoding in ("utf-8-sig", "utf-16-le", "cp1252"):
                for archive in (False, True):
                    with self.subTest(extension=extension, encoding=encoding, archive=archive), tempfile.TemporaryDirectory() as temp:
                        root = Path(temp)
                        audio = self.tagged_flac({"TRACKNUMBER": "1", "TRACKTOTAL": "1"})
                        name = f"(01) [Fixture] Example Song.{extension}"
                        cue = f'FILE "{name}" WAVE\r\n TRACK 01 AUDIO\r\n INDEX 01 00:00:00\r\n'.encode(encoding)
                        if encoding.startswith("utf-16"):
                            cue = b"\xff\xfe" + cue
                        target = "(01).[Fixture].Example.Song.flac"
                        files = {"Album/album.cue": cue, "Album/" + target: audio}
                        if archive:
                            with zipfile.ZipFile(root / "release.zip", "w") as output:
                                for filename, payload in files.items():
                                    output.writestr(filename, payload)
                        else:
                            (root / "Album").mkdir()
                            for filename, payload in files.items():
                                (root / filename).write_bytes(payload)
                        main.process_release(root, require_completeness=True)
                        repaired = cue.replace(name.encode(encoding.replace("-sig", "")), target.encode(encoding.replace("-sig", "")))
                        self.assertEqual((root / "album.cue").read_bytes(), repaired)
                        self.assertEqual((root / target).read_bytes(), audio)
                        main.process_release(root, require_completeness=True)
                        self.assertEqual((root / "album.cue").read_bytes(), repaired)

    def test_cue_space_to_dot_alias_keeps_exact_flac_and_wave_precedence(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name in ("Song Name.flac", "Song.Name.flac"):
                (root / name).write_bytes(self.tagged_flac({"ALBUM": name, "TRACKNUMBER": "1", "TRACKTOTAL": "1"}))
            (root / "album.cue").write_text('FILE "Song Name.wav" WAVE\n')
            cue = root / "album.cue"
            self.assertEqual(main.read_cues(main.tree_files(root), root)[cue][2]["Song Name.wav"], root / "Song Name.flac")
            (root / "Song Name.wav").write_bytes(b"RIFF" + bytes(32))
            self.assertEqual(main.read_cues(main.tree_files(root), root)[cue][2]["Song Name.wav"], root / "Song Name.wav")

    def test_cue_space_to_dot_alias_rejects_ambiguity_paths_and_other_whitespace(self) -> None:
        for reference, names, tail in (("Song Name.flac", ("Song.Name.flac", "Song.Name"), "WAVE"),
                                       ("sub/Song Name.flac", ("Song.Name.flac",), "WAVE"),
                                       ("../Song Name.flac", ("Song.Name.flac",), "WAVE"),
                                       ("Song\tName.flac", ("Song.Name.flac",), "WAVE"),
                                       ("Song Name.flac", ("Song.Name.flac",), "BINARY")):
            with self.subTest(reference=reference, tail=tail), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                for name in names:
                    (root / name).write_bytes(self.tagged_flac({"TRACKNUMBER": "1", "TRACKTOTAL": "1"}))
                (root / "album.cue").write_text(f'FILE "{reference}" {tail}\n TRACK 01 AUDIO\n')
                before = {p.name: p.read_bytes() for p in root.iterdir()}
                with self.assertRaises(ValueError):
                    main.process_release(root)
                self.assertEqual({p.name: p.read_bytes() for p in root.iterdir()}, before)

    def test_missing_local_wave_cue_resolves_matching_flac_and_preserves_encoding(self) -> None:
        for encoding in ('utf-8-sig', 'utf-16-le', 'utf-16-be', 'cp1252'):
            for archive in (False, True):
                with self.subTest(encoding=encoding, archive=archive), tempfile.TemporaryDirectory() as temp:
                    root = Path(temp)
                    audio = self.tagged_flac({'TRACKNUMBER': '1', 'TOTALTRACKS': '1'})
                    cue = 'FILE "01 Artist’s Song.wav" WAVE\r\n TRACK 01 AUDIO\r\n INDEX 01 00:00:00\r\n'
                    raw = cue.encode(encoding)
                    if encoding.startswith('utf-16'):
                        raw = (b'\xff\xfe' if encoding.endswith('le') else b'\xfe\xff') + raw
                    files = {'Album/01 Artist’s Song.flac': audio, 'Album/album.cue': raw}
                    if archive:
                        with zipfile.ZipFile(root / 'album.zip', 'w') as output:
                            for name, payload in files.items():
                                output.writestr(name, payload)
                    else:
                        (root / 'Album').mkdir()
                        for name, payload in files.items():
                            (root / name).write_bytes(payload)
                    main.process_release(root)
                    expected = raw.replace('.wav'.encode(encoding.replace('-sig', '')), '.flac'.encode(encoding.replace('-sig', '')))
                    self.assertEqual((root / 'album.cue').read_bytes(), expected)
                    self.assertEqual((root / '01 Artist’s Song.flac').read_bytes(), audio)
                    main.process_release(root)

    def test_disc_prefixed_cue_alias_preserves_complete_filename_identity(self) -> None:
        for variant in ('valid', 'album', 'artist', 'track', 'disc', 'mix', 'ambiguous', 'path', 'performer-header', 'album-header', 'duplicate-header', 'invalid-header'):
            with self.subTest(variant=variant), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                tags = {'ARTIST': 'Fixture Artist', 'ALBUM': 'Example - Disc 1',
                        'TITLE': 'Song', 'TRACKNUMBER': '1', 'TRACKTOTAL': '1'}
                if variant in {'album', 'artist'}:
                    tags[variant.upper()] = 'Foreign'
                if variant == 'track':
                    tags['TRACKNUMBER'] = '2'
                if variant == 'disc':
                    tags['DISCNUMBER'] = '2'
                name = '101-fixture_artist-song-group.flac'
                (root / name).write_bytes(self.tagged_flac(tags))
                if variant == 'ambiguous':
                    (root / '101.fixture.artist.song.group.flac').write_bytes(self.tagged_flac(tags))
                requested = '01-Fixture Artist-Song-group.wav'
                if variant == 'mix':
                    requested = '01-Fixture Artist-Song-other.wav'
                if variant == 'path':
                    requested = '../' + requested
                cue = f'FILE "{requested}" WAVE\n TRACK 01 AUDIO\n INDEX 01 00:00:00\n'
                headers = {'performer-header': 'PERFORMER "Other Artist"\n',
                           'album-header': 'TITLE "Other Album"\n',
                           'duplicate-header': 'TITLE "Example - Disc 1"\nTITLE "Example - Disc 1"\n',
                           'invalid-header': 'TITLE Other Album\n'}
                cue = headers.get(variant, '') + cue
                (root / 'example.disc.1.cue').write_text(cue)
                before = self.snapshot(root)
                if variant == 'valid':
                    main.process_release(root, require_completeness=True)
                    self.assertEqual((root / 'example.disc.1.cue').read_text(), cue.replace(requested, name))
                    self.assertEqual((root / name).read_bytes(), before[name])
                    main.process_release(root, require_completeness=True)
                else:
                    with self.assertRaises(ValueError):
                        main.process_release(root, require_completeness=True)
                    self.assertEqual(self.snapshot(root), before)

    def test_single_disc_label_keeps_unambiguous_alias_without_disc_totals(self) -> None:
        for disc_tags in ({}, {'DISCNUMBER': '1'}):
            with self.subTest(disc_tags=disc_tags), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                audio = self.tagged_flac({'ARTIST': 'Fixture Artist', 'ALBUM': 'Example', 'TITLE': 'Song',
                                          'TRACKNUMBER': '1', 'TRACKTOTAL': '1', **disc_tags})
                (root / 'hidden.flac').write_bytes(audio)
                cue = ('PERFORMER "Fixture Artist"\nTITLE "Example"\n'
                       'FILE "01 Song.wav" WAVE\n TRACK 01 AUDIO\n INDEX 01 00:00:00\n')
                (root / 'example.CD1.cue').write_text(cue)
                main.process_release(root, require_completeness=True)
                self.assertEqual((root / 'hidden.flac').read_bytes(), audio)
                self.assertEqual((root / 'example.CD1.cue').read_text(), cue.replace('01 Song.wav', 'hidden.flac'))
                main.process_release(root, require_completeness=True)

    def test_disc_label_keeps_metadata_alias_in_separate_complete_disc_folders(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            original = {}
            for disc in (1, 2):
                folder = root / f'CD{disc}'
                folder.mkdir()
                audio = self.tagged_flac({'ARTIST': 'Fixture Artist', 'ALBUM': 'Example', 'TITLE': 'Song',
                                          'TRACKNUMBER': '1', 'TRACKTOTAL': '1',
                                          'DISCNUMBER': str(disc), 'DISCTOTAL': '2'})
                original[disc] = audio
                (folder / 'hidden.flac').write_bytes(audio)
                (folder / f'example.CD{disc}.cue').write_text('PERFORMER "Fixture Artist"\nTITLE "Example"\n'
                    'FILE "01 Song.wav" WAVE\n TRACK 01 AUDIO\n INDEX 01 00:00:00\n')
            main.process_release(root, require_completeness=True)
            for disc in (1, 2):
                self.assertEqual((root / f'CD{disc}' / 'hidden.flac').read_bytes(), original[disc])
                self.assertIn('FILE "hidden.flac"', (root / f'CD{disc}' / f'example.CD{disc}.cue').read_text())
            stable = self.snapshot(root)
            main.process_release(root, require_completeness=True)
            self.assertEqual(self.snapshot(root), stable)

    def test_disc_label_scopes_metadata_cue_alias_without_ignoring_unknown_discs(self) -> None:
        for variant in ('valid', 'shared-title', 'missing-disc', 'conflicting-total', 'missing-disc-file', 'wrong-label', 'foreign-album', 'missing-total', 'ambiguous', 'malformed-performer'):
            with self.subTest(variant=variant), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                audio = {}
                for disc, title in ((1, 'Song A'), (2, 'Song B')):
                    if variant == 'shared-title':
                        title = 'Song A'
                    tags = {'ARTIST': 'Fixture Artist', 'ALBUM': 'Example', 'TITLE': title,
                            'TRACKNUMBER': '1', 'TRACKTOTAL': '1',
                            'DISCNUMBER': str(disc), 'DISCTOTAL': '2'}
                    if disc == 2 and variant == 'missing-disc':
                        del tags['DISCNUMBER']
                    if disc == 2 and variant == 'missing-total':
                        del tags['DISCTOTAL']
                    if disc == 2 and variant == 'conflicting-total':
                        tags['DISCTOTAL'] = '3'
                    if disc == 1 and variant == 'foreign-album':
                        tags['ALBUM'] = 'Foreign'
                    if disc == 2 and variant == 'missing-disc-file':
                        continue
                    name = f'{disc}01-hidden.flac'
                    audio[name] = self.tagged_flac(tags)
                    (root / name).write_bytes(audio[name])
                    if disc == 1 and variant == 'ambiguous':
                        (root / 'duplicate.flac').write_bytes(audio[name])
                    label = '3' if variant == 'wrong-label' and disc == 1 else str(disc)
                    cue = ('PERFORMER "Fixture Artist"\nTITLE "Example"\n'
                           f'FILE "01 {title}.wav" WAVE\n TRACK 01 AUDIO\n INDEX 01 00:00:00\n')
                    if variant == 'malformed-performer':
                        cue = 'PERFORMER Invalid\n' + cue
                    (root / f'example.CD{label}.cue').write_text(cue)
                before = self.snapshot(root)
                if variant in ('valid', 'shared-title'):
                    main.process_release(root, require_completeness=True)
                    for disc in (1, 2):
                        self.assertIn(f'FILE "{disc}01-hidden.flac"', (root / f'example.CD{disc}.cue').read_text())
                    self.assertEqual({p.name: p.read_bytes() for p in root.glob('*.flac')}, audio)
                    stable = self.snapshot(root)
                    main.process_release(root, require_completeness=True)
                    self.assertEqual(self.snapshot(root), stable)
                else:
                    with self.assertRaises(ValueError):
                        main.process_release(root, require_completeness=True)
                    self.assertEqual(self.snapshot(root), before)

    def test_missing_wave_cue_uses_exact_artist_title_track_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for number, title in ((1, 'Example Song (Radio Edit)'), (2, 'Example Song (LP Version)')):
                (root / f'{number:02d}-obfuscated.flac').write_bytes(self.tagged_flac({
                    'ARTIST': 'Fixture Artist', 'ALBUM': 'Example', 'TITLE': title, 'TRACKNUMBER': str(number)}))
            cue = ('PERFORMER "Fixture Artist"\nTITLE "Example"\n'
                   'FILE "01 Example Song (Radio Edit).wav" WAVE\n TRACK 01 AUDIO\n INDEX 01 00:00:00\n'
                   ' TRACK 02 AUDIO\n INDEX 00 03:00:00\n'
                   'FILE "02 Example Song (LP Version).wav" WAVE\n INDEX 01 00:00:00\n')
            (root / 'album.cue').write_text(cue)
            before = {p.name: p.read_bytes() for p in root.glob('*.flac')}
            main.process_release(root)
            self.assertEqual((root / 'album.cue').read_text(), cue.replace('01 Example Song (Radio Edit).wav', '01-obfuscated.flac').replace('02 Example Song (LP Version).wav', '02-obfuscated.flac'))
            self.assertEqual({p.name: p.read_bytes() for p in root.glob('*.flac')}, before)

    def test_missing_flac_cue_resolves_renamed_tracks_without_changing_audio(self) -> None:
        for archived in (False, True):
            with self.subTest(archived=archived), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                audio = self.tagged_flac({'ARTIST': 'Fixture Artist', 'ALBUM': 'Example',
                                          'TITLE': 'Example Song', 'TRACKNUMBER': '1', 'TRACKTOTAL': '1'})
                cue = b'PERFORMER "Fixture Artist"\r\nTITLE "Example"\r\nFILE "01 Example Song.FLAC" WAVE\r\n TRACK 01 AUDIO\r\n INDEX 01 00:00:00\r\n'
                files = {'Nested/01..Example.Song.flac': audio, 'Nested/album.cue': cue}
                if archived:
                    with zipfile.ZipFile(root / 'release.zip', 'w') as output:
                        for name, data in files.items():
                            output.writestr(name, data)
                else:
                    (root / 'Nested').mkdir()
                    for name, data in files.items():
                        (root / name).write_bytes(data)
                main.process_release(root, require_completeness=True)
                expected = {'01..Example.Song.flac': audio,
                            'album.cue': cue.replace(b'01 Example Song.FLAC', b'01..Example.Song.flac')}
                self.assertEqual(self.snapshot(root), expected)
                main.process_release(root, require_completeness=True)
                self.assertEqual(self.snapshot(root), expected)

    def test_cue_guest_artist_uses_explicit_matching_album_artist_and_album(self) -> None:
        for suffix in ('wav', 'flac'):
            for artist_key, prefix in itertools.product(('ALBUMARTIST', 'ALBUM ARTIST'), ('', 'Fixture Artist ', 'Guest Artist ')):
                with self.subTest(suffix=suffix, artist_key=artist_key, prefix=prefix), tempfile.TemporaryDirectory() as temp:
                    root = Path(temp)
                    audio = self.tagged_flac({'ARTIST': 'Guest Artist', artist_key: 'Fixture Artist',
                                              'ALBUM': 'Example', 'TITLE': 'Remix',
                                              'TRACKNUMBER': '1', 'TRACKTOTAL': '1'})
                    (root / 'obfuscated.flac').write_bytes(audio)
                    cue = f'PERFORMER "Fixture Artist"\nTITLE "Example"\nFILE "01 {prefix}Remix.{suffix}" WAVE\n TRACK 01 AUDIO\n'
                    (root / 'album.cue').write_text(cue)
                    main.process_release(root, require_completeness=True)
                    self.assertEqual((root / 'obfuscated.flac').read_bytes(), audio)
                    self.assertEqual((root / 'album.cue').read_text(), cue.replace(f'01 {prefix}Remix.{suffix}', 'obfuscated.flac'))
                    before = self.snapshot(root)
                    main.process_release(root, require_completeness=True)
                    self.assertEqual(self.snapshot(root), before)

    def test_cue_album_artist_fallback_rejects_missing_conflicting_or_wrong_identity(self) -> None:
        for variant in ('no-album-title', 'wrong-album', 'wrong-album-artist', 'conflicting-alias', 'wrong-version', 'ambiguous'):
            with self.subTest(variant=variant), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                tags = {'ARTIST': 'Guest Artist', 'ALBUMARTIST': 'Fixture Artist', 'ALBUM': 'Example',
                        'TITLE': 'Remix', 'TRACKNUMBER': '1', 'TRACKTOTAL': '1'}
                if variant == 'wrong-album-artist':
                    tags['ALBUMARTIST'] = 'Other Artist'
                if variant == 'conflicting-alias':
                    tags['ALBUM ARTIST'] = 'Other Artist'
                if variant == 'wrong-version':
                    tags['TITLE'] = 'Remix (Live)'
                (root / 'obfuscated.flac').write_bytes(self.tagged_flac(tags))
                if variant == 'ambiguous':
                    (root / 'another.flac').write_bytes(self.tagged_flac(tags))
                title = '' if variant == 'no-album-title' else 'TITLE "Wrong"\n' if variant == 'wrong-album' else 'TITLE "Example"\n'
                (root / 'album.cue').write_text('PERFORMER "Fixture Artist"\n' + title + 'FILE "01 Remix.flac" WAVE\n TRACK 01 AUDIO\n')
                before = self.snapshot(root)
                with self.assertRaises(ValueError):
                    main.process_release(root)
                self.assertEqual(self.snapshot(root), before)

    def test_missing_flac_alias_keeps_existing_references_and_rejects_foreign_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            audio = self.tagged_flac({'ARTIST': 'Fixture', 'ALBUM': 'Example', 'TITLE': 'Song',
                                      'TRACKNUMBER': '1', 'TRACKTOTAL': '1'})
            (root / 'existing.flac').write_bytes(audio)
            (root / 'obfuscated.flac').write_bytes(audio)
            (root / 'album.cue').write_text('FILE "existing.flac" WAVE\n')
            self.assertEqual(main.read_cues(list(root.iterdir()), root)[root / 'album.cue'][2]['existing.flac'], root / 'existing.flac')
            for reference, kind in (('01 Song.flac', 'BINARY'), ('../01 Song.flac', 'WAVE'),
                                    ('/01 Song.flac', 'WAVE'), ('C:\\01 Song.flac', 'WAVE')):
                (root / 'album.cue').write_text(f'PERFORMER "Fixture"\nTITLE "Example"\nFILE "{reference}" {kind}\n')
                with self.assertRaises(ValueError):
                    main.read_cues(list(root.iterdir()), root)

    def test_wave_cue_fallback_rejects_ambiguity_missing_identity_and_other_versions(self) -> None:
        tags = {'ARTIST': 'Fixture Artist', 'ALBUM': 'Example', 'TITLE': 'Example Song', 'TRACKNUMBER': '1'}
        cases = [({'a.flac': tags, 'b.flac': tags}, '01 Example Song.wav'),
                 ({'a.flac': {**tags, 'TITLE': 'Example Song (Live)'}}, '01 Example Song.wav'),
                 ({'a.flac': {**tags, 'ARTIST': 'Other Artist'}}, '01 Example Song.wav'),
                 ({'a.flac': {**tags, 'TRACKNUMBER': '2'}}, '01 Example Song.wav'),
                 ({'a.flac': {k: v for k, v in tags.items() if k != 'ALBUM'}}, '01 Example Song.wav'),
                 ({'a.flac': tags, 'b.flac': {**tags, 'ALBUM': 'Other Album', 'TRACKNUMBER': '2'}}, '01 Example Song.wav'),
                 ({'a.flac': {**tags, 'TRACK': '2'}}, '01 Example Song.wav'),
                 ({'01 Example Song.flac': tags}, 'Other Album/01 Example Song.wav')]
        for files, reference in cases:
            with self.subTest(reference=reference, files=files), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                for name, values in files.items():
                    (root / name).write_bytes(self.tagged_flac(values))
                (root / 'album.cue').write_text(f'PERFORMER "Fixture Artist"\nFILE "{reference}" WAVE\n TRACK 01 AUDIO\n')
                before = self.snapshot(root)
                with self.assertRaises(ValueError):
                    main.process_release(root)
                self.assertEqual(self.snapshot(root), before)

    def test_wave_cue_fallback_keeps_existing_wave_and_rejects_binary_or_foreign_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'song.wav').write_bytes(b'RIFF' + bytes(4) + b'WAVE' + bytes(32))
            (root / 'song.flac').write_bytes(b'fLaC' + bytes(32))
            (root / 'album.cue').write_text('FILE "song.wav" WAVE\n')
            cues = main.read_cues(list(root.iterdir()), root)
            self.assertEqual(cues[root / 'album.cue'][2]['song.wav'], root / 'song.wav')
            (root / 'song.wav').unlink()
            for reference, kind in (('song.wav', 'BINARY'), ('../song.wav', 'WAVE'), ('/song.wav', 'WAVE'), ('C:\\song.wav', 'WAVE')):
                (root / 'album.cue').write_text(f'FILE "{reference}" {kind}\n')
                with self.assertRaises(ValueError):
                    main.read_cues(list(root.iterdir()), root)

    def test_repaired_wave_cue_cannot_hide_missing_tracks_or_merge_references(self) -> None:
        cases = [("FILE \"01 Song.wav\" WAVE\n TRACK 01 AUDIO\n", {'TRACKNUMBER': '1', 'TOTALTRACKS': '2'}, '01 Song.flac'),
                 ('PERFORMER "Fixture"\nFILE "01 Song.wav" WAVE\n TRACK 01 AUDIO\nFILE "01 Fixture Song.wav" WAVE\n TRACK 02 AUDIO\n',
                  {'ARTIST': 'Fixture', 'TITLE': 'Song', 'ALBUM': 'Example', 'TRACKNUMBER': '1', 'TOTALTRACKS': '1'}, 'obfuscated.flac')]
        for cue, tags, name in cases:
            with self.subTest(cue=cue), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                (root / name).write_bytes(self.tagged_flac(tags))
                (root / 'album.cue').write_text(cue)
                before = self.snapshot(root)
                with self.assertRaises(ValueError):
                    main.process_release(root)
                self.assertEqual(self.snapshot(root), before)

    def test_repaired_wave_cue_keeps_album_images_and_mixed_exact_track_references(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            audio = self.tagged_flac({'TRACKNUMBER': '1', 'TOTALTRACKS': '2'})
            (root / 'album.flac').write_bytes(audio)
            (root / 'album.cue').write_text('FILE "album.wav" WAVE\n TRACK 01 AUDIO\n INDEX 01 00:00:00\n TRACK 02 AUDIO\n INDEX 01 03:00:00\n')
            main.process_release(root)
            self.assertIn('"album.flac"', (root / 'album.cue').read_text())
            self.assertEqual((root / 'album.flac').read_bytes(), audio)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for number in (1, 2):
                (root / f'{number:02d} Song.flac').write_bytes(self.tagged_flac({'TRACKNUMBER': str(number), 'TOTALTRACKS': '2'}))
            (root / 'album.cue').write_text('FILE "01 Song.wav" WAVE\n TRACK 01 AUDIO\nFILE "02 Song.flac" WAVE\n TRACK 02 AUDIO\n')
            main.process_release(root)
            self.assertIn('"01 Song.flac"', (root / 'album.cue').read_text())

    def test_cue_metadata_album_identity_and_cr_only_parsing(self) -> None:
        for ending in ('\n', '\r\n', '\r'):
            for album, accepted in (('Example', True), ('Example (single)', True), ('Other Album', False)):
                with self.subTest(ending=ending, album=album), tempfile.TemporaryDirectory() as temp:
                    root = Path(temp)
                    audio = self.tagged_flac({'ARTIST': 'Fixture', 'ALBUM': 'Example', 'TITLE': 'Song', 'TRACKNUMBER': '1', 'TOTALTRACKS': '1'})
                    (root / 'obfuscated.flac').write_bytes(audio)
                    cue = f'PERFORMER "Fixture"\nTITLE "{album}"\nFILE "01 Song.wav" WAVE\n TRACK 01 AUDIO\n'.replace('\n', ending).encode()
                    (root / 'album.cue').write_bytes(cue)
                    if accepted:
                        main.process_release(root, require_completeness=True)
                        self.assertEqual((root / 'album.cue').read_bytes(), cue.replace(b'01 Song.wav', b'obfuscated.flac'))
                    else:
                        before = self.snapshot(root)
                        with self.assertRaises(ValueError):
                            main.process_release(root)
                        self.assertEqual(self.snapshot(root), before)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'image.flac').write_bytes(self.tagged_flac({'TRACKNUMBER': '1', 'TOTALTRACKS': '2'}))
            (root / 'image.cue').write_bytes(b'FILE "image.wav" WAVE\r TRACK 01 AUDIO\r TRACK 02 AUDIO\r')
            main.process_release(root, require_completeness=True)
            self.assertEqual((root / 'image.cue').read_bytes(), b'FILE "image.flac" WAVE\r TRACK 01 AUDIO\r TRACK 02 AUDIO\r')

    def test_strict_repaired_track_cues_require_count_evidence_on_first_pass_and_retry(self) -> None:
        for count in (1, 2):
            with self.subTest(count=count), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                for number in range(1, count + 1):
                    (root / f'{number:02d} Song.flac').write_bytes(self.tagged_flac({'ALBUM': 'Example', 'TRACKNUMBER': str(number)}))
                (root / 'album.cue').write_text(''.join(f'FILE "{number:02d} Song.wav" WAVE\n TRACK {number:02d} AUDIO\n' for number in range(1, count + 1)))
                before = self.snapshot(root)
                with self.assertRaisesRegex(ValueError, 'unproven'):
                    main.process_release(root, require_completeness=True)
                self.assertEqual(self.snapshot(root), before)
                main.process_release(root)
                repaired = self.snapshot(root)
                with self.assertRaisesRegex(ValueError, 'unproven'):
                    main.process_release(root, require_completeness=True)
                self.assertEqual(self.snapshot(root), repaired)

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

    def test_space_renamed_playlist_paths_preserve_cues_encoding_and_audio(self) -> None:
        for archive in (False, True):
            for cleanup, strict in ((True, True), (False, False)):
                with self.subTest(archive=archive, cleanup=cleanup, strict=strict), tempfile.TemporaryDirectory() as temp:
                    root = Path(temp)
                    audio = {f"0{i}..Song.{i}.flac": self.tagged_flac(
                        {"ALBUM": "Fixture", "ARTIST": "Artist", "TITLE": f"Song {i}",
                         "TRACKNUMBER": str(i)}) for i in (1, 2)}
                    cue = b'FILE "01..Song.1.flac" WAVE\r\n  TRACK 01 AUDIO\r\nFILE "02..Song.2.flac" WAVE\r\n  TRACK 02 AUDIO\r\n'
                    files = {**audio, "album.cue": cue,
                             "album.m3u8": b"\xef\xbb\xbf#EXTM3U\r\n01. Song 1.flac\r\n02. Song 2.flac\r\n"}
                    if archive:
                        with zipfile.ZipFile(root / "release.zip", "w") as output:
                            for name, payload in files.items():
                                output.writestr("Rip/" + name, payload)
                    else:
                        for name, payload in files.items():
                            (root / name).write_bytes(payload)
                    main.process_release(root, cleanup=cleanup, require_completeness=strict)
                    expected = {**audio, "album.cue": cue,
                                "album.m3u8": b"\xef\xbb\xbf#EXTM3U\r\n01..Song.1.flac\r\n02..Song.2.flac\r\n"}
                    self.assertEqual(self.snapshot(root), expected)
                    main.process_release(root, cleanup=cleanup, require_completeness=strict)
                    self.assertEqual(self.snapshot(root), expected)

    def test_space_renamed_playlist_cleanup_and_exact_path_precedence(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            files = {"Song.One.flac": b"fLaC" + bytes(32)}
            (root / "Song.One.flac").write_bytes(files["Song.One.flac"])
            (root / "album.m3u").write_text("Song One.flac\n")
            main.process_release(root)
            self.assertEqual(self.snapshot(root), files)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name in ("Song One.flac", "Song.One.flac", "Song.Two.flac"):
                (root / name).write_bytes(b"fLaC" + bytes(32))
            (root / "album.m3u").write_text("Song One.flac\nSong Two.flac\n")
            refs = {}
            main.check_playlists(main.tree_files(root), set(), references=refs)
            self.assertEqual(refs[root / "album.m3u"][main.PurePosixPath("Song One.flac")], root / "Song One.flac")
            self.assertEqual(refs[root / "album.m3u"][main.PurePosixPath("Song Two.flac")], root / "Song.Two.flac")

    def test_space_renamed_playlists_reject_alias_collisions_and_missing_tracks(self) -> None:
        for text in ("Song One.flac\nSong.One.flac\n", "Song One.flac\nMissing.flac\n"):
            with self.subTest(text=text), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                (root / "Song.One.flac").write_bytes(b"fLaC" + bytes(32))
                (root / "album.m3u").write_text(text)
                before = self.snapshot(root)
                with self.assertRaisesRegex(ValueError, "ambiguous playlist|incomplete playlist"):
                    main.process_release(root)
                self.assertEqual(self.snapshot(root), before)

    def test_space_renamed_playlist_paths_do_not_infer_nested_or_remote_names(self) -> None:
        for text in ("Other Folder/Song One.flac\n", "https://example.com/Song One.flac\n",
                     "../Song One.flac\n", "Song\u00a0One.flac\n"):
            with self.subTest(text=text), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                (root / "Song.One.flac").write_bytes(b"fLaC" + bytes(32))
                (root / "album.m3u").write_text(text)
                before = self.snapshot(root)
                main.process_release(root)
                self.assertEqual(self.snapshot(root), before)

    def test_complete_obfuscated_album_retains_all_ten_tracks(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for track in range(1, 11):
                (root / f"{track:032x}.flac").write_bytes(self.tagged_flac({"TRACK": str(track), "TRACKTOTAL": "10"}))
            before = self.snapshot(root)
            self.assertEqual(self.run_main(root), main.SUCCESS)
            self.assertEqual(self.snapshot(root), before)

    def test_covering_playlist_preserves_vinyl_side_relative_track_numbers(self) -> None:
        for archive in (False, True):
            for strict in (False, True):
                for count in (1, 2):
                    with self.subTest(archive=archive, strict=strict, count=count), tempfile.TemporaryDirectory() as temp:
                        root = Path(temp)
                        files = {}
                        for side in ("a", "b"):
                            for track in range(1, count + 1):
                                name = f"{side}{track}-artist-song-{side}-{track}.flac"
                                files[name] = self.tagged_flac(
                                    {"ALBUM": "Fixture", "ARTIST": "Artist", "MEDIA": "Vinyl",
                                     "TITLE": f"Song {side} {track}", "TRACKNUMBER": str(track)})
                        files["album.m3u"] = ("\n".join(files) + "\n").encode()
                        if archive:
                            with zipfile.ZipFile(root / "release.zip", "w") as output:
                                for name, raw in files.items():
                                    output.writestr("Rip/" + name, raw)
                        else:
                            for name, raw in files.items():
                                (root / name).write_bytes(raw)
                        main.process_release(root, require_completeness=strict)
                        self.assertEqual(self.snapshot(root), files)
                        main.process_release(root, require_completeness=strict)
                        self.assertEqual(self.snapshot(root), files)

    def test_vinyl_side_inference_rejects_missing_mixed_or_ambiguous_evidence(self) -> None:
        for case in ("no-playlist", "partial", "gap", "non-A", "mixed", "duplicate-side", "disc-tags", "alias"):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                prefixes = {"gap": ("a1", "c1"), "non-A": ("b1", "c1"),
                            "mixed": ("101", "b1"), "duplicate-side": ("a1", "a1")}.get(case, ("a1", "b1"))
                names = []
                for index, prefix in enumerate(prefixes):
                    name = f"{prefix}-artist-song-{index}.flac"
                    tags = {"ALBUM": "Fixture", "ARTIST": "Artist", "TITLE": f"Song {index}", "TRACKNUMBER": "1"}
                    if case == "disc-tags":
                        tags.update(DISCNUMBER="1", DISCTOTAL="1")
                    (root / name).write_bytes(self.tagged_flac(tags))
                    names.append(name)
                if case != "no-playlist":
                    entries = names[:1] if case == "partial" else names
                    if case == "alias":
                        entries = [names[0], names[0].upper()]
                    (root / "album.m3u").write_text("\n".join(entries) + "\n")
                before = self.snapshot(root)
                self.assertEqual(main.playlist_disc_groups(main.tree_files(root), set(), root), {})
                with self.assertRaises(ValueError):
                    main.process_release(root, require_completeness=True)
                self.assertEqual(self.snapshot(root), before)

    def test_dotted_playlist_aliases_preserve_disc_inference_and_exact_precedence(self) -> None:
        for other_exact in (False, True):
            with self.subTest(other_exact=other_exact), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                expected = {}
                entries = []
                for disc in (1, 2):
                    for track in (1, 2):
                        name = f"{disc}{track:02d}.Song.{disc}.{track}.flac"
                        expected[name] = self.tagged_flac(
                            {"ALBUM": "Fixture", "ARTIST": "Artist", "TITLE": f"Song {disc} {track}",
                             "TRACKNUMBER": str(track), "TRACKTOTAL": "2"})
                        entries.append(name.replace(".", " ", 3))
                for name, raw in expected.items():
                    (root / name).write_bytes(raw)
                (root / "album.m3u").write_text("\n".join(entries) + "\n")
                if other_exact:
                    (root / entries[0]).write_bytes(self.tagged_flac(
                        {"ALBUM": "Other", "ARTIST": "Other", "TITLE": "Different recording",
                         "TRACKNUMBER": "1", "TRACKTOTAL": "1"}))
                    before = self.snapshot(root)
                    with self.assertRaisesRegex(ValueError, "duplicate FLAC track numbers"):
                        main.process_release(root, require_completeness=True)
                    self.assertEqual(self.snapshot(root), before)
                else:
                    main.process_release(root, require_completeness=True)
                    expected["album.m3u"] = ("\n".join(expected) + "\n").encode()
                    self.assertEqual(self.snapshot(root), expected)
                    main.process_release(root, require_completeness=True)
                    self.assertEqual(self.snapshot(root), expected)

    def test_covering_playlist_resolves_discless_scene_track_numbers(self) -> None:
        for totals, strict in ((False, False), (False, True), (True, False), (True, True)):
            with self.subTest(totals=totals, strict=strict), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                names = []
                for disc, count in ((1, 2), (2, 3)):
                    for track in range(1, count + 1):
                        name = f"{disc}{track:02d}-artist-song-{disc}-{track}.flac"
                        tags = {"ALBUM": "Example", "ARTIST": "Artist", "TITLE": f"Song {disc}-{track}",
                                "TRACKNUMBER": str(track)}
                        if totals:
                            tags["TRACKTOTAL"] = str(count)
                        (root / name).write_bytes(self.tagged_flac(tags))
                        names.append(name)
                (root / "album.m3u").write_text("\n".join(names) + "\n")
                before = self.snapshot(root)
                main.process_release(root, require_completeness=strict)
                self.assertEqual(self.snapshot(root), before)
                main.process_release(root, require_completeness=strict)
                self.assertEqual(self.snapshot(root), before)

    def test_disc_inference_does_not_partition_mixed_artists_into_cohorts(self) -> None:
        for split in (False, True):
            with self.subTest(split=split), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                names = []
                for disc, artist in ((1, "Artist"), (2, "Artist"), (3, "Other")):
                    for track in (1, 2):
                        name = f"{disc}{track:02d}-song.flac"
                        (root / name).write_bytes(self.tagged_flac(
                            {"ALBUM": "Example", "ARTIST": artist, "TITLE": "Song",
                             "TRACKNUMBER": str(track), "TRACKTOTAL": "2"}))
                        names.append(name)
                if split:
                    (root / "first.m3u").write_text("\n".join(names[:4]) + "\n")
                    (root / "other.m3u").write_text("\n".join(names[4:]) + "\n")
                else:
                    (root / "album.m3u").write_text("\n".join(names) + "\n")
                before = self.snapshot(root)
                with self.assertRaises(ValueError):
                    main.process_release(root, require_completeness=True)
                self.assertEqual(self.snapshot(root), before)

    def test_discless_scene_groups_require_unambiguous_complete_evidence(self) -> None:
        for problem in ("no playlist", "partial playlist", "duplicate entry", "wrong track",
                        "disc gap", "track gap", "explicit disc", "explicit total", "missing title",
                        "foreign album", "foreign artist", "artist aliases", "disc folder", "wrong total", "duplicate track", "unsafe playlist"):
            with self.subTest(problem=problem), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                names = []
                for disc, track in ((1, 1), (1, 2), (2, 1), (2, 2)):
                    name = f"{disc if problem != 'disc gap' or disc != 2 else 3}{track:02d}-song.flac"
                    tags = {"ALBUM": "Example", "ARTIST": "Artist", "TITLE": "Song", "TRACKNUMBER": str(track)}
                    if disc == 2 and track == 2:
                        if problem == "wrong track":
                            tags["TRACKNUMBER"] = "3"
                        if problem == "track gap":
                            name, tags["TRACKNUMBER"] = "203-song.flac", "3"
                        if problem == "explicit disc":
                            tags["DISCNUMBER"] = "1"
                        if problem == "explicit total":
                            tags["DISCTOTAL"] = "1"
                        if problem == "missing title":
                            del tags["TITLE"]
                        if problem == "foreign album":
                            tags["ALBUM"] = "Other"
                        if problem == "artist aliases":
                            tags["ALBUMARTIST"], tags["ALBUM ARTIST"] = "Artist", "Other"
                        if problem == "foreign artist":
                            tags["ARTIST"] = "Other"
                        if problem == "wrong total":
                            tags["TRACKTOTAL"] = "3"
                        if problem == "duplicate track":
                            name, tags["TRACKNUMBER"] = "201-other.flac", "1"
                    if problem == "disc folder":
                        name = "CD1/" + name
                        (root / "CD1").mkdir(exist_ok=True)
                    (root / name).write_bytes(self.tagged_flac(tags))
                    names.append(name)
                if problem != "no playlist":
                    entries = names[:-1] if problem == "partial playlist" else names
                    if problem == "duplicate entry":
                        entries = names + names[:1]
                    if problem == "unsafe playlist":
                        entries = names + ["../outside.flac"]
                    (root / "album.m3u").write_text("\n".join(entries) + "\n")
                before = self.snapshot(root)
                with self.assertRaises(ValueError):
                    main.process_release(root, require_completeness=True)
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
                    (root / "image.cue").write_text('FILE "image.flac" WAVE\n TRACK 01 AUDIO\n TRACK 02 AUDIO\n')
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
                        process.assert_called_once_with(root, verify_audio=False, require_completeness=True, require_audio=False)
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

    def nfo_numbered_disc_fixture(self, root: Path) -> dict[str, bytes]:
        root.mkdir(parents=True, exist_ok=True)
        audio = {}
        for disc, number, title in ((1, 1, 'Song One'), (1, 2, 'Song Two'), (2, 1, 'Song Three')):
            name = f'{disc}{number:02d}-fixture-{title.lower().replace(" ", "_")}.flac'
            audio[name] = self.tagged_flac({'ARTIST': 'Fixture Artist', 'ALBUM': 'Example Album',
                                          'TITLE': title, 'TRACKNUMBER': str(number)})
            (root / name).write_bytes(audio[name])
        (root / 'release.nfo').write_bytes(('     Artist | Fixture Artist\n     Title | Example Album\n'
            '     Source | CD                         Time | 3:00\n'
            '────┤ Tracks ├────────────────\n'
            '     CD 1/2\n     01. Song One                    1:00\n'
            '     02. Song Two                    1:00\n'
            '     CD 2/2\n     01. Song Three                  1:00\n').encode('cp437'))
        (root / 'extra.nfo').write_text('Fixture release notes\n')
        return audio

    def test_numbered_discs_use_matching_nfo_without_a_playlist_and_keep_evidence(self) -> None:
        for archived, ending in itertools.product((False, True), (b'\n', b'\r\n', b'\r')):
            with self.subTest(archived=archived, ending=ending), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                source = root / 'Source' if archived else root
                audio = self.nfo_numbered_disc_fixture(source)
                evidence = (source / 'release.nfo').read_bytes().replace(b'\n', ending)
                (source / 'release.nfo').write_bytes(evidence)
                if archived:
                    with zipfile.ZipFile(root / 'release.zip', 'w') as output:
                        for path in source.iterdir():
                            output.write(path, 'Nested/' + path.name)
                    shutil.rmtree(source)
                main.process_release(root)
                self.assertEqual({p.name: p.read_bytes() for p in root.glob('*.flac')}, audio)
                self.assertEqual((root / 'release.nfo').read_bytes(), evidence)
                self.assertFalse((root / 'extra.nfo').exists())
                main.plan_tree(root, require_completeness=True)
                stable = self.snapshot(root)
                main.process_release(root, require_completeness=True)
                self.assertEqual(self.snapshot(root), stable)

    def test_nfo_disc_inference_rejects_incomplete_conflicting_and_foreign_evidence(self) -> None:
        for variant in ('absent', 'artist', 'album', 'source', 'disc-total', 'duplicate-disc',
                        'duplicate-track', 'missing-track', 'extra-track', 'title', 'binary', 'oversize',
                        'filename-disc', 'track-tag', 'missing-title'):
            with self.subTest(variant=variant), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                self.nfo_numbered_disc_fixture(root)
                nfo = root / 'release.nfo'
                raw = nfo.read_bytes()
                replacements = {'artist': (b'Fixture Artist', b'Foreign Artist'),
                    'album': (b'Example Album', b'Foreign Album'), 'source': (b'Source | CD', b'Source | WEB'),
                    'disc-total': (b'CD 2/2', b'CD 2/3'), 'duplicate-disc': (b'CD 2/2', b'CD 1/2'),
                    'duplicate-track': (b'02. Song Two', b'01. Song Two'),
                    'missing-track': (b'     02. Song Two                    1:00\n', b''),
                    'extra-track': (b'CD 2/2', b'03. Extra Track                 1:00\n     CD 2/2'),
                    'title': (b'Song Two', b'Other Song')}
                if variant in replacements:
                    old, new = replacements[variant]
                    nfo.write_bytes(raw.replace(old, new))
                if variant == 'absent':
                    nfo.unlink()
                if variant == 'binary':
                    nfo.write_bytes(raw + b'\0binary')
                if variant == 'oversize':
                    nfo.write_bytes(raw + b' ' * 65536)
                if variant == 'filename-disc':
                    source = root / '201-fixture-song_three.flac'
                    source.rename(root / '301-fixture-song_three.flac')
                if variant in ('track-tag', 'missing-title'):
                    tags = {'ARTIST': 'Fixture Artist', 'ALBUM': 'Example Album', 'TRACKNUMBER': '2' if variant == 'track-tag' else '1'}
                    if variant != 'missing-title':
                        tags['TITLE'] = 'Song Three'
                    (root / '201-fixture-song_three.flac').write_bytes(self.tagged_flac(tags))
                before = self.snapshot(root)
                with self.assertRaises(ValueError):
                    main.process_release(root, require_completeness=True)
                self.assertEqual(self.snapshot(root), before)

    def test_nfo_disc_evidence_stays_inside_the_matching_edition_folder(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.nfo_numbered_disc_fixture(root / 'Edition A')
            self.nfo_numbered_disc_fixture(root / 'Edition B')
            (root / 'Edition A' / 'release.nfo').rename(root / 'release.nfo')
            (root / 'Edition B' / 'release.nfo').unlink()
            before = self.snapshot(root)
            with self.assertRaises(ValueError):
                main.process_release(root, require_completeness=True)
            self.assertEqual(self.snapshot(root), before)

    def release_total_fixture(self, root: Path, *, global_numbers: bool = False,
                              directories: bool = False) -> dict[str, bytes]:
        root.mkdir(parents=True, exist_ok=True)
        audio = {}
        for disc, track, number, title in ((1, 1, 1, "Opening"), (1, 2, 2, "Second Song"), (2, 1, 3, "Finale")):
            name = f'{disc}{track:02}-fixture-{title.lower().replace(" ", "_")}.flac'
            relative = f'CD{disc:02}/{name}' if directories else name
            tags = {'ALBUM': 'Example', 'ARTIST': 'Fixture', 'ALBUMARTIST': 'Fixture', 'TITLE': title,
                    'TRACKNUMBER': str(number if global_numbers else track), 'TOTALTRACKS': '3'}
            if not directories:
                tags.update(DISCNUMBER=str(disc), TOTALDISCS='2')
            audio[relative] = self.tagged_flac(tags)
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(audio[relative])
        (root / 'release.m3u').write_text(''.join(name + '\n' for name in audio))
        (root / 'release.nfo').write_text(
            'Artist...: Fixture       Title.....: Example\nSource....: 2CD\n'
            'Tracklist.. .\nCD1:\n01.Opening       [03:00]\n02.Second Song       [04:00]\n'
            'CD2:\n01.Finale       [05:00]\n')
        return audio

    def test_whole_release_totals_require_and_retain_both_manifests(self) -> None:
        for global_numbers, directories in itertools.product((False, True), repeat=2):
            with self.subTest(global_numbers=global_numbers, directories=directories), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                audio = self.release_total_fixture(root, global_numbers=global_numbers, directories=directories)
                (root / 'encoding.log').write_text('Extraction report\n')
                main.process_release(root, require_completeness=True)
                self.assertFalse((root / 'encoding.log').exists())
                self.assertTrue((root / 'release.nfo').exists())
                self.assertTrue((root / 'release.m3u').exists())
                for name, data in audio.items():
                    self.assertEqual((root / name).read_bytes(), data)
                before = self.snapshot(root)
                main.process_release(root)
                main.process_release(root, require_completeness=True)
                self.assertEqual(self.snapshot(root), before)

    def test_whole_release_totals_reject_missing_mismatched_and_binary_evidence(self) -> None:
        variants = ('missing_nfo', 'missing_playlist', 'artist', 'album', 'source', 'title', 'missing_row',
                    'extra_row', 'duplicate_disc', 'duplicate_artist', 'binary', 'oversized', 'partial_playlist',
                    'duplicate_playlist', 'track_gap', 'conflicting_total', 'missing_disc', 'missing_title')
        for variant in variants:
            with self.subTest(variant=variant), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                self.release_total_fixture(root, global_numbers=True)
                nfo, playlist = root / 'release.nfo', root / 'release.m3u'
                text = nfo.read_text()
                if variant == 'missing_nfo':
                    nfo.unlink()
                elif variant == 'missing_playlist':
                    playlist.unlink()
                elif variant in ('artist', 'album', 'source', 'title', 'missing_row', 'extra_row', 'duplicate_disc', 'duplicate_artist'):
                    old, new = {
                        'artist': ('Artist...: Fixture', 'Artist...: Foreign'),
                        'album': ('Title.....: Example', 'Title.....: Foreign'),
                        'source': ('Source....: 2CD', 'Source....: 3CD'),
                        'title': ('01.Finale', '01.Different Mix'),
                        'missing_row': ('01.Finale       [05:00]\n', ''),
                        'extra_row': ('01.Finale       [05:00]', '01.Finale       [05:00]\n02.Missing       [03:00]'),
                        'duplicate_disc': ('CD2:', 'CD1:'),
                        'duplicate_artist': ('Tracklist.. .', 'Artist...: Fixture\nTracklist.. .'),
                    }[variant]
                    nfo.write_text(text.replace(old, new))
                elif variant == 'binary':
                    nfo.write_bytes(nfo.read_bytes() + b'\0')
                elif variant == 'oversized':
                    nfo.write_text(text + ' ' * 65536)
                elif variant == 'partial_playlist':
                    playlist.write_text('\n'.join(playlist.read_text().splitlines()[:2]) + '\n')
                elif variant == 'duplicate_playlist':
                    playlist.write_text(playlist.read_text() + playlist.read_text().splitlines()[0] + '\n')
                else:
                    path = next(root.glob('201-*.flac'))
                    tags = main.flac_album_metadata(path)[0]
                    if variant == 'track_gap':
                        tags['TRACKNUMBER'] = '4'
                    elif variant == 'conflicting_total':
                        tags['TOTALTRACKS'] = '2'
                    elif variant == 'missing_disc':
                        tags['DISCNUMBER'] = '3'
                    else:
                        del tags['TITLE']
                    path.write_bytes(self.tagged_flac(tags))
                before = self.snapshot(root)
                with self.assertRaises(ValueError):
                    main.process_release(root, require_completeness=True)
                self.assertEqual(self.snapshot(root), before)

    def test_whole_release_evidence_cannot_cross_edition_boundaries(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.release_total_fixture(root / 'Edition A', global_numbers=True)
            self.release_total_fixture(root / 'Edition B', global_numbers=True)
            (root / 'Edition B/release.nfo').unlink()
            before = self.snapshot(root)
            with self.assertRaises(ValueError):
                main.process_release(root, require_completeness=True)
            self.assertEqual(self.snapshot(root), before)

    def test_whole_release_evidence_survives_archive_extraction_and_flattening(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / 'source'
            audio = self.release_total_fixture(source, global_numbers=True)
            with zipfile.ZipFile(root / 'release.zip', 'w') as archive:
                for path in main.tree_files(source):
                    archive.write(path, 'Release/' + path.relative_to(source).as_posix())
            shutil.rmtree(source)
            main.process_release(root)
            self.assertFalse((root / 'release.zip').exists())
            self.assertTrue((root / 'release.nfo').exists())
            self.assertTrue((root / 'release.m3u').exists())
            for name, data in audio.items():
                self.assertEqual((root / name).read_bytes(), data)
            main.plan_tree(root, require_completeness=True)

    def test_cdm_disc_completeness_and_references_survive_flattening(self) -> None:
        for missing in (False, True):
            with self.subTest(missing=missing), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                tracks = {}
                for disc in (1, 2):
                    if missing and disc == 2:
                        continue
                    for track in (1, 2):
                        name = f"Release/CDM-{disc}/Audio/{track:02}.flac"
                        tracks[name] = self.tagged_flac({"ALBUM": "Fixture", "ALBUMARTIST": "Artist",
                                                       "DISCNUMBER": str(disc), "DISCTOTAL": "2",
                                                       "TRACKNUMBER": str(track), "TRACKTOTAL": "2"})
                for name, data in tracks.items():
                    path = root / name
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(data)
                playlist = root / "Release/tracks.m3u"
                playlist.write_text("".join(name.removeprefix("Release/") + "\n" for name in tracks))
                before = self.snapshot(root)
                if missing:
                    with self.assertRaisesRegex(ValueError, "missing or invalid discs"):
                        main.process_release(root, require_completeness=True)
                    self.assertEqual(self.snapshot(root), before)
                else:
                    main.process_release(root, require_completeness=True)
                    self.assertEqual({str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*.flac")},
                                     {name.replace("Release/", "").replace("/Audio/", "/"): data
                                      for name, data in tracks.items()})
                    self.assertEqual((root / "tracks.m3u").read_text(),
                                     "".join(name.removeprefix("Release/").replace("/Audio/", "/") + "\n"
                                             for name in tracks))
                    before = self.snapshot(root)
                    main.process_release(root, require_completeness=True)
                    self.assertEqual(self.snapshot(root), before)

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
            (root / "unknown.nfo").write_bytes(art + "∞".encode("cp437"))
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

    def test_catalog_music_without_audio_preserves_files_and_archives(self) -> None:
        for archive in (False, True):
            with self.subTest(archive=archive), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                files = {'Release/movie.mkv': b'\x1aE\xdf\xa3' + bytes(32), 'Release/info.nfo': b'release info'}
                if archive:
                    with zipfile.ZipFile(root / 'release.zip', 'w') as output:
                        for name, data in files.items():
                            output.writestr(name, data)
                else:
                    for name, data in files.items():
                        path = root / name
                        path.parent.mkdir(parents=True, exist_ok=True)
                        path.write_bytes(data)
                before = self.snapshot(root)
                states = {p: main.file_state(p) for p in main.tree_files(root)}
                with mock.patch.dict(os.environ, {'NZBPP_CATEGORY': 'music', 'NZBPP_FINALDIR': str(root),
                                                 'NZBPR_DRONE': 'A' * 32}, clear=True):
                    self.assertEqual(main.main(), main.FAILURE)
                self.assertEqual(self.snapshot(root), before)
                self.assertEqual({p: main.file_state(p) for p in main.tree_files(root)}, states)

    def test_catalog_music_keeps_audio_and_video_and_supports_retries(self) -> None:
        for archive in (False, True):
            with self.subTest(archive=archive), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                audio = self.tagged_flac({'ALBUM': 'Fixture', 'TRACKNUMBER': '1', 'TRACKTOTAL': '1'})
                video = b'\x1aE\xdf\xa3' + bytes(32)
                if archive:
                    with zipfile.ZipFile(root / 'release.zip', 'w') as output:
                        output.writestr('Release/song.txt', audio)
                        output.writestr('Release/video.mkv', video)
                else:
                    (root / 'song.txt').write_bytes(audio)
                    (root / 'video.mkv').write_bytes(video)
                with mock.patch.dict(os.environ, {'NZBPP_CATEGORY': 'music', 'NZBPP_FINALDIR': str(root),
                                                 'NZBPR_DRONE': 'a' * 32}, clear=True):
                    self.assertEqual(main.main(), main.SUCCESS)
                    self.assertEqual((root / 'song.txt.flac').read_bytes(), audio)
                    self.assertEqual((root / 'video.mkv').read_bytes(), video)
                    before = self.snapshot(root)
                    self.assertEqual(main.main(), main.SUCCESS)
                self.assertEqual(self.snapshot(root), before)

    def test_manual_video_jobs_keep_existing_behavior(self) -> None:
        for drone in ('', 'manual', 'g' * 32):
            with self.subTest(drone=drone), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                video = b'\x1aE\xdf\xa3' + bytes(32)
                (root / 'video.mkv').write_bytes(video)
                with mock.patch.dict(os.environ, {'NZBPP_CATEGORY': 'music', 'NZBPP_FINALDIR': str(root),
                                                 'NZBPR_DRONE': drone}, clear=True):
                    self.assertEqual(main.main(), main.SUCCESS)
                self.assertEqual(self.snapshot(root), {'video.mkv': video})

    def test_catalog_audio_guard_uses_existing_audio_classification(self) -> None:
        for name, data in (('audio.mka', b'\x1aE\xdf\xa3' + bytes(32)),
                           ('audio.m4a', b'\x00\x00\x00\x18ftypisom' + bytes(32))):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                (root / name).write_bytes(data)
                with mock.patch.dict(os.environ, {'NZBPP_CATEGORY': 'music', 'NZBPP_FINALDIR': str(root),
                                                 'NZBPR_DRONE': 'a' * 32}, clear=True):
                    self.assertEqual(main.main(), main.SUCCESS)
                self.assertEqual((root / name).read_bytes(), data)

    def scene_playlist_tail_fixture(self, root: Path) -> tuple[list[Path], Path]:
        tracks = []
        for number in (1, 2):
            path = root / f"{number:02d}-artist-song_{number}_(remaster)-1234abc{number}.flac"
            path.write_bytes(self.tagged_flac({
                "ALBUM": "Fixture", "ALBUMARTIST": "Artist", "ARTIST": "Artist",
                "TITLE": f"Song {number}", "TRACKNUMBER": str(number), "TRACKTOTAL": "2", "DISCNUMBER": "1/1"}))
            tracks.append(path)
        playlist = root / "release.m3u"
        playlist.write_text("\n".join(p.name for p in tracks) + "\ner)-1234abc2.flac\n")
        return tracks, playlist

    def test_redundant_scene_playlist_tail_requires_complete_tagged_disc(self) -> None:
        for strict, archive in itertools.product((False, True), repeat=2):
            with self.subTest(strict=strict, archive=archive), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                tracks, playlist = self.scene_playlist_tail_fixture(root)
                before = {p.name: p.read_bytes() for p in tracks}
                if archive:
                    with zipfile.ZipFile(root / "release.zip", "w") as output:
                        for path in root.iterdir():
                            if path.suffix != '.zip':
                                output.write(path, 'Release/' + path.name)
                    for path in [*tracks, playlist]:
                        path.unlink()
                main.process_release(root, require_completeness=strict)
                self.assertEqual({p.name: p.read_bytes() for p in root.glob('*.flac')}, before)
                playlist = root / 'release.m3u'
                if strict:
                    self.assertEqual(playlist.read_text().splitlines(), list(before))
                    stable = {p.name: p.read_bytes() for p in root.iterdir()}
                    main.process_release(root, require_completeness=True)
                    self.assertEqual(stable, {p.name: p.read_bytes() for p in root.iterdir()})
                else:
                    self.assertFalse(playlist.exists())

    def test_redundant_scene_playlist_tail_preserves_encoding_and_comments(self) -> None:
        for encoding in ('utf-8-sig', 'utf-16-le', 'utf-16-be', 'cp1252'):
            with self.subTest(encoding=encoding), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                tracks, playlist = self.scene_playlist_tail_fixture(root)
                bom = {'utf-16-le': b'\xff\xfe', 'utf-16-be': b'\xfe\xff'}.get(encoding, b'')
                text = '#EXTM3U\r\n# Café\r\n' + '\r\n'.join(p.name for p in tracks) + '\r\ner)-1234abc2.flac\r\n\r\n'
                playlist.write_bytes(bom + text.encode(encoding))
                main.process_release(root, require_completeness=True)
                self.assertEqual(playlist.read_bytes(), bom + text.replace('\r\ner)-1234abc2.flac\r\n', '\r\n').encode(encoding))

    def test_scene_playlist_tail_does_not_hide_missing_or_foreign_tracks(self) -> None:
        variants = ('no_total', 'missing_track', 'other_album', 'other_artist', 'other_disc', 'wrong_position',
                    'wrong_total', 'extra_audio', 'resolving_tail', 'different_hash', 'numbered_tail',
                    'not_suffix', 'extensionless', 'reordered', 'cue_protected')
        for variant in variants:
            with self.subTest(variant=variant), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                tracks, playlist = self.scene_playlist_tail_fixture(root)
                if variant in {'no_total', 'other_album', 'other_artist', 'other_disc', 'wrong_position', 'wrong_total'}:
                    tags = main.flac_album_metadata(tracks[-1])[0]
                    if variant == 'no_total':
                        tags.pop('TRACKTOTAL')
                    else:
                        key, value = {'other_album': ('ALBUM', 'Other'), 'other_artist': ('ALBUMARTIST', 'Other'),
                                      'other_disc': ('DISCNUMBER', '2/2'), 'wrong_position': ('TRACKNUMBER', '1'),
                                      'wrong_total': ('TRACKTOTAL', '3')}[variant]
                        tags[key] = value
                    tracks[-1].write_bytes(self.tagged_flac(tags))
                elif variant == 'missing_track':
                    tracks[0].unlink()
                elif variant in {'extra_audio', 'resolving_tail'}:
                    (root / ('extra.flac' if variant == 'extra_audio' else 'er)-1234abc2.flac')).write_bytes(b'fLaC' + bytes(32))
                elif variant in {'different_hash', 'numbered_tail', 'not_suffix'}:
                    replacement = {'different_hash': 'er)-8765abcd.flac', 'numbered_tail': '3-er)-1234abc2.flac',
                                   'not_suffix': 'other-1234abc2.flac'}[variant]
                    playlist.write_text(playlist.read_text().replace('\ner)-1234abc2.flac', '\n' + replacement))
                elif variant == 'extensionless':
                    playlist = playlist.rename(root / 'list')
                elif variant == 'reordered':
                    rows = playlist.read_text().splitlines()
                    playlist.write_text('\n'.join([rows[1], rows[0], rows[2]]) + '\n')
                else:
                    (root / 'release.cue').write_text('FILE "release.m3u" WAVE\n  TRACK 01 AUDIO\n    INDEX 01 00:00:00\n')
                before = {p.name: p.read_bytes() for p in root.iterdir()}
                if variant in {'resolving_tail', 'cue_protected'}:
                    main.process_release(root, require_completeness=True)
                else:
                    with self.assertRaises(ValueError):
                        main.process_release(root, require_completeness=True)
                self.assertEqual(before, {p.name: p.read_bytes() for p in root.iterdir()})

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
                process.assert_called_once_with(root, verify_audio=True, require_completeness=False, require_audio=False)
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

    def test_flac_fingerprint_sidecars_preserve_media_and_cue_targets(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "track.flac").write_bytes(b"fLaC\x00audio")
            (root / "checksums.FFP").write_text("track.flac: 0123456789abcdef0123456789abcdef\n")
            (root / "renamed.ffp").write_bytes(b"fLaC\x00hidden audio")
            (root / "unknown.ffp").write_bytes(b"\x00binary")
            (root / "protected.ffp").write_text("cue target\n")
            (root / "album.cue").write_text('FILE "protected.ffp" WAVE\n  TRACK 01 AUDIO\n')
            self.assertEqual(self.run_main(root), main.SUCCESS)
            self.assertFalse((root / "checksums.FFP").exists())
            self.assertEqual((root / "renamed.ffp.flac").read_bytes(), b"fLaC\x00hidden audio")
            self.assertEqual((root / "unknown.ffp").read_bytes(), b"\x00binary")
            self.assertEqual((root / "protected.ffp").read_text(), "cue target\n")

    def test_windows_folder_sidecars_are_removed_without_flattening_conflicts(self) -> None:
        payload = (b"[.ShellClassInfo]\r\nFolderType=MusicAlbum\r\n"
                   b"MusicBuyUrl=providerName=AMG & Microsoft&album=Example\r\n\x00")
        for encoding in ("utf-8", "utf-16", "utf-16-be"):
            with self.subTest(encoding=encoding), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                raw = payload.decode().encode(encoding)
                if encoding == "utf-16-be":
                    raw = b"\xfe\xff" + raw
                with zipfile.ZipFile(root / "release.zip", "w") as archive:
                    archive.writestr("Release/desktop.ini", raw)
                    archive.writestr("Release/FLAC/Desktop.INI", raw)
                    archive.writestr("Release/FLAC/01.flac", b"fLaC\x00audio")
                self.assertEqual(self.run_main(root), main.SUCCESS)
                self.assertEqual(self.snapshot(root), {"01.flac": b"fLaC\x00audio"})

    def test_windows_folder_sidecar_recognition_is_conservative(self) -> None:
        valid = b"[.ShellClassInfo]\nFolderType=MusicArtist\nMusicBuyUrl=example\n"
        cases = (("desktop.ini", valid, True),
                 ("other.ini", valid, False),
                 ("desktop.ini", b"fLaC\x00audio", False),
                 ("desktop.ini", valid + b"\x00binary", False),
                 ("desktop.ini", valid + b"\x00\x00", False),
                 ("desktop.ini", valid + b"[Other]\nKey=value\n", False),
                 ("desktop.ini", valid + b"Unknown=value\n", False),
                 ("desktop.ini", valid + b"FolderType=MusicAlbum\n", False),
                 ("desktop.ini", valid.replace(b"MusicArtist", b"Unknown"), False),
                 ("desktop.ini", b"[.ShellClassInfo]\n", False),
                 ("desktop.ini", b"\xff\xfe[", False),
                 ("desktop.ini", valid + b" " * (65536 - len(valid)), True),
                 ("desktop.ini", valid + b" " * (65537 - len(valid)), False))
        for name, raw, expected in cases:
            with self.subTest(raw=raw[:80]), tempfile.TemporaryDirectory() as temp:
                path = Path(temp) / name
                path.write_bytes(raw)
                self.assertEqual(main.disposable(path), expected)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "desktop.ini").write_bytes(valid)
            (root / "album.cue").write_text('FILE "desktop.ini" WAVE\n  TRACK 01 AUDIO\n')
            self.assertEqual(self.run_main(root), main.SUCCESS)
            self.assertEqual((root / "desktop.ini").read_bytes(), valid)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "desktop.ini").write_bytes(valid)
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

    def test_extensionless_album_info_cleanup_before_import(self) -> None:
        info = "Album: Example Album\nArtist: Example Artist\nTracklist:\n01 Example Song\n"
        for name in ("album_info", "was95_album_info", "WAS95_ALBUM_INFO"):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                audio = b"fLaC" + bytes(32)
                (root / "song.flac").write_bytes(audio)
                (root / name).write_text(info)
                self.assertEqual(self.run_main(root), main.SUCCESS)
                self.assertEqual(self.snapshot(root), {"song.flac": audio})
                self.assertEqual(self.run_main(root), main.SUCCESS)

    def test_album_info_unknown_binary_and_oversized_content_preserved(self) -> None:
        info = b"Album: Example Album\nArtist: Example Artist\nTracklist:\n01 Example Song\n"
        cases = (("notes", info), ("was95_album_info", b"unrelated text"),
                 ("was95_album_info", b"Album:\nArtist:\nTracklist:\n01 Example Song\n"),
                 ("was95_album_info", b"Album:    \r\nArtist: \r\nTracklist:\r\n01 Example Song\r\n"),
                 ("was95_album_info", info + b"\x00"),
                 ("was95_album_info", info + b"x" * 65536),
                 ("was95_album_info", b"fLaC" + bytes(32)),
                 ("was95_album_info", b""))
        for name, payload in cases:
            with self.subTest(name=name, payload=payload[:80]), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                (root / "song.flac").write_bytes(b"fLaC" + bytes(32))
                (root / name).write_bytes(payload)
                self.assertFalse(main.disposable(root / name))
                self.assertEqual(self.run_main(root), main.SUCCESS)
                target = root / (name + ".flac" if payload.startswith(b"fLaC") else name)
                self.assertEqual(target.read_bytes(), payload)

    def test_album_info_only_and_cue_reference_remain_protected(self) -> None:
        info = "Album: Example Album\nArtist: Example Artist\nTracklist:\n01 Example Song\n"
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "was95_album_info").write_text(info)
            before = self.snapshot(root)
            self.assertEqual(self.run_main(root), main.FAILURE)
            self.assertEqual(self.snapshot(root), before)
            (root / "reference.cue").write_text('FILE "was95_album_info" WAVE\n')
            self.assertEqual(self.run_main(root), main.SUCCESS)
            self.assertEqual((root / "was95_album_info").read_text(), info)

    def test_missing_directory_and_cleanup_to_empty_fail(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.assertEqual(self.run_main(root / "missing"), main.FAILURE)
            with zipfile.ZipFile(root / "release.zip", "w") as output:
                output.writestr("notes.txt", b"only notes")
            before = self.snapshot(root)
            self.assertEqual(self.run_main(root), main.FAILURE)
            self.assertEqual(self.snapshot(root), before)

    def test_empty_completed_music_directory_is_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            category = Path(temp) / "usenet/completed/music"
            category.mkdir(parents=True)
            inode = category.stat().st_ino
            self.assertEqual(self.run_main(category), main.FAILURE)
            self.assertTrue(category.is_dir())
            self.assertEqual(category.stat().st_ino, inode)
            self.assertEqual(list(category.iterdir()), [])
            main.flatten_existing_tree(category)
            self.assertTrue(category.is_dir())
            self.assertEqual(category.stat().st_ino, inode)

    def test_empty_directory_cleanup_stays_inside_release(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            category = Path(temp) / "usenet/completed/music"
            root = category / "Album"
            (root / "Wrapper/Audio").mkdir(parents=True)
            (root / "Wrapper/Empty/Nested").mkdir(parents=True)
            sibling = category / "Other empty release"
            sibling.mkdir()
            audio = b"fLaC" + bytes(32)
            (root / "Wrapper/Audio/one.flac").write_bytes(audio)
            category_inode = category.stat().st_ino
            release_inode = root.stat().st_ino
            self.assertEqual(self.run_main(root), main.SUCCESS)
            self.assertEqual(self.snapshot(root), {"one.flac": audio})
            self.assertFalse((root / "Wrapper").exists())
            self.assertTrue(sibling.is_dir())
            self.assertEqual(category.stat().st_ino, category_inode)
            self.assertEqual(root.stat().st_ino, release_inode)

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

    def test_cleanup_only_retains_last_file(self) -> None:
        for extract in (False, True):
            with self.subTest(extract=extract), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                marker = root / "marker"
                marker.write_bytes(b"~^newz[NZB]~\n")
                before = self.snapshot(root)
                with self.assertRaisesRegex(ValueError, "no files would remain"):
                    main.process_release(root, extract=extract)
                self.assertEqual(self.snapshot(root), before)
                with self.assertRaisesRegex(ValueError, "no files would remain"):
                    main.remove_unwanted_files(root)
                self.assertEqual(self.snapshot(root), before)

    def test_retained_playlists_follow_flattening_and_extension_repairs(self) -> None:
        for mode in ("flatten", "extensions", "protected"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                (root / "Release/Audio").mkdir(parents=True)
                (root / "Release/Audio/one").write_bytes(b"fLaC" + bytes(32))
                (root / "Release/list.m3u").write_text("Audio/one.flac\r\n")
                if mode == "protected":
                    (root / "Release/album.cue").write_text('FILE "list.m3u" BINARY\n')
                    main.process_release(root)
                    playlist = root / "list.m3u"
                elif mode == "extensions":
                    main.add_missing_extensions(root)
                    playlist = root / "Release/list.m3u"
                else:
                    # Repair first so flatten-only input has a resolvable reference.
                    main.add_missing_extensions(root)
                    main.flatten_existing_tree(root)
                    playlist = root / "list.m3u"
                entries = main.playlist_entries(playlist)
                self.assertIsNotNone(entries)
                self.assertEqual(len(entries), 1)
                self.assertEqual((playlist.parent / entries[0]).read_bytes(), b"fLaC" + bytes(32))
                self.assertTrue(playlist.read_bytes().endswith(b"\r\n"))
                before = self.snapshot(root)
                if mode == "protected":
                    main.process_release(root)
                elif mode == "extensions":
                    main.add_missing_extensions(root)
                else:
                    main.flatten_existing_tree(root)
                self.assertEqual(self.snapshot(root), before)

    def test_unresolved_retained_playlist_preserves_paths(self) -> None:
        for text in ("../Audio/one.flac\n", "../Audio/one.flac\nunknown notes\n"):
            with self.subTest(text=text), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                (root / "Release/Audio").mkdir(parents=True)
                (root / "Release/Lists").mkdir()
                audio = root / "Release/Audio/one.flac"
                audio.write_bytes(b"fLaC" + bytes(32))
                (root / "Release/Lists/list.m3u").write_text(text)
                before = self.snapshot(root)
                main.process_release(root)
                self.assertEqual(self.snapshot(root), before)

    def test_partial_extensionless_playlist_keeps_paths_in_cleanup_disabled_helpers(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "Release/Audio").mkdir(parents=True)
            (root / "Release/Audio/one.flac").write_bytes(b"fLaC" + bytes(32))
            (root / "Release/list").write_text("Audio/one.flac\nAudio/missing.flac\n")
            before = self.snapshot(root)
            main.flatten_existing_tree(root)
            self.assertEqual(self.snapshot(root), before)

    def completed_cleanup_workspace(self, root: Path) -> Path:
        (root / "Release").mkdir()
        (root / "Release/one.flac").write_bytes(b"fLaC" + bytes(32))
        (root / "notes.txt").write_text("notes")
        rmtree = main.shutil.rmtree
        def partial_cleanup(path: Path, *args, **kwargs):
            if Path(path).name == "originals":
                (Path(path) / "0").unlink()
                raise OSError("injected partial backup cleanup failure")
            return rmtree(path, *args, **kwargs)
        with mock.patch.object(main.shutil, "rmtree", partial_cleanup), self.assertRaises(OSError):
            main.process_release(root)
        workspace = next(root.glob(".unpack-music-*"))
        self.assertEqual(json.loads((workspace / "recovery.json").read_text())["state"], "published")
        return workspace

    def test_completed_publication_cleanup_resumes_without_restoring_deleted_sidecars(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = self.completed_cleanup_workspace(root)
            self.assertEqual(main.cli(["--recover", str(workspace)]), 0)
            self.assertFalse(workspace.exists())
            self.assertEqual(self.snapshot(root), {"one.flac": b"fLaC" + bytes(32)})
            self.assertEqual(self.run_main(root), main.SUCCESS)

    def test_completed_cleanup_refuses_changed_missing_and_symlink_outputs(self) -> None:
        for kind in ("changed", "missing", "symlink"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                workspace = self.completed_cleanup_workspace(root)
                output = root / "one.flac"
                if kind == "changed":
                    output.write_bytes(b"external change")
                elif kind == "missing":
                    output.unlink()
                else:
                    output.unlink()
                    output.symlink_to(root / "notes.txt")
                with self.assertRaises((OSError, ValueError)):
                    main.recover(workspace)
                self.assertTrue((workspace / "recovery.json").exists())
                self.assertTrue((workspace / "originals").exists())

    def test_completion_record_failure_keeps_originals_recoverable(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "Release").mkdir()
            (root / "Release/one.flac").write_bytes(b"fLaC" + bytes(32))
            before = self.snapshot(root)
            replace = Path.replace
            def failed_record(source: Path, target: Path) -> Path:
                if source.name == "recovery.json.new":
                    raise OSError("injected completion-record failure")
                return replace(source, target)
            with mock.patch.object(Path, "replace", failed_record), self.assertRaises(OSError):
                main.process_release(root)
            workspace = next(root.glob(".unpack-music-*"))
            main.recover(workspace)
            self.assertEqual(self.snapshot(root), before)

    def test_empty_workspace_after_final_cleanup_failure_is_recoverable(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "Release").mkdir()
            (root / "Release/one.flac").write_bytes(b"fLaC" + bytes(32))
            rmdir = Path.rmdir
            def failed_rmdir(path: Path) -> None:
                if path.name.startswith(".unpack-music-"):
                    raise OSError("injected final directory cleanup failure")
                return rmdir(path)
            with mock.patch.object(Path, "rmdir", failed_rmdir), self.assertRaises(OSError):
                main.process_release(root)
            workspace = next(root.glob(".unpack-music-*"))
            self.assertEqual(list(workspace.iterdir()), [])
            main.recover(workspace)
            self.assertEqual(self.snapshot(root), {"one.flac": b"fLaC" + bytes(32)})

    def test_playlist_comments_survive_helper_and_strict_rewriting(self) -> None:
        for strict in (False, True):
            with self.subTest(strict=strict), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                (root / "Release").mkdir()
                (root / "Release/#one.mp3").write_bytes(b"ID3audio")
                text = b"#one.mp3\r\n./#one.mp3\r\n"
                (root / "Release/list.m3u").write_bytes(text)
                if strict:
                    main.process_release(root, require_completeness=True)
                else:
                    main.flatten_existing_tree(root)
                self.assertEqual((root / "list.m3u").read_bytes(), text)
                self.assertEqual(main.playlist_entries(root / "list.m3u"), [main.PurePosixPath("#one.mp3")])
                main.process_release(root, require_completeness=True)
                self.assertEqual((root / "list.m3u").read_bytes(), text)

    def test_restored_originals_cleanup_is_resumable_after_backup_directory_removal(self) -> None:
        for interrupt in (False, True):
            with self.subTest(interrupt=interrupt), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                workspace, original = self.interrupted_workspace(root)
                rmtree = main.shutil.rmtree
                def failed_cleanup(path: Path, *args, **kwargs):
                    result = rmtree(path, *args, **kwargs)
                    if Path(path).name == "originals":
                        if interrupt:
                            raise KeyboardInterrupt()
                        raise OSError("injected failure after original-backup directory removal")
                    return result
                with mock.patch.object(main.shutil, "rmtree", failed_cleanup), self.assertRaises(
                        KeyboardInterrupt if interrupt else OSError):
                    main.recover(workspace)
                journal = json.loads((workspace / "recovery.json").read_text())
                self.assertEqual(journal["state"], "restored")
                for name, payload in original.items():
                    self.assertEqual((root / name).read_bytes(), payload)
                self.assertFalse((workspace / "originals").exists())
                main.recover(workspace)
                self.assertEqual(self.snapshot(root), original)

    def test_preview_and_recovery_cli_need_explicit_paths(self) -> None:
        with self.assertRaises(SystemExit) as result:
            main.cli(["--recover"])
        self.assertEqual(result.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
