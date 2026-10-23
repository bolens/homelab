# Tasks

- [x] T001 Inspect upstream auth/release and current runtime, capture private operation scope and baseline.
- [x] T002 Improve complete ErsatzTV stack contract and validate isolated preparation.
- [x] T003 Verify affected configuration/application backups before existing-service mutations.
- [x] T004 Deploy healthy ErsatzTV with verified read-only media access.
- [x] T005 Configure protected tunnel hostname and verify anonymous/origin denial.
- [x] T006 Connect the library, create bounded station programming and integrate Dispatcharr/Plex.
- [x] T007 Verify preservation, guide and playback; clean operation-created temporary copies after success.
- [x] T008 Regenerate affected documentation and run focused checks plus make validate.
- [x] T009 Expand stations from the fully indexed library, preserving existing output order and identities; verify backup restores, new schedules, logos, guide mappings and playback before cleanup.

## Evidence

- T001: reviewed upstream v26.11.3 source and matching OCI digest. No existing ErsatzTV container or volume. Private runtime baselines retained outside Git.
- T002: isolated preparation rejects missing directories, preserves existing environment and ingress on two runs, invokes no container lifecycle, and renders the original Compose contract.
- T003: private config restore hashes match. Dispatcharr dump restored into an isolated PostgreSQL database with matching counts. Native Plex snapshots pass integrity checks and byte-identical isolated copies. Complete tunnel and active Caddy configurations retained privately.
- T004: healthy pinned Legacy v26.11.3 with bundled Next 0.2.2 and FFmpeg 8.1.2-etv.4. One NVIDIA GPU reserved through the optional override; real NVENC encode and channel playback pass. Final application health checks are all green.
- T005: anonymous public requests require Access login; connector validates the application audience. Direct IPv4 and IPv6 origin requests return 403. Existing tunnel routes are preserved.
- T006: 13 stations have populated playouts, authored logos, imported streams, XMLTV bindings and enabled Plex mappings. Morning cartoons run 06:00–12:00, with family animation outside that block. Halloween and holiday movie stations are populated. Smart Collections expand as indexing proceeds; the original six-hour scan interval is restored.
- T007: all 13 streams decode picture and audio through Dispatcharr. Plex tunes the cartoon station with H.264/AAC tracks and its HLS output decodes successfully. Plex guide entries retain the public artwork URLs. All 2,222 original Dispatcharr channel IDs and UUIDs survive; the recording baseline remains zero. Existing Plex library definitions, DVR identity and zero subscription baseline match. An application-consistent ErsatzTV SQLite copy passes integrity and foreign-key checks, media counts do not decrease, and all 13 Next channels retain populated playouts and cached logos. All three services are healthy. Operation-created backup, restore, fixture and credential copies were removed after verification; private receipts remain. Integration writes are finished; separate operator-authorized channel ordering may change output numbers while retaining UUIDs.
- T008: final make validate passes under the repository validation dependencies. PostHog generated bundle skipped; existing Stoat optional-example warning. Catalog, topology and site regenerated through owning scripts. The optional NVIDIA override renders in an isolated example fixture; all 13 logos were checked at guide and full sizes on light and dark backgrounds.

- [x] T010 Refine ambiguous station names and wide logos; verify matching names/artwork throughout the guide.
- [x] T011 Place all library stations before multiviews in the Plex lineup, preserving identities and complete guide mappings.
- [ ] T012 Recover the two physically damaged movie files from verified preservation copies and fresh replacements; retain the warning until actual playback is verified.
- [x] T013 Set preferred English audio on every custom channel and verify visible language plus playback.
- [x] T014 Add studio, superhero, sports and related library stations with populated schedules, matching wide logos and preserved existing identities; integrate before multiviews while retaining expansion space.
- [x] T015 Audit all collection memberships against the actual native search index, repair omitted punctuation-sensitive titles and inherited episode fields, then recommend titles missing from the available catalog.
- [x] T016 Add requested franchise and Scooby-Doo television stations, audit the complete icon family, refine theme-specific artwork, and preserve natural lineup grouping plus future number space.


## Expansion and refinement evidence

- T009–T011: the library lineup has 50 themed stations at output 100–149, with 150–179 reserved and multiviews at 180–189. Existing channel IDs, UUIDs, stream links, memberships, guide identities and DVR identity are preserved. All 519 Plex channels are enabled and bound to their guides. Ambiguous names were clarified and their artwork updated. Complete mapping replacement semantics were verified and documented.
- T013–T014: every custom station prefers English audio, uses the existing NVIDIA profile and has a populated playout. New studio, genre, network and franchise stations have authored wide SVG/PNG pairs. The 14 initial additions, bedtime station, 17 studio/network additions and five final franchise/television additions pass video/audio decoding; post-language playback also passes. Native Plex playback was verified and its test buffer stopped. Live buffers, recording subscriptions and scheduled recordings remain zero.
- T015: native Lucene membership checks cover all 1,855 movie and 10,123 episode IDs. Eight franchise collections match independent title predicates. Repairs cover title punctuation, inherited episode fields, stale index records, legacy studio credits and known co-production exceptions. Network collections include canonical suggested series for future additions. All 50 collections are nonempty. Private receipts retain full membership and preservation comparisons.
- T016: all 50 logo pairs render at 768 × 384 with accessible names and scoped IDs. Theme-specific refinements distinguish franchise and network stations. Public artwork URLs and Plex names/thumbnails match across the complete lineup. Browser checks show all 50 logos loaded and English displayed on all 50 rows. Repository validation passes; PostHog generated bundle skipped and the existing Stoat optional-example warning remains. Operation-created channel rollback and restore copies were removed after acceptance; established backups were preserved.
- T012 remains incomplete: We’re Back! has a verified healthy replacement and its duration warning cleared. Transformers One is physically damaged; two replacements failed because Usenet articles were unavailable, and the refreshed search offered no unblocked compact HEVC candidate. Its warning remains visible. Private preservation copies and the verified Radarr recovery backup are retained. The operator prefers compact H.265/x265 Blu-ray encodes for further replacements; global quality profiles were preserved.

- [x] T017 Add nine approved library stations, expand the boxing collection into fighting cinema, refine generic artwork, and verify incoming recommendation filters.

- T017: 59 custom stations occupy output 100–158, with 159–179 reserved and multiviews retained at 180–189. Nine additions pass video/audio decoding, including a 32-film fighting collection covering every requested franchise and title. Existing native channel rows, Dispatcharr UUIDs, stream links, memberships and Plex DVR identity are preserved. All 528 Plex channels remain enabled and mapped. All 59 collections are nonempty and playouts populated; all prefer English and the existing NVENC profile. The current index covers 1,864 movies and 10,123 episodes, preserving every prior media ID. Nine new wide SVG/PNG logos and 21 refined icons pass source, public-asset and Plex-thumbnail checks. Five studio/sports filters pass 37 exact title/year fixtures with unknown studio metadata; real imported recommendations match their intended collections. Backups were restored and checked before mutations. Repository validation and generated-document checks pass. The separate damaged-movie recovery remains pending under T012.

- [x] T018 Refine remaining generic icons, synchronize the science-fiction/fantasy name across integrations, and reduce the library scan interval.

- T018: ten refined wide SVG/PNG pairs pass guide-size visual checks and native/public/Plex artwork hash checks. Sci-Fi Series is renamed Sci-Fi & Fantasy TV in the channel, collection, schedule, source stream and Plex guide, preserving source/output numbers and UUIDs. The library refresh interval changes from six hours to one. All 59 channel schedules and prior media IDs are preserved; all 528 Plex bindings and DVR identity remain unchanged. The renamed station passes video/audio decoding. Verified native PostgreSQL and SQLite restores precede writes. Repository validation and generated-document checks pass.

- [x] T019 Finish remaining ambiguous genre/decade icons with guide-size proof and integration preservation.

- T019: 90s Movies uses a rental case and VHS tape; Movie Musicals combines a microphone and notes; Romance frames a heart in film; Sports Cinema uses a starred trophy and laurel; Sci-Fi Movies refines the planet/orbit artwork. Five SVG/PNG pairs retain 768×384 geometry and legible guide-size rendering. Native and public asset hashes match source exports and Plex thumbnails. All 59 channels, names, numbers, schedules and collection queries remain intact, including the prior science-fiction/fantasy rename and one-hour refresh setting. All 528 Plex bindings and DVR identity are preserved. Native PostgreSQL and SQLite restore verification precedes the artwork-only writes. Repository validation passes.

- [x] T020 Add six approved seasonal stations with future gap-title filters, distinct wide logos, natural guide placement and preserved existing integrations.

- T020: Spooky Toons & Tales, Holiday Sitcom Shuffle, Winter Wonderland, Thanksgiving Table, Summer Vacation and Spring & Easter have populated schedules, preferred English audio and the existing NVENC profile. Their current pools contain 671, 49, 17, 12, 23 and 5 indexed items respectively. All six pass picture/audio decoding through Dispatcharr. All 59 prior native station rows and media IDs are preserved, together with Dispatcharr UUIDs, links and profile memberships. All 534 enabled Plex guide bindings and DVR identity match the intended complete mapping. The seasonal group sits within custom output 100–164, with 165–179 reserved and multiviews at 180–189. Six new wide SVG/PNG pairs pass guide-size visual checks, native/public asset hashes and Plex thumbnail checks. Native Lucene verifies all 65 current filters are nonempty, 28 future title/show matches with unknown studio metadata, and five unrelated-film exclusions. Exact year/title aliases cover the recommended gaps; hourly library synchronization remains enabled. Existing guide slots can persist until playout regeneration. Verified isolated PostgreSQL, Plex SQLite and complete ErsatzTV restore copies precede mutations. Repository validation and generated-document checks pass. Optional PostHog bundle and unavailable yamllint checks are skipped, with the existing Stoat optional-example warning retained.

- [x] T021 Audit all existing channel memberships, expand fitting collections without removing prior matches, verify future aliases and family-content exclusions, and refresh affected schedules while preserving the lineup and artwork.

- T021: all 65 station queries plus the shared animation pool were audited with native Lucene. Updated filters add 937 memberships across 28 channels on the same fresh index while retaining every prior match. The current library contains 1,929 films, 218 shows and 10,409 episodes. All 297 future title, series and holiday fixtures and five exclusion groups pass. The 64 newly imported films match the reviewed studio, franchise and seasonal destinations. Exact aliases cover missing Lilo & Stitch metadata, Homeward Bound co-production credits and Easter Beagle punctuation. The live-action remake is excluded from animation pools. All nine indexed Over the Garden Wall episodes match Cartoon Network Classics, Morning Cartoons, Spooky Toons & Tales, Sci-Fi & Fantasy TV and TV Variety; episode 10 is not indexed. Regenerated schedules are populated on all 65 channels. Dispatcharr contains all 3,726 checked native future guide programs. All 534 Plex mappings, DVR identity, channel rows, UUIDs, numbers, artwork, English preference and NVENC settings are preserved. Four representative updated channels pass picture/audio decoding through Dispatcharr. SQLite integrity and foreign keys pass, and all three services are healthy. Verified isolated restores precede changes; operation-created temporary copies were removed after acceptance while established and separate movie-recovery backups remain. Repository validation and generated-document checks pass with the previously recorded optional-tool skips.

- [x] T022 Refine franchise metadata fallbacks and cartoon guards, extend Looney Tunes programming, and exclude the modern Wacky Races remake from Retro Cartoons while preserving the classic series and integration identities.

- T022: eight existing filters were refined with native Lucene proof across 85 future film/series matches and 11 exclusion groups. Looney Tunes adds six playable films, all represented in the rebuilt playout. Retro Cartoons excludes only the 78 episodes of Wacky Races (2017); the original series remains, and the remake stays in Morning Cartoons and TV Variety. Bond uses exact title/year aliases instead of an unrestricted producer match. MCU adds missing-studio fallbacks, and MCU/Star Wars exclude documentaries. Cartoon Network and Nicktoons exception branches retain animation and rating guards; Hanna-Barbera gains classic-series metadata fallbacks. All other prior matches remain, all 66 collection pools are nonempty, and all 65 schedules are populated. Existing channel/artwork/schedule/library rows and prior media IDs are preserved. Dispatcharr contains all 3,712 checked native future guide programs. All 534 enabled Plex bindings and DVR identity are unchanged. Looney Tunes, Retro Cartoons, Cartoon Network Classics and 007 Cinema pass picture/audio decoding through Dispatcharr. Native PostgreSQL, Plex SQLite and ErsatzTV SQLite isolated restores precede the writes. Integrity and foreign-key checks pass, all three services are healthy, and operation-created temporary backup/restore/snapshot copies were removed after acceptance. Repository validation and generated-document checks pass with the recorded optional PostHog/yamllint skips and existing Stoat warning.

- [x] T023 Improve theme-specific logo silhouettes and metadata-resilient studio/seasonal filters, then verify source renders, delivered artwork, guide, playback and preservation.

- T023: eight additive filters preserve every previous match. Reviewed studio title/year fallbacks pass 224 missing-metadata cases and four exclusion groups. Seasons of Giving adds one match each to Holiday Movies, Winter Wonderland and Thanksgiving Table; Mickey's House of Villains adds one to Spooky Toons & Tales. Eight wide SVG/PNG logos gain clearer DreamWorks, 007, Scooby-Doo, Jurassic, Kaiju, Adult Animation, Action & Adventure and Disney motifs. All 65 source pairs pass dimensions, safe-markup, accessible-title and unique-ID checks, with guide/full-size light/dark render proof. The stale native XMLTV channel-list cache was identified through the exported old-image hash and upstream refresh ownership. Restarting only ErsatzTV regenerates it; all eight native HTTP images, public Dispatcharr images and Plex thumbnails now match source PNG hashes. Browser proof shows updated DreamWorks and 007 logos. All 65 channel identities, names, numbers, schedule definitions, prior media IDs, English preference, NVENC profile, Dispatcharr links/memberships/recordings, all 534 Plex bindings and DVR identity are preserved. All 65 playouts are populated, all 3,702 checked native future programs reach Dispatcharr, and four representative channels pass picture/audio decoding after the restart. Isolated native PostgreSQL, Plex/ErsatzTV SQLite and logo-file restores precede changes. Integrity and foreign-key checks pass; all three containers are healthy. Verified-operation temporary backup/restore/snapshot copies are removed while established and separate damaged-movie backups remain. Repository validation and generated-document checks pass with the recorded optional PostHog/yamllint skips and existing Stoat warning.

- [x] T024 Refine reference-based studio/franchise logo geometry, identify unfilled film gaps against current media and Radarr, and verify exact future aliases, image delivery, guide, playback and preservation.

- T024: current ErsatzTV movie metadata and read-only Radarr inventory establish ten unfilled, untracked film suggestions. Seven additive collection updates provide exact studio/family/seasonal aliases with 41 native Lucene future matches and four live-action-remake/spoof exclusions. Every current match survives; the already monitored Return of Jafar is excluded from new recommendations. Four logo pairs correct the 2016 DC monogram, Avengers A/circle/arrow, asymmetric Starfleet delta/command star and articulated Pixar lamp/ball. Inspected imported paths retain documented PD-textlogo/CC0 source provenance; custom reference drawings and all 65 pairs pass safety, accessible-title, unique-ID and dimension checks with guide/full-size light/dark proof. Isolated native PostgreSQL, Plex/ErsatzTV SQLite and affected logo restores precede writes. Native/public image hashes and Plex thumbnails match all four PNGs after an ErsatzTV-only cached-guide refresh. All 65 channel names, numbers, schedule definitions, prior media IDs, English/NVENC settings, Dispatcharr identities/links/memberships/recordings, all 534 enabled Plex bindings and DVR identity are preserved. All schedules are populated and all 3,706 checked future programs reach Dispatcharr. Pixar, MCU, DC Universe and Star Trek pass picture/audio decoding. Integrity and foreign-key checks pass; all containers are healthy. Verified-operation temporary copies are removed while established and damaged-movie recovery backups remain. Repository validation and generated-document checks pass with the documented optional-tool skips and existing Stoat warning. Browser proof shows corrected marks in the intact lineup.

