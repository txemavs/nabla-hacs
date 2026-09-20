# Nabla Display for Home Assistant

Home Assistant custom integration for viewing Nabla ESP-UI display mirrors and sending encoder actions.

## Installation via HACS

1. Open HACS in your Home Assistant instance
2. Click the three dots menu → **Custom repositories**
3. Add `https://github.com/txemavs/nabla-hacs` as **Integration**
4. Search for "Nabla Display" and install
5. Restart Home Assistant

### Manual installation

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

## Lovelace Card

### Installation

1. Copy `www/nabla-display-card.js` to your Home Assistant `config/www/` directory
2. Add the resource in **Settings → Dashboards → Resources**:

```yaml
url: /local/nabla-display-card.js
type: module
```

### Usage

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

## Button Entities

For devices with input capability, four button entities are created:

- `button.nabla_display_{device_id}_up`
- `button.nabla_display_{device_id}_down`
- `button.nabla_display_{device_id}_enter`
- `button.nabla_display_{device_id}_back`

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

## Supported Devices

| Profile | Dimensions | Format | Frame size | Input |
|---------|------------|--------|------------|-------|
| Kit1 (ST7735) | 160×128 | rgb332 | 20,480 bytes | encoder |
| T-Call (SSD1309) | 128×64 | mono1 | 1,024 bytes | encoder |
| T-Watch | 240×240 | rgb332 | 57,600 bytes | — |
| Large | 480×320 | rgb332 | 153,600 bytes | — |

## Requirements

ESP devices must run firmware with the Nabla display mirror component, exposing:

- `GET /mirror/capabilities` — Device profile (dimensions, format, input capability)
- `GET /mirror/frame` — Raw framebuffer bytes
- `GET /mirror/token` — CSRF token for input (if `input: true`)
- `POST /mirror/action` — Encoder action (requires `X-Nabla-Token` header)

### Fallback Mode

When `/mirror/capabilities` fails (connection reset on some firmware), the integration infers the profile from frame byte count. Input is disabled in fallback mode until capabilities become available.

## License

MIT
