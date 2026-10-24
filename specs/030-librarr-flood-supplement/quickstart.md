# Operator verification

Read the Librarr and Flood stack READMEs. Verify remote mounts, consistent backups
and isolated restores first. Migrate Flood runtime before recreation. Select both
optional overrides with private environment values and retain original images.
Run adapter unit tests, contract tests and make validate. Verify native login
after Flood recreation, native Librarr connection testing, single/multi-file
path behavior, and existing catalog/state preservation. Configure private tracker
credentials directly in Prowlarr. Review bounded supplementation before applying
it, retain seeding payloads, and verify Bookshelf file records after copy import.

For native NZB downloads, see the owning Librarr README's NZBGet setup. Select
its docker-compose.nzbget.yml alongside all existing overrides, configure the
independent adapter key, and verify category/destination mapping before an actual
acquisition. Native SABnzbd connection success proves connectivity only. Verify
an accepted job in NZBGet and Librarr, then completion/source retention separately.
