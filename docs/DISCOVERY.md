# Discovery and address tracking

Nabla Control 0.8.0 adds **Search new devices** to the Devices toolbar.
This is separate from the text filter, which searches already configured rows.

## What search does

An administrator can ask Nabla Control to probe the hosts already registered
by Home Assistant's ESPHome integration. A device must answer a compatible
`/mirror/capabilities` or `/nabla/state` endpoint before it is offered.
Disabled ESPHome entries are ignored. This does not sweep network ranges or
assume that every ESPHome device runs Nabla UI.

- **Add** creates a device entry without restarting HA.
- **Link IP** binds an existing manual entry at the same address to that
  ESPHome entry, preserving its device ID, buttons and dashboard references.
- **Linked** means that association already exists.

Search is administrator-only and read-only until Add/Link is clicked. Adding
rechecks the current source entry and endpoint; stale search results are not
trusted. Concurrent searches share one task. At most 64 entries are examined,
with four concurrent probes, two seconds per endpoint and a 20-second overall
budget. Partial results are labelled; response bodies are bounded to 16 KiB.

## Following a changed IP

A linked device has an optional **Follow ESPHome address** setting. Every
60 seconds Nabla Control compares the linked entry's current address with
its own. If it changed and a compatible endpoint responds, it saves the new
address and reloads only that device. Unchanged addresses generate no extra
network requests. Missing/disabled sources, unavailable endpoints and an
address already assigned to another Nabla entry do not overwrite the address.
Disable the option when you want to manage the address manually.

The identity anchor is the existing Home Assistant ESPHome config-entry ID,
not the IP address or display name. This association is local to that HA
installation and is not a new cryptographic hardware identity. If an ESPHome
entry is deleted and recreated, reconfiguration may be necessary.

## Limits and next work

Home Assistant must first learn the new address itself. This feature does not
solve mDNS across routed Wi-Fi networks, create Tailscale routes, or let a device
announce itself through an arbitrary MQTT broker. Manual Add remains available
for devices not registered with HA's ESPHome integration.

Pending separately:

- Stable firmware identity and authenticated/scoped MQTT address announcements
  across subnets or multiple Home Assistants.
- Remote touch coordinates and negotiated touch capability for mirrored displays.

The optional MQTT log remains a viewer, not a discovery or command transport.
