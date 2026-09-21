# Quality Scale Tracking

This document tracks Nabla Control's alignment with Home Assistant's
[Integration Quality Scale](https://developers.home-assistant.io/docs/integration_quality_scale_index/).

**Note:** Official quality scale badges do not apply to custom/HACS integrations.
This tracking is for internal quality maintenance at Gold-level practices.

## Current Status Summary

| Tier | Status |
|------|--------|
| Bronze | Mostly complete |
| Silver | Partial |
| Gold | Partial |
| Platinum | Not targeted |

---

## Bronze Tier

| Rule | Status | Notes |
|------|--------|-------|
| action-setup | done | Services registered in `async_setup` |
| appropriate-polling | done | Configurable 0.2–30s interval, local network only |
| brands | done | Custom brand assets in `brand/` |
| common-modules | done | Uses HA helpers, aiohttp client session |
| config-flow | done | Full UI config flow with options |
| config-flow-test-coverage | todo | Tests exist but coverage not measured |
| dependency-transparency | done | Only Pillow in requirements |
| docs-actions | done | Services documented in README |
| docs-high-level-description | done | README describes purpose |
| docs-installation-instructions | done | HACS and manual install documented |
| docs-removal-instructions | done | Removal section added |
| entity-event-setup | n/a | No event entities |
| entity-unique-id | done | Unique IDs for all entities |
| has-entity-name | partial | Uses `_attr_name` directly |
| runtime-data | partial | Uses `hass.data[DOMAIN]` |
| test-before-configure | done | Probes device before creating entry |
| test-before-setup | done | Discovery probes endpoints |
| unique-config-entry | done | Duplicate host detection |

## Silver Tier

| Rule | Status | Notes |
|------|--------|-------|
| action-exceptions | done | HomeAssistantError/ServiceValidationError raised |
| config-entry-unloading | done | Full unload support |
| docs-configuration-parameters | done | Options table in README |
| docs-installation-parameters | n/a | No install-time parameters beyond config flow |
| entity-unavailable | done | Availability tracks device state |
| integration-owner | done | @txemavs in manifest |
| log-when-unavailable | done | Logs connection failures |
| parallel-updates | partial | Devices poll independently |
| reauthentication-flow | n/a | No external auth required |
| test-coverage | todo | Tests exist, 95% threshold not measured |

## Gold Tier

| Rule | Status | Notes |
|------|--------|-------|
| devices | done | Device registry entries created |
| diagnostics | done | `diagnostics.py` provides entry/device info |
| discovery | partial | ESPHome discovery, no zeroconf/SSDP |
| discovery-update-info | partial | Follow ESPHome address changes |
| docs-data-update | partial | Polling described in README |
| docs-examples | partial | Card example in README |
| docs-known-limitations | todo | Need explicit limitations section |
| docs-supported-devices | partial | Mirror/web types described |
| docs-supported-functions | done | Features listed in README |
| docs-troubleshooting | done | Troubleshooting section added |
| docs-use-cases | partial | Use cases implied in description |
| dynamic-devices | partial | Devices added via config entries |
| entity-category | done | Primary controls remain uncategorized (correct) |
| entity-device-class | partial | Buttons use default class |
| entity-disabled-by-default | done | Secondary actions disabled by default |
| entity-translations | partial | Config strings translated |
| exception-translations | done | Exception translation keys added |
| icon-translations | todo | Icons not using translation keys |
| reconfiguration-flow | done | Options flow for address/settings |
| repair-issues | todo | No repair flows implemented |
| stale-devices | todo | No automatic stale device removal |

## Platinum Tier (Not Targeted)

| Rule | Status | Notes |
|------|--------|-------|
| async-dependency | done | All async code |
| inject-websession | done | Uses `async_get_clientsession` |
| strict-typing | todo | No py.typed marker |

---

## Remaining Work

### Short-term (next PR)

- [ ] `docs-known-limitations`: Add explicit limitations section
- [ ] `icon-translations`: Add icon translation keys
- [ ] `has-entity-name`: Migrate to `_attr_has_entity_name = True` pattern

### Medium-term

- [ ] `test-coverage`: Measure and improve to 95% threshold
- [ ] `repair-issues`: Add repair flows for common problems
- [ ] `stale-devices`: Implement unavailable device cleanup prompts
- [ ] `strict-typing`: Add type hints and py.typed marker

### Not Planned

- Platinum-tier items beyond current scope
- Full zeroconf/SSDP discovery (devices are local ESPHome)
- Official quality scale badge (HACS custom integration)
