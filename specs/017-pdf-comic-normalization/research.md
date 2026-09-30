# Research

- Existing archiving-utils has no PDF conversion command; retain its CBZ verification and add a small Poppler adapter, not a second archive framework.
- Poppler `pdftoppm -png -singlefile -f N -l N -scale-to pixels` renders a complete page with its layout. See [Debian Poppler manual](https://manpages.debian.org/trixie/poppler-utils/pdftoppm.1.en.html). Raw image extraction was rejected because it loses text, masks and composed artwork.
- PNG introduces no further lossy image encoding; rendering/resizing still changes the original representation. Preserve PDFs, including search text/forms/attachments, separately.
- Page dimensions can be much larger than expected for art books. Use bounded longest-edge pixels rather than unbounded DPI rendering.
- Cache keys include input digest and options; validate outputs before reuse. Partial download extensions remain excluded. No unresolved research decisions.
