#!/usr/bin/env python3
"""Install the private artwork bridge and optional Plex special-episode fix."""

import hashlib
import ipaddress
import os
from pathlib import Path
import re
from urllib.parse import urlsplit


REVIEWED_TEMPLATE_SHA256 = "c96911de9034e9ea7988e98e5afeec91b756094c34e75a9d58482a8d4846bfd3"
BEGIN = "    # BEGIN private library artwork bridge\n"
END = "    # END private library artwork bridge\n"
ANCHOR = "    # Serve Django via uWSGI\n"
REVIEWED_EXPORTER_SHA256 = "aae125da464db4501fe6ef000dc3ca06601aa4cdcffaa3c1ff192496d34995b1"
EXPORTER_LINE = '''                            program_xml.append(f'    <episode-num system="xmltv_ns">{season}.{episode}.</episode-num>')'''
EXPORTER_PATCH = '''                            # BEGIN Plex special-episode identity compatibility
                            # Plex reads explicit zero-numbered labels when the invalid namespace is absent.
                            onscreen_zero = (
                                (season == -1 or episode == -1)
                                and season >= -1
                                and episode >= -1
                                and custom_data.get("onscreen_episode") == f"S{season + 1:02d}E{episode + 1:02d}"
                            )
                            if not onscreen_zero:
                                program_xml.append(f'    <episode-num system="xmltv_ns">{season}.{episode}.</episode-num>')
                            # END Plex special-episode identity compatibility'''


def render_exporter(original, enabled):
    """Change serialization only; reject upstream drift and malformed prior patches."""
    marker = "Plex special-episode identity compatibility"
    if marker in original and (original.count(EXPORTER_PATCH) != 1
                               or original.count(marker) != 2):
        raise ValueError("Unrecognized XMLTV compatibility patch")
    canonical = original.replace(EXPORTER_PATCH, EXPORTER_LINE, 1)
    if not enabled and canonical == original:
        return original
    if hashlib.sha256(canonical.encode()).hexdigest() != REVIEWED_EXPORTER_SHA256:
        raise ValueError("Unreviewed XMLTV exporter; review this image before enabling compatibility")
    if canonical.count(EXPORTER_LINE) != 1:
        raise ValueError("Missing XMLTV export insertion point")
    return canonical.replace(EXPORTER_LINE, EXPORTER_PATCH, 1) if enabled else canonical


def render(original, origin):
    parsed = urlsplit(origin)
    if (not re.fullmatch(r"https://[A-Za-z0-9][A-Za-z0-9.-]*[A-Za-z0-9](?::443)?", origin)
            or parsed.scheme != "https" or "." not in (parsed.hostname or "")
            or parsed.username or parsed.password or parsed.path or parsed.query
            or parsed.fragment or parsed.port not in (None, 443)):
        raise ValueError("Artwork origin must be a public HTTPS hostname without a path")
    try:
        ipaddress.ip_address(parsed.hostname)
    except ValueError:
        pass
    else:
        raise ValueError("Artwork origin must use a public DNS hostname")
    if parsed.hostname.endswith((".local", ".localhost", ".home.arpa")):
        raise ValueError("Plex requires a public image origin")
    clean = original
    if BEGIN in clean:
        if clean.count(BEGIN) != 1 or clean.count(END) != 1:
            raise ValueError("Ambiguous existing artwork bridge")
        start = clean.index(BEGIN)
        end = clean.index(END, start) + len(END)
        clean = clean[:start] + clean[end:]
    canonical = re.sub(r"listen (\[::\]:)?\d+;", r"listen \1NGINX_PORT;", clean)
    if hashlib.sha256(canonical.encode()).hexdigest() != REVIEWED_TEMPLATE_SHA256:
        raise ValueError("Unreviewed nginx template; review this image before enabling the bridge")
    if clean.count(ANCHOR) != 1:
        raise ValueError("Missing nginx insertion point")
    block = BEGIN + f'''    # Docker DNS is resolved again when ErsatzTV is recreated.
    resolver 127.0.0.11 valid=30s ipv6=off;
    location = /__library/xmltv.xml {{
        allow 127.0.0.1;
        deny all;
        limit_except GET {{ deny all; }}
        set $library_backend ersatztv:8409;
        proxy_pass http://$library_backend/iptv/xmltv.xml;
        proxy_set_header Host {parsed.netloc};
        proxy_set_header X-Forwarded-Host {parsed.netloc};
        proxy_set_header X-Forwarded-Proto https;
        proxy_set_header Accept-Encoding "";
        sub_filter_types application/xml text/xml;
        sub_filter_once off;
        sub_filter 'http://{parsed.netloc}/iptv/artwork/' '{origin}/iptv/artwork/';
    }}
    location ~ ^/iptv/artwork/(posters|thumbnails|logos)/(plex/[0-9]+|[A-Fa-f0-9]+(?:\\.jpg)?)$ {{
        limit_except GET {{ deny all; }}
        set $library_backend ersatztv:8409;
        proxy_pass http://$library_backend$request_uri;
        proxy_set_header Host ersatztv:8409;
        proxy_set_header X-Forwarded-Host ersatztv:8409;
        proxy_set_header X-Forwarded-Proto http;
    }}
''' + END
    return clean.replace(ANCHOR, block + ANCHOR)


def main():
    target = Path("/etc/nginx/sites-enabled/default")
    original = target.read_text()
    updated = render(original, os.environ.get("LIBRARY_ARTWORK_ORIGIN", ""))
    mode = os.environ.get("PLEX_XMLTV_SPECIALS", "false").lower()
    if mode not in ("true", "false"):
        raise ValueError("PLEX_XMLTV_SPECIALS must be true or false")
    exporter = Path("/app/apps/output/epg.py")
    if exporter.is_symlink() or (exporter.exists() and not exporter.is_file()):
        raise ValueError("XMLTV exporter must be a regular application file")
    source = exporter.read_bytes().decode("utf-8") if exporter.exists() else None
    if source is None and mode == "true":
        raise ValueError("XMLTV exporter is missing")
    changed = render_exporter(source, mode == "true") if source is not None else None
    # Validate both reviewed sources before changing either startup file.
    if changed != source:
        exporter.write_text(changed)
    if updated != original:
        # The upstream init script also edits this existing configuration file.
        target.write_text(updated)
    print("Private library XMLTV/artwork bridge prepared; Plex specials " + mode)


if __name__ == "__main__":
    main()
