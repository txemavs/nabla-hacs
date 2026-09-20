# Nabla for Home Assistant

HACS integration repository for Nabla projects. Today it ships **Nabla Display**; additional integrations may be added here as the Nabla ecosystem grows.

---

## Nabla Display

**Nabla ESP-UI** is firmware and a UI layer for ESP32 devices with screens — menu system, rotary encoder input, display mirroring, and network integration (Nabla Net, Home Assistant, etc.). It runs on boards like LILYGO T-Call, T-Watch, and various ST7735/SSD1309-based kits.

**Nabla Display** (`nabla_display`) brings those device screens into Home Assistant:

- **Live display mirror** — see the ESP screen in a Lovelace card, updated via polling
- **Encoder actions** — send up/down/enter/back commands from HA buttons or automations
- **Management panel** — sidebar panel to view all devices and add cards to dashboards

This is useful for monitoring device state, remote control, and building dashboards that include your ESP-UI screens.

---

## Installation via HACS

1. Open HACS in your Home Assistant instance
2. Click the three dots menu → **Custom repositories**
3. Add `https://github.com/txemavs/nabla-hacs` as **Integration**
4. Search for "Nabla Display" and install
5. Restart Home Assistant

### Manual Installation

Copy the `custom_components/nabla_display/` folder to your Home Assistant `config/custom_components/` directory.

## Configuration

Add to your `configuration.yaml`:

```yaml
nabla_display:
  devices:
    - host: "10.10.10.204"
      name: "Kit1 Display"
      poll_interval: 1.0
    - host: "10.10.10.205"
      name: "T-Call Display"
      poll_interval: 0.5
```

### Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `host` | string | required | Device IP or hostname |
| `name` | string | `"Nabla Display {host}"` | Friendly name |
| `poll_interval` | float | `1.0` | Seconds between frame fetches (0.2–30) |

---

## Management Panel

After installation and restart, a new **Nabla Displays** entry appears in the sidebar. The panel provides:

- **Device overview** — grid of all configured devices with live preview thumbnails
- **Status indicators** — online/offline state for each device
- **Device info** — resolution, format, input capability
- **Live view** — full-size live mirror with encoder controls (for devices with input)
- **Add to dashboard** — select any Lovelace dashboard and view, then add a card with one click

### Adding Cards to Dashboards

1. Open the **Nabla Displays** panel from the sidebar
2. Click **Add to Dashboard** on any device card
3. Select a dashboard from the list
4. Choose which view to add the card to
5. Click **Add Card**

The card configuration is automatically saved to the selected dashboard. For YAML-mode dashboards, copy the generated YAML and paste it manually.

---

## Lovelace Card

The Lovelace card can be added manually or via the management panel.

### Manual Installation

1. Copy `www/nabla-display-card.js` to your Home Assistant `config/www/` directory
2. Add the resource in **Settings → Dashboards → Resources**:

```yaml
url: /local/nabla-display-card.js
type: module
```

### Manual Usage

Add a card to your dashboard:

```yaml
type: custom:nabla-display-card
device_id: "10_10_10_204"
name: "Kit1 Display"
poll_interval: 1000
scale: 2
show_controls: true
```

The `device_id` is the host IP with dots replaced by underscores.

### Card Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `device_id` | string | required | Device ID (host with dots as underscores) |
| `name` | string | `"Nabla Display"` | Card title |
| `poll_interval` | number | `1000` | Milliseconds between frame fetches |
| `scale` | number | `2` | Display scale factor (1–5) |
| `show_controls` | boolean | `true` | Show encoder buttons |

---

## Services

### nabla_display.send_action

Send an encoder action to a device.

```yaml
service: nabla_display.send_action
data:
  device_id: "10_10_10_204"
  action: "enter"
```

Actions: `up`, `down`, `enter`, `back`

---

## Button Entities

For devices with input capability, four button entities are created:

- `button.nabla_display_{device_id}_up`
- `button.nabla_display_{device_id}_down`
- `button.nabla_display_{device_id}_enter`
- `button.nabla_display_{device_id}_back`

---

## HTTP API

Frame image endpoint (requires HA auth):

```
GET /api/nabla_display/{device_id}/frame
```

Response headers:
- `X-Nabla-Width`: Display width
- `X-Nabla-Height`: Display height
- `X-Nabla-Format`: Pixel format (`rgb332` / `mono1`)
- `X-Nabla-Input`: Input capability (`1` / `0`)

---

## WebSocket API

The integration exposes a WebSocket command for the panel:

```json
{"type": "nabla_display/devices"}
```

Returns an array of device objects with `device_id`, `name`, `host`, `available`, `width`, `height`, `format`, `has_input`, and `poll_interval`.

---

## Supported Devices

| Profile | Dimensions | Format | Frame Size | Input |
|---------|------------|--------|------------|-------|
| Kit1 (ST7735) | 160×128 | rgb332 | 20,480 bytes | encoder |
| T-Call (SSD1309) | 128×64 | mono1 | 1,024 bytes | encoder |
| T-Watch | 240×240 | rgb332 | 57,600 bytes | — |
| Large | 480×320 | rgb332 | 153,600 bytes | — |

---

## Requirements

ESP devices must run firmware with the Nabla display mirror component, exposing:

- `GET /mirror/capabilities` — Device profile (dimensions, format, input capability)
- `GET /mirror/frame` — Raw framebuffer bytes
- `GET /mirror/token` — CSRF token for input (if `input: true`)
- `POST /mirror/action` — Encoder action (requires `X-Nabla-Token` header)

### Fallback Mode

When `/mirror/capabilities` fails (connection reset on some firmware), the integration infers the profile from frame byte count. Input is disabled in fallback mode until capabilities become available.

---

## License

MIT
