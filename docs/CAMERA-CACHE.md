# Camera Cache in Nabla Control

Available in **0.7.0**. The temporary `nabla_camera_cache` service has been
incorporated into Nabla Control; no separate app/add-on or second integration
is needed. Sources are ordinary Home Assistant `camera.*` entities, including
ESPHome cameras without Nabla firmware.

## Configure and view

1. Settings → Devices & services → Nabla Control → Add entry → **Cameras**.
2. Select 1–32 cameras, minimum refresh interval, maximum stale age and JPEG quality.
3. Open **Nabla Control → Cameras**. Choose the 480-pixel view or 64×64 icon.
4. Use the Camera Cache entry's options to change the selection and limits.
   Changes reload only the cache; Home Assistant does not need a restart.

There is one Camera Cache entry per Home Assistant. Its defaults are a
1-second interval, 8-second maximum stale age and JPEG quality 70. The
browser requests images at most once per second (or the configured slower
interval), pauses when hidden, and never overlaps its polling rounds.
Faster firmware clients may request more often: the configured interval is
a **minimum freshness interval**, not a promise of camera FPS.

## HTTP contract

- `GET /api/nabla_control/camera/{entity_id}?size=view`: aspect-preserving JPEG,
  bounded by 480×480, no upscaling.
- `GET /api/nabla_control/camera/{entity_id}?size=icon`: 64×64 JPEG with black
  letterboxing; aspect ratio preserved.
- Only explicitly configured camera entities are served.
- Authentication is inherited from Home Assistant `CameraView`: a valid HA
  Bearer token or that camera's rotating access token. The panel uses Bearer
  headers and blob URLs, never secrets in browser links.
- `ETag` / `If-None-Match`, `X-Nabla-Age`, `X-Nabla-Stale` and
  `X-Nabla-Generation` describe the cached frame. Responses are private.
- A missing usable image returns 503 with `Retry-After: 2`.
- `/api/nabla_camera/{entity_id}` remains a compatibility alias, backed by
  **the same cache and authentication**, for existing firmware and dashboards.
  New clients should use the canonical route. Keep the alias until deployed
  clients have migrated; it is not a separate running service.

## Resource use

No viewers means no captures. One in-flight operation per camera supplies
both sizes to all concurrent readers. A global semaphore bounds concurrent
captures/rendering to two. Pillow runs in the executor, not the HA event
loop. Only the latest immutable image pair is retained. Warm clients may
receive an older frame during refresh up to the configured stale limit;
expired frames are not served after a capture failure. Failures back off.

Sources are limited to 10 MB / 16 million pixels; each encoded variant is
limited to 128 KB. Upstream error messages and camera credentials are not
returned to clients or logged by the cache.

## Migration from the standalone service

Back up the old integration and its YAML first. Remove the old top-level
`nabla_camera_cache:` configuration, including any included package. Move
its values under this temporary import block instead:

```yaml
nabla_control:
  camera_cache:
    cameras:
      - camera.example_entrance
    refresh_interval: 1.0
    max_stale: 8.0
    quality: 70
```

Install 0.7.0 and restart once to load the new code and replace the old HTTP
route registration. Do **not** enable both integrations simultaneously.
Confirm the Camera Cache entry exists and the images work, then remove the
temporary import block. Existing entries win over imports on later boots.
Keep the old source in a backup for rollback; it is no longer loaded.
Device entries and firmware URLs remain valid.

## Validation and remaining scope

Tests cover real JPEG dimensions/padding, 23 simultaneous readers sharing one
capture, stale refresh, expiry, failure backoff, reader cancellation, alias
behavior and config-entry lifecycle. HA boundaries use test doubles; deployment
also requires a real Home Assistant configuration/startup check.

This is not a recorder, RTSP transcoder, continuous video stream, or external
media worker. An app/add-on would become useful if a future media workload
needed separate processes, dependencies or independent resource limits.

### Developer checks

```sh
python -m pip install -r requirements-test.txt
python -m unittest discover -s tests -v
```

The optional browser regression (`tests/panel-browser.cjs`) uses Playwright
and Chromium with synthetic devices and images. It checks tab navigation,
the details view, camera/MQTT polling suspension, resuming previews and mobile
rendering. Install Playwright in a local test environment and run
`node tests/panel-browser.cjs`. It does not contact production devices.
