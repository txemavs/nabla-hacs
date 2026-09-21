# Remote taps

Nabla Control 0.8.1 can tap a mirrored LVGL display from **Live View**.
The firmware must explicitly advertise `touch: true`; color or display size
alone is not evidence of touch support. Existing encoder-only devices and
older mirrors remain unchanged.

Enable the optional firmware feature in the device composition:

```yaml
nabla_display_mirror:
  id: screen_mirror
  lvgl_id: nabla_lvgl
  color: true
  width: 240
  height: 240
  touch: true
```

Use a Nabla ESP UI revision containing the remote-touch component and the
logical geometry appropriate to the existing display. Upload firmware and
reload the HA device entry to rediscover capabilities (installing/restarting
Nabla Control also reloads them).

An administrator opens **View** and clicks/taps the displayed image. HA sends
logical pixel coordinates to `/mirror/touch`, using the device's current
per-boot token. Borders and letterboxing are excluded from coordinate mapping.
A token rejection is refreshed/retried once; timeouts are not retried, because
the tap may already have executed. The firmware releases the press itself,
so closing a browser cannot leave an input held. Physical touch takes priority.

This first phase supports **short taps only**. Dragging, held presses, keyboard
focus and multi-touch are not part of the protocol. Runtime display rotation
has the mirror's existing qualification limits; coordinates refer to the
captured logical frame, never raw touchscreen coordinates.

Validation covers scaled center/letterbox input in Chromium, transport bounds
and retry policy, native firmware tap expiry/release tests, and T-Watch OTA with
remote Settings/open and triangle/back checked against actual captured frames.
The 480×320 firmware compiled; its physical upload/test depends on device
availability and must be recorded separately.
