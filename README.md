# Nabla Control for Home Assistant

HACS integration for **Nabla Control**. Technical domain: `nabla_control`
(YAML key, `custom_components/nabla_control/`, WebSocket types).

Device menus and on-device UI come from **[Nabla ESP UI](https://github.com/txemavs/nabla-esp-ui)** —
not from this Home Assistant component. From that project:

> **Declare what the device does; Nabla owns how its standard UI looks and works.**
> Device YAML supplies menus, content and actions. Shared components and profiles
> own typography, spacing, borders, focus and supported presentation.

**Nabla Control** is the Home Assistant side: mirror previews, Nabla web UI / camera
devices, encoder actions, and the sidebar panel.

---

## Nabla Control

**Nabla Control** brings Nabla devices into Home Assistant:

- **Mirror displays** — live ESP screen preview and encoder actions (firmware from Nabla ESP UI)
- **Nabla web UI** — devices that serve an HTML Nabla UI (`/nabla/state`), with an **Open Nabla** link
- **Cameras** — when a web device reports `camera_port`, the panel shows a live MJPEG preview

YAML / Python domain and product name: **Nabla Control** (`nabla_control`).

---

## Installation via HACS

1. Open HACS → Custom repositories
2. Add `https://github.com/txemavs/nabla-hacs` as **Integration**
3. Search for **Nabla Control** and install
4. Restart Home Assistant

### Manual Installation

Copy `custom_components/nabla_control/` into your Home Assistant `config/custom_components/` directory.

## Configuration

In Home Assistant, open **Settings → Devices & services → Add integration →
Nabla Control**. Enter the device hostname/IP, name, type and refresh interval.
The panel's **Manage devices** link opens the integration settings. New entries,
removals and option changes do not restart Home Assistant.

Use an entry's **Configure** action to change its address or refresh interval.
Only that entry reloads. Dashboard IDs stay stable when its IP changes.

### Upgrade from YAML (0.4.x)

The first installation of this code requires a Home Assistant restart. Existing
`nabla_control: devices:` YAML is imported automatically, including offline
units. Imported devices retain their previous card/button IDs. Confirm the
entries appear, then remove that YAML section: leaving it in place will import
a deleted device again on the next boot. Existing entries are not overwritten
by old YAML values.

New devices receive a persistent local ID. Automatic hardware identity,
discovery across subnets, MQTT announcements/logging and remote touch are next
phases; this release supports manual address updates, not roaming discovery.

### Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `host` | string | required | Device IP or hostname |
| `name` | string | `"Nabla Control {host}"` | Friendly name |
| `poll_interval` | float | `1.0` | Seconds between polls (0.2–30) |
| `kind` | string | `auto` | `auto` \| `mirror` \| `web` |

**Kind detection (`auto`):** tries `GET /nabla/state` (web fingerprint) first, then `/mirror/capabilities` (mirror).

**Web devices:** available when `/nabla/state` succeeds. If `camera_port` is present, `camera_url` is `http://{host}:{camera_port}/` (MJPEG). The panel uses that URL directly as `img.src` (LAN, no HA proxy).

---

## Nabla Control panel

After restart, **Nabla Control** appears in the sidebar:

- Device overview with live preview (mirror PNG or web MJPEG)
- Status, kind (Mirror / Web), camera yes/no
- **Open Nabla** for web devices
- Live View and Add to Dashboard for mirror devices
- Encoder controls when `has_input` is true

On-device menus remain owned by device YAML + [Nabla ESP UI](https://github.com/txemavs/nabla-esp-ui); this panel observes and controls from Home Assistant.

---

## Lovelace Card

Resource: `/local/nabla-control-card.js` (module). Example:

```yaml
type: custom:nabla-control-card
device_id: "10_10_10_204"
name: "Kit1"
poll_interval: 1000
scale: 2
show_controls: true
```

---

## Services

Service domain: `nabla_control` (e.g. `nabla_control.send_action`).

---

## WebSocket

`nabla_control/devices` returns devices including `kind`, `has_camera`, `camera_url`, `open_url`, `has_input`, `available`.

---

## Related projects

- [Nabla ESP UI](https://github.com/txemavs/nabla-esp-ui) — on-device menus and mirror contract

---

## License

MIT
