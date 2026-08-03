# MusicBrainz Picard

MusicBrainz Picard is an advanced music tagger and organizer. This stack provides a browser-accessible Picard UI and mounts both your main library and a staging import directory so you can review, tag, and move files into your canonical music tree.

**Homepage:** https://picard.musicbrainz.org/  
**Docs:** https://picard-docs.musicbrainz.org/

Access via Caddy at **https://picard.yourdomain.com** (or your configured hostname).

## Quick start

1. Run `./prepare-stack.sh`.
2. Review `stack.env` and set:
   - `PICARD_MUSIC_PATH` (default `/mnt/unraid/media/music`)
   - `PICARD_IMPORT_PATH` (default `/mnt/unraid/media/downloads/soulseek`)
3. Deploy with `docker compose up -d`.
4. Open Picard and add files from `/import`, then save organized files to `/music`.

## How this fits your flow

- Soulseek writes completed downloads to `/mnt/unraid/media/downloads/soulseek`.
- Explo can continue doing frequent automated migrations into `/mnt/unraid/media/music`.
- Picard gives you a manual quality pass for metadata and naming normalization on anything that still needs cleanup.

## Configuration

| Item | Details |
|------|---------|
| **Access** | Via Caddy only (no host port; reverse-proxy to `picard:5800`) |
| **Network** | `monitor` |
| **Image** | `jlesage/musicbrainz-picard:latest` |
| **Storage** | `picard_config` named volume for app state; bind mounts `${PICARD_MUSIC_PATH}:/music` and `${PICARD_IMPORT_PATH}:/import` |
| **Auth** | VNC/noVNC session security is app-level; keep hostname behind SSO when exposed publicly |

## Notes

- Picard does not provide a built-in unattended library auto-organize daemon in this image; it is best used as a review/cleanup step.
- For your "more often than once/day" requirement, keep Explo’s schedule as the frequent automated sorter and use Picard for higher-quality tagging passes.
