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
discovery across subnets, MQTT announcements and remote touch are next
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

## Optional MQTT monitor (0.6)

Open **MQTT · visor opcional** in the Nabla Control panel. An administrator can
activate it, enter up to eight MQTT topic filters and select 50–1000 retained
history rows (200 by default). This uses the existing Home Assistant MQTT broker;
there is no additional broker login or dependency when the monitor is disabled.
Configure the MQTT integration first if it is not already available.

- Disabled by default; no default topic subscription.
- Read-only: no publish API, command replay or control messages.
- Filters support MQTT `+` and terminal `#`; for example `nabla/ha/+/ui/#`.
- Timestamp is receive time in UTC, not proof of when a command executed.
- Retained messages are marked separately. A command is not an acknowledgement.
- Message contents stay in memory, not Recorder, files or HA logs. Only settings
  persist in HA storage. Restart, disabling or applying settings clears history.
- Each payload is limited to 2048 bytes (binary UTF-8 errors are replaced), topic
  display to 256 characters, and reception to 100 messages per second. The panel
  reports dropped messages and marks truncated payloads. Overlapping topic
  filters can produce duplicate entries; prefer disjoint filters.
- Pause freezes only this browser view; recording continues. Closing the section
  stops browser polling but leaves the explicitly enabled recording running.
- Administrators alone can configure, inspect or clear this log.

Installation of new Python integration code needs one HA restart. Enabling,
disabling and changing MQTT settings afterwards does not. Use Apply again if
MQTT was unavailable during startup; ordinary broker reconnects use HA MQTT's
existing subscriptions.

## Verification

Run `python3 -m unittest discover -s tests -v`. The tests exercise production
lifecycle and MQTT code through an isolated HA boundary; they are not a full
Home Assistant/frontend suite. Keep physical, runtime and owner verification
separate from unit test results.
