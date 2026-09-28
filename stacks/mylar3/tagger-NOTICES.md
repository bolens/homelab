# ComicTagger runtime components

The isolated runtime contains unmodified ComicTagger 1.6.0b11.dev0 and the exact
packages in requirements.txt. Installed distribution metadata and license
files remain under `/opt/comictagger/lib/python3.10/site-packages/*.dist-info/`.
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
