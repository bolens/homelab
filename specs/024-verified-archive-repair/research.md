# Archive repair design evidence

## Preserve ordinary verification

Decision: classify only the direct failed source inventory and preserve terminal refusal. The strict initial repair supports fewer variants than the ordinary reader; replacing that reader would reject valid comics. Catalog, lock, owner and correction failures are not archive defects.

## Initial repair family

Decision: one verified empty directory missing a slash with consistent Unix type and DOS directory flag. Full CRC and member/page/root-metadata comparison plus inverse reconstruction prove unchanged compressed content, timestamps, extras and comments. Missing content, guessed reconstruction and disabled CRC remain excluded.

## Dedicated ownership

Decision: separate repair kind. Existing `publication_derivative.plan_value` covers nested metadata and rejects equal payloads; ordinary original admission also refuses this malformed source. Equal comic content still changes archive bytes and requires owned custody, current correction policy and reader acceptance.

## Exact portable sources

Decision: generate exact pure module copies into the worker. Adding generated headers would invalidate embedded checked-module hashes. A separate provenance/source map can record ownership. No new executable, mount, network privilege or dependency is needed.

## Preliminary evidence

Private fixtures, actual-runtime tests and a verified private derivative of one original prove the bounded repair is possible. They do not install production modules, provide owning preparation/adoption or complete live acceptance. RAR/7z compatibility and PDF conversion remain separate paths.

## NFS source-suffix namespace

The isolated AM probe and read-only checks of its selected native container
show the same NFS subtree encoded in `SOURCE` with `FSROOT=/`. Raw mountinfo
confirms this is not just findmnt display formatting. Device and mount options
match the original host facts. [util-linux's NFS handling](https://github.com/util-linux/util-linux/blob/master/libmount/src/tab.c#L1844-L1849)
also accounts for the root at the end of the NFS source.

Accept this additional representation only with both roots `/` and an exact
original host export plus authenticated relative host bind subtree. Preserve
target, device, access, inode/full9, retention, same-mount and namespace checks.
Apply it to both probe validators and native adoption together. The changed
adoption module requires matching native image/SDK and installation evidence.
