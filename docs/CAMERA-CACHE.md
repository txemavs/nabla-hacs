# Camera cache in Nabla Control

## Today

Small Nabla displays (and other clients) need cheap, authenticated JPEG
previews of Home Assistant cameras. That behaviour already exists as a
**temporary standalone integration** on Nave:

- Domain: `nabla_camera_cache`
- HTTP: `GET /api/nabla_camera/{entity_id}?size=view|icon`
- Auth: same as Home Assistant camera views (Bearer / camera access token)
- Engine: demand-driven cache (`cache.py`) — single in-flight capture per
  camera, semaphore, JPEG `view` (≤480px) and `icon` (64×64), freshness
  (`refresh_interval` / `max_stale`), no secrets in logs

Sources today are ordinary HA `camera.*` entities (ESPHome / generic SCAM,
etc.). They do **not** need Nabla firmware on the camera.

Reference implementation (Nave):
`/config/custom_components/nabla_camera_cache/`.
Upstream notes also live under Nabla ESP UI
`services/homeassistant` documentation.

## Target

Fold that capability into **this** HACS package — product **Nabla Control**,
domain `nabla_control` — so camera proxy is not a second integration.

Nabla Control already treats **display** and **camera** as capabilities of
one control surface. The HA camera cache is the same idea for any camera HA
can see, including non-Nabla firmware.

## Adoption plan

1. **Port the cache engine** into `custom_components/nabla_control/`
   (keep the JPEG / single-flight / stale semantics; do not invent a second
   algorithm).
2. **Expose HTTP under Nabla Control**, e.g.
   `GET /api/nabla_control/camera/{entity_id}?size=view|icon`, with the same
   camera authentication model as today.
3. **Configure via Nabla Control** (config entry / options): list of
   `camera.*` entities, refresh interval, max stale, quality. Prefer UI over
   a separate YAML domain.
4. **Surface in the Nabla Control panel** next to mirror / web devices
   (thumbnails from the proxy URL).
5. **Migrate clients** (ESP panels, dashboards) from
   `/api/nabla_camera/...` to `/api/nabla_control/camera/...`.
   Optionally keep a short-lived compatibility alias or redirect so old
   firmware URLs do not break during the cutover.
6. **Deprecate and remove** `nabla_camera_cache` once nothing depends on its
   domain or URL.

## Non-goals (this phase)

- Replacing Home Assistant’s native camera integrations
- Requiring Nabla firmware on every camera (optional later as a first-class
  Nabla camera device kind)
- Long-term dual shipping of `nabla_camera_cache` + `nabla_control`

## Status

| Piece | Status |
|-------|--------|
| Standalone `nabla_camera_cache` on Nave | In use |
| Engine / API inside `nabla_control` | Planned |
| Panel UI for cached cameras | Planned |
| Deprecation of `nabla_camera_cache` | After migration |
