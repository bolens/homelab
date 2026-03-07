# Mosquitto (MQTT broker)

Lightweight MQTT broker for Home Assistant, Zigbee2MQTT, Node-RED, and other IoT/automation clients.

**Website:** https://mosquitto.org/  
**Docs:** https://mosquitto.org/documentation/  
**Docker image:** https://hub.docker.com/_/eclipse-mosquitto  

## Quick start

1. From this directory, copy `stack.env.example` → `stack.env` and adjust `TZ` / locale if needed.
2. Start the stack:

   ```bash
   docker compose up -d
   ```

3. Create a `mosquitto.conf` in the `mosquitto_config` volume (see docs) to define listeners, authentication, and persistence.
4. Point clients (Home Assistant, Zigbee2MQTT, etc.) at:
   - Host: Docker host IP (for LAN devices) or `mosquitto` (for other stacks on `monitor`)
   - Port: `1883`

## Configuration

| Item        | Details                                                                                 |
| ----------- | --------------------------------------------------------------------------------------- |
| **Access**  | MQTT on host port `1883` for LAN devices; `mosquitto:1883` for other Docker stacks     |
| **Volumes** | `mosquitto_config` (config including `mosquitto.conf`), `mosquitto_data`, `mosquitto_log` |
| **Network** | `monitor` — shared with Home Assistant, Zigbee2MQTT, Node-RED, etc.                    |
| **Env**     | See `stack.env.example` and `documents/ENV-VARS.md` for TZ/locale.                     |

See the official Mosquitto docs for example `mosquitto.conf` files including password files and TLS.

