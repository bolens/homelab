# Komga next-UI notification patch

Komga is copyright its contributors and licensed under GNU GPL version 3.
Komga version: 1.30.0.
Upstream source: https://github.com/gotson/komga/tree/ff800c21253793d4d3fd855651b82d4924915950

The Dockerfile downloads and verifies that complete source archive, applies
patch-source.py and import-title.ts, and builds with the upstream npm lockfile.
package-ui.py replaces UI resources while verifying all other JAR entries.
The patch source and build instructions are maintained in this directory.
