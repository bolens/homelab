# Homelab topology

Generated from `documents/topology.yaml`. Do not edit the generated section directly.

<!-- TOPOLOGY_GENERATED_START -->
```mermaid
%%{init: {'flowchart': {'curveStyle': 'linear'}}}%%
flowchart TB

    subgraph internet["Internet / LAN"]
        users["Clients"]
        outbound["Internet"]
    end

    subgraph ingress["Ingress"]
        tunnel["`cloudflare-tunnel
(optional)`"]
        caddy["`caddy
Reverse proxy
:80 / :443`"]
    end

    subgraph vpn["VPN & remote access"]
        direction TB
        headscale["`headscale
Mesh VPN (Tailscale)`"]
        wireguard["`wireguard
Remote access VPN`"]
        gluetun["`gluetun
Container egress VPN`"]
        netbird["`netbird
WireGuard mesh VPN`"]
    end

    internet ~~~ ingress ~~~ vpn

    subgraph apps["Application stacks"]
        direction TB
        apps_acquisition["`Media acquisition & *arr
torrents, *arr, Usenet`"]
        apps_ai["`AI & LLM
local models, chat UIs`"]
        apps_dev["`Developer & IT utilities
it-tools, ConvertX, CUPS, Dozzle, Gitea, Kasm, CI, dashboard, PDF, NetBox, PostHog, Snipe-IT`"]
        apps_gaming["`Gaming
ROMs, Steam, in-browser emulation`"]
        apps_home["`Home automation & IoT
Home Assistant, MQTT, Zigbee`"]
        apps_links["`Links, shorteners & presence
YOURLS, Shlink, Linkstack, Stoat, homepage`"]
        apps_media["`Media & personal data
photos, docs, music, RSS, notes`"]
        apps_osint["`OSINT & recon
homelab-user/email/phone recon`"]
        apps_privacy["`Privacy & opt-out
data broker deletion`"]
        apps_search["`Search
SearXNG metasearch, Meilisearch`"]
        apps_sec_tooling["`Security & compliance tooling
SBOM, threat model, scanner, forensics`"]
        apps_security["`Security & identity
passwords, secrets, aliases, IdP`"]
        apps_tor["`Tor / dark web
OnionScan, OnionProbe, TorBot`"]
        apps_workflow["`Workflow automation
n8n, Node-RED`"]
    end
    apps_acquisition ~~~ apps_ai ~~~ apps_dev ~~~ apps_gaming ~~~ apps_home ~~~ apps_links ~~~ apps_media ~~~ apps_osint ~~~ apps_privacy ~~~ apps_search ~~~ apps_sec_tooling ~~~ apps_security ~~~ apps_tor ~~~ apps_workflow

    infra["`Infra
& monitoring`"]

    users --> tunnel
    users --> caddy
    tunnel --> caddy
    users --> wireguard
    users --> headscale
    caddy --> apps_acquisition
    caddy --> apps_ai
    caddy --> apps_dev
    caddy --> apps_gaming
    caddy --> apps_home
    caddy --> apps_links
    caddy --> apps_media
    caddy --> apps_osint
    caddy --> apps_privacy
    caddy --> apps_search
    caddy --> apps_sec_tooling
    caddy --> apps_security
    caddy --> apps_tor
    caddy --> apps_workflow
    caddy --> infra

    wireguard -.->|VPN| caddy
    headscale -.->|mesh| caddy
    apps_acquisition -.->|VPN egress| gluetun
    gluetun -.->|egress| outbound
    apps_privacy -.->|mail| infra
    apps_workflow -.->|mail| infra
```

#### Infrastructure & monitoring

```mermaid
%%{init: {'flowchart': {'curveStyle': 'linear'}}}%%
flowchart TB

    subgraph infra["Infrastructure & monitoring"]
        direction TB
        adguard_home["`adguard-home
DNS / ad blocking`"]
        alertmanager["`alertmanager
Alert routing`"]
        blackbox_exporter["`blackbox-exporter