- [x] T025 Refine DreamWorks, Cartoon Network, Transformers and Ghibli logos against references, verify artwork delivery and preserve all channel filters and integration identities.

- T025: four wide SVG/PNG pairs refine the DreamWorks fisher/moon silhouette, CN tiles and lettering, Autobot insignia and Totoro body/face/belly markings. Imported paths are inspected and source terms documented. All 65 pairs pass markup safety, accessible-title, scoped-ID and dimension checks, with full/guide-size light/dark visual proof. Native HTTP and public image hashes and Plex thumbnails match all four exports after an ErsatzTV-only cached-guide refresh. All 66 collection queries remain unchanged, including the seven prior gap-alias refinements. All 65 channel identities, names, numbers, schedule definitions, prior media IDs, English/NVENC settings, hourly refresh, Dispatcharr links/memberships/recordings, all 534 enabled Plex mappings and DVR identity are preserved. All schedules remain populated and all 3,694 checked native future programs reach Dispatcharr. All four changed channels pass picture/audio decoding. Isolated native PostgreSQL, Plex/ErsatzTV SQLite and affected artwork restores precede writes. Database integrity and foreign keys pass, all three containers are healthy, and operation-created temporary copies are removed after acceptance. Browser screenshots confirm the installed artwork. Repository validation and generated-document checks pass with the recorded PostHog/yamllint skips and existing Stoat warning. The separate damaged-movie recovery remains pending under T012.

- [x] T026 Refine the 007, Star Wars, Nicktoons and Disney Cartoons reference marks, verify delivered artwork and preserve channel data and integration identities.

- T026: four SVG/PNG pairs replace approximations with the 007 gun mark, Rebel Alliance emblem, Nickelodeon splat and three-circle Mickey silhouette. Source terms and Font Awesome attribution are documented. All 65 pairs pass safe-markup, accessible-title, scoped-ID and dimension checks, with full/guide-size light/dark render proof. All four native/public image hashes and Plex guide thumbnails match the exports. All 66 collection queries, 65 channel identities and schedules, prior media IDs, English/NVENC settings, hourly refresh, Dispatcharr links/memberships/recordings and all 534 Plex mappings and DVR identity remain intact. All schedules are populated and all 3,716 checked future programs reach Dispatcharr. All four changed channels pass picture/audio decoding. Verified isolated database and logo restores precede writes. Integrity and foreign keys pass, all containers are healthy, and only this operation's temporary copies were removed after acceptance. Repository validation passes with the previously recorded optional-tool skips and Stoat warning. The separate iOS/TestFlight logo-display diagnosis and T012 damaged-movie recovery remain unresolved.

- [x] T027 Improve the Fight Night Cinema boxing glove and verify delivered artwork, playback and preservation of the preceding logo pass and complete lineup.

- T027: Fight Night Cinema now uses a padded glove silhouette with a curved thumb, palm seam and laced wrist cuff. Its SVG and 768×384 PNG pass the 65-pair source checks and full/guide-size light/dark visual review. The native HTTP image, public Dispatcharr image and Plex thumbnail match the export, and Fight Night passes picture/audio decoding through Dispatcharr. The preceding four revised logos are preserved. All 66 queries, 65 channel rows/schedules, prior media IDs, English/NVENC settings, hourly refresh, Dispatcharr identities/links/memberships/recordings and all 534 enabled Plex mappings and DVR identity remain intact. All schedules are populated and all 3,723 checked native future guide programs reach Dispatcharr. Isolated native PostgreSQL, Plex/ErsatzTV SQLite and artwork restores precede writes; integrity and foreign keys pass and all containers are healthy. Operation-only temporary copies are removed after acceptance. Browser proof shows the installed glove. Repository validation and generated-document checks pass with the recorded PostHog/yamllint skips and existing Stoat warning. This artwork change does not resolve the separately diagnosed iOS/TestFlight display issue.

- [x] T028 Refine both Scooby-Doo logos, Wizarding World, Middle-earth, Looney Tunes, Kaiju, Nature & Wildlife and Jurassic Cinema, verifying delivered images, playback and preserved channel/integration data.

- T028: eight SVG/PNG pairs refine both Scooby-Doo stations with the SD tag and Mystery Machine, plus the Deathly Hallows symbol, Gondor tree/crown/seven stars, Bugs Bunny with title rings, Godzilla-inspired silhouette, stag and T. rex fossil skull. Lorc and Delapouite CC BY 3.0 geometry is attributed in the logo README; all other new geometry is custom. All 65 pairs pass source safety, accessible-title, scoped-ID and dimension checks. Visual proof covers full size, 192×96 and 96×48, including light/dark backgrounds. Native/public image hashes and Plex thumbnails match all eight exports. All eight changed stations pass picture/audio decoding. All 66 queries, 65 channel identities and schedules, prior media IDs, English/NVENC settings, hourly refresh, Dispatcharr rows/links/memberships/recordings and all 534 Plex mappings and DVR identity are preserved. All schedules are populated and all 3,723 checked native future programs reach Dispatcharr. Verified isolated database and artwork restores precede writes; database integrity and foreign keys pass and all three containers are healthy. Only operation-created temporary copies are removed after acceptance. Browser screenshots confirm installed artwork. Repository validation and generated-document checks pass with recorded optional-tool skips and the existing Stoat warning. The separate iOS/TestFlight display issue remains unresolved.

- [x] T029 Refine Hanna-Barbera, Die Hard Cinema, Planet of the Apes and eight seasonal logos, preserving the preceding eight-logo pass and verifying delivery, representative playback and integration data.

- T029: eleven SVG/PNG pairs refine Hanna-Barbera's Flintmobile, the Fox/Nakatomi Plaza tower and the ape face, plus all eight seasonal motifs: decorated evergreen, carved pumpkin, friendly ghost with pumpkin, festive gift television, snowman globe, roast turkey/platter, beach umbrella/chair/waves and Easter basket/eggs. The tower uses the architect's photographs as a reference; no reference photograph is embedded. All final geometry in this batch is custom. All 65 source/export pairs pass safety, accessible-title, scoped-ID and dimension checks, with full/guide-size light/dark proof down to 96×48. Native/public PNG hashes and Plex guide thumbnails match all eleven exports. Six representative stations pass picture/audio decoding, supplementing the preceding eight successful station checks. All prior logos outside the selected eleven, 66 queries, 65 channel identities and schedule definitions, prior media IDs, English/NVENC settings, hourly refresh, Dispatcharr rows/links/memberships/recordings and all 534 enabled Plex mappings and DVR identity are preserved. All schedules remain populated and all 3,718 checked native future programs reach Dispatcharr. Isolated native database and affected-artwork restores precede writes; database integrity and foreign keys pass and all three containers are healthy. Temporary copies created by this operation are removed after acceptance, preserving established and separate movie-recovery backups. Browser proof covers all eleven installed logos, and a combined gallery shows all 19 changes across T028/T029. Repository validation and generated-document checks pass with the recorded optional PostHog/yamllint skips and existing Stoat warning. The separate iOS/TestFlight display issue remains unresolved.

- [x] T030 Refine eleven genre/category logos, including Fantasy Movies, verify guide-size rendering and delivered artwork, and preserve all channel/filter/integration data.

- T030: eleven SVG/PNG pairs refine Fantasy Movies, Comedy Movies, Drama Movies, Crime & Mystery, Family Animation, Action & Adventure, Documentary Movies, Documentary Series, TV Variety, Retro Cartoons and Morning Cartoons. The dragon uses attributed Lorc CC BY 3.0 geometry; the other ten motifs are custom. All 65 pairs pass source safety, accessible-title, scoped-ID and dimension checks, with full/guide-size light/dark visual proof down to 96×48. The legacy crime artwork's accessible title now matches the live channel name. Native/public image hashes and Plex guide thumbnails match all eleven exports. Six representative stations pass picture/audio decoding. All 66 queries, 65 channel identities/numbers/schedule definitions, prior media IDs, English/NVENC settings, hourly refresh, preceding artwork outside this batch, Dispatcharr links/memberships/recordings and all 534 enabled Plex mappings and DVR identity are preserved. All schedules are populated and all 3,728 checked native future programs reach Dispatcharr. Library identity and sync selection checks remain exact; the only PlexLibrary difference is a forward-moving background network-scan timestamp, recorded separately. Native database and affected-artwork isolated restores precede installation. Integrity and foreign keys pass and all three containers are healthy. Temporary copies created by this operation are removed after acceptance; established and separate damaged-movie recovery backups remain. Browser proof covers all eleven installed logos. The owning README now documents target-name preflight and separation of scan timestamps from persistent settings. Repository validation and generated-document checks pass with the recorded optional PostHog/yamllint skips and existing Stoat warning. The separate iOS/TestFlight display issue remains unresolved.

- [x] T031 Refine twelve priority remaining station icons, review guide-size rendering, and verify delivered artwork, representative playback and complete lineup preservation.

- T031: twelve priority SVG/PNG pairs refine Disney Movies, DC Animated Adventures, Fast & Furious Cinema, Adult Animation, Bedtime Cartoons, After Dark TV, Sitcom Shuffle, Workplace Comedy, Western Movies, War & History, Thriller Theater and Sci-Fi & Fantasy TV. All 65 pairs pass source safety, accessible-title, scoped-ID and dimension checks, with full/guide-size light/dark review down to 96×48. All twelve native/public hashes and Plex thumbnails match. Six representative stations pass picture/audio decoding. All 65 channels and schedules, 66 queries, prior media IDs, English/NVENC settings, hourly refresh, Dispatcharr identities/links/memberships/recordings, all 534 Plex mappings and DVR identity are preserved. All 3,717 checked native future programs reach Dispatcharr. Verified isolated database and artwork restores precede writes; integrity and foreign keys pass and all three services are healthy. Operation-only temporary copies were removed after acceptance. Repository validation and generated-document checks pass with recorded optional-tool skips and existing Stoat warning. The separate iOS/TestFlight display issue remains unresolved.

- [x] T032 Bring the three decade stations, Movie Musicals, Romance Movies, Sports Cinema and Classic Cinema into the same filled icon style, with delivered-artwork and playback proof.

- T032: seven SVG/PNG pairs bring 80s Movies, 90s Movies, 2000s Movies, Movie Musicals, Romance Movies, Sports Cinema and Classic Cinema into the filled icon style. All 65 pairs pass source checks; full/guide-size light/dark review extends down to 96×48. All seven native/public hashes and Plex thumbnails match. Every changed station passes picture/audio decoding. All 65 channels and schedules, 66 queries, prior media IDs, English/NVENC settings, hourly refresh, Dispatcharr identities/links/memberships/recordings and all 534 Plex mappings and DVR identity are preserved. All 3,725 checked native future programs reach Dispatcharr. Verified isolated database and artwork restores precede writes; integrity and foreign keys pass and all three services are healthy. Operation-only temporary copies were removed after acceptance. Repository validation and generated-document checks pass with the recorded optional-tool skips and existing Stoat warning. The separate iOS/TestFlight display issue remains unresolved.

- [x] T033 Complete the remaining Movie Night, Crime Series and Sci-Fi Movies icons in the coordinated filled style, verifying artwork delivery, playback and lineup preservation.

- T033: Movie Night, Crime Series and Sci-Fi Movies now use filled clapperboard, fingerprint scanner and striped planet/ring/moon motifs. All 65 pairs pass source safety, accessible-title, scoped-ID and dimension checks, with full/guide-size light/dark review down to 96×48. Native/public hashes and Plex thumbnails match all three exports, and all three stations pass picture/audio decoding. All 65 channel identities and schedules, 66 queries, prior media IDs, English/NVENC settings, hourly refresh, Dispatcharr identities/links/memberships/recordings and all 534 Plex mappings and DVR identity are preserved. All 3,731 checked native future programs reach Dispatcharr. Verified isolated database and artwork restores precede writes; integrity and foreign keys pass and all three services are healthy. Operation-only temporary copies were removed after acceptance. Repository validation and generated-document checks pass with recorded optional-tool skips and existing Stoat warning. All 65 current icons now have documented geometry and source terms.

- [x] T034 Refine six branded icons with stronger filled silhouettes and contrasting detail, preserving source attribution and verifying delivered artwork, playback and lineup data.

- T034: Pixar, Ghibli, MCU, 007, Transformers and Die Hard gain stronger filled silhouettes and contrasting detail. All 65 pairs pass source safety, accessible-title, scoped-ID and dimension checks, with full/guide-size light/dark review down to 96×48. All six native/public hashes and Plex thumbnails match and all six channels pass picture/audio decoding. All 65 custom channels and schedules, 66 queries, prior media IDs, English/NVENC settings and hourly refresh are preserved. The concurrent user-authorized IPTV trim is verified against its exact 57-channel plan: only those non-custom memberships change, all source channel records/links/recordings remain intact, and all 477 remaining Plex mappings and DVR identity are preserved. All 3,730 checked native future programs reach Dispatcharr. Verified isolated database and artwork restores precede writes; integrity and foreign keys pass and all three services are healthy. Operation-only temporary copies were removed after acceptance. Browser proof covers all six changes. Repository validation and generated-document checks pass with recorded optional-tool skips and existing Stoat warning. The separate iOS/TestFlight display issue remains unresolved.

- [x] T035 Audit the full 65-icon suite and refine nine remaining style inconsistencies, including Fantasy Movies and the Pixar lampshade, with delivery, playback and preservation proof.

- T035: a complete 65-icon visual audit identifies nine priority refinements: Fantasy Movies, Pixar Movies, Wizarding World Cinema, Middle-earth Cinema, Documentary Movies, Documentary Series, Crime & Mystery, Holiday Movies and Holiday Sitcom Shuffle. Fantasy gains clipped shading, eye and flame detail; Pixar gains a conical shade with an elliptical opening, separate jointed rods and spring. All nine delivered native/public hashes and Plex thumbnails match their exports. Six representative channels pass picture/audio decoding. All 65 existing channel identities and schedules, 66 queries, prior media IDs, English/NVENC settings, hourly refresh, Dispatcharr identities/links/memberships/recordings and the current 476 enabled Plex mappings and DVR identity are preserved. All 3,725 checked native future programs reach Dispatcharr. The parallel station-addition task holds runtime writes until this batch's verification and cleanup finish. Verified isolated database and artwork restores precede installation; integrity and foreign keys pass and all services are healthy. Temporary operation copies are removed after acceptance. Browser proof covers Fantasy, the corrected Pixar lamp and franchise/category artwork. Two additional matching SVG/PNG pairs for Portlandia and Teenage Mutant Ninja Turtles are handed to the parallel task for its own channel creation and runtime binding. Source safety, accessible titles, scoped IDs, 768×384 exports and guide-size proof cover all 67 pairs. Repository validation and generated-document checks pass with recorded optional-tool skips and existing Stoat warning. The separate iOS/TestFlight display issue remains unresolved.

- [x] T036 After the parallel station-addition task completes, audit the full 67-station logo suite and refine six remaining guide-size weaknesses while preserving the new stations and complete lineup.

- T036: after the parallel task's final acceptance/cleanup handoff, all 67 station icons were reviewed at guide size. Fight Night gains shaded leather padding and contrasting laces; Kaiju gains belly/dorsal contrast, teeth and claws; 80s Movies uses a horizontal VHS housing; Winter Wonderland gains a filled globe/base and reflection; Thanksgiving Table gains a shaded roast, wing, drumstick, herbs and platter; Summer Vacation gains a striped fabric deck chair. All 67 SVG/PNG pairs pass source safety, accessible-title, scoped-ID and 768×384 checks, with full-size and 192×96/96×48 light/dark visual proof. All six native/public image hashes and Plex thumbnails match, and every revised station passes picture/audio decoding. All 67 channel identities and schedule definitions, 68 queries, prior media IDs, English/NVENC settings, hourly refresh, unrelated artwork, Dispatcharr links/memberships/recordings and the captured 478 Plex mappings and DVR identity are preserved at verification. Both new Portlandia and Teenage Mutant Ninja Turtles artwork bindings remain intact. All 3,973 checked native future programs reach Dispatcharr. A subsequent independently authorized four-channel IPTV membership trim belongs to the parallel task and starts after this pass's mapping verification; no further lineup writes are made here. Verified isolated database and affected-artwork restores precede installation. Integrity and foreign keys pass and all services are healthy. Operation-only temporary copies are removed after acceptance, preserving established backups. Browser proof shows the installed changes and complete 67-station list, including the two additions. Repository validation and generated-document checks pass with recorded optional PostHog/yamllint skips and existing Stoat warning. The separate iOS/TestFlight display issue remains unresolved.

