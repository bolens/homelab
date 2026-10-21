# Optional Multiview 0.5.0 compatibility patch

`multiview-0.5.0-forward-pts.patch` changes the source clock reset in Multiview
0.5.0. The original decoder resets a backward discontinuity of two seconds or
more. A forward discontinuity of that size can instead leave frames queued in
the future, producing a blank tile while audio continues. The patch resets the
clock and video queue for either direction.

Use this only with the reviewed Multiview 0.5.0 source. Check the installed
plugin version first. The reviewed original `channel.py` SHA-256 is
`5b15701eb52b2a692b96b58955c841210a881f14bf9c80e9e51fed74f97773ac`. Require that exact hash before applying this workaround,
then restore-verify a backup of the complete Dispatcharr
`/data` volume. Copy the plugin source into an isolated directory and dry-run
this patch before applying it to the persistent plugin directory:

```sh
patch --dry-run -p1 -d /path/to/reviewed/multiview \
  < multiview-0.5.0-forward-pts.patch
```

A version or context mismatch requires fresh review. Preparation does not apply
this patch. After an authorized application, restart the affected mosaic workers
and verify every decoded tile plus the selected audio through the HDHR route.
Existing workers keep their imported source until restarted. Plugin upgrades
can replace this local fix, so check upstream behavior and remove or re-review
the workaround during an upgrade. Roll back with the verified prior plugin file
and restart affected workers if output regresses.