Probes`"]
        cadvisor["`cAdvisor
Container metrics`"]
        crowdsec["`crowdsec
Security engine`"]
        ddns_updater["`ddns-updater
Dynamic DNS`"]
        diun["`diun
Image update notifier`"]
        dockergc["`docker-gc
Docker GC job`"]
        grafana["`grafana
Dashboards`"]
        kuma["`uptime-kuma
Monitoring`"]
        loki["`loki
Log aggregation`"]
        mailpit["`mailpit
SMTP catcher`"]
        minio["`minio
S3 object storage`"]
        node_exporter["`node-exporter
Host metrics`"]
        nut_server["`nut-server
UPS monitor`"]
        ntopng["`ntopng
Traffic analytics`"]
        pihole["`pihole
DNS sinkhole`"]
        portainer["`portainer
Docker UI`"]
        postfix["`postfix
SMTP relay`"]
        prometheus["`prometheus
Metrics`"]
        restic["`restic
Backups (cron)`"]
        scrutiny["`scrutiny
SMART disk health`"]
        snowflake_relay["`snowflake-relay
Tor bridge relay`"]
        umami["`umami
Web analytics`"]
        unbound["`unbound
DNS resolver`"]
        vector["`vector
Log shipper`"]
        watchtower["`watchtower
Auto-updates`"]
    end
    adguard_home ~~~ alertmanager ~~~ blackbox_exporter ~~~ cadvisor ~~~ crowdsec ~~~ ddns_updater ~~~ diun ~~~ dockergc ~~~ grafana ~~~ kuma ~~~ loki ~~~ mailpit ~~~ minio ~~~ node_exporter ~~~ nut_server ~~~ ntopng ~~~ pihole ~~~ portainer ~~~ postfix ~~~ prometheus ~~~ restic ~~~ scrutiny ~~~ snowflake_relay ~~~ umami ~~~ unbound ~~~ vector ~~~ watchtower

    caddy["caddy"]
    apps["apps"]
    users["users"]

    caddy -.->|logs| crowdsec
    kuma -.->|health| caddy
    prometheus -.->|scrapes| cadvisor
    grafana -.->|queries| prometheus
    watchtower -.->|updates| apps
    dockergc -.->|cleanup| apps
    diun -.->|notify| users
    portainer -.->|manage| apps
```

