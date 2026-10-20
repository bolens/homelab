# ComicTagger runtime components

The isolated runtime contains unmodified ComicTagger 1.6.0b11.dev0 and the exact
packages in requirements.txt. Installed distribution metadata and license
files remain under `/opt/comictagger/lib/python3.13/site-packages/*.dist-info/`.
The legacy Mylar environment is separate.

ComicTagger is Apache-2.0. comicfn2dict is GPL-3.0-only; chardet is LGPL-2.1-or-later;
isocodes includes LGPL-2.1 data. Exact upstream source archives for these components
are retained in `/opt/comictagger/sources/`, with their versions, download locations
and SHA-256 checksums in manifest.json. No modifications to those packages are made.

Other runtime components use MIT, BSD, Apache, PSF, MPL-2.0 or related permissive
licenses as recorded in their installed metadata and notices. PyICU's extension is
built against the ICU 70 libraries supplied by the pinned Ubuntu base, whose package
copyright notices remain in `/usr/share/doc/`. Build-only setuptools, wheel, packaging
and compilers are not copied into this runtime, except packaging which is also a
required application dependency.

Modern's normal-GIL CPython 3.13.16 is compiled from the unmodified official
source in the same pinned Jammy image, installed under `/opt/tagger-python`,
and retained separately from Mylar/Legacy's Python 3.10. Its exact source archive
is in `/opt/comictagger/sources`, with its verified SHA-256 and official URL in
manifest.json. Before pinning, the release archive's Sigstore bundle was verified
against `thomas@python.org`, issuer `https://accounts.google.com`. CPython's
LICENSE and incorporated-software notices remain at
`/opt/tagger-python/LICENSE` and `/opt/tagger-python/LICENSES.rst`; see https://docs.python.org/3.13/license.html.

Pillow 13.0.0 uses the exact CPython 3.13 linux/amd64 manylinux wheel from the
hash lock. Its distribution license files include the notices for its bundled
image codecs. PyICU is rebuilt against the pinned base's ICU 70.1. CPython's
system libraries and their package copyright notices remain in the final image.
No foreign distribution's interpreter, libc, or dynamic loader is copied.
