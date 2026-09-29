# DDL discovery runtime components

The unmodified packages in `requirements-ddl.txt` live in `/opt/ddl-transport`.
Distribution metadata and license files remain in its site-packages directories.
This environment is separate from Mylar and ComicTagger.

- curl_cffi 0.16.3: MIT, https://github.com/lexiforest/curl_cffi/tree/v0.16.3
- cffi 2.1.1: MIT-0, https://github.com/python-cffi/cffi
- pycparser 3.0: BSD-3-Clause, https://github.com/eliben/pycparser
- certifi 2026.7.22: MPL-2.0, https://github.com/certifi/python-certifi

Certifi's corresponding source archive is retained in `/opt/ddl-transport/sources`
with its URL, version and verified SHA-256 manifest. The installed CA bundle is
unchanged. The pinned curl wheel supplies its native implementation. This image is
built and tested for linux/amd64, not every platform that upstream wheels support.

Dependabot's `/stacks/mylar3` pip inventory includes requirements files. Review
wheel hashes, corresponding source pins and native notices together when updating.
