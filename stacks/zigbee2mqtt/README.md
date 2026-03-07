# Zigbee2MQTT

Bridge Zigbee devices to MQTT so they can be used by Home Assistant, Node-RED, and other automation tools.

**Website:** https://www.zigbee2mqtt.io/  
**Docs:** https://www.zigbee2mqtt.io/guide/installation/01_docker.html  
**Docker image:** https://hub.docker.com/r/koenkk/zigbee2mqtt  

## Quick start

1. Plug your Zigbee coordinator (USB stick, etc.) into the Docker host and note the device path (e.g. `/dev/ttyUSB0`).
2. From this directory, copy `stack.env.example` → `stack.env` and:
   - Set `ZIGBEE2MQTT_CONFIG_MQTT_SERVER` to your MQTT broker URL (e.g. `mqtt://mosquitto:1883`).
   - Optionally set `ZIGBEE2MQTT_CONFIG_MQTT_USER` / `ZIGBEE2MQTT_CONFIG_MQTT_PASSWORD`.
3. Update `docker-compose.yml` to match your adapter device path if it differs from `/dev/ttyUSB0`.
4. Start the stack:

   ```bash
   docker compose up -d
   ```

5. Access the Zigbee2MQTT web UI via Caddy (e.g. `https://zigbee2mqtt.yourdomain.com`) after adding a site block that reverse-proxies to `zigbee2mqtt:8080`.

## Configuration

| Item        | Details                                                                                      |
| ----------- | -------------------------------------------------------------------------------------------- |
| **Access**  | Web UI via Caddy (reverse-proxy to `zigbee2mqtt:8080`); MQTT via your existing Mosquitto broker |
| **Volume**  | `zigbee2mqtt_data` (configuration, network map, device state)                               |
| **Network** | `monitor` — shared with Mosquitto and Home Assistant                                        |
| **Env**     | See `stack.env.example` and `documents/ENV-VARS.md` for TZ/locale and MQTT settings.        |

Zigbee2MQTT reads additional configuration from `configuration.yaml` inside the `zigbee2mqtt_data` volume (`/app/data`). Refer to the official docs for configuring adapters, channels, and devices.

