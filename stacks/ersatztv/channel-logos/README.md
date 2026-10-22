# Channel logo sources

The SVG originals own the 768 × 384 PNG exports. Keep the station names readable
at guide size and preserve each file's accessible title and scoped IDs.

Keep all icon decorations, including stars, inside one icon group. Leave the
frame and wordmark outside it so the complete artwork is measured together.

Center the visible icon group at y=192 in the 768 × 384 canvas, independently
of the frame and channel text. Use an icon-only transparent render to measure
its bounds, allowing at most two source pixels of centering error. Move the group
without scaling it or moving the wordmark, and check the result at guide size.

Long three-word station names use three centered text lines in the right-hand
column. Fit each line within that column, keeping short connectors attached to
adjacent words. Longer titles can use three balanced phrases. Measure the visible
text bounds at y=192 and review 192 × 96 and 96 × 48 previews; preserve the icon,
frame, wording and palette when changing only the wordmark.

Reference refinements retain the station palette and layout:

| Asset | Geometry or reference | Source terms |
| --- | --- | --- |
| `dc-universe-movies.svg` | Recolored and scaled 2016 DC monogram with a shaded face from [Wikimedia Commons](https://commons.wikimedia.org/wiki/File:DC_Comics_logo.svg), designed by [Pentagram](https://www.pentagram.com/work/dc-entertainment/story) | Source lists PD-textlogo |
| `mcu-cinema.svg` | Custom filled Avengers mark with corrected counter, arrow separation and a shaded face, following the inspected symbol from [SVG Repo](https://www.svgrepo.com/svg/29290/the-avengers) | Source lists CC0 |
| `star-trek-cinema.svg` | Custom beveled guide drawing of the asymmetric delta and elongated command star, following [Star Trek's insignia reference](https://www.startrek.com/news/starfleet-insignia-explained) | Custom SVG geometry |
| `pixar-movies.svg` | Custom articulated lamp with conical shade, elliptical opening, jointed rods and spring, plus Luxo ball with contrasting stripe and star, following [Pixar's Luxo Jr. reference](https://www.pixar.com/luxo-jr/) | Custom SVG geometry |
| `dreamworks-animation.svg` | Recolored fisher/moon contours from [Logotyp.us](https://logotyp.us/get/dreamworks/), with the source wordmark omitted, shaded moon and reinforced fishing rod/line | Source permits personal/educational use; commercial use requires owner verification |
| `cartoon-network-classics.svg` | Recolored CN tiles and lettering from [Wikimedia Commons](https://commons.wikimedia.org/wiki/File:Cartoon_Network_2010_logo.svg) | Source lists PD-textlogo |
| `transformers-tv.svg` | Filled Autobot plates and contrasting seams derived from the inspected outline from [SVG Repo](https://www.svgrepo.com/svg/104313/autobots), filled for guide-size legibility, with shaded armor plates and edge highlights | Source lists CC0 |
| `ghibli-theater.svg` | Custom filled Totoro silhouette with contrasting belly, eyes, whiskers and chevrons following [Studio Ghibli's film reference](https://www.ghibli.jp/works/totoro/) | Custom SVG geometry |
| `007-cinema.svg` | Recolored 007 gun mark from [Wikimedia Commons](https://commons.wikimedia.org/wiki/File:007_Logo.svg), enlarged within a custom segmented gun-barrel frame | Source lists PD-textlogo |
| `star-wars-cinema.svg` | Recolored and scaled [Font Awesome Rebel Alliance icon](https://github.com/FortAwesome/Font-Awesome/blob/6.x/svgs/brands/rebel.svg) by Fonticons, Inc. | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/), [Font Awesome license](https://fontawesome.com/license/free); color and scale adapted for the station, with clipped warm red shading and rim highlights |
| `nicktoons.svg` | Recolored splat silhouette from [Wikimedia Commons](https://commons.wikimedia.org/wiki/File:Nickelodeon_splat_logo_(variation).svg), with source lettering omitted and custom clipped slime shading/highlights | Source lists PD-textlogo |
| `disney-cartoons.svg` | Custom Mickey face with round ears, forehead mask, oval eyes, nose and smile, following [Disney's character reference](https://mickey.disney.com/) | Custom SVG geometry |
| `fight-night-cinema.svg` | Custom shaded leather boxing glove with padded knuckles, curved thumb, palm seam and contrasting laced cuff | Custom SVG geometry |
| `scooby-doo-movies.svg` | Custom turquoise and gold SD collar tag with split ring, collar strip, beveled diamond rim and filled monogram | Custom SVG geometry |
| `scooby-doo-cartoons.svg` | Custom Mystery Machine with shaded blue/green bodywork, sloping cab, reflective windows, door seams, bumper, tire hubs and orange flower | Custom SVG geometry |
| `wizarding-world-cinema.svg` | Custom shaded Deathly Hallows medallion with beveled triangle edges, tangent ring, central wand and sparks | Custom SVG geometry |
| `middle-earth-cinema.svg` | Custom shaded Gondor shield with a contrasting White Tree, gold crown and one arc of seven stars | Custom SVG geometry |
| `looney-tunes.svg` | Custom shaded Bugs Bunny face with tapered ears, expressive eyes, muzzle, open grin, buck teeth and filled concentric title rings | Custom SVG geometry |
| `kaiju-cinema.svg` | Custom Godzilla-inspired silhouette with contrasting ribbed belly and shaded dorsal plates, teeth, claws, long tail, buildings and atomic breath | Custom SVG geometry |
| `nature-wildlife.svg` | Recolored and scaled [Stag Head](https://game-icons.net/1x1/lorc/stag-head.html) by Lorc | [CC BY 3.0](https://creativecommons.org/licenses/by/3.0/); color and scale adapted, with custom clipped face/antler shading, eyes, nose and muzzle detail |
| `jurassic-cinema.svg` | Recolored and scaled [T. rex Skull](https://game-icons.net/1x1/delapouite/t-rex-skull.html) by Delapouite | [CC BY 3.0](https://creativecommons.org/licenses/by/3.0/); color and scale adapted for the station, with clipped bone ridges, jaw highlights and deeper recess shading |
| `hanna-barbera-classics.svg` | Custom Flintmobile with shaded stone rollers, wood frame, folded canvas roof, seat, steering column and foot propulsion | Custom SVG geometry |
| `die-hard-cinema.svg` | Custom filled Nakatomi Plaza tower with contrasting glass faces, window bands and stepped roof following [Johnson Fain's Fox Plaza photographs](https://www.johnsonfain.com/projects/architecture/commercial/fox-plaza/) | Custom SVG geometry; reference photograph is not included in the asset |
| `planet-of-the-apes.svg` | Custom shaded ape face with individual fur highlights, heavy brow, inset amber eyes and a modeled copper/cream muzzle | Custom SVG geometry |
| `holiday-movies.svg` | Custom shaded evergreen, garland, ornaments and gold star | Custom SVG geometry |
| `halloween-horror.svg` | Custom shaded ribbed jack-o'-lantern with a textured stem, leaf and lit carved eyes and mouth | Custom SVG geometry |
| `spooky-toons-tales.svg` | Custom shaded friendly ghost holding a pumpkin, with expressive eyes, sheet highlight and two stars | Custom SVG geometry |
| `holiday-sitcom-shuffle.svg` | Custom filled gift television with contrasting screen, festive garland and bow | Custom SVG geometry |
| `winter-wonderland.svg` | Custom filled snow globe with shaded base, reflection, snowman, scarf, hat and falling snow | Custom SVG geometry |
| `thanksgiving-table.svg` | Custom shaded roast turkey with wing, drumstick, bone, herbs, filled platter and steam | Custom SVG geometry |
| `summer-vacation.svg` | Custom paneled beach umbrella, highlighted sun, striped fabric deck chair, sand bank and layered waves | Custom SVG geometry |
| `spring-easter.svg` | Custom woven basket with patterned eggs and a peeking rabbit face and ears | Custom SVG geometry |
| `fantasy.svg` | Recolored and scaled [Dragon Head](https://game-icons.net/1x1/lorc/dragon-head.html) by Lorc | [CC BY 3.0](https://creativecommons.org/licenses/by/3.0/); color and scale adapted, with custom clipped shading, eye and flame |
| `comedy.svg` | Custom laughing theatre mask with a raised rim, shaded cheeks, modeled nose and inset tooth grille | Custom SVG geometry |
| `drama.svg` | Custom tragedy mask with a raised rim, shaded face, highlighted tear and inset frown | Custom SVG geometry |
| `crime-mystery.svg` | Custom layered case file and magnifying glass with contrasting fingerprint ridges | Custom SVG geometry |
| `family-animation.svg` | Custom smiling fox emerging from an open storybook, with contrasting muzzle, inset ears and a star | Custom SVG geometry |
| `action-adventure.svg` | Custom folded treasure map with terrain marks, shaded folds, four-point compass, route and destination | Custom SVG geometry |
| `documentaries.svg` | Custom shaded globe with continents, latitude/longitude grid and detailed motion-picture camera with perforated reels and tripod | Custom SVG geometry |
| `documentary-series.svg` | Custom perforated documentary filmstrip with mountain landscape and globe | Custom SVG geometry |
| `tv-mix.svg` | Custom shaded television with four genre tiles, inset controls, reflective bezel and detailed remote | Custom SVG geometry |
| `retro-cartoons.svg` | Custom shaded CRT cabinet with curved glass, pie-cut cartoon eyes, tuner knobs, speaker grille and twin antennas | Custom SVG geometry |
| `morning-cartoons.svg` | Custom shaded cereal bowl with contrasting cereal rings, reflective spoon and smiling sunrise with cheek highlights | Custom SVG geometry |
| `disney-movies.svg` | Custom shaded five-turret castle with contrasting roofs, archway and gate, stone details and shooting-star arc | Custom SVG geometry |
| `dc-animated-adventures.svg` | Reuses the inspected 2016 DC monogram above, framed by a filled animation cel with contrasting perforations and a shaded pencil | Monogram source lists PD-textlogo; framing is custom SVG geometry |
| `fast-furious-cinema.svg` | Custom muscle-car front with quad headlights, grille and hood-mounted blower | Custom SVG geometry |
| `adult-animation.svg` | Custom antenna robot with shaded metal dome, half-lidded eyes, curved tooth grille and segmented neck | Custom SVG geometry |
| `bedtime-cartoons.svg` | Custom sleepy retro television resting on a pillow and folded blanket, with closed cartoon eyes, tuning knobs, speaker grille and sleep marks | Custom SVG geometry |
| `after-dark-tv.svg` | Custom shaded haunted house with layered roofs, divided glowing windows, brick details, ajar door, moon, bats and bare tree | Custom SVG geometry |
| `sitcom-shuffle.svg` | Custom shaded sofa with tufted cushions, seat piping, curved arms and tapered feet beneath a laughing speech bubble | Custom SVG geometry |
| `workplace-comedy.svg` | Custom dimensional desk with drawer, reflective monitor, keyboard, sticky note, paperwork, steaming smiling coffee mug and padded swivel chair | Custom SVG geometry |
| `western-movies.svg` | Custom pinched cowboy hat, curved brim and sheriff badge | Custom SVG geometry |
| `war-history.svg` | Custom shaded helmet and dog tags beside a filled classical column | Custom SVG geometry |
| `thriller-theater.svg` | Custom shaded ajar door, concealed figure and broad shaft of light | Custom SVG geometry |
| `sci-fi-series.svg` | Custom shaded portal arch with inset glowing trim and rune details, a dimensional rocket with window and fins, layered exhaust and star | Custom SVG geometry |
| `80s-movies.svg` | Custom horizontal VHS cassette with tape window, reels, label and molded housing | Custom SVG geometry |
| `90s-movies.svg` | Custom filled rental case and VHS cassette | Custom SVG geometry |
| `2000s-movies.svg` | Custom filled disc case and reflective optical disc | Custom SVG geometry |
| `movie-musicals.svg` | Custom shaded microphone with reflective grille casing, pivot joints, filled stand base and music notes | Custom SVG geometry |
| `romance.svg` | Custom shaded heart with highlight inside a perforated film frame | Custom SVG geometry |
| `sports-cinema.svg` | Custom shaded trophy with reflective cup, inset star, filled base and inset plaque and laurel leaves | Custom SVG geometry |
| `classic-cinema.svg` | Custom shaded twin-reel movie camera with reel perforations, housing controls, dimensional lens and tripod | Custom SVG geometry |
| `movie-night.svg` | Custom shaded clapperboard with reflective striped clapsticks, riveted hinge, recessed slate, ruled panels and beveled star | Custom SVG geometry |
| `crime-series.svg` | Custom shaded fingerprint scanner with reflective inset glass, contrasting loop ridges, alignment corners, translucent scan band and status controls | Custom SVG geometry |
| `sci-fi.svg` | Custom filled striped planet, broad orbital ring, moon and stars | Custom SVG geometry |
| `portlandia.svg` | Custom bird perched over a bicycle, following the series' bird and Portland cycling themes | Custom SVG geometry |
| `teenage-mutant-ninja-turtles.svg` | Custom four turtle faces with blue, red, purple and orange masks | Custom SVG geometry |

Seven additional station marks use custom SVG geometry: a shaded LEGO-style brick,
an elongated alien head with a dreadlocked Predator mask, a shaded comic book
with web-mask, hammer and green-fist panels, a late-night animation cel with an
expressive cartoon face, a reel-to-reel self-destruct recorder, a tablet, and a
streaming television.
Their complete icon groups are centered at y=192 and their wordmarks follow the
same measured two-line or three-line layout as the existing suite.

Imported vector geometry is limited to inspected paths. Source document types,
metadata, IDs and external references are excluded from the station assets.

Wes Anderson Cinema uses custom symmetrical pastel hotel architecture, mountain
silhouettes, paired lamps and a three-line wordmark. Its complete icon group is
centered at y=192 with the same guide-size checks as the existing suite.


## Display names and guide order

[`lineup.json`](lineup.json) owns the example display names, artwork slugs and
Dispatcharr/Plex output order. Keep the slugs stable when changing a display
name, and update the SVG title, wordmark and PNG export together. Resolve the
existing native channel, Dispatcharr UUID and Plex tuner bindings from the live
inventory before changing an installed lineup. Source tuner numbers and media
identities remain application-owned.

Clare's Nighttime Cartoons leads the custom guide, followed by Morning Cartoons
and Bedtime Cartoons. Movie Night then leads into movie genres, decades, studios
and animation films, franchises,
seasonal programming, television and cartoons. Portlandia sits beside Sitcom
Shuffle; Teenage Mutant Ninja Turtles sits beside Transformers TV and Anime
Action. Custom stations occupy 100–194, 195–199 remain reserved, and multiviews
occupy 300–309 after the existing local-news groups. The following news block
occupies 310–330, preserving its original order.

Use playful names where the subject remains clear: Comedy Reels, Reel Romance,
Silver Screen Classics, Prime Crime TV and Fright Night TV. Decade names use all
four year digits, including 1980s Rewind Cinema and 1990s Rewind Cinema. Use TV
or Cinema where it distinguishes a film station from a series station. Existing
studio and franchise names stay recognizable.


Clare's Nighttime Cartoons uses a curled amber tabby cradled by a shaded lavender
crescent. Contrasting cream paws and muzzle, pink inner ears, a wrapped tail and
closed eyes keep the sleeping pose readable at guide size. The complete icon is
vertically centered beside the three-line personal wordmark. Its schedule uses
explicit series identities for Bob's Burgers, Futurama, Disenchantment and BoJack Horseman, plus
reviewed related films. It does not use broad genre or title searches. New episodes
under those identities remain eligible without admitting other series. The
retained Bedtime Cartoons also includes Archer, South Park, Mike Tyson Mysteries,
Brickleberry and Trailer Park Boys: The Animated Series, with one schedule item
per series. Related South Park films and specials are explicitly selected; its
making-of documentary is excluded.


The additional studio marks use a silver-goggled yellow character for
Illumination, an acorn and ice shelf for Blue Sky, a spectrum-ribbon family identifier for
Sony, and a sewn button with a clay dog for LAIKA/Aardman. The combined
LAIKA/Aardman station includes credited CGI productions as well as stop-motion.
Spielberg uses a bicycle against the moon, Tim Burton a gothic spiral hill,
Nolan a spinning top within a maze, Ridley Scott a folded-paper unicorn, and
Villeneuve a desert, planet, monolith and small aircraft. All nine marks retain
the suite's 2:1 frame and centered icon/wordmark columns. The director stations
follow directing credits rather than production credits. The additional studios
sit after Ghibli, with the director group beside Wes Anderson.


The Nolan refinement adds a rounded machined-metal top, threaded stem, layered
rim and rotation arcs within an open-path maze. The LAIKA/Aardman refinement
adds paired clay-dog eyes, long shaded ears, a shaped muzzle, stitched button,
thread and needle. Their full icon groups remain vertically centered, and the
existing frame, title, wordmark and palette remain unchanged.

The five additional production-studio stations use a moonlit bicycle and open
book for Amblin, a dimensional BH house for Blumhouse, the interlaced Legendary
knot, New Line's diagonal filmstrip and a beveled WB shield with an animator's
pencil. All five retain the centered 2:1 frame and measured guide-size wordmarks.
Amblin's bicycle includes spokes, pedals and a woven basket. Blumhouse has
rooflines, wall panels and a lit side window. The Warner pencil includes a
ferrule, eraser and graphite tip.

| Asset | Geometry or reference | Source terms |
| --- | --- | --- |
| `legendary-cinema.svg` | Recolored symbol-only paths from [Wikimedia Commons](https://commons.wikimedia.org/wiki/File:Legendary_Entertainment_logo.svg), sourced there to Legendary's website | Source lists PD-textlogo |
| `new-line-cinema.svg` | Recolored symbol-only path from [Wikimedia Commons](https://commons.wikimedia.org/wiki/File:New_Line_Cinema.svg), sourced there to New Line publicity downloads | Source lists PD-textlogo |

Studio filters follow production credits and reviewed title/year aliases rather
than a distributor's whole catalog. Warner Animation also requires animation
and excludes reviewed live-action adaptations with misleading tags. Future
films enter through the production aliases, while exact title/year fallbacks
cover reviewed films with incomplete credits.

The color-reference pass preserves the studio symbols and guide layout while
using Amblin's blue/orange accents and pale moon, Blumhouse's teal-lit house H,
Legendary's silver face with gold edging, Warner's cobalt field and gold shield,
and New Line's dark filmstrip against a blue halo. Internal scoped gradients
provide the lighting without embedded raster images or external references.
The filmstrip silhouette and perforations stay visible at 96 × 48.

Color references inspected separately from the imported vector paths:
[Amblin](https://www.filmaffinity.com/en/name.php?name-id=933495875),
[Blumhouse](https://www.thepopverse.com/blumhouse-blumfest-2023-jason-blum-horror-panel-livestream-nycc-new-york-comic-con-2023-empire-stage),
[Legendary](https://filmstories.co.uk/news/legendary-entertainment-reportedly-considering-a-split-from-warner-bros/),
[Warner](https://www.thecomposerworks.com/composers/adam-price/) and
[New Line](https://www.dailymotion.com/video/xhwby1).

The studio audit retains the frames and wordmarks while refining four symbols.
Pixar's articulated lamp uses a silver reflector, neutral metal arms and visible
joint bolts, beside the yellow ball with its blue stripe and red star. Ghibli's
Totoro uses gray fur, a cream belly, seven chevrons and a green head leaf.
DreamWorks retains the inspected fisher/moon contours with blue-white moonlight.
Blue Sky uses a shaded acorn, crosshatched cap, bare stem and bright ice facets.
All four icon groups remain centered at y=192 and readable down to 96 × 48.

Color and material references: [Pixar's Luxo Jr.](https://www.pixar.com/luxo-jr),
[Ghibli's Totoro](https://www.ghibli.jp/works/totoro/),
[DreamWorks' screen ident](https://www.gizmodo.jp/2022/11/dreamworks-new-logo-animation.html)
and [Disney's Scrat artwork](https://www.disneylatino.com/novedades/top-5-los-divertidos-animales-que-hicieron-historia-en-disney).
These refinements add no embedded raster files or external SVG references.

During artwork-only operations, verify prior media rows by identity and allow
concurrent library imports as additions. Added movie metadata and non-channel
artwork are library growth, not a reason to restore an older database. Preserve
all prior rows, require channel artwork changes to match the reviewed asset list,
and keep complete channel, collection, schedule and tuner comparisons exact.

Disney Movies uses warm pink/gold castle stone, blue roofs and lit windows from
[Disney's screen-logo reference](https://thewaltdisneycompany.com/news/moana-live-action-cast/).
Illumination uses yellow skin, blue overalls, silver goggles, dark gloves, boots,
combed hair and visible teeth following [licensed Stuart artwork](https://minionrush.com/).
Sony Animation uses Sony Pictures' spectrum ribbon as a studio-family identifier,
following [Sony's full-color press mark](https://www.prnewswire.com/news-releases/sony-pictures-entertainment-receives-leed-gold-certification-for-culver-city-lot-office-project-101807818.html).
The ribbon replaces the generic play/slate motif. LAIKA/Aardman retains its sewn
button and refines the clay dog with cream, brown ears and a glossy dark nose,
following [Aardman's Gromit reference](https://www.aardman.com/film-tv-games/wallace-gromit/).

Bedtime Cartoons uses a sleepy retro television on a pillow and folded blanket.
Its closed screen eyes, tuning knobs and sleep marks distinguish it from Clare's
Nighttime Cartoons, which retains the sleeping cat and crescent moon. Neither
station's wording, content, schedule or position changes with this artwork pass.

The additional material-color pass gives Disney Cartoons black/cream Mickey
features and a pink tongue, Star Trek a gold metal delta with dark command star,
Nature & Wildlife a brown stag with pale antlers, Kaiju charcoal scales with icy
blue plates and breath, and Jurassic Cinema shaded ivory fossil bone. Their
existing geometry, frames and wordmarks remain intact. Color references include
[Mickey](https://www.cartonionline.com/en/characters/topolino.html),
[a licensed Starfleet badge](https://www.superherostuff.com/star-trek/pins/star-trek-command-badge-pin.html?itemcd=pinstcmmnd)
and [Godzilla's practical-effects colors](https://www.slashfilm.com/1493064/stolen-godzilla-suit-washed-up-on-japans-beaches/).

The next material-color pass retains existing icon geometry, frames and text:
Alien/Predator uses a charcoal dome and contrasting patinated mask; Planet of
the Apes uses dark fur and natural brown facial planes; Adult Animation TV uses
silver robot panels and cream eyes/mouth; Sports Cinema uses a gold cup with
green laurels; War & History separates an olive helmet, ivory stone and steel
tags; Encore uses a chrome microphone and gold notes; Fantasy Realms uses an
emerald dragon with ivory horns and warm fire; Fright Night TV uses weathered
wood, slate roofs, warm windows and a pale moon.

Character/material references inspected for the pass include
[Weta's Caesar](https://www.wetafx.co.nz/articles/unity-announces-intent-to-acquire-weta-digitals-tools-pipeline-technology-and-engineering-talent),
[a licensed Alien replica](https://distortionsunlimited.com/products/deluxe-alien-xenomorph-mask),
[a production-made Predator mask](https://propstoreauction.com/lot-details/index/catalog/319/lot/88985/Lot-282-Predator-2-1990-Production-Made-Predator-Bio-Mask)
and [Bender's cartoon colors](https://pngimg.com/image/31274).
No reference bitmap is embedded. Internal gradients provide material shading,
and every changed icon retains its measured vertical center.

The Alien/Predator redesign replaces the simple head/helmet arrangement with an
elongated continuous Xenomorph skull, a projecting toothed mouth and inner jaw,
curved ribbed neck and biomechanical hose. The larger Predator biomask has a
broad brow, separate inset eye slits, raised central nose, cheek/chin vents,
banded dreadlocks and three red targeting lights. Charcoal and patinated metal
remain distinct at guide size. The name, three-line wordmark, frame and palette
remain unchanged; the complete icon stays centered at y=192.

Crime & Mystery separates a buff case folder, cream evidence papers, red case
tab and steel magnifier around the fingerprint. Fight Night Cinema uses shaded
red leather, a separate ivory cuff, steel piping and small seam stitches. Both
retain their existing frame, wordmark and vertically centered icon bounds;
review full-size and 192×96 exports together before installing.

The decade suite keeps its names, layout and frame colors while separating
materials within each icon. The 1980s cassette has a charcoal shell, ivory reels
and label with a pink stripe. The 1990s rental case has a blue/green landscape
cover and gold sun beside a charcoal cassette with a cream label. The 2000s
case has a landscape cover beside a silver disc with spectral reflections.
The 2010s tablet and 2020s television use graphite housings, metal edges and
blue/purple/warm screen colors. The television remote has distinct colored
buttons. Inspect all five together at full size, 192×96 and 96×48.

On the Clock Comedy separates an oak desk, graphite monitor with metal edges,
cream coffee mug and teal fabric chair. Fast & Furious Cinema keeps a charcoal
muscle car while separating its chrome blower, grille, bumper and headlight
bezels from reflective blue glass, cream lamps and amber indicators. The
wordmarks and frames retain their existing colors and positions.

Family Movie Matinee adds a custom three-person cinema illustration with a
perforated film screen, warm play symbol, distinct clothing/skin colors and
a striped popcorn carton. Its mint frame and three-line wordmark distinguish
the general family-movie station from Family Toon Theater’s fox/storybook.
Both retain independent content pools.

Morning Cartoons keeps its smiling sunrise, cereal bowl, spoon and established
wordmark. A shaded blue bowl, white milk and brighter cereal rings distinguish
the breakfast illustration from the yellow sun and text. Its geometry and
vertical centering remain unchanged; full-size and guide-size previews preserve
the existing suite layout.

Josh Gates: Expedition TV uses a custom multicolor expedition hat, brass compass,
map and dotted trail. The complete icon is vertically centered, with a three-line
wordmark checked at 768 × 384 and 240 × 120. It sits beside Unexplained Files in
the television group, ahead of cartoons. Existing channel identities stay stable
when the cartoon output positions move down one slot.