- [x] T037 Center visible icon artwork across all 67 logos, preserve size/frame/text, and verify the changed assets through ErsatzTV, Dispatcharr and Plex.

- T037: icon-only transparent renders identify 43 of 67 logos with vertical offsets greater than two source pixels. Translating only those SVG groups centers all 67 visible icon bounds at y=192 within two pixels. Source checks prove preserved icon dimensions and horizontal bounds, frames, accessible names, wordmarks and other non-icon attributes; all artwork remains inside the inner frame. Full/guide-size light/dark review includes before/after comparisons and all 67 source/export pairs. All 43 native/public PNG hashes and Plex thumbnails match the aligned exports. Six representative stations, including Teenage Mutant Ninja Turtles, pass picture/audio decoding. All 67 channel identities/schedules, 68 queries, prior media IDs, language/NVENC choices, hourly refresh, unrelated artwork, Dispatcharr links/memberships/recordings, all 474 current Plex mappings and DVR identity are preserved after the parallel membership task's final handoff. All 3,975 checked native future programs reach Dispatcharr. Verified isolated database and affected-artwork restores precede installation; integrity and foreign keys pass and all services are healthy. Operation-only temporary backup/restore copies are removed after acceptance, preserving established backups. The logo README now defines the y=192 icon-only centering contract. Browser proof confirms the delivered alignment. Repository validation and generated-document checks pass with recorded optional PostHog/yamllint skips and existing Stoat warning. The separate iOS/TestFlight display issue remains unresolved.

- [x] T038 Audit current library memberships, add fitting existing content through six precise filters, retain all current matches, improve four centered logos, and verify guide/playback and complete data preservation.

- T038: all 68 current station/helper queries are evaluated with the native Lucene analyzer against a 13,365-document index. Six refined queries retain every current match and add 44 memberships: Disney Movies adds The Nightmare Before Christmas; DreamWorks adds Trollhunters: Rise of the Titans; DC Universe adds Deathstroke: Knights & Dragons; Summer Vacation adds five available vacation films; Workplace Comedy adds 36 DAVE/Better Call Saul: Employee Training episodes. Exact title/year fallbacks pass 12 missing-metadata fixtures and 11 exclusion groups. All 44 additions have nonempty media files and nonzero durations. A read-only frame identifies the misdated Grave of the Fireflies copy as animation, so Ghibli retains that verified item through a scoped exception, gains the correct-year future fallback and excludes other same-title remakes without losing its current pool. Nature & Wildlife, War & History, Thriller Theater and Planet of the Apes gain contrasting detail; all 67 icons retain vertical centering. All four native/public PNG hashes and Plex thumbnails match. The five expanded schedules are regenerated, all 67 schedules are populated, all 3,958 checked native future programs reach Dispatcharr and all 4,024 checked current/future guide rows have no overlaps. Six affected channels pass video/audio decoding. All 67 channel identities and schedule definitions, 62 unchanged queries, prior media IDs, every ConfigElement, English/NVENC settings, unrelated artwork, Dispatcharr links/memberships/recordings and all 474 Plex mappings and DVR identity are preserved. A coordinated runtime window leaves the other chat's poster bridge and classification work untouched. Verified isolated database and affected-artwork restores precede writes. Integrity and foreign keys pass, all services are healthy, and operation-only backup/restore/media-identification copies are removed after acceptance. Browser proof covers all four logos. Repository validation and generated-document checks pass with recorded optional PostHog/yamllint skips and existing Stoat warning. The separate iOS/TestFlight display issue remains unresolved.

- [x] T039 Refine four remaining category logos, close six verified film-membership gaps with exact title/year fallbacks, and verify preservation, guide delivery and playback after the parallel poster task releases its runtime window.

- T039: all 68 queries are audited with the native Lucene analyzer against 13,365 documents. Three exact-title/year refinements retain every match and add six available films: DC Universe adds Legion of Super-Heroes and Reign of the Supermen; Fight Night adds both Batman Ninja films and The LEGO Ninjago Movie; Movie Musicals adds The Point, with punctuation aliases for future imports. Seven missing-metadata fixtures and 22 exclusion groups pass, and all six media files are nonempty with nonzero durations. Action & Adventure, Romance Movies, Sports Cinema and Movie Musicals gain shaded detail. All 67 icons retain vertical centering; source safety and full/guide-size light/dark checks extend down to 96x48. All four native/public PNG hashes and Plex thumbnail URLs match. Three schedules are rebuilt; all 67 remain populated. All 3,963 checked native future programmes reach Dispatcharr, and 4,028 current/future rows have no overlaps. Six stations pass video/audio decoding. The playback worker terminated after four accepted checks; only the two remaining stations were resumed, with no repeated content or artwork writes. All 67 channel identities, schedule definitions, prior media IDs, every ConfigElement, 65 unchanged queries, unrelated artwork, Dispatcharr links/memberships/recordings and 474 Plex mappings and DVR identity are preserved. Fresh isolated database/artwork restores precede writes. All guide-source settings, including the parallel task's private poster bridge URL, remain exact. Integrity, foreign keys and service health pass; operation-only temporary copies are removed after acceptance. Browser proof covers all four logos. Repository validation passes with the existing PostHog generated-bundle skip and optional-example warning.

- [x] T040 Refine Marvel, both DC, DreamWorks, Star Trek, Disney Cartoons, Scooby-Doo tag and Wizarding World logos; verify installed images, centering and lineup preservation without changing content filters.

- T040: eight SVG/PNG pairs refine MCU Cinema, DC Universe Movies, DC Animated Adventures, DreamWorks Animation, Star Trek Cinema, Disney Cartoons, Scooby-Doo Movies and Wizarding World Cinema. The Avengers emblem gains corrected counter/arrow spacing and shading; both DC stations share the exact inspected monogram with a shaded face, with a filled animation cel and pencil on the animation station. DreamWorks retains the inspected fisher/moon contour and gains a reinforced rod/line. The Starfleet delta gains a beveled face; Mickey gains a face, ears, eyes and smile; the SD collar tag gains a split ring, beveled rim and filled monogram; the Hallows mark gains a tangent ring and beveled triangle/wand. All 67 icon centers remain within two source pixels of y=192. All source/export pairs pass safety, accessible-title, scoped-ID and dimensions checks; light/dark and full/guide-size review extends to 96x48. The first native HTTP check caught a prior cached Marvel image after healthy startup. A later read-only check confirmed all eight final images without repeating artwork writes; native/public hashes and Plex thumbnail URLs match. Six representative stations pass picture/audio decoding. All 67 channel identities, schedules, prior media IDs, all 68 queries, ConfigElements, English/NVENC choices, unrelated artwork, Dispatcharr links/memberships/recordings and all 474 Plex mappings and DVR identity are preserved. All 3,991 checked native future programmes reach Dispatcharr, with no overlaps among 4,060 checked current/future rows. Fresh isolated database/artwork restores precede writes, health and integrity checks pass, and all guide-source settings including the poster bridge remain exact. Operation-only temporary copies are removed after acceptance. Browser proof shows installed studio and franchise marks. Repository validation passes with the existing generated-bundle skip and optional-example warning.

- [x] T041 Refine Looney Tunes, Transformers TV and Halloween Horror logos, retain the preceding twelve-logo and six-film pass, and verify guide delivery, playback, centering and integration preservation.

- T041: three SVG/PNG pairs refine Bugs Bunny's expression and filled title rings, the attributed Autobot armor plates and a shaded jack-o'-lantern with lit carvings, stem and leaf. All 67 icon centers and safe source/export checks pass, with full/guide-size light/dark review down to 96x48. Native cache refresh briefly exposed a missing image URL; a read-only diagnostic and subsequent acceptance prove HTTP 200 and exact PNG bytes for all three, without repeating artwork writes. Native/public hashes and Plex thumbnail URLs match. All three changed stations pass picture/audio decoding. All 67 identities/schedules, 68 queries including the six-film additions, prior media IDs, ConfigElements, English/NVENC settings, prior artwork, Dispatcharr links/memberships/recordings and all 474 Plex mappings and DVR identity are preserved. All 3,993 checked native future programmes reach Dispatcharr, and 4,060 checked current/future rows have no overlaps. All guide-source settings, including the poster bridge URL, remain exact. Fresh isolated database/artwork restores precede installation; health/integrity/foreign-key checks pass. Operation-only temporary copies are removed after acceptance. Browser proof confirms all three installed logos. Repository validation, generated-document checks and whitespace checks pass, with the existing generated-bundle skip and optional-example warning.

- [x] T042 Refine Scooby-Doo Cartoons, Hanna-Barbera Classics, Middle-earth Cinema, Spooky Toons & Tales and Nature & Wildlife, consolidate all visible icon decorations, and verify complete-icon centering and integration preservation.

- T042: five SVG/PNG illustrations refine the Mystery Machine with shaded bodywork, glass reflections and wheel hubs; the Flintmobile with folded canopy, wood frame, seat, steering and stone rollers; the White Tree shield with one arc of seven stars; the ghost and pumpkin with sheet/face shading; and the attributed stag contour with antler/face shading, eyes and muzzle detail. The audit finds decorative geometry outside the first icon group in eight files, including duplicated seven-star sets on Middle-earth. The two illustrated assets consolidate their decorations; six other files group their existing stars with the main icon without changing their geometry. Holiday Movies moves 1.5 pixels and Sci-Fi & Fantasy TV moves 2 pixels; the other four grouped images retain their visual placement. All 67 assets now have exactly one complete icon group centered at y=192 within two pixels. All eleven selected frames, wordmarks, accessible names and root attributes are preserved, with exact decoration geometry checks for the six grouping-only files. Source/export, full/guide-size light/dark and native/public PNG/Plex thumbnail checks pass. Five changed theme channels pass picture/audio decoding. All 67 identities/schedules, 68 queries, six earlier film additions, prior media IDs, ConfigElements, English/NVENC choices, unrelated artwork, Dispatcharr links/memberships/recordings and 474 Plex mappings and DVR identity remain intact. All 3,990 checked native future programmes reach Dispatcharr, and 4,056 checked current/future rows have no overlaps. Fresh isolated database/artwork restores precede installation; health, integrity, foreign keys and exact guide-source/poster-bridge preservation pass. Temporary operation copies are cleaned after acceptance. Browser proof shows the five installed illustrations. Repository validation and whitespace checks pass with the existing generated-bundle skip and optional-example warning.

- [x] T043 Refine Classic Cinema, Kaiju Cinema, Summer Vacation, Spring & Easter and Disney Movies after prior-batch acceptance; verify complete-icon centering, guide images, playback and lineup preservation.

- T043: five SVG/PNG pairs refine the classic camera with reel perforations, shaded housing, controls, lens and tripod; the kaiju with shaded scales, ribbed belly, dorsal plates, teeth, claws, buildings and atomic breath; the summer scene with paneled umbrella, sun, fabric chair, sand and layered waves; the Easter basket with patterned eggs and a peeking rabbit; and the Disney castle with shaded turrets, roofs, arched gate, stone details and shooting-star arc. Sources are staged privately and installed only after T042 acceptance/cleanup, with exact original source pins checked to avoid changing Disney Movies during prior verification. All 67 assets retain one complete visible icon group centered at y=192 within two pixels. All five frames, labels, accessible names and root attributes are preserved. All 67 source/export pairs pass safety/scoped-ID/dimension checks, with full/guide-size light/dark review down to 96x48. All five native/public PNG hashes and Plex thumbnail URLs match. All five stations pass picture/audio decoding. All 67 channel identities and schedules, 68 queries including the six earlier film additions, prior media IDs, ConfigElements, English/NVENC choices, preceding artwork, Dispatcharr links/memberships/recordings and all 474 Plex mappings and DVR identity remain intact. All 3,993 checked native future programmes reach Dispatcharr, and 4,060 checked current/future rows have no overlaps. Fresh isolated database/artwork restores precede installation; health, integrity, foreign keys and guide-source/poster-bridge preservation pass. Only operation-created temporary backup/restore/staging copies are removed after acceptance, preserving established backups. Browser proof shows the installed cinema/seasonal logos and Disney castle. The combined preview contains all 25 illustrations refined across T039-T043. Repository validation, generated-document checks and whitespace checks pass, with the existing generated-bundle skip and optional-example warning.

- [x] T044 Reflow fourteen long station wordmarks into three centered lines, preserve every icon/frame/label and all content settings, and verify delivered logos, guide readability and representative playback.

- T044: fourteen long wordmarks use three centered lines: nine three-word names, plus five longer names grouped into balanced phrases with short connectors attached. Cartoon Network, Wizarding World, Fast & Furious, DC, Star Trek/Star Wars, Fight Night and other long labels gain larger individual lines. Before/after 192x96 and 96x48 renders are reviewed. Transparent text-only renders prove centered, unclipped bounds inside the right column, and exact source/pixel comparisons preserve every icon, frame, original word sequence, title, root attribute and palette. All 67 assets retain complete centered icon groups and pass SVG/source-export checks. All fourteen native/public PNG hashes and Plex thumbnail URLs match. Six representative stations pass picture/audio decoding. All 67 channel identities/schedule definitions, all 68 filters, prior media IDs, ConfigElements, English/NVENC choices, unrelated artwork, Dispatcharr links/memberships/recordings and 474 Plex mappings and DVR identity remain intact. All 3,979 checked native future programmes reach Dispatcharr; 4,046 checked current/future rows have no overlaps. Guide-source and poster-bridge settings are preserved exactly. Fresh isolated database/artwork restores precede installation; health/integrity/foreign-key checks pass. Operation-only temporary backup/restore copies are removed after acceptance; existing backups remain. Browser proof shows installed three-line franchise titles. Repository validation, generated-document checks and whitespace checks pass with the existing generated-bundle skip and optional-example warning.


- [x] T045 Add the seven recommended library stations with matching centered SVG/PNG
  logos; preserve all existing stations and media, add animation metadata safeguards,
  remove verified incidental holiday matches, and diagnose Star Trek TV visibility.
  Verify native membership and future-import fixtures, isolated restores before
  writes, sorted Dispatcharr/Plex mappings, reserved 174–179, seven playback paths,
  guide/logo convergence, preserved poster bridge and data, and repository checks.

- T045: seven new stations use 27 LEGO titles, 15 Alien/Predator films, 72 Marvel
  multiverse films, 34 adult-animation films, eight Mission: Impossible films,
  602 films from the 2010s and 335 release-date matches from the 2020s. Native
  Lucene membership checks pass, along with ten missing-studio/future-import
  fixtures and unrelated-title guards. Four existing filters gain scoped guards:
  three animation pools exclude incorrectly tagged Fantastic Four (2015), and
  Holiday Movies excludes Ted (2012) and Dumb and Dumber To (2014), whose plots
  mention a Christmas prologue and Lloyd Christmas respectively. Only those two
  holiday matches are removed; other existing memberships remain. Seven custom
  SVG/PNG marks pass centered-icon and source-safety checks and guide-size review.
  Isolated PostgreSQL, Plex SQLite, complete ErsatzTV and configuration restores
  precede writes. All prior native channels, artwork and schedule definitions,
  media IDs, configuration, Dispatcharr links/profiles/recordings and guide-source
  settings including the poster bridge are preserved. Sorted custom outputs now
  span 100–173, with 174–179 reserved and multiviews at 180–189. All 481 Plex
  mappings and DVR identity verify; all 74 names/numbers/logo URLs match. All seven
  new streams pass video/audio decoding, all 74 schedules populate in English
  with NVENC, and all 4,198 checked native future programmes reach Dispatcharr.
  No overlaps appear in 4,274 checked current/future guide rows. Native/public
  image bytes match every new PNG. Plex's enabled TV libraries and ErsatzTV both
  report no Star Trek series; the 13-film station remains intact and no empty TV
  station is created. Browser proof shows all seven installed logos. Operation
  temporary backup/restore/staging copies are removed after acceptance, retaining
  established backups. Repository validation, generated docs/Pages checks and
  whitespace checks pass, with the existing PostHog generated-bundle skip and
  Stoat optional-example warning.


