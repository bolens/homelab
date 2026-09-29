# Settings and monitoring

Existing Activity policy submission accepts `library_missing_tags` and `library_nested_metadata` as booleans. Both default false and preserve unrelated settings. Existing authentication and CSRF validation apply.

Post-processing status gains `library_metadata` with current scan state and up to 100 recent repair/review observations. Strings are bounded and rendered as text. Existing converted-tag status includes missing-tag admissions from library discovery. No public API or port is added.
