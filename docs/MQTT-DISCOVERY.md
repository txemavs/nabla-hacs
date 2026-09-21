# MQTT identity and changing addresses

Nabla Control 0.9 adds optional MQTT discovery independently of the message log.
It uses Home Assistant's existing MQTT integration and credentials. No second
broker connection or background subnet scan is created.

## Enable and link

1. Add the optional [`nabla_presence` firmware component](https://github.com/txemavs/nabla-esp-ui/tree/main/external_components/nabla_presence)
   to the existing ESPHome composition. Keep its current MQTT credentials and
   Wi-Fi fallbacks. Install that firmware; old firmware does not announce itself.
2. Open **Nabla Control → MQTT → Descubrimiento y cambios de IP**. Enable discovery,
   keep `nabla/discovery` or enter the same prefix as the firmware, and apply.
3. After an announcement (normally within a minute), select the existing Nabla
   Control device and choose **Vincular y seguir IP**. For new devices, select
   **Añadir dispositivo nuevo**. HTTP identity and renderer verification must pass.
4. Future IP changes update only the host option. Existing device IDs, buttons and
   dashboard references remain stable. Only that config entry reloads, not HA.

Discovery settings survive HA restarts; announcements remain in memory only.
The message log has its own enable switch and filters. To stop following one
device, disable **Follow MQTT address** in its integration options. Linking turns
off ESPHome-source following for that entry; MQTT has precedence while enabled,
so an older source address cannot bounce the entry back and forth.

## Contract and limits

MQTT topic `<prefix>/esp32-<MAC>/announce`, QoS 1, retained. JSON v1 carries
`device_id`, random per-boot `boot_id`, `name`, and `host` (IPv4). Firmware publishes
on connection/reconnection/address change with a 5-second check and 60-second
heartbeat. This component never changes existing MQTT birth/will topics.

Control stores at most 64 hints of 1 KiB and expires them after 180 seconds.
Every 15 seconds it checks at most four changed, linked entries. Before updating,
`GET http://<host>/nabla/identity` must return the same v1 identity and boot value,
and the normal mirror/web probe must succeed. HTTP bodies and timeouts are
bounded and redirects are rejected. Retained messages are hints, not liveness;
the normal HTTP polling remains the source of availability.

Unknown versions, malformed topics/addresses, stale boot identities, collisions,
unreachable endpoints and disabled following do not change existing entries.
The latest announcement must still be current after verification. Wi-Fi outages
never erase the last known address. Address verification is read-only; it sends
no touch, button or MQTT control commands.

IDs are not authentication. This is for trusted MQTT brokers and LANs, with
per-device publish ACLs. Matching boot values prevents stale endpoint confusion;
it does not protect against a malicious publisher impersonating hardware.
No MQTT feature creates routes, DNS records or a Tailscale tunnel. If an ESP moves
to a network HA cannot reach, its old host stays unchanged until a verified one
is reachable. Multiple HAs may independently subscribe and link the same device.
Changing the topic prefix does not delete retained messages from the broker.

## Validation status

Backend regression tests cover parsing, stale hints, identity/boot mismatch,
explicit linking, new entry flow, preserved IDs, collisions, opt-out during probe,
and bounded inventory. Chromium exercises independent discovery settings and
linking. ESP32-S3 firmware compile passes with ESPHome 2026.8.2. Physical roaming
and large fleet soak tests remain pending; no claim of verified roaming yet.
