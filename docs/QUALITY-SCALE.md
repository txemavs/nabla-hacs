# ∇ Nabla Control — Quality Scale Tracking

**Nabla Control** is a HACS custom integration for Home Assistant. As a Custom
tier integration distributed through HACS, it is **not eligible** for the
official Home Assistant Integration Quality Scale badges (Bronze, Silver, Gold,
Platinum), which apply exclusively to integrations in the core repository.

Nevertheless, we track the [official quality scale rules][quality-scale] as a
checklist to maintain **Gold-level practices** in code, configuration, testing
and documentation.

[quality-scale]: https://developers.home-assistant.io/docs/core/integration-quality-scale/

---

## Target: Gold 🥇

We aim to satisfy all Bronze, Silver and Gold rules where applicable. Platinum
rules are listed as stretch goals but are not required for this project.

### Status Legend

| Status    | Meaning                                              |
|-----------|------------------------------------------------------|
| `done`    | Rule is fully satisfied                              |
| `partial` | Rule is partially implemented; work remains          |
| `todo`    | Rule is not yet addressed                            |
| `exempt`  | Rule does not apply to this integration              |

---

## Bronze Rules

| Rule ID                         | Status    | Notes                                                                 |
|---------------------------------|-----------|-----------------------------------------------------------------------|
| `action-setup`                  | done      | Services registered in `async_setup`, schema validated                |
| `appropriate-polling`           | done      | Configurable poll interval (0.2–30s); no background polling when no viewers |
| `brands`                        | done      | Local brand assets in `brand/` (SVG, PNGs); HA 2026.3+ required       |
| `common-modules`                | done      | Uses `homeassistant.helpers`, `aiohttp_client`, `config_validation`   |
| `config-flow-test-coverage`     | partial   | Config flow exists; no dedicated `test_config_flow.py` yet            |
| `config-flow`                   | done      | Full UI config flow with options, import, and discovery steps         |
| `dependency-transparency`       | done      | `requirements` in manifest; only `Pillow>=10.0.0`                     |
| `docs-actions`                  | done      | `services.yaml` documents `send_action` with selectors                |
| `docs-triggers`                 | exempt    | No device triggers exposed                                            |
| `docs-conditions`               | exempt    | No device conditions exposed                                          |
| `docs-high-level-description`   | done      | README.md describes purpose, features and related projects            |
| `docs-installation-instructions`| done      | HACS and manual install steps in README                               |
| `docs-removal-instructions`     | partial   | Standard HA removal; explicit uninstall doc not written               |
| `entity-event-setup`            | done      | Entities created in `async_setup_entry`; platforms forwarded          |
| `entity-unique-id`              | done      | Buttons use `nabla_control_{device_id}_{action}`                      |
| `has-entity-name`               | done      | `_attr_name` set per entity                                           |
| `runtime-data`                  | done      | Device state stored in `hass.data[DOMAIN]`                            |
| `test-before-configure`         | done      | `probe()` validates device before creating entry                      |
| `test-before-setup`             | done      | `_discover_kind()` runs before polling starts                         |
| `unique-config-entry`           | done      | Duplicate host check; unique IDs per entry                            |

---

## Silver Rules

| Rule ID                         | Status    | Notes                                                                 |
|---------------------------------|-----------|-----------------------------------------------------------------------|
| `action-exceptions`             | partial   | Actions log warnings; no `ServiceValidationError` raised yet          |
| `config-entry-unloading`        | done      | `async_unload_entry` cancels polling and removes device               |
| `docs-configuration-parameters` | done      | Options table in README; `strings.json` documents fields              |
| `docs-installation-parameters`  | done      | Host, name, kind, poll_interval documented                            |
| `entity-unavailable`            | done      | `available` property tracks device reachability                       |
| `integration-owner`             | done      | `codeowners: ["@txemavs"]` in manifest                                |
| `log-when-unavailable`          | done      | Warnings logged on connection/fetch failures                          |
| `parallel-updates`              | done      | Each device polls independently; semaphore limits camera captures     |
| `reauthentication-flow`         | exempt    | No credentials stored; devices are local HTTP                         |
| `test-coverage`                 | partial   | Tests for MQTT, discovery, camera cache, dynamic devices; no full suite |

---

## Gold Rules

| Rule ID                         | Status    | Notes                                                                 |
|---------------------------------|-----------|-----------------------------------------------------------------------|
| `devices`                       | done      | `device_info` with identifiers, name, manufacturer                    |
| `diagnostics`                   | todo      | No `diagnostics.py` yet                                               |
| `discovery-update-info`         | done      | MQTT presence and ESPHome discovery update host without restart       |
| `discovery`                     | done      | ESPHome probe and MQTT identity discovery implemented                 |
| `docs-data-update`              | partial   | Polling described; data-update coordinator doc not explicit           |
| `docs-examples`                 | done      | Lovelace card YAML example in README                                  |
| `docs-known-limitations`        | done      | Limits documented in DISCOVERY.md, MQTT-DISCOVERY.md, CAMERA-CACHE.md |
| `docs-supported-devices`        | partial   | Mirror and web device types described; no hardware list               |
| `docs-supported-functions`      | done      | Features listed: preview, encoder actions, camera, MQTT log           |
| `docs-troubleshooting`          | todo      | No dedicated troubleshooting section                                  |
| `docs-use-cases`                | done      | Use cases described in README and linked docs                         |
| `dynamic-devices`               | done      | Devices added/removed without HA restart; tested in `test_dynamic_devices.py` |
| `entity-category`               | todo      | Buttons do not set `entity_category`                                  |
| `entity-device-class`           | exempt    | Button entities; no applicable device class                           |
| `entity-disabled-by-default`    | todo      | All entities enabled by default                                       |
| `entity-translations`           | partial   | Config flow translated; entity names not in translations              |
| `exception-translations`        | todo      | Error messages not translation-key based                              |
| `icon-translations`             | exempt    | Custom icon set (`nabla:logo`); no translation needed                 |
| `reconfiguration-flow`          | done      | Options flow allows host, poll_interval, kind changes                 |
| `repair-issues`                 | todo      | No `repairs` integration used                                         |
| `stale-devices`                 | partial   | Devices removed on entry delete; no automatic stale cleanup           |

---

## Platinum Rules (Stretch Goals)

These rules are optional for this project but listed for completeness.

| Rule ID                         | Status    | Notes                                                                 |
|---------------------------------|-----------|-----------------------------------------------------------------------|
| `async-dependency`              | done      | Uses `aiohttp` async HTTP client throughout                           |
| `inject-websession`             | done      | `async_get_clientsession(hass)` used consistently                     |
| `strict-typing`                 | todo      | No `py.typed` marker; type hints present but incomplete               |

---

## Summary

| Tier     | Done | Partial | Todo | Exempt | Total |
|----------|------|---------|------|--------|-------|
| Bronze   | 17   | 2       | 0    | 2      | 21    |
| Silver   | 7    | 2       | 0    | 1      | 10    |
| Gold     | 11   | 4       | 6    | 2      | 23    |
| Platinum | 2    | 0       | 1    | 0      | 3     |

This tracking document will be updated as improvements are made.

---

## References

- [Home Assistant Integration Quality Scale](https://developers.home-assistant.io/docs/core/integration-quality-scale/)
- [Nabla Control repository](https://github.com/txemavs/nabla-hacs)
- [Nabla ESP UI firmware](https://github.com/txemavs/nabla-esp-ui)
