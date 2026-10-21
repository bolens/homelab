# Research decisions

- Keep the existing selected tuner profile and use its native XMLTV profile URL. Plex exposes lineup/preferences APIs, so preserve the DVR identity and recording rules while changing the lineup URI.
- Dispatcharr schedules must describe the actual FAST feed. Prefer current Roku/Pluto exact-station feeds over unrelated full OTA schedules. Verify current program times before assignment.
- Plugin retries within one run are not independent failed days. Disable immediate plugin deletion and maintain a separate dated quarantine gate. Do not modify upstream plugin source.
- Use native online PostgreSQL dumps and native Plex SQLite snapshots. Backups become usable only after isolated restore checks; reuse existing encrypted Restic for the retained recovery copy when its source coverage is verified.
- Use existing monitoring rather than creating external recipients. Emit fixed health/count/age signals without stream URLs, credentials, program titles or usernames.
- Native Plex commercial detection can mark breaks without cutting footage. Apply settings to future recordings and preserve existing schedules.

## City and network mosaics

Research covered Denver, Milwaukee, Atlanta, Seattle, Minneapolis and the
Sanibel/Fort Myers market. Official station pages supplied the Tegna NBC feeds
for KUSA, WXIA, KING and KARE, and KOMO's ABC playback URL. WSB's official
breaking-news page identifies its 24/7 news feed. Its Amagi stream requires the
existing extensionless-segment HLS options. Older KOMO Stirr URLs returned 404.

CBS Colorado, CBS Minnesota and the existing KIRO/FOX local news feeds remain
separate station channels. CBS identifies WUPA as Atlanta's current affiliate.
Do not classify WANF's independent news stream as CBS. No reusable working CBS
Atlanta or Milwaukee stream, or FOX Denver stream, passed this research.

Sanibel-area WBBH NBC and WZVN ABC pages exposed playable dated newscast replays,
but their live feeds were off-air or failed decoding. WINK's embedded player did
not expose a reusable anonymous stream. WFTX's catalog HLS failed decoding.
Do not persist dated replay URLs or relabel national news as local coverage.
Leave this market unavailable until stable feeds can be verified.

Keep source channels independently selectable. City mosaics use NBC, ABC, CBS,
FOX in that order, skipping gaps, with the first available network's audio.
Network mosaics follow Denver, Milwaukee, Atlanta, Seattle and Minneapolis,
skipping gaps. Preserve the original four-city layout and Denver audio.
Generated mosaic listings describe the tiles and audio. Source feeds without an
exact FAST schedule retain explicit live-feed fallback listings.

Denver7's official main feed is the Uplynk channel beginning `4608c2dc`, while
its older `64ca339f` URL is a secondary breaking-news feed. Both masters failed
the FFmpeg demuxer's playlist parsing. The official main feed passed a separate
Streamlink-to-FFmpeg picture/audio decode inside Dispatcharr. Use that feed with
the existing Streamlink profile. The standalone Atlanta FOX feed also passed
through Streamlink and uses that profile.

Fort Myers FOX 4's catalog Uplynk stream also failed FFmpeg playlist parsing but
passed Streamlink-to-FFmpeg decoding, with FOX 4 branding visible. It was added
as a standalone Sanibel/Fort Myers news channel and the fifth FOX network tile.
NBC WBBH and ABC WZVN live feeds still failed through Streamlink. A city mosaic
requires two sources, so Sanibel remains a standalone channel until another
regional feed is available.

The official PBS main players for KRMA, WMVS, KTCA, KCTS/KBTC, WGTV and WGCU
exposed DRM streams without a usable clear alternative. Some initial plain HLS
links play an update notice. These are not station programming. Seattle WORLD
and Create and WGTV-DT3 had decodable clear subchannels, but they do not replace
the main local PBS feed and were not relabeled or inserted into city layouts.
PBS main remains unavailable in this matrix. Official local PBS apps/browser
players and an in-area antenna tuner are the supported alternatives.
