# Komga next-UI notification patch

Komga is copyright its contributors and licensed under GNU GPL version 3.
Upstream source: https://github.com/gotson/komga/tree/2ab7a5a61a8b8bb12a6edd576fed380b4b613c99

The Dockerfile downloads and verifies that complete source archive, applies
patch-source.py and import-title.ts, and builds with the upstream npm lockfile.
package-ui.py replaces UI resources while verifying all other JAR entries.
The patch source and build instructions are maintained in this directory.
