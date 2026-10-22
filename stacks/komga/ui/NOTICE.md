# Komga next-UI notification patch

Komga is copyright its contributors and licensed under GNU GPL version 3.
Komga version: 1.29.1.
Upstream source: https://github.com/gotson/komga/tree/a9b59dbee73424d7f2e186b24b0905913f816709

The Dockerfile downloads and verifies that complete source archive, applies
patch-source.py and import-title.ts, and builds with the upstream npm lockfile.
package-ui.py replaces UI resources while verifying all other JAR entries.
The patch source and build instructions are maintained in this directory.
