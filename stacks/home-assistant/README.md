# Home Assistant

Home automation hub for integrating lights, sensors, switches, and other devices. This stack runs Home Assistant in Docker with persistent config and exposes the web UI via Caddy.

**Website:** https://www.home-assistant.io/  
**Docs:** https://www.home-assistant.io/docs/  
**Docker image:** https://github.com/home-assistant/docker/  

## Quick start

1. From this directory, copy `stack.env.example` → `stack.env` and adjust `TZ` / locale if needed.
2. Start the stack:

   ```bash
   docker compose up -d
   ```

3. Expose Home Assistant via Caddy (e.g. `https://home.yourdomain.com`) using the example site block in the Caddyfile; internally it listens on port `8123`.
4. Open the UI and complete the initial onboarding (create user, set location, etc.).

## Configuration

| Item        | Details                                                                 |
| ----------- | ----------------------------------------------------------------------- |
| **Access**  | Via Caddy only (no host port; reverse-proxy to `home-assistant:8123`)  |
| **Volume**  | `home_assistant_config` (YAML config, automations, history, add-ons)   |
| **Network** | `monitor` — shared with Caddy and related automation stacks            |
| **Env**     | See `stack.env.example` and `documents/ENV-VARS.md` for TZ/locale.     |

### Hardware and integrations

- For Zigbee, Z-Wave, and other radio integrations, you can either:
  - Use **Zigbee2MQTT** (separate stack in this repo) with an MQTT broker (Mosquitto), or
  - Pass USB devices through to this container (e.g. `/dev/ttyUSB0`) and configure integrations directly.
- If you need USB passthrough, update `docker-compose.yml` to add `devices:` and any required privileges per the Home Assistant Docker docs.

