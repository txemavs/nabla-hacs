# Nabla Display

View and control Nabla ESP-UI display mirrors in Home Assistant.

## Features

- Live display mirroring from ESP devices
- Encoder control buttons (up/down/enter/back)
- Lovelace card with pixelated rendering
- Service for automation integration
- Fallback profile detection for legacy firmware

## Quick Start

```yaml
# configuration.yaml
nabla_display:
  devices:
    - host: "10.10.10.204"
      name: "My Display"
```

```yaml
# Lovelace card
type: custom:nabla-display-card
device_id: "10_10_10_204"
```

See [README](https://github.com/txemavs/nabla-hacs) for full documentation.
