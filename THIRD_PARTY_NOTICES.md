# Third-party notices

## License scope

The root MIT license covers original material authored by bolens. It does not
replace third-party licenses, copyright notices, trademarks, or service terms.
Imported and modified third-party material keeps its applicable upstream terms.

## Stacks and assets

The MIT grant covers original Compose definitions, scripts, and documentation.
Images and software installed by stack builds retain their own terms. Upstream
logos under `stacks/*/logo.*` are not relicensed under MIT. Stack metadata records
project links, but individual logo permissions and source revisions have not
been established for every asset.

Redistribution of built images requires an audit of their exact digests,
installed packages, license files, and corresponding-source obligations.
Referencing an image in Compose does not itself copy that image into this source
repository. Existing image artifacts were not audited by the source notice fix.

## GitHub Spec Kit

Imported `.specify/scripts/`, `.specify/templates/`, and
`.agents/skills/speckit-*` integration files retain GitHub's MIT copyright and
permission notice in [.specify/LICENSE](.specify/LICENSE). Include it when
copying these files. Project-authored memory documents have separate ownership.

## Dependency inputs

Dependency declarations are recorded in:

- `package.json`
- `stacks/acquire/requirements.txt`
- `stacks/blackbird/requirements.txt`
- `stacks/clark-browser/build/requirements.txt`
- `stacks/docker-forensics-toolkit/requirements.txt`
- `stacks/ghunt/requirements.txt`
- `stacks/metagoofil/requirements.txt`
- `stacks/privotron/requirements.txt`
- `stacks/torbot/requirements.txt`

## Redistribution

Keep applicable full license and copyright notices with copied source and
bundled dependencies, including minified JavaScript and compiled executables.
Use the exact dependency versions selected by the lockfile or build. Preserve
Apache NOTICE material and satisfy copyleft source requirements where they
apply. Development-only tools and separately installed programs keep their own
terms but are not automatically part of a distributed application.

This source inventory is not proof that every historical release, external
asset, fetched dataset, or built container has satisfied its license obligations.
