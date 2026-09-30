# PDF conversion contract

`pdf_conversion`: object; `enabled` boolean default false; `long_edge_pixels` integer 512–6000 default 3200; `max_pages` integer 1–1000 default 1000. Invalid types/ranges fail configuration validation. Existing `max_expanded_bytes` also bounds PDF input and PNG payload size.

One PNG per PDF page, zero-padded numeric names, full page bounds, document order. Source PDF retained with checksum in `/state/pdf-derivatives`. No decryption, split spreads, guessed catalog identities, automatic partial-file adoption or source-PDF cleanup. Text/search, vector, interactive, attachment and original color information remain in the PDF, not the CBZ.

Existing shared writer, recovery copies, no-clobber publication, Mylar rescan/tagging and Komga notifications apply. No new API, credential, mount, ingress or service dependency.
