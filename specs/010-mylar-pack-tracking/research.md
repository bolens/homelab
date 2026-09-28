# Research decisions

- Native PostProcessor repeats its regular issue query in the annual fallback. Select non-deleted annual fields, including ReleaseComicName, and preserve parent identity.
- Native constructor sets APILOCK before execution and early exits do not clear it. Serialize the entire processing call, release ownership in finally, and join API runs so queue workers cannot outrun processing.
- Native `helpers.issue_find_ids` and `search.search_init` reserve and mark inferred integer ranges Snatched without edition proof. Track uncertain membership at pack level rather than making these status changes. Reversal must not demote already downloaded issues.
- `importer.manualAnnual(..., manualupd=True)` returns native candidate rows without writing. The mutating path overwrites Deleted/Status, so additions must exclude existing rows. Exact native catalog calls are preferred to invented local issue IDs.
- Existing recovery catalog excludes annuals and edition/type evidence. Extend exact identity paths without loosening guided aliases.
- Existing worker owns conversion, content equality and preserved sources. Reuse those checks and shared cache staging; do not add another converter.
- Pack status currently relies on number ranges and a single anchor. Retained per-member manifests are required for annuals/extras and removed DDL rows.

Evidence: inspected pinned runtime source copies and tracked integration on base `10a4a007f5c82a5c1e78044bf91b9027c49cb094`; bounded read-only catalog research confirmed native API/add/status seams.