- [x] T046 Audit all seven new channels for missing library media and filter
  resilience; add verified matches, refine four priority icons, preserve station
  identities/order and verify future imports, data, guide/artwork and playback.

- T046: a fresh seven-station audit adds ten existing titles without losing prior
  native matches: Marvel Multiverse grows 72→80 with Hulk (2003), Big Hero 6 and
  six LEGO Marvel specials; Adult Animation grows 34→35 with The Long Halloween,
  Part One; 2020s grows 335→336 through a scoped Lilo & Stitch (2025) fallback for
  its missing release date. LEGO retains all 27 current matches and gains a future
  Piece by Piece (2024) alias; other reviewed pools have no current gaps. Native
  Lucene comparison and seven missing-metadata/future positives plus seventeen
  library/type/year and unrelated-title negatives pass. All ten additions have
  accessible nonempty files and nonzero duration. Four icons gain paired alien
  and Predator imagery, comic-book hero panels, a late-night cartoon cel and a
  self-destruct tape recorder; exact frame/wordmark comparisons and complete-group
  centering pass with full/guide-size review. All four native/public PNG hashes
  and Plex thumbnails match; all seven new-channel streams decode picture/audio.
  All 74 station identities/order/schedules, 75 collections except four planned
  queries, prior media, settings, Dispatcharr links/profiles/recordings and all
  481 Plex mappings/DVR identity remain intact. All 4,176 checked native future
  programmes import; 4,248 current/future guide rows have no overlaps. Guide
  sources, poster bridge, English/NVENC and hourly refresh remain unchanged.
  Fresh isolated database/artwork restores precede writes. Operation-only
  temporary backup/restore copies are removed after acceptance; established
  backups remain. Browser proof shows installed refinements. Repository,
  generated-document/Pages and whitespace checks pass with the existing generated
  PostHog bundle skip and Stoat optional-example warning.

- [x] T047 Correct verified Plex source matches, genres and edition/release metadata;
  reconcile imported fields and remove superseded item exceptions. Verify native
  collection membership, regenerated guides, playback and preserved library/user
  state, then remove operation-only backup copies after acceptance.

- T047: ten Plex source records are repaired through native matching and metadata
  editing. Corrections cover the 1988 animated Grave of the Fireflies, Nightmare
  on Elm Street: The Dream Child, The Legend of Zelda's missing genres, incorrect
  Animation/Documentary tags on Fantastic Four (2015) and the 1966 Grinch,
  Superman and Spider-Man compilations, the 2022 Long Halloween Deluxe Edition,
  Scooby-Doo Meets Batman and Frosty Returns (1992). All rating keys, file bindings,
  watch state and thirteen Zelda episode identities/states survive. Valid Lilo &
  Stitch premiere dates and genuinely unrated compilations remain unchanged.
  Verified isolated native database, configuration and artwork restores precede
  writes. The pinned scanner's stale year/date and unchanged-ETag behavior is
  traced in upstream source, then reconciled within the affected records.
  Actual native index regeneration is verified rather than inferred from startup.
  All 75 filters pass a 13,380-document membership audit and 23 focused fixtures.
  Ten collection queries align aliases with corrected source metadata and remove
  the superseded Ghibli item-ID exception. Five removed memberships follow
  reviewed genre, release-year or edition corrections. Thirteen concurrent film
  imports are preserved. All 1,953 movies have a year and release date.
  Nature & Wildlife retains 92 documentary episodes, including legitimate CGI
  documentary material. Native XMLTV, Dispatcharr and Plex provider-grid evidence
  place nature programmes at 159 and Nicktoons at 166, confirming the reported
  transient cartoon guide entries followed client caching after renumbering.
  Thirty affected schedules are regenerated, all 74 remain populated, and all
  4,176 checked native future programmes reach Dispatcharr. All 4,254 checked
  current/future guide rows have no overlaps. All channel identities, numbers,
  logos, schedule definitions, English/NVENC choices, hourly sync, Dispatcharr
  links/profiles/recordings, guide-source/poster-bridge settings and 481 Plex
  mappings and DVR identity are preserved. Repository validation passes using
  system Python with installed PyYAML, with the existing generated PostHog
  bundle skip and Stoat optional-example warning.
  Six representative stations pass video/audio decoding through Dispatcharr,
  including both nature and cartoon channels. All three services are healthy.
  Operation-only backup, restore and snapshot copies are removed after acceptance.
  Established backups and the separate damaged-movie recovery backups remain.

- [x] T048 Correct verified Plex episode ordering and channel curation labels;
  balance bedtime shows, rename Music & Musicals, add Anime Action and Unexplained,
  and audit all existing collections against the synchronized library.
- [x] T049 Add Mindbender Cinema from the available puzzle-film library with future
  title/year aliases and matching artwork; verify natural guide order, reserved
  capacity, delivered images, programme content, playback and preserved data.


- T048–T049: thirteen verified per-show Plex TVDB aired-order overrides correct
  577 episode titles; two verified special display titles bring the total to
  579. Rating keys, file bindings, episode numbering, watch history and unrelated
  preferences survive. Justice League retains its valid TVDB combined layout.
  Source episode titles, years and dates are checked after native synchronization;
  a deep scan handles the two manually locked special titles. An Expedition
  Unknown episode-zero record still contains two different specials as alternate
  versions; no single title or new file numbering is guessed for that collision.
  Transformers One is physically corrupt and remains pending replacement: all
  compact H.265/Blu-ray candidates returned by the read-only search were already
  blocklisted. A native Plex quarantine label excludes it from all collections
  and actual playouts without removing the file. Native sports-exclusion labels
  remove the two Ralph crossovers while preserving valid secondary genres.
  Fifty-four movie-capable queries gain exact quarantine guards. Disney gains
  the verified A Kid in King Arthur's Court co-production alias; Unexplained
  gains punctuation-safe documentary matches with fiction negatives.
  Music & Musicals retains its identity with an accurate name and wordmark.
  Bedtime Cartoons rotates all four shows evenly, with Disenchantment story
  order preserved. Anime Action has 271 episodes, Unexplained has 242 items,
  and Mindbender Cinema has 26 films plus future title/year aliases. Four wide
  SVG/PNG logos pass source-render equality, complete-icon vertical centering,
  guide-size review and delivered native/public image hash checks.
  All 82 smart collections are nonempty; 35 focused native-Lucene fixtures pass.
  Actual scheduled content on all 77 channels passes 5,607 distinct membership
  checks. All original station/media identities, English/NVENC settings, hourly
  sync, recordings, integration links and guide-source settings survive. Five
  concurrent movie imports are preserved. Custom channels occupy 100–176,
  177–179 remain free, and multiviews remain at 180–189. All 484 Plex mappings
  and DVR identity survive, with all 77 guide names, numbers and logo URLs verified.
  All 4,410 checked native future programmes import; 4,484 current/future guide
  rows have no overlaps. Isolated configuration, database and artwork restores
  are verified before writes. Repository validation and whitespace checks pass
  with the existing generated PostHog skip and Stoat optional-example warning.

  Eight representative streams decode video and audio through Dispatcharr,
  including all three additions, bedtime, music, sports, Disney and DC animation.
  All three services are healthy. The final 1,192 indexed source-episode comparison
  has zero pending title, year or release-date mismatches after the deep scan.

  The final deep-scan index preserves all 157 baseline/current query memberships
  and passes the same 35 fixtures. Operation-only temporary backup, restore and
  snapshot copies are removed after acceptance; established backups and separate
  damaged-movie recovery backups are preserved.


- [x] T050 Expand Mindbender Cinema and Hanna-Barbera Classics from verified
  library omissions; guard cartoon collections against live-action namesakes,
  refine Adult Animation and Family Animation artwork, and verify preserved
  channels, native membership, guide delivery and playback.


- T050: Mindbender Cinema gains seven existing films: A Beautiful Mind,
  Ex Machina, Resolution, The Double, The Endless, The Illusionist and The
  Lighthouse. Premiere/release-year aliases preserve future eligibility without
  admitting the unrelated 2010 Illusionist or 2011 Double. All 33 current films
  appear in the regenerated playout. Hanna-Barbera Classics gains 34 original
  Wacky Races episodes, with eleven scheduled in the generated guide and the
  2017 remake excluded from the added branch. Four cartoon collections gain
  animation guards without losing any existing matches. All 82 collections remain
  nonempty. The 164 baseline/current native Lucene queries and 26 focused fixtures
  verify all existing members survive. All 77 actual schedules pass 5,236 distinct
  content-membership checks. Adult Animation gains a shaded dome, half-lidded
  eyes, curved grille and segmented neck. Family Animation gains an expressive
  fox emerging from a storybook. Both retain the frame, palette and wordmark,
  match their PNG exports, stay unclipped and center the complete icon at y=192.
  Full-size, 192 by 96 and 96 by 48 previews are reviewed. Native and public
  delivered PNGs match, and Plex uses the new image URLs.
  All channel identities/numbers, schedules, media IDs, English/NVENC settings,
  hourly refresh, guide-source/poster-bridge settings, Dispatcharr links,
  recordings and profiles survive. All 484 Plex mappings and DVR identity remain
  unchanged. All 4,396 checked native future programmes import; 4,474 current
  and future guide rows have no overlaps. Four representative streams decode
  picture and audio through Dispatcharr. All three services remain healthy.
  Isolated native database, configuration and artwork restores precede changes.
  Operation-only temporary backup/restore copies are removed after acceptance.
  Repository validation and generated Pages checks pass with the existing
  generated PostHog skip and Stoat optional-example warning. Whitespace and
  focused Markdown checks pass. The earlier corrupt-film quarantine and
  ambiguous two-file Expedition Unknown source record remain unchanged.


- [x] T051 Add Wes Anderson Cinema using native director credits and exact
  title/year fallbacks. Refine three television filters and the Documentary
  Series and Crime & Mystery logos. Verify natural order, original identities,
  complete guide mapping, delivered artwork, scheduled content and playback.


- T051: Wes Anderson Cinema is added at output 128, after Ghibli Theater, with
  thirteen available films/shorts. Native director credits automatically include
  future imports; exact title/year aliases cover missing credits, the 1994 Bottle
  Rocket short and the 2023 Dahl shorts while excluding unrelated same-name films.
  Documentary and quarantine guards remain explicit. Its custom pastel hotel,
  paired lamps and mountain silhouette use a centered three-line wordmark.
  Crime & Mystery gains fingerprint detail in its magnifier and a layered case
  file. Documentary Series gains a perforated filmstrip, mountain scene and globe.
  All three PNGs match safe accessible SVG sources, complete icon groups are
  centered at y=192 and guide-size previews remain legible. Native/public image
  bytes and all 78 Plex logo URLs match. Existing wordmarks and frames survive.
  Animation guards protect Scooby-Doo Cartoons and Transformers TV. A proposed
  unrestricted Fantasy-genre expansion is rejected after it adds 827 unrelated
  cartoon episodes; the accepted live-action Fantasy branch preserves all current
  Sci-Fi & Fantasy TV memberships while covering future correctly tagged imports.
  All 165 baseline/current native Lucene queries and 21 focused director, alias,
  remake, genre and quarantine fixtures pass. All 83 pools remain nonempty.
  Every prior member survives and all thirteen Wes titles appear in its playout.
  All 78 actual schedules pass 4,987 distinct content-membership checks.
  Custom channels occupy 100–177, with 178–179 reserved and multiviews unchanged
  at 180–189. Native channel numbers and identities remain intact. All 485 Plex
  mappings and DVR identity are verified after the output renumbering. All 4,448
  checked native future programmes import; 4,527 current/future guide rows across
  all 78 channels have no overlaps. Four affected streams decode picture and
  sound through Dispatcharr. All three services remain healthy. Original media
  IDs, schedule definitions, configuration, English/NVENC choices, hourly sync,
  guide-source/poster-bridge settings, links, profiles and recording rules survive.
  Isolated native database and affected artwork restores are verified before
  changes, including a stopped SQLite restore and separate channel fixture.
  Operation-only temporary backup, restore and snapshot copies are removed after
  acceptance; established and separate damaged-movie recovery backups remain.
  Repository validation, generated Pages and whitespace checks pass with the
  existing generated PostHog skip and Stoat optional-example warning.


- [x] T052 Correct the verified Jungle Book source rating, expand mature-animation
  and spooky-film curation, refine paired Comedy/Drama artwork, and verify source
  state, collection membership, guide delivery, playback and preserved channels.


- T052: the verified 1967 animated Jungle Book feature has its Plex content rating
  corrected from Not Rated to G and locked, following Disney's official film page.
  Source rating key, GUID, file bindings, watch/progress state, tags, dates and
  unrelated metadata survive. Only its ErsatzTV integration ETag is invalidated;
  the native scanner imports and indexes the source correction. It now matches
  Morning Cartoons, Family Animation and the unbound Animated Movies helper pool.
  Exact film/year aliases add the 1988 Grave of the Fireflies to Adult Animation
  Cinema and The Batman vs. Dracula (2005) to Spooky Toons & Tales.
  Fifteen concurrent movie imports are preserved and audited against all pools.
  Two unrated Alpha and Omega sequels gain animation-guarded family fallbacks,
  while the Great Wolf Games, Family Vacation, Howl-iday Adventure and Big Fureeze
  gain fitting sports, summer or winter aliases. Numbered and unnumbered title
  forms remain eligible without inventing ratings or broadening the whole series
  into seasonal channels. All fifteen new files are accessible, nonempty and have
  positive indexed durations. Seven distinct affected channel schedules rebuild.
  Both Comedy and Drama gain matching raised-rim masks, shaded faces, modeled
  noses and clearer mouth/eye detail. Their frames, wordmarks and palettes remain
  intact; complete icon groups center at y=192. Safe accessible SVGs match PNGs,
  full and small-guide previews pass, and delivered native/public PNGs and Plex
  logo URLs match.
  All 166 baseline/current native Lucene queries pass on the 13,400-document
  synchronized index, including 42 rating, remake, quarantine, new-import alias
  and seasonal-negative fixtures. Same-index query comparisons distinguish the
  reviewed rule additions from source-rating changes and fifteen new imports.
  All 83 pools remain nonempty and every prior member survives. All 78 schedules
  pass 4,772 distinct content-membership checks. All 4,443 checked native future
  programmes import; 4,520 current/future rows across all 78 guide channels have
  no overlaps. Eight representative streams decode video/audio through Dispatcharr.
  Original channel identities/numbers, schedule definitions, English/NVENC,
  hourly sync, library selections, guide-source/poster-bridge settings, links,
  profiles, recording rules and all 485 Plex mappings/DVR identity survive.
  All three services remain healthy. Verified native database, affected source
  metadata-bundle and artwork restores precede changes, with a fresh SQLite
  restore before the additional imported-film query updates. Operation-only
  temporary backup, restore and snapshot copies are removed after acceptance;
  established backups remain. Repository validation, generated Pages, Markdown
  and whitespace checks pass with the existing generated PostHog skip and Stoat
  optional-example warning. The source-rating reference is
  https://movies.disney.com/the-jungle-book-1967.


- [x] T053 Add curated cartoon-series film tie-ins to Nicktoons, Disney Cartoons
  and DC Animated Adventures. Refine Nicktoons and Retro Cartoons artwork while
  preserving existing programming, identities and guide integration. Verify
  native matches, future negatives, mixed-media schedules and playback.


