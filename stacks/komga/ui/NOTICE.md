# Komga next-UI notification patch

Komga is copyright its contributors and licensed under GNU GPL version 3.
Upstream source: https://github.com/gotson/komga/tree/4f4099c56281b629f65896bc9e2c68447133d9ef

The Dockerfile downloads and verifies that complete source archive, applies
patch-source.py and import-title.ts, and builds with the upstream npm lockfile.
package-ui.py replaces UI resources while verifying all other JAR entries.
The patch source and build instructions are maintained in this directory.
