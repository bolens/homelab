# Validation guide

1. Use source copied from the pinned Mylar image and disposable SQLite fixtures.
   Run the image's compatibility gate and new workflow/health tests without live mounts.
2. Build the normalizer image to run archive, matching and recovery regressions.
3. Verify Activity and Import problems at desktop and narrow widths: links, filters,
   stale refresh, explicit selections, settings validation and matching theme controls.
4. Test competing claims, duplicate POSTs, missing CSRF, changed proposal versions,
   uncertain downloader/API responses and restart recovery. No real download is needed.
5. Run repository validators, review publication contents, and merge only passing CI.
6. Publish both images, verify source provenance, then deploy Mylar before the worker
   after verified private backups/isolated restores. Compare data and monitor health.
7. Remove operation backups and merged task branches only after successful verification.