- T053: three cartoon stations gain seventeen reviewed TV-series film tie-ins.
  Nicktoons adds the four SpongeBob films and three Rugrats films; Disney Cartoons
  adds DuckTales: The Movie, Stitch! The Movie, Leroy & Stitch and Tangled: Before
  Ever After. DC Animated Adventures adds six Batman/Superman/Teen Titans animated
  TV follow-ups. Exact year/title aliases cover future missing-credit imports
  without admitting unrelated live-action adaptations, adult DC films or
  making-of documentaries. Animation and quarantine guards apply to the film
  branches. Every previous episode match survives. All 166 baseline/current
  queries pass against the 13,400-document native index, with 40 focused alias,
  type, documentary, maturity and quarantine fixtures. All 83 pools remain
  nonempty and the only rule additions are the seventeen reviewed films.
  All seventeen files are accessible, nonempty and have positive durations.
  Generated playouts mix episodes with two distinct Nicktoons films, one Disney
  film and three DC films during the current guide window. One-item shuffle
  schedules and all existing schedule definitions remain unchanged.
  Nicktoons retains its original imported splat contour with custom clipped slime
  shading and highlights. Retro Cartoons gains a dimensional CRT cabinet, curved
  glass, smiling pie-cut eyes, tuner knobs, speaker grille and twin antennas.
  Frames, wordmarks and palettes survive. Safe local SVG references, matching PNG
  exports, unclipped bounds and complete-icon centering at y=192 pass. Full-size,
  192 by 96 and 96 by 48 previews pass, as do native/public delivered image hashes
  and Plex thumbnail URLs.
  All 78 schedules pass 4,900 distinct content-membership checks. All 4,447 checked
  native future programmes import; 4,528 current/future guide rows across all 78
  stations have no overlaps. Four affected streams decode picture and audio
  through Dispatcharr. All channel identities/numbers, prior media IDs, English/
  NVENC settings, hourly sync, library selections, guide-source/poster-bridge
  settings, links, profiles, recordings and all 485 Plex mappings/DVR identity
  survive. All three services are healthy. Native database and affected artwork
  restores are verified before changes. Operation-only temporary backup/restore
  and snapshot copies are removed after acceptance; established backups remain.
  Repository validation, generated Pages, focused Markdown and whitespace checks
  pass with the existing generated PostHog skip and Stoat optional-example warning.


- [x] T054 Expand reviewed classic/network and seasonal film programming, retain
  historical/rating boundaries, refine TV Variety and Documentary Movies artwork,
  and verify preserved matches, mixed-media schedules, guide delivery and playback.


- T054: four channel filters gain eighteen reviewed film matches: ten for
  Hanna-Barbera Classics, one for Cartoon Network Classics, two for Spooky Toons
  & Tales and five for Winter Wonderland. The Hanna-Barbera film branch keeps a
  pre-2000 boundary and family-rating guard, with exact aliases for reviewed
  unrated films and the classic Scooby-Doo Meets Batman DVD compilation. Exact
  year/title aliases cover future relevant imports without admitting unrelated
  remakes. Animation, documentary and quarantine boundaries pass forty fixtures.
  All 166 baseline/current queries pass against the 13,400-document native index;
  every previous match survives, all 83 pools remain populated and all eighteen
  new film matches have accessible nonempty files and positive durations.
  The current guide contains three new Hanna-Barbera films and all five Winter
  films. The Cartoon Network and Spooky additions are eligible for the normal
  shuffle but have not appeared in the current guide window. Existing schedule
  definitions and shuffle behavior remain unchanged.
  TV Variety gains a shaded television cabinet, four genre tiles, reflective
  bezel and detailed remote. Documentary Movies gains a shaded globe with
  continents and latitude/longitude grid, perforated film reels, camera controls,
  lens and tripod. Frames, wordmarks and palettes survive. Safe local SVG
  references, matching 768 by 384 PNG exports, unclipped bounds and complete-icon
  centering at y=192 pass. Full-size, 192 by 96 and 96 by 48 previews pass; native
  and public image hashes match and Plex guide thumbnail URLs are verified.
  All 78 schedules pass 4,999 distinct content-membership checks. All 4,411 checked
  native future programmes import; 4,490 current/future guide rows across all 78
  stations have no overlaps. All six affected streams decode picture and audio
  through Dispatcharr. All channel identities/numbers, media IDs, English/NVENC
  settings, hourly sync, library selections, guide-source/poster-bridge settings,
  links, profiles, recordings and all 485 Plex mappings/DVR identity survive.
  All three services are healthy. Native database and affected artwork restores
  are verified before changes. Operation-only temporary backup, restore and
  snapshot copies are removed after acceptance; established backups remain.
  Repository validation, focused Markdown and whitespace checks pass with the
  existing generated PostHog skip and Stoat optional-example warning.


- [x] T055 Expand reviewed Thanksgiving and holiday sitcom episode coverage,
  refine Morning Cartoons and Bedtime Cartoons artwork, and verify native
  matches, preservation, guide delivery and playback.


- T055: Thanksgiving Table gains the Thanksgiving episodes from Dino-Riders
  and The League plus New Looney Tunes' No Thanks Giving. Holiday Sitcom Shuffle
  gains four The League episodes: Ghost Monkey, Kegel the Elf, Thanksgiving and
  The 8 Defensive Points of Hanukkah. These are seven new channel memberships
  across six distinct episodes. Show-scoped holiday title/plot rules catch future
  imports without admitting unrelated dramas, Easter Island stories or ordinary
  episodes. Quarantine guards apply to both updated pools. All 166 baseline and
  proposed queries pass against the 13,400-document native index, all previous
  matches survive and all 83 pools remain populated. Thirty-three focused
  episode, future-import, unrelated-show, wrong-library and quarantine fixtures
  pass. Every added episode has accessible nonempty media and positive duration;
  all seven added memberships appear in the current generated schedules.
  Morning Cartoons gains a shaded cereal bowl, contrasting cereal rings,
  reflective spoon and smiling sunrise with cheek highlights. Bedtime Cartoons
  gains a layered crescent moon and shaded sleeping cat with tucked paw,
  highlighted tail, inner ears and whiskers. The complete wordmarks, frames,
  palettes and root attributes remain unchanged. Both icon groups are centered
  at y=192 with safe bounds. Safe local SVG references, matching 768 by 384 PNG
  exports, full-size and 192 by 96 / 96 by 48 visual previews pass. Native and
  public image bytes match the source exports and Plex guide thumbnails use the
  intended URLs.
  All 78 schedules pass 4,876 distinct content-membership checks. All 4,411 checked
  native future programmes import; 4,488 current/future guide rows across all 78
  stations have no overlaps. All four affected streams decode picture and audio
  through Dispatcharr. Channel identities/numbers, media IDs, English/NVENC
  settings, hourly sync, library selections, guide-source/poster-bridge settings,
  links, profiles, recordings and all 485 Plex mappings/DVR identity survive.
  All three services are healthy. Native database and affected artwork backups
  pass isolated restore verification before mutation. Operation-only temporary
  backup, restore and snapshot copies are removed after acceptance; established
  backups remain. Repository validation, focused Markdown and whitespace checks
  pass with the existing generated PostHog skip and Stoat optional-example warning.


- [x] T056 Expand Mindbender Cinema with reviewed library films, refine Sitcom
  Shuffle and Workplace Comedy artwork, and verify native membership, preserved
  state, guide delivery and playback.


- T056: Mindbender Cinema grows from 33 to 37 films with Unbreakable (2000),
  Split (2017), Glass (2019) and Synchronic (2019). Exact title/year aliases retain
  future imports with missing production credits without admitting Glass Onion,
  Synchronicity, unrelated films, documentaries or quarantined files. All 166
  baseline and proposed queries pass against the 13,400-document native index;
  every prior match survives and all 83 pools remain populated. Twenty-seven
  focused title/year, future-import, media-type, library, documentary and
  quarantine fixtures pass. All four added films have accessible nonempty media,
  positive durations and entries in the generated guide. Existing schedule
  definitions and shuffle behavior remain unchanged.
  Sitcom Shuffle gains a shaded sofa with tufted cushions, seat piping, curved
  arms and tapered feet beneath a laughing speech bubble. Workplace Comedy gains
  a dimensional desk and drawer, reflective monitor, keyboard, sticky note,
  paperwork, steaming smiling mug and padded swivel chair. Complete wordmarks,
  frames, palettes and root attributes remain unchanged. Both complete icon
  groups are centered within two source pixels of y=192 with safe bounds. Local
  SVG references, matching 768 by 384 PNG exports, full-size and 192 by 96 / 96 by
  48 visual previews pass. Native/public image bytes match the source exports;
  Plex guide thumbnails use the intended URLs.
  All 78 schedules pass 4,823 distinct content-membership checks. All 4,424 checked
  native future programmes import; 4,503 current/future guide rows across all 78
  stations have no overlaps. All three affected streams decode picture and audio
  through Dispatcharr. Channel identities/numbers, media IDs, English/NVENC
  settings, hourly sync, library selections, guide-source/poster-bridge settings,
  links, profiles, recordings and all 485 Plex mappings/DVR identity survive.
  All three services are healthy. Native database and affected artwork backups
  pass isolated restore verification before mutation. Operation-only temporary
  backup, restore and snapshot copies are removed after acceptance; established
  backups remain. Repository validation, focused Markdown and whitespace checks
  pass with the existing generated PostHog skip and Stoat optional-example warning.


- [x] T057 Bind four seasonal filters to the intended native libraries without
  changing current memberships, refine Movie Night and Crime Series artwork,
  and verify boundaries, preservation, guide delivery and playback.


- T057: Spooky Toons & Tales, Holiday Sitcom Shuffle, Thanksgiving Table and
  Spring & Easter now constrain movie and episode branches to their selected
  native library IDs. Native fixtures reproduce the previous unscoped episode
  matches and show why a quoted library name alone also admits a longer name.
  Exact ID guards reject foreign libraries, duplicate names, misleading name
  suffixes, wrong media types and quarantined items. Forty-eight focused checks
  pass, as do all 166 baseline/proposed queries against the 13,400-document native
  index. Every membership in all 83 collections remains unchanged; all pools
  remain populated. The four updated pools retain 718, 134, 28 and 13 items.
  Their 893 memberships belong to the intended movie or television library.
  Saving each Smart Collection invokes the native dependent-playout refresh.
  All 371 checked future programme rows retain every field except the regenerated
  primary key, including media, start/finish times and playback settings. Channel
  and media identities remain stable. Documentation now explains tokenized
  library names, exact native library IDs and disposable programme-row IDs.
  Movie Night gains a shaded clapperboard, reflective striped clapsticks,
  riveted hinge, recessed slate, ruled panels and beveled star. Crime Series
  gains a shaded fingerprint scanner with reflective glass, loop ridges,
  alignment corners, translucent scan band and status controls. Complete
  wordmarks, frames, palettes and root attributes remain unchanged. Both complete
  icon groups are centered within two source pixels of y=192 with safe bounds.
  Safe local SVG references, matching 768 by 384 PNG exports, full-size and
  192 by 96 / 96 by 48 previews pass. Native/public image bytes match source
  exports; Plex guide thumbnail URLs are verified.
  All 78 schedules pass 4,737 distinct content-membership checks. All 4,430 checked
  native future programmes import; 4,509 current/future guide rows across all 78
  stations have no overlaps. All six affected streams decode picture and audio
  through Dispatcharr. Channel identities/numbers, media IDs, English/NVENC
  settings, hourly sync, library selections, guide-source/poster-bridge settings,
  links, profiles, recordings and all 485 Plex mappings/DVR identity survive.
  All three services are healthy. Native database and affected artwork backups
  pass isolated restore verification before mutation. Operation-only temporary
  backup, restore and snapshot copies are removed after acceptance; established
  backups remain. Repository validation, generated Pages, focused Markdown and
  whitespace checks pass with the existing generated PostHog skip and Stoat
  optional-example warning.


- [x] T058 Improve display names and matching logo wordmarks, arrange the custom
  guide in natural browsing groups, and verify complete tuner mappings, station
  identities, programming and recording preservation across the live integration.


- T058: twenty-three stations gain clearer display names with distinct identities:
  Comedy Reels, Drama Theater, Reel Romance, Fantasy Realms Cinema, Sci-Fi Cinema,
  Western Trails Cinema, Encore! Music & Musicals, Silver Screen Classics,
  1980s/1990s Rewind Cinema, the 2000s/2010s/2020s Movie Vault stations, Family
  Toon Theater, Mission: Impossible Cinema, Planet of the Apes Cinema, Holiday
  Movie Mix, Channel Surf TV, On the Clock Comedy, Prime Crime TV, Fright Night TV,
  Unexplained Files and Adult Animation TV. Existing studio and franchise names
  remain recognizable. All twenty-three SVG titles and wordmarks match their
  installed display names. Original icons, frames, palettes and root attributes
  survive; only titles and text blocks change. Measured right-column text bounds
  fit and center at y=192. Local SVG references, matching 768 by 384 PNG exports,
  large previews and 192 by 96 / 96 by 48 thumbnails pass. All twenty-three native
  and public delivered image hashes match; Plex guide thumbnails use those URLs.
  Morning Cartoons occupies 100, Bedtime Cartoons 101 and Movie Night 102. The
  remaining guide groups movie genres, decades, studios and animation films,
  franchises, seasons, television and cartoons. Portlandia follows Sitcom Shuffle;
  TMNT sits beside Transformers TV and Anime Action. Seventy-seven existing output
  positions change through a collision-safe transaction. All 78 positions and
  names match the retained lineup manifest. Slots 178–179 remain free and all ten
  multiviews retain 180–189. Native source tuner numbers, playlist URLs, guide IDs,
  channel IDs and Dispatcharr UUIDs remain stable. Dispatcharr stream hashes use
  URL only; every existing stream hash survives the name changes, preventing
  duplicate stations on future playlist imports. Native and downstream display
  names and logo metadata agree. Source number order remains application-owned;
  the new browsing order is the Dispatcharr/Plex output lineup.
  All 83 native collection matches remain unchanged against the 13,400-document
  index. Queries, schedules, profiles, selected libraries and media identities
  survive. All 78 schedules pass 4,654 distinct content-membership checks. All
  4,657 checked future programme rows retain their original fields and IDs. All
  4,439 checked native future programmes import; 4,518 current/future guide rows
  across all 78 stations have no overlaps. Eight representative streams decode
  picture and audio across favorites, renamed genres/decades and repositioned TV.
  All 485 enabled Plex bindings, all 407 noncustom bindings, DVR identity and the
  empty Plex subscription set are verified. Dispatcharr stream links, profile
  memberships, recording rows and recurring rules survive. All services are
  healthy. Application-consistent database backups and all twenty-three affected
  artwork copies pass isolated restore checks before mutation. Operation-only
  temporary backup, restore and snapshot copies are removed after acceptance;
  the two superseded decade cache files are verified absent and established
  backups remain. Repository
  validation, generated Pages, focused Markdown and whitespace checks pass with
  the existing generated PostHog skip and Stoat optional-example warning.


- [x] T059 Apply exact selected-library boundaries across all remaining channel
  collections, refine Sci-Fi & Fantasy TV and Fright Night TV artwork, and verify
  preserved programming, names, order, mappings, guide delivery and playback.

  Acceptance: all 83 Smart Collections now use exact selected-library/type
  boundaries. All current memberships remain unchanged across the 13,400-document
  native index. Seventy-two synthetic fixtures reject foreign-library matches.
  Sci-Fi & Fantasy TV and Fright Night TV have refined, vertically centered
  artwork with preserved wordmarks, frames and palettes. Source PNGs match native
  and public delivered images and Plex thumbnails. All 78 channel identities,
  names, output positions and populated English/NVENC schedules survive. All 485
  Plex bindings, DVR identity, Dispatcharr links and recording rules survive.
  Six movie schedules regenerated during the native collection refresh; the other
  72 retain their future programming apart from disposable row IDs. Every new
  programme passes channel membership checks. There are no overlaps in 4,502
  current/future guide rows. Six representative streams decode video and audio.
  Database and affected artwork backups pass isolated restore checks before
  installation. Operation-only temporary copies are removed after acceptance.
  Repository validation passes with the existing generated PostHog skip and Stoat
  optional-example advisory. Evidence is retained privately under
  `ersatztv-refine-ten-20261020`.

