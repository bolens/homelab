# Storage decisions

- Decision: Bind only `/data/library` on remote storage. Local staging is on a
  different filesystem, so retain Immich's hash verification for finalization.
  A whole `/data` bind would add staging and generated directories beneath the
  requested user-folder root. Separate mounts on the same device are avoided.
- Decision: Use date folders and timestamp-prefixed original filenames globally,
  as requested in the user's follow-up. A storage label is human-readable;
  absent labels fall back to unique account IDs. No static account path is mounted.
- Decision: Optional Compose file with required path and `create_host_path: false`.
  The portable base retains its named-volume deployment and permissions.
- Sources: [Custom locations](https://docs.immich.app/guides/custom-locations/),
  [Storage templates](https://docs.immich.app/administration/storage-template/).
- Operational baseline: v3.3.5, zero assets/albums, one account, empty mounted
  destination. Private host settings and identifiers stay outside this record.
