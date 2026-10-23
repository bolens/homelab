# Integration contract

| Client | Destination | Intended access |
| --- | --- | --- |
| Caddy on ingress-admin | librarr:5050 | HTTP proxy; authenticated application |
| Host/LAN direct container publication | host:5050 | No published port |
| Librarr on media-automation | prowlarr:9696 | Optional authenticated search |
| Librarr on torrents | gluetun:8080 | Optional qBittorrent API; distinct categories |
| Librarr base networks | reader API endpoints | No configured reader connection |
| Librarr with readers override | kavita:5000, komga:25600, audiobookshelf:80 | Optional authenticated catalog/scan APIs |
| Kavita with Librarr override | dedicated ebook/manga output binds | Read only; separate non-overlapping library roots |
| Komga with Librarr override | dedicated manga output bind | Read only; existing comics stay separate |
| Audiobookshelf existing media bind | audiobooks/Librarr subtree | Read only; matching host root required |
| Bookshelf and Calibre-Web | Librarr ebooks | Reviewed manual import/upload; no direct-download client bridge |

Compose rendering verifies these declared networks, ports and mounts. It does
not prove firewall or WAN isolation, peer identity, credentials, remote mounts,
provider success or reader acceptance. The optional reader network also permits
communication with its other members. No network membership implies VPN egress.