- [x] T060 Add Clare's Nighttime Cartoons first in the guide, limited to four
  explicit series and related movies, improve the retained Bedtime Cartoons
  rotation, and verify artwork, content boundaries, existing stations and full
  Plex/Dispatcharr mapping preservation after the reorder.

  Acceptance: Clare's Nighttime Cartoons occupies output 100, followed by Morning
  Cartoons 101, retained Bedtime Cartoons 102 and Movie Night 103. Four manual
  collections reference only the exact Bob's Burgers, Futurama, Disenchantment
  and BoJack Horseman series identities. Bob's Burgers also contains its reviewed
  2022 film. Four Futurama movies are already available as series specials.
  New episodes expand under those identities; unrelated metadata cannot widen
  this personal station. One schedule item per series balances the rotation.
  Disenchantment and BoJack use Shuffle in Order. Every generated personal-station
  item belongs to the explicit allowed set, and all four series appear.
  Bedtime retains Archer and every original series, adds BoJack and the Bob's
  Burgers film, and schedules all five series. Its schedule uses the same explicit
  identity approach. All 77 other existing stations retain future programming.
  All previous native channel rows, artwork, library selections, media identities,
  settings and Smart Collection queries survive. All 79 stations have populated
  English/NVENC schedules. A three-line personal logo preserves the established
  centered cat/crescent design and passes full-size and guide-thumbnail review.
  Native and public image bytes match, and every Plex guide name and thumbnail
  agrees with the output lineup. The initial receipt reported 486 Plex mappings.
  T061 later found that a
  duplicate numeric identifier concealed the missing Adult Animation TV binding;
  that follow-up restores it and verifies unique rows, the full expected enabled
  set and every prior binding. The original DVR identity survives. All prior Dispatcharr channel rows, links, profile
  memberships, recordings and rules survive. Custom stations occupy 100–178,
  slot 179 remains free, and multiviews stay at 180–189. The complete native guide
  imports without overlaps. Clare, Morning, Bedtime and Movie Night all decode
  video and audio. Application-consistent backups pass isolated database/file
  restore checks before mutation; full ErsatzTV backup and fixture checks pass
  before native installation. Temporary operation copies are removed after
  acceptance, preserving established backups. Repository validation, generated
  Pages, focused Markdown and whitespace checks pass. Private receipts remain
  under `ersatztv-clare-20261020`.

- [x] T061 Expand retained Bedtime Cartoons with four additional library series
  and related South Park films, add four studio and five director stations with
  themed artwork and future-import aliases, preserve Clare's strict content,
  group the expanded guide, retain growth space and repair the missed Plex
  binding while verifying unique complete mappings and actual playback.

  Acceptance: Bedtime Cartoons remains 102 and retains its five existing series.
  South Park, Mike Tyson Mysteries, Brickleberry and Trailer Park Boys: The
  Animated Series add 464 episodes. Seven related South Park films/specials add
  to the existing Bob's Burgers film. The explicit schedule and its summary
  search agree on 1,220 items, excluding the South Park making-of documentary.
  One schedule item per series balances all nine shows. Clare's fixed references,
  four-item schedule, content and future programming remain unchanged.
  Nine new stations occupy grouped studio/director positions: Illumination
  Animation 131 with 14 films, Blue Sky Animation 132 with 8, Sony Animation
  Cinema 133 with 15, LAIKA & Aardman Cinema 134 with 8, Spielberg Cinema 136
  with 17, Tim Burton's Twisted Tales 137 with 12, Nolan Cinema 138 with 10,
  Ridley Scott Cinema 139 with 9, and Villeneuve Visions 140 with 7. Wes Anderson
  remains beside the director group at 135. The combined LAIKA/Aardman station
  includes credited CGI work as well as stop-motion. The new pools cover 99
  distinct films and 100 channel memberships. Production/directing rules and
  exact title/year aliases catch credited films and known alternate metadata.
  All ten updated/new searches pass against the 13,412-document native index.
  Five hundred forty synthetic checks cover aliases with unknown credits,
  exact-library boundaries, quarantine, release years and producer/franchise
  counterexamples. Every new scheduled movie belongs to its reviewed pool.
  All 88 stations have populated English/NVENC schedules. The other 78 existing
  stations retain their future programming. All prior native channel rows,
  artwork, media, selected libraries and settings survive; all previous schedule
  items remain, with only four additions to Bedtime. The Bedtime summary query is
  the only changed existing Smart Collection query. Nine new centered SVG/PNG
  logos pass full-size and 192 by 96 / 96 by 48 visual checks. All native/public
  delivered image hashes and Plex guide thumbnails match.
  Custom stations occupy 100–187, with 188–199 reserved. Existing local-news
  channels at 200–273 retain their numbers. The ten multiviews move to 280–289,
  the first free ten-channel block beyond those groups. All existing Dispatcharr
  UUIDs, stream links, profile memberships, recording rows and rules survive,
  allowing only reviewed output-number changes. All 495 unique enabled Plex
  mappings verify, including all 485 baseline bindings, nine new channels and
  the restored missing Adult Animation TV binding. Its former output 178 was
  missing from the enabled Plex map after T060; it is now enabled at 187. The
  prior receipt's count conflated duplicate identifiers. The owning README and
  private correction receipt record the stronger numeric/uniqueness check.
  DVR identity and the empty Plex subscription set survive. All 4,789 checked
  native future programmes import; 4,881 current/future guide rows have zero
  overlaps. Twelve streams decode picture and audio: all nine additions,
  Bedtime, Clare and Adult Animation TV. Services are healthy. Application-
  consistent backups and the full ErsatzTV configuration pass isolated
  database/file restore checks before installation, with a fixture migration
  before the live write. Operation-only backups and restore copies are removed
  after acceptance while established backups remain. Repository validation,
  generated Pages, focused Markdown and whitespace checks pass, with the existing
  generated PostHog skip and Stoat optional-example advisory. Private evidence
  remains under `ersatztv-bedtime-expand-20261020`.

- [x] T062 Expand Mindbender Cinema with eight reviewed library films, enforce
  Sports Cinema's opt-out across aliases, support Sony's alternate Scared Silly
  release year, refine Nolan/LAIKA-Aardman artwork and verify the complete lineup,
  restricted Clare content, current guide, preserved mappings and playback.

  Acceptance: Mindbender Cinema adds Upgrade, 10 Cloverfield Lane, The Cloverfield
  Paradox, The Usual Suspects, Gone Girl, The Girl on the Train, Blade Runner and
  Blade Runner 2049, expanding from 37 to 45 eligible films. Sports Cinema's exact
  opt-out label now encloses every alias branch; its 74 matches are unchanged.
  Sony Animation adds unknown-credit Scared Silly aliases for 2016 alongside
  existing 2015 aliases, preserving all 15 current matches. Both revised unions
  explicitly group the complete earlier query. Native parser fixtures caught an
  initially optional new branch before installation. All 184 previous/current
  queries pass against the 13,412-document index. All 92 prior pools preserve
  every match, with only eight Mindbender additions. Fifty-four synthetic checks
  cover the additions, foreign libraries, documentaries, quarantine, alternate
  years and opt-out behavior through ordinary and explicit sports aliases.
  The existing positive title aliases were also checked for silent omissions;
  the only unmatched present titles are intentional exclusions.
  Nolan's top gains rounded metallic surfaces, a threaded stem, layered rim and
  rotation arcs within an open maze. LAIKA/Aardman's clay dog gains paired eyes,
  shaded ears, shaped muzzle and knit detail beside a stitched button, thread and
  needle. Icon bounds center at y=192. Existing wordmark groups, frames, titles,
  palettes and root attributes survive. Local originals and native cache files
  pass byte-verified restore checks before replacement. Both PNGs match native
  and public delivery, and Plex thumbnails use the installed URLs. Full-size,
  192 by 96 and 96 by 48 previews pass visual review.
  Actual scheduled content on all 88 stations passes 4,896 distinct membership
  checks. All 92 pools remain nonempty within selected source libraries. Every
  manual collection, strict Clare reference and existing schedule item survives.
  The other 85 stations retain future programming; only three affected pools
  refresh their playouts. All 4,764 checked native future programmes import.
  The guide has 4,852 current/future rows with no overlaps. Plex's current
  provider-grid programme and times match native XMLTV on all three affected
  channels. All 495 unique enabled Plex bindings, DVR identity, 88 station names,
  positions, source stream identities/hashes, Dispatcharr links, profile
  memberships, recording rows, rules and guide sources survive. All 88 schedules
  remain populated, English and NVENC. Six streams decode picture and sound:
  Clare, Mindbender, Sports, Sony, LAIKA/Aardman and Nolan. Services are healthy.
  Database and affected artwork backups pass isolated restore checks before
  installation; operation-only backup, restore and index copies are removed
  after acceptance while established backups remain. Repository validation,
  generated Pages, focused Markdown and whitespace checks pass, with the existing
  generated PostHog skip and Stoat optional-example advisory. Private evidence
  remains under `ersatztv-refine-eleven-20261020`.

- [x] T063 Add Amblin, Blumhouse, Legendary, New Line and Warner Animation studio
  channels with future-import production rules, reviewed aliases and themed
  artwork. Start multiviews at 300, preserve the displaced news group's order,
  retain custom-channel growth space and verify complete unique Plex mappings,
  content, artwork, existing data, schedules and playback. Identify genuine A24
  and Don Bluth library gaps through title and original-title checks.

- T063: five stations occupy 135–139 in the grouped studio section: Amblin
  Movie Magic, Blumhouse After Dark, Legendary Cinema, New Line Cinema and
  Warner Animation Cinema. Their reviewed pools contain 36, 28, 28, 61 and 132
  films respectively. Production aliases and exact title/year fallbacks pass
  1,816 native Lucene fixtures covering future imports, incomplete credits,
  foreign libraries, quarantine, documentaries and unrelated franchise films.
  Warner requires animation and rejects reviewed live-action tagging mistakes.
  All five logos receive a second refinement pass. Inspected symbol-only paths
  correct the Legendary knot and New Line filmstrip with documented provenance.
  Amblin gains bicycle spokes, pedals and basket detail; Blumhouse gains house
  panels and a lit side window; Warner gains shield bevels and a detailed pencil.
  SVG safety, exact PNG exports, full-size and 192x96/96x48 review pass. Every
  new icon is vertically centered within one source pixel of y=192.
  Custom stations occupy 100–192 with 193–199 reserved. Multiviews move to
  300–309 and the following news block moves to 310–330 in its existing order.
  All 500 unique enabled Plex bindings and the original DVR identity survive.
  All 93 names, positions and thumbnails match. Existing channel UUIDs, stream
  links, profile memberships, recordings, rules and guide-source settings are
  preserved. All previous 88 native channels, filters, artwork, schedules,
  media and library selections remain exact, including Clare's strict references.
  All 93 schedules remain populated, English and NVENC. Every scheduled item on
  the five new stations belongs to its reviewed pool, and 5,011 prior future
  schedule rows survive. Native/public image hashes match the final exports.
  The final guide imports native future programmes without overlaps. Ten streams
  decode picture and sound, including all five studios, Clare, Bedtime, Adult
  Animation TV and moved multiview/news samples. Services and database checks
  pass. Isolated native PostgreSQL, Plex/ErsatzTV SQLite and affected file restores
  precede installation. Operation-only temporary copies are removed after final
  acceptance, preserving established backups. Repository validation, focused
  Markdown, generated Pages and whitespace checks pass with the existing
  generated PostHog skip and Stoat optional-example advisory. Title and original
  title checks establish 14 A24 and six Don Bluth gaps, while Swiss Army Man is
  confirmed present. Private evidence remains under
  `ersatztv-studios-two-20261020`.

- [x] T064 Refine all five new studio logos against inspected full-color screen
  references, including New Line's blue-lit filmstrip. Preserve centered guide
  layouts, station content and order. Verify isolated restores, source/export
  safety, small-size legibility, native/public artwork and Plex delivery.

- T064: five color references are inspected visually before editing. Amblin
  gains a pale moon and blue/orange wordmark accents; Blumhouse uses a teal-lit
  house H; Legendary uses silver shading with gold edging; Warner uses richer
  cobalt and layered gold; New Line uses the retained filmstrip contour with a
  dark celluloid face, visible perforations and a blue halo. All five SVG/PNG
  pairs pass active-content, scoped internal-gradient, title, dimension and
  exact-export checks. Full-size, 192x96 and 96x48 review passes. Icon and wordmark
  centers remain within one source pixel of y=192. Native and public hashes
  match all five final exports, and all 93 Plex names, positions and thumbnails
  match. All 500 unique enabled tuner mappings and DVR identity remain exact.
  All 93 native channels, filters, schedules, media and settings survive, along
  with 5,161 prior future programme rows. All 4,922 checked native future
  programmes reach Dispatcharr; 5,015 current/future rows have zero overlaps.
  New Line and Warner pass picture/audio decoding after the artwork refresh.
  Isolated native database and file restores precede installation, integrity
  checks pass and all services are healthy. Operation-only temporary copies
  are removed after acceptance while established backups remain. Repository,
  generated Pages, focused Markdown and whitespace checks pass with the existing
  generated PostHog skip and Stoat optional-example advisory. Private evidence
  remains under `ersatztv-studio-color-20261020`.

- [x] T065 Audit studio marks and refine Pixar, Ghibli, DreamWorks and Blue Sky
  against full-color references. Verify guide-size legibility, centering, safe
  exports and live artwork delivery while preserving all station data.

- T065: a contact-sheet audit of 13 studio stations selects Pixar, Ghibli,
  DreamWorks and Blue Sky for refinement. Inspected full-color Pixar, Ghibli,
  DreamWorks and Disney/Ice Age references inform neutral silver lamp parts,
  gray Totoro fur and cream belly with seven chevrons and a green leaf, blue-white
  moonlight, and a warm shaded acorn with crosshatched cap and bright ice facets.
  Existing frames, palettes and wordmarks remain exact. Four source/export pairs
  pass SVG safety, scoped gradient references, title/dimension and raster parity
  checks. Full-size and 192x96/96x48 visual review passes, with all four icon
  centers within one source pixel of y=192. Native and public artwork hashes
  match all four exports, and all 93 Plex station names, positions and thumbnails
  match. All 500 unique enabled tuner bindings and DVR identity remain exact.
  All channel definitions, filters, collections, schedules, settings, prior
  media/metadata and 5,151 prior future programme rows survive. Concurrent
  imports add ten films and metadata rows plus non-channel artwork; no prior
  media rows are missing or changed. The preservation check allows only these
  additive library rows and the four reviewed channel artwork paths.
  All 4,914 checked native future programmes import; 5,007 current/future rows
  have zero overlaps. Pixar and Ghibli decode picture and audio. Isolated native
  PostgreSQL, Plex/ErsatzTV SQLite and file restores precede installation.
  Database integrity and service health checks pass. Temporary operation-only
  backup/restore copies are removed after acceptance while established backups
  remain. Repository validation, focused Markdown, generated Pages and whitespace
  checks pass with the existing generated PostHog skip and Stoat advisory.
  Private evidence remains under `ersatztv-studio-audit-20261020`.

- [x] T066 Refine Disney, Illumination, Sony Animation and LAIKA/Aardman from
  full-color references. Give Bedtime Cartoons a distinct symbol while preserving
  Clare's sleeping cat/moon. Verify source exports, live artwork, full station
  preservation and guide/playback behavior.

- [x] T067 Extend the authorized color pass to Disney Cartoons, Star Trek,
  Nature & Wildlife, Kaiju and Jurassic Cinema, retaining recognizable forms,
  centered symbols, guide text and all channel behavior.

- T066–T067: ten SVG/PNG pairs refine the four requested studios, distinguish
  Bedtime Cartoons and add material colors to five additional stations. Inspected
  full-color references inform Disney's pink/gold castle and blue roofs,
  Illumination's yellow character with denim, metal goggle, gloves, boots and
  combed hair, Sony Pictures' spectrum ribbon as a studio-family identifier,
  and LAIKA/Aardman's cream clay dog with brown ears and a glossy dark nose.
  Bedtime Cartoons replaces its cat/moon with a sleepy retro television resting
  on a pillow and folded blanket. Clare's original sleeping cat/moon SVG and PNG
  remain byte-identical, and its exported native image matches the unchanged
  PNG. Additional refinements give Mickey black/cream features and a pink tongue,
  Star Trek a gold metal badge, Nature & Wildlife a brown stag with pale antlers,
  Kaiju charcoal scales with blue plates/breath, and Jurassic shaded ivory bone.
  Frames, wordmarks, titles and all unrelated source artwork remain exact.
  All ten pairs pass safe SVG, scoped/resolved gradient and clip references,
  dimension and raster-parity checks. Full-size, 192x96 and 96x48 reviews pass,
  and every changed icon is centered within one source pixel of y=192.
  Native/public image hashes match all ten exports; all 93 Plex channel names,
  positions and thumbnails match. All 500 unique enabled mappings and DVR
  identity remain exact. Channel definitions, filters, collections, schedules,
  media, metadata, settings and 5,128 prior future programme rows survive.
  All 4,922 checked native future programmes import; 5,015 current/future rows
  have zero overlaps. Bedtime and Disney Movies decode picture and audio.
  Isolated native database and file restores precede installation. Integrity
  and service health checks pass. Operation-only temporary copies are removed
  after acceptance, preserving established backups. Repository validation,
  focused Markdown, generated Pages and whitespace checks pass with the existing
  generated PostHog skip and Stoat advisory. Private evidence remains under
  `ersatztv-studio-night-20261020`.