- **Traffic:** All HTTP(S) to apps and to web UIs (e.g. Uptime Kuma, Grafana) goes through Caddy. Clients reach Caddy directly (local DNS) or via Cloudflare Tunnel; Caddy routes by hostname.
- **VPN & remote access:** **Headscale** – mesh VPN (Tailscale); mesh clients reach Caddy and apps. **WireGuard** – remote-access VPN (UDP 51820); VPN clients connect from outside. **Gluetun** – outbound VPN for containers; media acquisition stacks (e.g. qbittorrent) send traffic through Gluetun to a VPN provider.
- **Application categories:** **Media acquisition & *arr** – download clients and *arr automation (torrents, Usenet, Sonarr/Radarr/Lidarr/Readarr, Bazarr, Explo, MeTube, Mylar3, Soulseek). **AI & LLM** – local models and chat UIs (Ollama, Open WebUI, LibreChat, Open Notebook, Perplexica, Anything LLM, LiteLLM, Kokoro TTS, Whisper ASR). **Developer & IT utilities** – it-tools, ConvertX, CUPS print server, Dozzle, Gitea, Harbor, Woodpecker CI, Homarr dashboard, Baserow, Stirling-PDF, ntfy, NetBox, PostHog, Snipe-IT, code-server, Beszel, Mattermost, Terminus, NodePad, Asking-NG. **Gaming** – Steam automation (ArchiSteamFarm), ROM manager and in-browser emulation (RomM), Twitch drops mining. **Home automation & IoT** – Home Assistant, Mosquitto (MQTT), Zigbee2MQTT. **Links, shorteners & presence** – YOURLS, Shlink, Linkstack, Stoat, Glance, static homepage/landing. **Media & personal data** – consumption and personal content (photos, docs, music, tagging/organization, recipes, bookmarks, RSS, comics, eBooks, tasks, wiki, notes, budgeting, Affine, Appflowy, CryptPad, Trilium, Oasis, Paperless AI). **OSINT & recon** – homelab-user/email/phone recon, breach lookups, subdomain enumeration, AIL. **Privacy & opt-out** – data broker deletion (Naisho, Privotron). **Search** – SearXNG, Meilisearch. **Security & compliance tooling** – SBOM/vuln tracking (Dependency-Track), threat modeling (Threat Dragon), web scanner (ZAP/ZAP GUI), digital forensics (Acquire, Plaso, Docker Forensics Toolkit). **Security & identity** – passwords, secrets, aliases, remote desktop, secure sharing, IdP (Keycloak, authentik, Enclosed, RustDesk). **Tor / dark web** – OnionScan, OnionProbe, TorBot. **Workflow automation** – n8n, Node-RED, Cal.com
- **Application stacks (detail):** Each category and what it does:
- **Media acquisition & *arr:** download clients and *arr automation (torrents, Usenet, Sonarr/Radarr/Lidarr/Readarr, Bazarr, Explo, MeTube, Mylar3, Soulseek) Stacks: bazarr, explo, flaresolverr, lidarr, metube, mylar3, nzbget, nzbhydra2, qbittorrent, prowlarr, radarr, readarr, rtorrent-flood, seerr, sonarr, soulseek, whisparr.
- **AI & LLM:** local models and chat UIs (Ollama, Open WebUI, LibreChat, Open Notebook, Perplexica, Anything LLM, LiteLLM, Kokoro TTS, Whisper ASR) Stacks: anything-llm, kokoro-tts, litellm, ollama, open-webui, librechat, open-notebook, perplexica, whisper-asr.
- **Developer & IT utilities:** it-tools, ConvertX, CUPS print server, Dozzle, Gitea, Harbor, Woodpecker CI, Homarr dashboard, Baserow, Stirling-PDF, ntfy, NetBox, PostHog, Snipe-IT, code-server, Beszel, Mattermost, Terminus, NodePad, Asking-NG Stacks: baserow, beszel, code-server, convertx, cups, dozzle, gitea, harbor, homarr, it-tools, kasm, mattermost, netbox, nodepad, ntfy, posthog, snipe-it, stirling-pdf, terminus, woodpecker-ci.
- **Gaming:** Steam automation (ArchiSteamFarm), ROM manager and in-browser emulation (RomM), Twitch drops mining Stacks: archisteamfarm, romm, twitch-drops-miner.
- **Home automation & IoT:** Home Assistant, Mosquitto (MQTT), Zigbee2MQTT Stacks: home-assistant, mosquitto, zigbee2mqtt.
- **Links, shorteners & presence:** YOURLS, Shlink, Linkstack, Stoat, Glance, static homepage/landing Stacks: glance, homepage, linkstack, shlink, stoat, yourls.
- **Media & personal data:** consumption and personal content (photos, docs, music, tagging/organization, recipes, bookmarks, RSS, comics, eBooks, tasks, wiki, notes, budgeting, Affine, Appflowy, CryptPad, Trilium, Oasis, Paperless AI) Stacks: affine, appflowy, actual-budget, archivebox, audiobookshelf, bookstack, calibre-web, cryptpad, docuseal, emby, firefly-iii, freshrss, hedgedoc, immich, jellyfin, jellystat, joplin-server, logseq-sync, kavita, komga, lanraragi, linkding, linkwarden, mealie, navidrome, nextcloud, oasis, outline, paperless-ai-next, paperless-gpt, paperless-ngx, picard, plex, seafile, slink, super-productivity, syncthing, trilium, vikunja.
- **OSINT & recon:** homelab-user/email/phone recon, breach lookups, subdomain enumeration, AIL Stacks: social-hunt, maigret, spiderfoot, phoneinfoga, theharvester, holehe, blackbird, ghunt, metagoofil, reconftw, sublist3r, ail, web-check.
- **Privacy & opt-out:** data broker deletion (Naisho, Privotron) Stacks: naisho, privotron.
- **Search:** SearXNG, Meilisearch Stacks: meilisearch, searx-ng.
- **Security & compliance tooling:** SBOM/vuln tracking (Dependency-Track), threat modeling (Threat Dragon), web scanner (ZAP/ZAP GUI), digital forensics (Acquire, Plaso, Docker Forensics Toolkit) Stacks: acquire, dependency-track, docker-forensics-toolkit, plaso, threat-dragon, zap, zed-attack-proxy.
- **Security & identity:** passwords, secrets, aliases, remote desktop, secure sharing, IdP (Keycloak, authentik, Enclosed, RustDesk) Stacks: authentik, enclosed, guacamole, infisical, keycloak, password-pusher, privatebin, rustdesk, simplelogin, vaultwarden.
- **Tor / dark web:** OnionScan, OnionProbe, TorBot Stacks: onionprobe, onionscan, torbot.
- **Workflow automation:** n8n, Node-RED, Cal.com Stacks: calcom, n8n, node-red.
- **Infrastructure:** Portainer manages stacks; Watchtower updates images; Docker GC cleans up; Diun notifies on image changes; Uptime Kuma monitors Caddy and app health; Grafana/Prometheus/cAdvisor provide metrics; CrowdSec consumes Caddy logs. **MinIO** provides S3-compatible object storage, often used as a backend for apps and backups; **Restic** handles scheduled backups to object storage; **Scrutiny** monitors disk SMART health. **Postfix** – SMTP relay for outbound mail from apps (e.g. Naisho, n8n). Dozzle (behind Caddy) is a log viewer.
- **Relations:**
  - **users → tunnel**: Clients use optional Cloudflare Tunnel to reach Caddy.
  - **users → caddy**: Clients reach Caddy directly (local DNS or tunnel).
  - **tunnel → caddy**: Tunnel forwards to Caddy by hostname.
  - **users → wireguard**: Clients connect via WireGuard for remote access.
  - **users → headscale**: Clients join mesh via Headscale (Tailscale).
  - **caddy → apps**: Caddy routes HTTP(S) to all application stacks by hostname.
  - **caddy → infra**: Caddy is managed and monitored by infra services.
  - **wireguard → caddy** (VPN): VPN clients reach Caddy and apps.
  - **headscale → caddy** (mesh): Mesh clients reach Caddy and apps.
  - **apps_acquisition → gluetun** (VPN egress): Media acquisition stacks send traffic through Gluetun (VPN).
  - **gluetun → outbound** (egress): Gluetun egresses via VPN provider to internet.
  - **apps_privacy → postfix** (mail): Privacy/opt-out apps send mail via Postfix.
  - **apps_workflow → postfix** (mail): Workflow apps (e.g. n8n) send mail via Postfix.
  - **postfix → mailpit** (relay (internal-only)): When RELAYHOST=mailpit:1025, Postfix relays to Mailpit; no external delivery.
  - **caddy → crowdsec** (logs): Caddy logs feed CrowdSec security engine.
  - **kuma → caddy** (health): Uptime Kuma monitors Caddy and app health.
  - **prometheus → cadvisor** (scrapes): Prometheus scrapes cAdvisor for container metrics.
  - **grafana → prometheus** (queries): Grafana queries Prometheus for dashboards.
  - **watchtower → apps** (updates): Watchtower updates container images for app stacks.
  - **dockergc → apps** (cleanup): Docker GC cleans stopped containers and unused images.
  - **diun → users** (notify): Diun notifies users of new image tags.
  - **portainer → apps** (manage): Portainer manages Docker stacks and containers.
<!-- TOPOLOGY_GENERATED_END -->
