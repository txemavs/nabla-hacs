# Nabla Control

Control and monitor Nabla devices from Home Assistant — mirror displays, Nabla web UI, and camera streams.

On-device menus are defined by device YAML and **[Nabla ESP UI](https://github.com/txemavs/nabla-esp-ui)**
(“Device YAML supplies menus, content and actions”). This integration is the HA control surface.

Domain remains `nabla_display` for configuration and APIs.

## Quick Start

```yaml
nabla_display:
  devices:
    - host: "10.10.10.204"
      name: "Kit1"
    - host: "10.10.10.251"
      name: "Dashcam Web"
      kind: web
      poll_interval: 5.0
```

After restart, open **Nabla Control** from the sidebar.