- [x] T068 Add useful material and natural colors to eight remaining illustrated
  logos, preserve frames/text and unrelated artwork, and verify live delivery
  and station/data preservation.

- T068: eight SVG/PNG pairs receive material and natural colors. Alien/Predator
  separates a charcoal dome from a patinated mask; Apes uses dark fur and brown
  facial planes; Adult Animation TV uses silver panels and cream eyes/mouth;
  Sports uses a gold cup and green laurels; War & History separates olive fabric,
  ivory stone and steel; Encore uses chrome and gold notes; Fantasy uses emerald,
  ivory horns and warm fire; Fright Night TV uses weathered wood, slate, lit
  windows and a pale moon. Inspected color references are documented. Shapes,
  frames, wordmarks and all unrelated assets remain exact. All eight exports
  pass safe SVG, scoped/resolved references, dimension and raster-parity checks.
  Full-size, 192x96 and 96x48 reviews pass, with all icon centers within one
  source pixel of y=192. Native and public hashes match all eight final PNGs.
  All 93 Plex names, positions and thumbnails match; all 500 unique enabled
  mappings and DVR identity remain exact. Channel definitions, filters,
  collections, schedules, media/metadata and settings survive, together with
  5,146 prior future programme rows. Clare's unchanged native logo matches its
  unchanged source. All 4,892 checked native future programmes import; 4,989
  current/future rows have zero overlaps. Sports Cinema and Adult Animation TV
  decode picture and audio. Verified isolated database/file restores precede
  installation. Database integrity and service health checks pass. Temporary
  operation-only backup/restore copies are removed after acceptance, preserving
  established backups. Repository validation, focused Markdown, generated Pages
  and whitespace checks pass with the existing generated PostHog skip and Stoat
  advisory. Private evidence remains under `ersatztv-color-next-20261020`.

- [x] T069 Redesign Alien & Predator Cinema with more recognizable creature
  geometry, retaining guide layout and verifying artwork delivery and data.

- T069: Alien & Predator Cinema receives a new continuous Xenomorph skull
  profile with projecting toothed mouth, inner jaw, curved ribbed neck and hose.
  A larger Predator biomask has separate eye slits, broad brow, raised nose,
  cheek/chin vents, banded dreadlocks and three red targeting lights. The icon
  retains charcoal/patinated-metal shading, while the frame, name, wordmark and
  every unrelated asset remain exact. Safe SVG, scoped reference, dimension,
  raster parity and full/guide-size before-after checks pass. The icon is
  vertically centered at y=192. Native/public hashes match the final PNG, and
  all 93 Plex names, positions and thumbnails match. All 500 enabled mappings
  and DVR identity remain exact. All prior channel definitions, filters,
  collections, schedules, media/metadata and settings survive, together with
  5,163 prior future programme rows. All 4,917 checked native future programmes
  import; 5,009 current/future guide rows have zero overlaps. The revised station
  decodes picture and audio. Isolated database/file restores precede installation;
  integrity and health checks pass. Operation-only backup/restore copies are
  removed after acceptance while established backups remain. Repository,
  focused Markdown, generated Pages and whitespace checks pass with the existing
  generated PostHog skip and Stoat advisory. Private evidence remains under
  `ersatztv-alien-design-20261020`.

- [x] T070 Correct Amblin/Legendary omissions, expand the reviewed Kaiju pool,
  and refine Crime & Mystery/Fight Night artwork; verify native memberships,
  future schedules, integrations, playback and preservation before cleanup.

- T070: reviewed title/year fallbacks add Jurassic Park III to Amblin (36→37)
  and Jurassic World: Fallen Kingdom to Legendary (28→29), matching the studios’
  own catalogs while preserving Plex’s primary Universal credit. Kaiju grows
  from 12 to 15 with Monsters, Monsters: Dark Continent and Monster Hunter. All
  prior matches survive; 30 native-parser fixtures reject wrong years, types,
  libraries, documentaries and quarantined files. Crime & Mystery gains buff
  folder/cream paper, a red case tab and a steel magnifier; Fight Night gains
  red leather, an ivory cuff, metal piping and seam detail. Full and 192×96
  renders preserve wordmarks, frames and optical vertical centering. All 93
  stations and 97 pools pass native scope/membership checks (4,927 scheduled
  memberships); Clare’s exact references and 5,089 future programme rows on
  the other 90 stations survive. Private evidence: `ersatztv-refine-twelve-20261020`.
  The complete refreshed guide imports all 4,920 checked future programmes;
  5,012 current/future rows have zero overlaps. All 93 Plex names, positions and
  thumbnails match; all 500 enabled mappings and DVR identity remain exact.
  Public/native logo hashes match, and all five affected stations decode video
  and audio. Database integrity, isolated restores, service health, repository,
  Markdown, Pages and whitespace checks pass, with the existing generated
  PostHog skip and Stoat advisory. Temporary operation backup/restore copies
  are removed after acceptance; established backups remain.

- [x] T071 Complete five reviewed studio omissions and refine the five decade
  logos, preserving names/order, content boundaries and integrations; verify
  backups, native memberships, guide imports, artwork and playback.

- T071: Amblin gains Monster House and The Last Voyage of the Demeter (37→39).
  Legendary gains Dracula Untold, Steve Jobs and a 2007 alias for 300 (29→32),
  using reviewed studio catalogs and the library’s stored year. All prior
  matches remain. Thirty-five native-parser fixtures verify future imports,
  wrong-year/type/library rejection, documentary/quarantine guards and Ghibli’s
  exact 1988-versus-2005/2008 edition boundary. The five decade icons gain
  distinct tape, paper, metal, disc and screen colors while retaining names,
  layout, palette borders and measured vertical centering. Full-size, 192×96
  and 96×48 comparisons pass. All 93 stations and 97 content pools pass native
  membership checks, covering 4,928 scheduled memberships. Clare’s fixed
  references and 5,104 future programme rows on the other 91 stations remain.
  All seven affected stations decode video and audio. Private evidence is
  retained under `ersatztv-refine-thirteen-20261020`.

  A concurrent Plex refresh rematched the existing Grave of the Fireflies
  item to 2005. A video frame and 5,311.598-second probe confirm the file is
  animated, despite its 2005 path. No source metadata or media paths were
  changed: the user clarified that their queued 1988 replacement owns this
  repair. Its import remains pending. The existing Ghibli rule already catches
  a correctly identified 1988 import and excludes the live-action adaptations.
  The two refreshed source-art URLs and plot/rating changes are checked
  against Plex and recorded as concurrent changes, separate from this pass.

  Final integration checks match all 93 Plex names, positions and thumbnails.
  All 500 enabled mappings and DVR identity remain exact. All 4,909 checked
  future programmes import, and 5,001 current/future guide rows have no overlaps.
  Native/public artwork hashes, database integrity and service health pass.
  Repository, Markdown, Pages and whitespace checks pass with the existing
  generated PostHog skip and Stoat advisory. Temporary operation-only backups
  and isolated restores, including unused media-rename copies, are removed
  after acceptance. Established backups and the user’s download queue remain.

- [x] T072 Include the newly imported seasonal/sports films, correct Snow
  Buddies’ source sport genre, and refine On the Clock/Fast & Furious icons.
  Verify future-import boundaries, source metadata preservation, all channel
  pools, guide/artwork delivery and playback before removing temporary backups.

- T072: existing filters automatically catch three newly imported Air Bud
  sports sequels, Santa Buddies for Holiday Movie Mix and Snow Buddies for
  Winter Wonderland. Reviewed fallbacks add Spooky Buddies to Spooky Toons
  & Tales (718→719) and Snow Buddies to Sports Cinema (79→80). The sports
  fallback also covers all five Air Bud sports films with incomplete genres,
  preserves existing sports documentaries such as Nitro Circus, and rejects
  unrelated Buddies adventures. Fifty-three native-parser fixtures pass for
  future imports, years, types, libraries, quarantine and the sports opt-out.
  Snow Buddies gains a locked Sport genre in Plex with existing genres, file,
  GUID, rating key and user state preserved. A scoped ETag invalidation lets
  the native sync import the tag; the committed native index confirms it.

  On the Clock Comedy separates oak, graphite/metal, cream ceramic and teal
  fabric. Fast & Furious separates charcoal bodywork, chrome, reflective glass,
  cream quad headlights and amber indicators. The frames, wording, text layout
  and vertical icon centering remain. Full-size, 192×96 and 96×48 comparisons
  pass. Names and order stay unchanged. All 93 stations and 97 pools pass
  current native membership checks, covering 4,896 scheduled memberships.
  The new 1988 Grave of the Fireflies import (13435) matches Ghibli Theater.
  Its old misnamed entry remains; this operation does not rename or delete
  either file. All Dogs Go to Heaven and Treasure Buddies also arrive during
  verification. All prior media identities, metadata, file rows, collections
  and settings remain apart from the reviewed source genre and sync timestamp.
  Native startup cleans six portrait rows proven unreferenced by every
  artwork foreign key; no channel or referenced media art is lost.
  Evidence remains private under `ersatztv-refine-fourteen-20261020`.

  Final checks retain 5,010 prior future programme rows on the other 91
  stations. All 4,916 checked native future programmes import into Dispatcharr;
  5,009 current/future rows have no overlaps. All 93 Plex names, positions and
  thumbnails match; all 500 enabled mappings and DVR identity remain exact.
  Native/public logo hashes match and all four affected channels decode video
  and audio. Database integrity, foreign keys, verified isolated restores and
  service health pass. Repository, Markdown, generated Pages and whitespace
  checks pass with the existing generated PostHog skip and Stoat advisory.
  Operation-only backup, restore and native-index snapshots are removed after
  acceptance, preserving established backups and user-controlled downloads.

- [x] T073 Exclude Air Bud/Buddies from Sports Cinema, add a separate Family
  Movie Matinee beside Family Toon Theater, and preserve cartoon-only pools.
  Verify future franchise exclusions, family eligibility, artwork, all prior
  channel identities, the complete Plex map, guide imports and playback.

- T073: all 64 native-parser fixtures pass. The reviewed Sports
  pool excludes six current Air Bud/Buddies films (80→74) and the new Family
  Movie Matinee pool includes all 11 franchise films among 652 eligible movies.
  Existing family-animation, cartoon and seasonal queries remain exact. The
  new logo passes full-size and guide-size review. Repository validation,
  Markdown, Pages and whitespace checks pass with the existing generated
  PostHog skip and Stoat advisory. Database/file backups pass isolated restores.
  Family Movie Matinee is installed at output 126 with native source 9094,
  English audio, NVENC and the existing movie-channel quality settings. The
  prior custom outputs 126–192 move to 127–193 with identities preserved;
  194–199 remain free and multiviews remain at 300–309. All 501 unique enabled
  Plex bindings match the reviewed map. Existing channels, links, profiles,
  recordings, source metadata and files remain intact. The Sports playout is
  explicitly rebuilt after the query update to remove its stale franchise
  slots; 5,102 future schedule rows on the other 92 stations remain exact.
  All 94 stations and 98 pools pass content checks, 4,961 future native guide
  entries are imported without overlaps, and both changed stations pass
  picture/audio playback. Public and native artwork bytes match the new PNG.
  Services are healthy and SQLite integrity/foreign-key checks pass.
  Operation-only backup and restore copies are removed after acceptance;
  established backups remain. Private evidence is retained under
  `ersatztv-buddies-family-20261020`.

- [x] T074 Retire the missing Grave of the Fireflies entry after the user's
  verified 1988 replacement, rebuild affected playouts and clear File Not Found.

- T074: the obsolete 2005-named path is absent and its original Plex item returns
  404. The replacement has a distinct Plex/native identity, correct 1988 match,
  accessible 1080p HEVC media and a 5,313.984-second duration. An isolated native
  deletion fixture and complete configuration restore pass before the approved
  single-entry removal through ErsatzTV's trash. The replacement and every other
  media/metadata/file row remain exact against the reviewed cascade fixture.
  File Not Found now passes with zero missing items. All 98 native query pools
  retain their memberships except the retired item; the replacement qualifies
  for Movie Night, Drama, 1980s, War & History, Ghibli and Adult Animation.
  Rebuilt playouts cover 1980s Rewind Cinema, Ghibli Theater and Adult Animation
  Cinema; 5,113 future programme rows on the other 91 stations remain exact.
  All 94 stations pass content checks across 4,933 scheduled memberships, and
  4,962 checked future native programmes reach Dispatcharr without overlaps.
  The replacement and all three affected channels decode picture and audio.
  Channel definitions, filters, artwork, ordering, recording data and all 501
  original enabled Plex mappings/DVR identity remain intact. SQLite integrity
  and foreign keys pass, and all three services are healthy. The existing
  quarantined Transformers One zero-duration warning remains separate.
  Focused Markdown and whitespace checks pass. Verified operation-only database,
  configuration, index and restore copies are removed after acceptance;
  established backups remain. Private evidence and browser health proof are
  retained under `ersatztv-fireflies-replacement-20261020`.

- [x] T075 Make Morning Cartoons a Saturday-morning-style, episodes-only channel
  throughout the day, fix its Plex programme listings and refine its breakfast
  illustration while preserving the other stations.

- T075: the former duration schedule has roughly 18-hour offline gaps that
  become channel-name guide placeholders. The user's clarified episode-only
  policy replaces both timed blocks with one ordinary episode shuffle. The
  complete Morning query gains an episode boundary and excludes mature
  Fullmetal Alchemist programming, which remains available in anime stations.
  Its pool contains 3,651 episodes across 67 shows and zero films; all 97 other
  queries retain their previous memberships and continue accepting new imports.
  Thirteen native-parser fixtures reject current/future films, wrong libraries,
  quarantine, mature animation and live-action series while retaining the
  reviewed children's cartoon aliases. An isolated native container proves
  contiguous playout and individual show/episode XMLTV entries before installation.

  The live Morning playout has 186 episode entries with no gaps or custom-title
  grouping. All 94 stations pass content checks across 4,909 memberships; 4,981
  checked future native programmes reach Dispatcharr without overlaps. After
  Plex finishes refreshing, every show, episode and airtime over the next 24
  hours matches the native guide: 70 individual airings, no films, overlaps,
  gaps or channel-name placeholder blocks. Morning passes picture/audio playback.
  Its blue bowl, white milk and brighter cereal improve separation from the
  yellow sunrise and lettering; unchanged geometry and vertical centering pass
  full-size and small-guide review. Native/public PNG bytes and Plex thumbnails
  match. Existing station identities, names/order, Clare's strict references,
  recording data, runtime image/environment and all 501 enabled Plex mappings
  remain intact; 4,861 future rows on the other 93 stations remain exact.

  Additive library imports remain intact. Two concurrent Plex poster/timestamp
  refreshes for Annihilation and Gattaca are verified against Plex separately
  from this pass. SQLite integrity/foreign keys and service health pass. Native
  database/configuration, PostgreSQL, Plex and file backups pass isolated restores
  before writes. Repository validation passes using system Python's existing
  PyYAML, with the existing generated PostHog skip and Stoat advisory. Focused
  Markdown and whitespace checks pass. Verified operation-only backup, restore,
  index and isolated-container copies are removed after acceptance, preserving
  established backups. Private evidence remains under
  `ersatztv-morning-guide-20261021`.

- [x] T076 Add balanced Morning Cartoons rotation, silent station IDs,
  intermittent channel graphics and recurring Movie Night seasonal weekends.
  Verify isolated restores, disconnected scheduling fixtures, calendar selection,
  strict content boundaries, preserved station/DVR mappings, guide import and
  picture/audio playback. Record unavailable local trailer assets explicitly.

- T076: verified native, PostgreSQL and Plex backups through isolated restores
  before installation. A disconnected application fixture verifies the local
  scanner, balanced rotation, generated Next engine items and actual XMLTV
  programme fields. Season/episode marathon order omitted five specials-only
  shows in the first fixture; the installed grouped chronological rotation
  retains all 67 eligible shows and season-zero shorts, with multipart group
  sizing and individual episode listings. Morning remains episodes-only apart
  from its hidden three-second silent station IDs. Eleven selected daytime,
  movie and seasonal stations have individual ID collections/presets. Ninety-two
  channels use their own logo for ten seconds every fifteen minutes at 12%
  width and 55% opacity; both nighttime stations remain free of filler and
  graphics, with Clare's exact manual identities preserved. Movie Night has five
  recurring weekend alternates using scoped movie-only seasonal filters:
  Halloween, holiday, summer, spring and Thanksgiving. The shipped native
  calendar selector passes 730 dates, including weekday/off-season fallback.
  All five pools are populated, with future imports following their rules.
  All 94 native engine representations, the continuous episode guide, prior
  station definitions and media IDs, and 4,430 unrelated future programme rows
  pass preservation checks. Dispatcharr receives the updated guide without
  overlaps, and Plex's actual next-24-hour episode names and airings exactly
  match native XMLTV. All 501 enabled DVR bindings and recording rules remain
  intact. Four representative stations decode picture and audio. Runtime images,
  environment files, mounts and host settings are unchanged, and database
  integrity/foreign-key checks pass. No standalone trailers or sub-ten-minute
  films are imported, so trailer/short-film pre-rolls remain absent. Generated
  Pages, whitespace checks and `make validate` pass, retaining the existing
  generated-bundle skip and optional Stoat example advisory. Operation-only
  temporary backups/restores and fixture state are removed after acceptance;
  established backups remain.

- [x] T077 Add optional ErsatzTV maintenance: reproducible private recipes,
  derived-filter planning/reconciliation, guide correctness and restriction
  metrics/alerts, online verified daily backups and disconnected restore proof.
- [x] T078 Test and enable Next loudness normalization, English forced subtitle
  burn-in, rolling seven-day guides and stable future programming; verify
  transitions, concurrent viewers, cleanup, DVR/data/runtime preservation and
  complete repository validation before operation-only backup cleanup.

- T077–T078: enabled the optional observer, private recipes, guarded derived-filter
  reconciliation and verified daily ErsatzTV backup through the existing host
  maintenance timers. All 94 current programme guides agree across native XMLTV,
  Dispatcharr and Plex: zero missing channels, gaps, overlaps or field differences;
  restriction checks pass and recipe drift is zero. Five new alert rules pass
  native Prometheus fixtures, load healthy and receive the expected scraped
  metrics. The unchanged default configuration leaves ErsatzTV maintenance off.

  A disconnected restore rebuilds the omitted search index, generates all 94
  seven-day guides and preserves 5,609 prior future programme fields. LoudNorm
  tests with a 20 dB source difference measure -18.00 and -18.05 LUFS after Next
  encoding. The actual channel path selects, natively extracts and burns an
  English forced text track; the rendered caption and a continuous 28-second
  content/ID/content transition pass review. All 94 live channels use Forced
  English/Burn and the retained NVENC H.264/AAC profile uses LoudNorm at -18 LUFS.
  Existing audio format, bitrate, language and GPU settings remain intact.

  Seven-day continuation preserves 5,611 existing future programme records and
  all 13,977 media identities. Daily reset times are cleared. Initial subtitle
  extraction delays guide exports through the shared native queue; acceptance
  waits for all actual XMLTV exports, Dispatcharr imports and Plex's asynchronous
  import, rather than relying on database horizons or an early refresh response.
  Every custom station has actual Plex coverage six days ahead. Three viewers
  decode picture/audio on two stations; two viewers share one proxy upstream.
  Proxy sessions and both Next channel engines expire automatically after viewing.
  All 501 Plex mappings, Dispatcharr channel/link/membership/recording/rule rows,
  strict cartoon pools, images, environment, mounts and exposure remain intact.
  Native database integrity/foreign keys and service health pass.

  Twenty-six maintenance fixtures, native alert fixtures, generated documentation,
  whitespace checks and final `make validate` pass. Repository validation retains
  the existing generated PostHog bundle skip and optional Stoat example advisory.
  A fresh normal retained generation includes the final installed helpers,
  private configuration, recipes and verified application data. Operation-only
  backup/restore copies, temporary database dump and disconnected containers are
  removed after acceptance; normal backup generations and retention are preserved.
  Private reports and synthetic QA frames remain under
  `ersatztv-reliability-20261021`.


- [x] T079 Add Josh Gates: Expedition TV with a centered multicolor hat/compass
  logo and a scoped, future-import-aware series filter. Preserve existing channel
  identities, personal pools, recording rules and multiview positions.
- [x] T080 Simplify the episode-only Morning Cartoons query and add outer
  quarantine guards to fifteen active TV collections without losing legitimate
  members. Correct Plex observer time-filter encoding with regression coverage.

- T079–T080: the new station includes all 296 indexed episodes from Expedition
  Unknown, its Hunt for Extraterrestrials miniseries, Expedition X, Expedition
  Files and Josh Gates Tonight. Explicit future aliases cover Destination Truth,
  Search for the Afterlife, Megalodon, Shark Secrets and Expedition: Back to the
  Future. Forty-two native-analyzer fixtures verify future episode inclusion,
  library/type boundaries, quarantine exclusion and unrelated-series rejection.
  All sixteen changed filters preserve their legitimate native-index membership.
  The new schedule rotates all five shows, retains chronological episodes and
  multipart grouping, and has no gaps or overlaps. Eight seconds of video and
  audio decode through Dispatcharr. SVG and PNG exports pass full-size and
  guide-size review with the established 2:1 layout and vertical centering.

  Josh Gates occupies output 182 beside Unexplained Files. Twelve cartoon
  outputs move down one slot, retaining source identities and UUIDs. Custom
  outputs span 100–194, with 195–199 reserved; favorites and multiviews retain
  their positions. All 502 unique Plex bindings and the existing DVR identity
  and recording rules pass comparison. All 95 native, Dispatcharr and Plex
  programme guides agree, with zero missing channels, gaps, overlaps or field
  differences, healthy restrictions and zero recipe drift. Actual XMLTV coverage
  exceeds six days. Existing future airings and media identities are preserved.

  A large-guide comparison exposed an observer defect: URL-encoded time-filter
  names included an extra equals sign. Plex ignored the window and returned a
  truncated 20,000 rows from 20,566 programmes. Correct operator keys return all
  1,139 programmes in the requested two-hour window. The new regression fails
  before the fix and passes afterward; all 32 portable maintenance tests pass.
  Seven isolated checks using the installed helper sources pass before the
  scoped live correction. The observer still refuses truncated responses.


  Final acceptance also verifies actual Plex programme coverage six days ahead
  for all 95 channels, the new logo through Plex's 240 × 120 image endpoint,
  automatic expiry of the playback test, and unchanged container images,
  environment, mounts and exposure. A fresh normal retained generation verifies
  database restoration and file hashes with the updated private recipe. Native
  SQLite integrity and foreign keys pass, all original media identities remain,
  and existing recording rules are preserved. Operation-only backups, restore
  copies and the disconnected test container are removed after acceptance;
  established backup generations and retention remain intact.


## Current follow-up pass

- [x] T081 Trace and repair season-zero XMLTV identity collisions in Plex without
  changing correct source titles, season numbering, files or recording rules.
  Add a deterministic reproduction and verify affected specials and normal
  episodes separately in the actual Plex guide.
- [x] T082 Exclude nonfiction/talk programming from Sitcom Shuffle and animation
  from Prime Crime TV. Verify the exact removals, preserve every other current
  member and test future-import, source/type and quarantine boundaries with
  the native analyzer.
- [x] T083 Refine Star Wars, Jurassic and Planet of the Apes artwork. Preserve
  source attribution, station names, wordmarks, frames and centered icon bounds;
  verify full-size and small-guide renders. File Wes Anderson under Directors
  in the lineup manifest.
- [x] T084 Install the reviewed changes after verified native backup restores,
  compare station identities and persistent data, verify downstream guide and
  artwork behavior, clean operation-only copies and deliver through passing
  repository checks. Preserve the user's Mylar-wait waiver.


- T082–T083: the native analyzer checks all 104 literal collections against the
  captured 14,142-document index. Sitcom Shuffle changes from 2,325 to 2,167
  episodes, removing only the four nonfiction/talk series identified in the
  audit. Prime Crime TV changes from 1,993 to 1,669 episodes, removing only six
  animated series. Every other prior member survives. Nineteen native-analyzer
  fixtures pass future-import, source/library/type and quarantine boundaries.
  The source genres and other stations remain intact.

  Three SVG/PNG pairs pass deterministic export, safe local-reference checks,
  full-size and guide-size visual review. The existing wordmarks, frames and
  vertical centering remain intact; source licenses and adaptation notes are
  retained. Wes Anderson's manifest section is Directors, with its name and
  number unchanged.


- T084: verified isolated database restores and asset hashes precede installation.
  Final native SQLite integrity and foreign keys pass; every original media ID,
  all 95 populated playouts and 17,687 unrelated future programme records survive.
  All 95 native/Dispatcharr guides agree over the next day with no missing
  channels, gaps or overlaps. All 502 Plex mappings, the DVR identity, recording
  rules, channel links and memberships survive. The three public logos and
  Plex's 240 × 120 thumbnails pass. Both updated channels decode four seconds of
  video and audio; their sessions expire automatically. Container images,
  environment, mounts and exposure remain unchanged and services are healthy.

  Overnight imports advance stream `last_seen` timestamps and copy the three
  reviewed `tvg-logo` values into stream metadata. These exact expected changes
  are verified separately; every other persistent field matches the baseline.
  The initial Plex refresh still showed the old pools for the two changed
  channels. Their actual guide entries converge after import completion.

  T081 remains incomplete: five title substitutions in the final next-day Plex
  guide reproduce negative-season specials colliding with season-two identities.
  Source and Dispatcharr titles, episode numbering and air times are correct.
  No speculative rewrite is installed, and the correctness observer continues
  reporting the limitation. Correct source metadata and recording rules remain
  intact. Native analyzer, artwork checks, `make validate-changed` and
  `make ci-local` pass; the separate self-review finds no actionable regression.
  Both publication secret scanners pass. Final retained backups pass isolated
  restore verification; operation-only database/index/restore copies are removed
  while normal backup generations and retention are preserved.


### T081 acceptance — 2026-10-22

The optional Dispatcharr XMLTV compatibility flag is enabled after a fresh
application-consistent backup and isolated restore verification. It omits only
invalid negative `xmltv_ns` components when the existing onscreen label supplies
the matching season-zero or episode-zero identity. Source metadata, media files,
normal episode numbering and the native ErsatzTV guide remain unchanged. The
startup patch is reversible, idempotent and guarded by the complete reviewed
exporter hash; it defaults off in the portable example.

Deterministic imports into an isolated copy of the exact live Plex runtime
(1.43.5.11029) reproduce the collision and prove distinct stable identities after
the fix. Native exporter comparison changes only 58 invalid namespaces, preserving
every other XML field. The isolated full-guide check covers 95 custom channels
for 163.9 hours, including 57 specials and one explicit episode-zero airing.

After the live guide refresh, all 95 custom channels match the source across
162.3 hours with no missing, extra or duplicate programmes. All 55 season-zero
airings and the explicit episode-zero airing have their correct Plex season,
episode and GUID. All 502 DVR mappings, DVR identity, recording rules, durable
application records, source definitions and library media IDs are preserved.
Database integrity and foreign-key checks pass. The installed observer reports
zero differences, missing channels, gaps, overlaps or recipe drift; restrictions
remain healthy. Four seconds of video and audio decode through Dispatcharr pass.

The existing image, mounts, ports, networks and other environment values are
preserved. Normal retained backups before and after installation both pass
isolated restore verification; future configuration backups now include the
startup helper chain. The disconnected test container is removed after its test
sessions expire. Eleven exporter/bridge regression tests, twenty override tests,
`make validate-changed` and `make ci-local` pass. The separate self-review corrects
raw-byte source-guard handling; publication scans find no secrets. This acceptance
supersedes the earlier T081 pending-status note above.


## Network collections and library-only lineup — 2026-10-23

- [x] T083 Capture current native/Dispatcharr/Plex definitions, rows and images;
  take an application-consistent backup and prove isolated restoration before
  changing state. Preserve strict personal stations, mappings and recording rules.
- [x] T084 Add supported studio/director/franchise and network-themed stations
  with future-ready filters, distinct logos and organized output numbering.
  Verify literal queries against a stable copy of the native search index.
- [x] T085 Separate live-action Family Movie Matinee from Family Toon Theater,
  tighten Fantasy curation, and simplify equivalent filters with membership proof.
  Improve the identified small-title and wildlife logos at guide size.
- [x] T086 Hide and disable non-Ersatz channels without deleting their records,
  links, sources, profiles, artwork or rules. Retain mappings in a private exact
  restoration manifest; verify every visible tuner and Plex channel is custom.
- [x] T087 Verify native/Dispatcharr/Plex programme fields, all intended content,
  playback, restrictions and preservation; verify final backups and clean only
  operation-created copies. Deliver reviewed public assets/docs through CI,
  merge, mirror and documentation deployment.


Acceptance — 2026-10-23:

- Fourteen new stations bring the enabled custom lineup to 109. Nine network
  collections cover FX/FXX, Comedy Central, HBO/Max, Showtime, AMC, NBC comedy,
  Apple TV+, Prime Video and Netflix. Don Bluth, A24, James Cameron, Scorsese and
  Stargate provide the other five additions. Native network/director metadata,
  reviewed aliases and intentional Plex labels keep future imports eligible.
- A stable native search-index copy proves 45 shortened filters retain identical
  membership. Two curation updates separate 203 live-action family films from
  animation and remove three reviewed Fantasy exclusions. The corresponding
  Plex exclusion labels preserve all prior labels, files and watch state.
- Nineteen SVG/PNG pairs are installed and their public image bytes match.
  Clare remains first, Morning and Bedtime Cartoons follow, and the remaining
  stations follow the grouped manifest. Custom positions skip retained IPTV
  identities; source channel IDs and numbers remain unchanged.
- All 2,222 non-Ersatz channels remain in Dispatcharr with their stream links,
  profiles, logos, rules and original numbers. Their output and memberships are
  disabled, external source polling is paused, and quarantine mutation is paused
  without rewriting its history. Both tuner outputs and Plex publish only the
  109 custom stations. Plex drops mappings absent from the tuner; all 407 prior
  IPTV bindings remain exact in the private restoration manifest under normal
  backup coverage. The operator authorized these mapping changes.
- Native, Dispatcharr and actual Plex programme fields match across 167.3 hours
  for all 109 stations. The observer reports no missing channels, differences,
  gaps, overlaps or recipe drift. Strict personal restrictions remain healthy;
  62 season-zero and three episode-zero airings retain correct identities.
  Video and audio decode through Dispatcharr for Clare, FX and Stargate.
- Original source-media IDs, recording rules and persistent rows are preserved.
  Application images and container identities remain unchanged. Pre-update,
  numbering-adjustment and final backups pass isolated restore verification.
  Test sessions expire and container staging is removed. Normal retained
  backups and the IPTV restoration manifest are kept.
- Thirty-four maintenance tests, `make validate-changed` and `make ci-local`
  pass. The separate self-review fixes the dormant mapping-number collision,
  documents Plex's absent-channel pruning, and corrects stale artwork counts.
  Publication scans find no secrets. Delivery verifies the reviewed head,
  required CI, merge, mirror and Pages before removing the operation's remaining
  temporary copies and managed worktree.
