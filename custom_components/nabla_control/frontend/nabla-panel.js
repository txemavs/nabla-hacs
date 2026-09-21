import "./mqtt-log.js?v=20260921access1";
// Nabla Control panel for Home Assistant (domain: nabla_control)
// Sidebar listing configured Control devices (mirror displays, Nabla web UI, cameras)
// with live preview and dashboard assignment.

class NablaPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._hass = null;
    this._narrow = false;
    this._devices = [];
    this._dashboards = [];
    this._selectedDevice = null;
    this._pollIntervals = new Map();
    this._wsConnection = null;
  }

  set hass(hass) {
    this._hass = hass;
    const monitor = this.shadowRoot.querySelector("nabla-mqtt-log");
    if (monitor) monitor.hass = hass;
    if (!this._initialized) {
      this._initialized = true;
      this._render();
      this._loadData();
    }
  }

  set narrow(narrow) {
    this._narrow = narrow;
  }

  set panel(panel) {
    this._panel = panel;
  }

  async _loadData() {
    await Promise.all([this._loadDevices(), this._loadDashboards()]);
    this._renderDeviceList();
  }

  async _loadDevices() {
    if (!this._hass) return;
    try {
      this._devices = await this._hass.callWS({
        type: "nabla_control/devices",
      });
    } catch (e) {
      console.error("Failed to load nabla devices:", e);
      this._devices = [];
    }
  }

  async _loadDashboards() {
    if (!this._hass) return;
    try {
      this._dashboards = await this._hass.callWS({
        type: "lovelace/dashboards/list",
      });
      // Add default dashboard (null url_path)
      this._dashboards = [
        { url_path: null, title: "Overview (default)", icon: "mdi:view-dashboard" },
        ...this._dashboards,
      ];
    } catch (e) {
      console.error("Failed to load dashboards:", e);
      this._dashboards = [];
    }
  }

  _render() {
    this.shadowRoot.innerHTML = `
      <style>
        :host {
          display: block;
          height: 100%;
          background: var(--primary-background-color, #fafafa);
        }
        .container {
          max-width: 1200px;
          margin: 0 auto;
          padding: 16px;
        }
        .header {
          display: flex;
          flex-wrap: wrap;
          gap: 8px;
          align-items: center;
          justify-content: space-between;
          padding: 16px 0;
          border-bottom: 1px solid var(--divider-color, #e0e0e0);
          margin-bottom: 24px;
        }
        .header h1 {
          margin: 0;
          font-size: 24px;
          font-weight: 400;
          color: var(--primary-text-color);
          display: flex;
          align-items: center;
          gap: 12px;
        }
        .header-icon {
          width: 32px;
          height: 32px;
          color: var(--primary-color);
        }
        .refresh-btn {
          background: var(--primary-color);
          color: white;
          border: none;
          border-radius: 4px;
          padding: 8px 16px;
          cursor: pointer;
          font-size: 14px;
          display: flex;
          align-items: center;
          gap: 8px;
        }
        .refresh-btn:hover {
          filter: brightness(1.1);
        }
        .device-grid {
          display: grid;
          grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
          gap: 16px;
        }
        .device-card {
          background: var(--ha-card-background, var(--card-background-color, white));
          border-radius: 8px;
          box-shadow: var(--ha-card-box-shadow, 0 2px 4px rgba(0,0,0,.1));
          overflow: hidden;
          transition: box-shadow 0.2s;
        }
        .device-card:hover {
          box-shadow: 0 4px 12px rgba(0,0,0,.15);
        }
        .device-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 12px 16px;
          background: var(--primary-color);
          color: white;
        }
        .device-name {
          font-weight: 500;
          font-size: 16px;
        }
        .device-status {
          font-size: 12px;
          padding: 2px 8px;
          border-radius: 12px;
          background: rgba(255,255,255,0.2);
        }
        .device-status.online {
          background: #4caf50;
        }
        .device-status.offline {
          background: #f44336;
        }
        .device-preview {
          display: flex;
          justify-content: center;
          align-items: center;
          padding: 8px;
          background: #1a1a1a;
          height: 220px;
          width: 100%;
          box-sizing: border-box;
        }
        .device-preview img {
          width: 100%;
          height: 100%;
          object-fit: contain;
          image-rendering: pixelated;
          image-rendering: crisp-edges;
          border: 1px solid #333;
          background: #000;
        }
        .device-preview .no-preview {
          color: #666;
          font-size: 14px;
        }
        .device-preview .web-placeholder {
          color: #9e9e9e;
          font-size: 16px;
          text-align: center;
        }
        .device-preview img.mjpeg {
          image-rendering: auto;
        }
        .action-btn.open-nabla {
          background: #00897b;
          color: #fff;
          border-color: #00897b;
        }
        .action-btn.open-nabla:hover {
          filter: brightness(1.08);
        }
        
        .device-encoder {
          display: flex;
          justify-content: center;
          align-items: center;
          gap: 8px;
          padding: 10px 12px 4px;
          background: var(--secondary-background-color, #f5f5f5);
          border-bottom: 1px solid var(--divider-color, #e0e0e0);
        }
        .encoder-btn {
          width: 44px;
          height: 44px;
          border: none;
          border-radius: 50%;
          background: var(--primary-color, #03a9f4);
          color: #fff;
          cursor: pointer;
          display: flex;
          align-items: center;
          justify-content: center;
          transition: filter 0.15s, transform 0.1s;
        }
        .encoder-btn:hover {
          filter: brightness(1.1);
        }
        .encoder-btn:active {
          transform: scale(0.94);
        }
        .encoder-btn svg {
          width: 22px;
          height: 22px;
          fill: currentColor;
        }

        .device-info {
          padding: 12px 16px;
          border-bottom: 1px solid var(--divider-color, #e0e0e0);
        }
        .device-info-row {
          display: flex;
          justify-content: space-between;
          font-size: 13px;
          margin-bottom: 4px;
        }
        .device-info-row:last-child {
          margin-bottom: 0;
        }
        .device-info-label {
          color: var(--secondary-text-color);
        }
        .device-info-value {
          color: var(--primary-text-color);
          font-family: monospace;
        }
        .device-actions {
          padding: 12px 16px;
          display: flex;
          gap: 8px;
          flex-wrap: wrap;
        }
        .action-btn {
          flex: 1;
          min-width: 100px;
          padding: 8px 12px;
          border: 1px solid var(--divider-color, #e0e0e0);
          border-radius: 4px;
          background: var(--card-background-color, white);
          color: var(--primary-text-color);
          cursor: pointer;
          font-size: 13px;
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 6px;
          transition: background 0.2s;
        }
        .action-btn:hover {
          background: var(--secondary-background-color, #f5f5f5);
        }
        .action-btn.primary {
          background: var(--primary-color);
          color: white;
          border-color: var(--primary-color);
        }
        .action-btn.primary:hover {
          filter: brightness(1.1);
        }
        .action-btn svg {
          width: 16px;
          height: 16px;
          fill: currentColor;
        }

        /* Modal styles */
        .modal-overlay {
          display: none;
          position: fixed;
          top: 0;
          left: 0;
          right: 0;
          bottom: 0;
          background: rgba(0,0,0,0.5);
          z-index: 1000;
          justify-content: center;
          align-items: center;
        }
        .modal-overlay.active {
          display: flex;
        }
        .modal {
          background: var(--ha-card-background, white);
          border-radius: 8px;
          max-width: 600px;
          width: 90%;
          max-height: 90vh;
          overflow: auto;
          box-shadow: 0 8px 32px rgba(0,0,0,.3);
        }
        .modal-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 16px 20px;
          border-bottom: 1px solid var(--divider-color, #e0e0e0);
        }
        .modal-header h2 {
          margin: 0;
          font-size: 18px;
          font-weight: 500;
        }
        .modal-close {
          background: none;
          border: none;
          font-size: 24px;
          cursor: pointer;
          color: var(--secondary-text-color);
          padding: 4px;
          line-height: 1;
        }
        .modal-close:hover {
          color: var(--primary-text-color);
        }
        .modal-body {
          padding: 20px;
        }
        .modal-footer {
          display: flex;
          justify-content: flex-end;
          gap: 12px;
          padding: 16px 20px;
          border-top: 1px solid var(--divider-color, #e0e0e0);
        }

        /* Live view modal */
        .live-view-container {
          text-align: center;
        }
        .live-view-container img {
          width: 100%;
          max-height: 70vh;
          object-fit: contain;
          image-rendering: pixelated;
          image-rendering: crisp-edges;
          border: 2px solid #333;
          background: #000;
        }
        .live-controls {
          display: flex;
          justify-content: center;
          gap: 8px;
          margin-top: 16px;
        }
        .control-btn {
          width: 48px;
          height: 48px;
          border: none;
          border-radius: 50%;
          background: var(--primary-color);
          color: white;
          cursor: pointer;
          display: flex;
          align-items: center;
          justify-content: center;
        }
        .control-btn:hover {
          filter: brightness(1.1);
        }
        .control-btn:disabled {
          background: var(--disabled-color, #9e9e9e);
          cursor: not-allowed;
        }
        .control-btn svg {
          width: 24px;
          height: 24px;
          fill: currentColor;
        }
        .live-info {
          margin-top: 12px;
          font-size: 14px;
          color: var(--secondary-text-color);
        }

        /* Dashboard assignment */
        .dashboard-list {
          list-style: none;
          padding: 0;
          margin: 0;
        }
        .dashboard-item {
          display: flex;
          align-items: center;
          padding: 12px;
          border: 1px solid var(--divider-color, #e0e0e0);
          border-radius: 4px;
          margin-bottom: 8px;
          cursor: pointer;
          transition: background 0.2s;
        }
        .dashboard-item:hover {
          background: var(--secondary-background-color, #f5f5f5);
        }
        .dashboard-item.selected {
          border-color: var(--primary-color);
          background: rgba(var(--rgb-primary-color), 0.1);
        }
        .dashboard-icon {
          width: 24px;
          height: 24px;
          margin-right: 12px;
          color: var(--secondary-text-color);
        }
        .dashboard-title {
          flex: 1;
          font-size: 14px;
        }
        .view-select {
          margin-top: 16px;
        }
        .view-select label {
          display: block;
          margin-bottom: 8px;
          font-weight: 500;
        }
        .view-select select {
          width: 100%;
          padding: 10px;
          border: 1px solid var(--divider-color, #e0e0e0);
          border-radius: 4px;
          font-size: 14px;
          background: var(--card-background-color, white);
        }

        /* Card preview */
        .card-preview {
          margin-top: 16px;
          padding: 12px;
          background: var(--secondary-background-color, #f5f5f5);
          border-radius: 4px;
        }
        .card-preview-label {
          font-size: 12px;
          color: var(--secondary-text-color);
          margin-bottom: 8px;
        }
        .card-preview-code {
          font-family: monospace;
          font-size: 12px;
          white-space: pre;
          overflow-x: auto;
          background: #1e1e1e;
          color: #d4d4d4;
          padding: 12px;
          border-radius: 4px;
        }
        .copy-btn {
          margin-top: 8px;
          padding: 6px 12px;
          font-size: 12px;
        }

        .success-message {
          padding: 12px;
          background: #e8f5e9;
          color: #2e7d32;
          border-radius: 4px;
          margin-bottom: 16px;
        }
        .error-message {
          padding: 12px;
          background: #ffebee;
          color: #c62828;
          border-radius: 4px;
          margin-bottom: 16px;
        }

        .empty-state {
          text-align: center;
          padding: 48px 24px;
          color: var(--secondary-text-color);
        }
        .empty-state svg {
          width: 64px;
          height: 64px;
          margin-bottom: 16px;
          opacity: 0.5;
        }
        .empty-state h3 {
          margin: 0 0 8px;
          color: var(--primary-text-color);
        }
        .empty-state p {
          margin: 0;
        }
      </style>

      <div class="container">
        <div class="header">
          <h1>
            <svg class="header-icon" viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M2.4 6.4574373H21.6L12 23.0851253Z M5.664 8.341908L12 19.3161827L18.336 8.341908Z"/></svg>
            Nabla Control
          </h1>
          <button class="refresh-btn" id="mqtt-open">MQTT</button>
          <a class="refresh-btn" href="/config/integrations/integration/nabla_control">Gestionar dispositivos</a>
          <button class="refresh-btn" id="refresh-btn">
            <svg viewBox="0 0 24 24" width="18" height="18"><path fill="currentColor" d="M17.65,6.35C16.2,4.9 14.21,4 12,4A8,8 0 0,0 4,12A8,8 0 0,0 12,20C15.73,20 18.84,17.45 19.73,14H17.65C16.83,16.33 14.61,18 12,18A6,6 0 0,1 6,12A6,6 0 0,1 12,6C13.66,6 15.14,6.69 16.22,7.78L13,11H20V4L17.65,6.35Z"/></svg>
            Refresh
          </button>
        </div>
        <nabla-mqtt-log></nabla-mqtt-log>
        <div class="device-grid" id="device-grid">
          <!-- Devices rendered here -->
        </div>
      </div>

      <!-- Live View Modal -->
      <div class="modal-overlay" id="live-modal">
        <div class="modal">
          <div class="modal-header">
            <h2 id="live-modal-title">Live View</h2>
            <button class="modal-close" id="live-modal-close">&times;</button>
          </div>
          <div class="modal-body">
            <div class="live-view-container">
              <img id="live-frame" alt="Live display" />
              <div class="live-controls" id="live-controls">
                <button class="control-btn" data-action="up" title="Up">
                  <svg viewBox="0 0 24 24"><path d="M7.41 15.41L12 10.83l4.59 4.58L18 14l-6-6-6 6z"/></svg>
                </button>
                <button class="control-btn" data-action="down" title="Down">
                  <svg viewBox="0 0 24 24"><path d="M7.41 8.59L12 13.17l4.59-4.58L18 10l-6 6-6-6z"/></svg>
                </button>
                <button class="control-btn" data-action="enter" title="Enter">
                  <svg viewBox="0 0 24 24"><path d="M9 16.2L4.8 12l-1.4 1.4L9 19 21 7l-1.4-1.4L9 16.2z"/></svg>
                </button>
                <button class="control-btn" data-action="back" title="Back">
                  <svg viewBox="0 0 24 24"><path d="M20 11H7.83l5.59-5.59L12 4l-8 8 8 8 1.41-1.41L7.83 13H20v-2z"/></svg>
                </button>
              </div>
              <div class="live-info" id="live-info"></div>
            </div>
          </div>
        </div>
      </div>

      <!-- Assign to Dashboard Modal -->
      <div class="modal-overlay" id="assign-modal">
        <div class="modal">
          <div class="modal-header">
            <h2>Add to Dashboard</h2>
            <button class="modal-close" id="assign-modal-close">&times;</button>
          </div>
          <div class="modal-body">
            <div id="assign-message"></div>
            <p style="margin-top:0;">Select a dashboard to add the Nabla Control card:</p>
            <ul class="dashboard-list" id="dashboard-list">
              <!-- Dashboards rendered here -->
            </ul>
            <div class="view-select" id="view-select-container" style="display:none;">
              <label for="view-select">Select view:</label>
              <select id="view-select">
                <option value="">Loading views...</option>
              </select>
            </div>
            <div class="card-preview">
              <div class="card-preview-label">Card configuration:</div>
              <pre class="card-preview-code" id="card-preview"></pre>
              <button class="action-btn copy-btn" id="copy-yaml-btn">
                <svg viewBox="0 0 24 24" width="14" height="14"><path fill="currentColor" d="M19,21H8V7H19M19,5H8A2,2 0 0,0 6,7V21A2,2 0 0,0 8,23H19A2,2 0 0,0 21,21V7A2,2 0 0,0 19,5M16,1H4A2,2 0 0,0 2,3V17H4V3H16V1Z"/></svg>
                Copy YAML
              </button>
            </div>
          </div>
          <div class="modal-footer">
            <button class="action-btn" id="assign-cancel">Cancel</button>
            <button class="action-btn primary" id="assign-confirm">Add Card</button>
          </div>
        </div>
      </div>
    `;

    this.shadowRoot.querySelector("nabla-mqtt-log").hass = this._hass;
    this._setupEventListeners();
  }

  _setupEventListeners() {
    this.shadowRoot.getElementById("mqtt-open").addEventListener("click", () => {
      this.shadowRoot.querySelector("nabla-mqtt-log").open();
    });
    // Refresh button
    this.shadowRoot.getElementById("refresh-btn").addEventListener("click", () => {
      this._loadData();
    });

    // Live modal
    this.shadowRoot.getElementById("live-modal-close").addEventListener("click", () => {
      this._closeLiveModal();
    });
    this.shadowRoot.getElementById("live-modal").addEventListener("click", (e) => {
      if (e.target.id === "live-modal") this._closeLiveModal();
    });

    // Live controls
    this.shadowRoot.getElementById("live-controls").addEventListener("click", (e) => {
      const btn = e.target.closest(".control-btn");
      if (btn && this._selectedDevice) {
        this._sendAction(this._selectedDevice.device_id, btn.dataset.action);
      }
    });

    // Assign modal
    this.shadowRoot.getElementById("assign-modal-close").addEventListener("click", () => {
      this._closeAssignModal();
    });
    this.shadowRoot.getElementById("assign-modal").addEventListener("click", (e) => {
      if (e.target.id === "assign-modal") this._closeAssignModal();
    });
    this.shadowRoot.getElementById("assign-cancel").addEventListener("click", () => {
      this._closeAssignModal();
    });
    this.shadowRoot.getElementById("assign-confirm").addEventListener("click", () => {
      this._confirmAssign();
    });
    this.shadowRoot.getElementById("copy-yaml-btn").addEventListener("click", () => {
      this._copyYaml();
    });
  }

  _renderDeviceList() {
    const grid = this.shadowRoot.getElementById("device-grid");

    if (this._devices.length === 0) {
      grid.innerHTML = `
        <div class="empty-state">
          <svg viewBox="0 0 24 24"><path fill="currentColor" d="M21,16H3V4H21M21,2H3C1.89,2 1,2.89 1,4V16A2,2 0 0,0 3,18H10V20H8V22H16V20H14V18H21A2,2 0 0,0 23,16V4C23,2.89 22.1,2 21,2Z"/></svg>
          <h3>No Nabla Control devices configured</h3>
          <p>Add Control devices to your configuration.yaml under nabla_control.</p>
        </div>
      `;
      return;
    }

    grid.innerHTML = this._devices
      .map(
        (device) => {
          const isWeb = device.kind === "web";
          const openUrl = device.open_url || device.web_url || `http://${device.host}/`;
          let previewHtml;
          if (isWeb) {
            if (device.has_camera && device.camera_url) {
              previewHtml = `<img id="preview-${device.device_id}" class="mjpeg" alt="${this._escapeHtml(device.name || device.device_id)}" src="${this._escapeHtml(device.camera_url)}" />`;
            } else if (device.available) {
              previewHtml = '<span class="web-placeholder">Nabla Web</span>';
            } else {
              previewHtml = '<span class="no-preview">No preview available</span>';
            }
          } else if (device.available) {
            previewHtml = `<img id="preview-${device.device_id}" alt="${this._escapeHtml(device.name || device.device_id)}" />`;
          } else {
            previewHtml = '<span class="no-preview">No preview available</span>';
          }

          const infoExtra = isWeb
            ? `<div class="device-info-row">
            <span class="device-info-label">Kind</span>
            <span class="device-info-value">Web</span>
          </div>
          <div class="device-info-row">
            <span class="device-info-label">Camera</span>
            <span class="device-info-value">${device.has_camera ? "Yes" : "No"}</span>
          </div>`
            : `<div class="device-info-row">
            <span class="device-info-label">Kind</span>
            <span class="device-info-value">Mirror</span>
          </div>
          <div class="device-info-row">
            <span class="device-info-label">Resolution</span>
            <span class="device-info-value">${device.width}×${device.height}</span>
          </div>
          <div class="device-info-row">
            <span class="device-info-label">Format</span>
            <span class="device-info-value">${device.format}</span>
          </div>
          <div class="device-info-row">
            <span class="device-info-label">Input</span>
            <span class="device-info-value">${device.has_input ? "Yes" : "No"}</span>
          </div>`;

          const actions = isWeb
            ? `<button class="action-btn open-nabla" data-action="open" data-device-id="${device.device_id}" data-open-url="${this._escapeHtml(openUrl)}">
            <svg viewBox="0 0 24 24"><path fill="currentColor" d="M14,3V5H17.59L7.76,14.83L9.17,16.24L19,6.41V10H21V3M19,19H5V5H12V3H5C3.89,3 3,3.9 3,5V19A2,2 0 0,0 5,21H19A2,2 0 0,0 21,19V12H19V19Z"/></svg>
            Open Nabla
          </button>
          <button class="action-btn" data-action="live" data-device-id="${device.device_id}">
            <svg viewBox="0 0 24 24"><path fill="currentColor" d="M12,9A3,3 0 0,0 9,12A3,3 0 0,0 12,15A3,3 0 0,0 15,12A3,3 0 0,0 12,9M12,17A5,5 0 0,1 7,12A5,5 0 0,1 12,7A5,5 0 0,1 17,12A5,5 0 0,1 12,17M12,4.5C7,4.5 2.73,7.61 1,12C2.73,16.39 7,19.5 12,19.5C17,19.5 21.27,16.39 23,12C21.27,7.61 17,4.5 12,4.5Z"/></svg>
            Live View
          </button>`
            : `<button class="action-btn" data-action="live" data-device-id="${device.device_id}">
            <svg viewBox="0 0 24 24"><path fill="currentColor" d="M12,9A3,3 0 0,0 9,12A3,3 0 0,0 12,15A3,3 0 0,0 15,12A3,3 0 0,0 12,9M12,17A5,5 0 0,1 7,12A5,5 0 0,1 12,7A5,5 0 0,1 17,12A5,5 0 0,1 12,17M12,4.5C7,4.5 2.73,7.61 1,12C2.73,16.39 7,19.5 12,19.5C17,19.5 21.27,16.39 23,12C21.27,7.61 17,4.5 12,4.5Z"/></svg>
            Live View
          </button>
          <button class="action-btn primary" data-action="assign" data-device-id="${device.device_id}">
            <svg viewBox="0 0 24 24"><path fill="currentColor" d="M19,13H13V19H11V13H5V11H11V5H13V11H19V13Z"/></svg>
            Add to Dashboard
          </button>`;

          return `
      <div class="device-card" data-device-id="${device.device_id}">
        <div class="device-header">
          <span class="device-name">${this._escapeHtml(device.name)}</span>
          <span class="device-status ${device.available ? "online" : "offline"}">
            ${device.available ? "Online" : "Offline"}
          </span>
        </div>
        <div class="device-preview">
          ${previewHtml}
        </div>

        ${
          !isWeb && device.has_input
            ? `<div class="device-encoder" data-device-id="${device.device_id}">
          <button type="button" class="encoder-btn" data-encoder="up" data-device-id="${device.device_id}" title="Up">
            <svg viewBox="0 0 24 24"><path d="M7.41 15.41L12 10.83l4.59 4.58L18 14l-6-6-6 6z"/></svg>
          </button>
          <button type="button" class="encoder-btn" data-encoder="down" data-device-id="${device.device_id}" title="Down">
            <svg viewBox="0 0 24 24"><path d="M7.41 8.59L12 13.17l4.59-4.58L18 10l-6 6-6-6z"/></svg>
          </button>
          <button type="button" class="encoder-btn" data-encoder="enter" data-device-id="${device.device_id}" title="Enter">
            <svg viewBox="0 0 24 24"><path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/></svg>
          </button>
          <button type="button" class="encoder-btn" data-encoder="back" data-device-id="${device.device_id}" title="Back">
            <svg viewBox="0 0 24 24"><path d="M20 11H7.83l5.59-5.59L12 4l-8 8 8 8 1.41-1.41L7.83 13H20v-2z"/></svg>
          </button>
        </div>`
            : ""
        }
        <div class="device-info">
          <div class="device-info-row">
            <span class="device-info-label">Host</span>
            <span class="device-info-value">${this._escapeHtml(device.host)}</span>
          </div>
          ${infoExtra}
        </div>
        <div class="device-actions">
          ${actions}
        </div>
      </div>
    `;
        }
      )
      .join("");

    // Add click handlers for actions
    grid.querySelectorAll(".action-btn").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        const deviceId = btn.dataset.deviceId;
        const action = btn.dataset.action;
        const device = this._devices.find((d) => d.device_id === deviceId);
        if (action === "open") {
          const url = btn.dataset.openUrl || (device && (device.open_url || device.web_url)) || (device && `http://${device.host}/`);
          if (url) window.open(url, "_blank");
        } else if (action === "live") {
          this._openLiveModal(device);
        } else if (action === "assign") {
          this._openAssignModal(device);
        }
      });
    });

    grid.querySelectorAll(".encoder-btn").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        const deviceId = btn.dataset.deviceId;
        const action = btn.dataset.encoder;
        if (deviceId && action) {
          this._sendAction(deviceId, action);
        }
      });
    });

    // Start polling previews
    this._startPreviewPolling();
  }


  async _loadAuthenticatedFrame(imgEl, deviceId) {
    if (!imgEl || !this._hass || !deviceId) return;
    try {
      const url = `/api/nabla_control/${deviceId}/frame?t=${Date.now()}`;
      const resp = await fetch(url, {
        headers: { Authorization: `Bearer ${this._hass.auth.data.access_token}` },
        cache: "no-store",
      });
      if (!resp.ok) {
        imgEl.removeAttribute("src");
        return;
      }
      const blob = await resp.blob();
      const old = imgEl.src;
      imgEl.src = URL.createObjectURL(blob);
      if (old && old.startsWith("blob:")) URL.revokeObjectURL(old);
    } catch (e) {
      console.warn("Nabla frame load failed", deviceId, e);
    }
  }

  _startPreviewPolling() {
    // Clear existing intervals
    this._pollIntervals.forEach((interval) => clearInterval(interval));
    this._pollIntervals.clear();

    // Poll each mirror device's preview (web MJPEG uses camera_url as img.src)
    this._devices.forEach((device) => {
      if (device.available && device.kind !== "web") {
        const interval = setInterval(() => {
          const img = this.shadowRoot.getElementById(`preview-${device.device_id}`);
          if (img) {
            this._loadAuthenticatedFrame(img, device.device_id);
          }
        }, 2000);
        this._pollIntervals.set(device.device_id, interval);
        // Initial load
        const img0 = this.shadowRoot.getElementById(`preview-${device.device_id}`);
        if (img0) this._loadAuthenticatedFrame(img0, device.device_id);
      }
    });
  }

  _openLiveModal(device) {
    this._selectedDevice = device;
    const modal = this.shadowRoot.getElementById("live-modal");
    const title = this.shadowRoot.getElementById("live-modal-title");
    const frame = this.shadowRoot.getElementById("live-frame");
    const controls = this.shadowRoot.getElementById("live-controls");
    const info = this.shadowRoot.getElementById("live-info");

    title.textContent = `Live View - ${device.name}`;
    controls.style.display = device.has_input && device.kind !== "web" ? "flex" : "none";

    if (device.kind === "web") {
      const openUrl = device.open_url || device.web_url || `http://${device.host}/`;
      if (device.has_camera && device.camera_url) {
        frame.removeAttribute("style");
        frame.style.maxWidth = "100%";
        frame.style.width = "640px";
        frame.src = device.camera_url;
        info.textContent = `Nabla Web · Camera MJPEG · ${openUrl}`;
      } else {
        frame.removeAttribute("src");
        info.textContent = `Nabla Web · No camera · ${openUrl}`;
        window.open(openUrl, "_blank");
      }
      modal.classList.add("active");
      return;
    }

    this._loadAuthenticatedFrame(frame, device.device_id);
    frame.style.width = `${Math.min(device.width * 3, 480)}px`;
    info.textContent = `${device.width}×${device.height} ${device.format}`;

    modal.classList.add("active");

    // Start live polling
    this._liveInterval = setInterval(() => {
      this._loadAuthenticatedFrame(frame, device.device_id);
    }, 500);
  }

  _closeLiveModal() {
    const modal = this.shadowRoot.getElementById("live-modal");
    modal.classList.remove("active");
    this._selectedDevice = null;
    if (this._liveInterval) {
      clearInterval(this._liveInterval);
      this._liveInterval = null;
    }
    const frame = this.shadowRoot.getElementById("live-frame");
    if (frame) {
      frame.removeAttribute("src");
    }
  }

  async _sendAction(deviceId, action) {
    if (!this._hass) return;
    try {
      await this._hass.callService("nabla_control", "send_action", {
        device_id: deviceId,
        action: action,
      });
    } catch (e) {
      console.error("Failed to send action:", e);
    }
  }

  _openAssignModal(device) {
    this._selectedDevice = device;
    this._selectedDashboard = null;
    this._selectedView = 0;
    this._dashboardConfig = null;

    const modal = this.shadowRoot.getElementById("assign-modal");
    const list = this.shadowRoot.getElementById("dashboard-list");
    const viewContainer = this.shadowRoot.getElementById("view-select-container");
    const message = this.shadowRoot.getElementById("assign-message");

    message.innerHTML = "";
    viewContainer.style.display = "none";

    // Render dashboard list
    list.innerHTML = this._dashboards
      .map(
        (db) => `
      <li class="dashboard-item" data-url-path="${db.url_path || ""}">
        <svg class="dashboard-icon" viewBox="0 0 24 24"><path fill="currentColor" d="M13,3V9H21V3M13,21H21V11H13M3,21H11V15H3M3,13H11V3H3V13Z"/></svg>
        <span class="dashboard-title">${this._escapeHtml(db.title || db.url_path || "Untitled")}</span>
      </li>
    `
      )
      .join("");

    // Add click handlers
    list.querySelectorAll(".dashboard-item").forEach((item) => {
      item.addEventListener("click", () => {
        list.querySelectorAll(".dashboard-item").forEach((i) => i.classList.remove("selected"));
        item.classList.add("selected");
        const urlPath = item.dataset.urlPath || null;
        this._selectDashboard(urlPath === "" ? null : urlPath);
      });
    });

    // Update card preview
    this._updateCardPreview();

    modal.classList.add("active");
  }

  async _selectDashboard(urlPath) {
    this._selectedDashboard = urlPath;
    const viewContainer = this.shadowRoot.getElementById("view-select-container");
    const viewSelect = this.shadowRoot.getElementById("view-select");

    try {
      // Fetch dashboard config
      this._dashboardConfig = await this._hass.callWS({
        type: "lovelace/config",
        url_path: urlPath,
      });

      if (this._dashboardConfig && this._dashboardConfig.views) {
        viewSelect.innerHTML = this._dashboardConfig.views
          .map(
            (view, idx) => `
            <option value="${idx}">${this._escapeHtml(view.title || `View ${idx + 1}`)}</option>
          `
          )
          .join("");

        viewContainer.style.display = "block";
        viewSelect.onchange = (e) => {
          this._selectedView = parseInt(e.target.value, 10);
        };
        this._selectedView = 0;
      } else {
        viewContainer.style.display = "none";
      }
    } catch (e) {
      console.error("Failed to load dashboard config:", e);
      viewContainer.style.display = "none";
      this._dashboardConfig = null;
    }
  }

  _updateCardPreview() {
    const preview = this.shadowRoot.getElementById("card-preview");
    if (!this._selectedDevice) return;

    const yaml = `type: custom:nabla-control-card
device_id: "${this._selectedDevice.device_id}"
name: "${this._selectedDevice.name}"
poll_interval: 1000
scale: 2
show_controls: ${this._selectedDevice.has_input}`;

    preview.textContent = yaml;
  }

  _closeAssignModal() {
    const modal = this.shadowRoot.getElementById("assign-modal");
    modal.classList.remove("active");
    this._selectedDevice = null;
    this._selectedDashboard = null;
    this._dashboardConfig = null;
  }

  async _confirmAssign() {
    if (!this._selectedDevice) return;

    const message = this.shadowRoot.getElementById("assign-message");

    // Build the card config
    const cardConfig = {
      type: "custom:nabla-control-card",
      device_id: this._selectedDevice.device_id,
      name: this._selectedDevice.name,
      poll_interval: 1000,
      scale: 2,
      show_controls: this._selectedDevice.has_input,
    };

    if (!this._dashboardConfig || this._selectedDashboard === null) {
      // No dashboard selected or config not loaded - show copy instructions
      message.innerHTML = `
        <div class="error-message">
          Please select a dashboard first, or copy the YAML above and paste it manually into your dashboard.
        </div>
      `;
      return;
    }

    try {
      // Clone the config and add the card to the selected view
      const newConfig = JSON.parse(JSON.stringify(this._dashboardConfig));

      if (!newConfig.views || newConfig.views.length === 0) {
        newConfig.views = [{ title: "Home", cards: [] }];
      }

      if (!newConfig.views[this._selectedView].cards) {
        newConfig.views[this._selectedView].cards = [];
      }

      newConfig.views[this._selectedView].cards.push(cardConfig);

      // Save the config
      await this._hass.callWS({
        type: "lovelace/config/save",
        url_path: this._selectedDashboard,
        config: newConfig,
      });

      message.innerHTML = `
        <div class="success-message">
          Card added successfully! The dashboard will update automatically.
        </div>
      `;

      // Close after a short delay
      setTimeout(() => {
        this._closeAssignModal();
      }, 1500);
    } catch (e) {
      console.error("Failed to save dashboard config:", e);
      message.innerHTML = `
        <div class="error-message">
          Failed to save: ${e.message || "Unknown error"}. 
          This may happen if the dashboard uses YAML mode. 
          Copy the YAML above and paste it manually.
        </div>
      `;
    }
  }

  async _copyYaml() {
    const preview = this.shadowRoot.getElementById("card-preview");
    try {
      await navigator.clipboard.writeText(preview.textContent);
      const btn = this.shadowRoot.getElementById("copy-yaml-btn");
      const originalText = btn.innerHTML;
      btn.innerHTML = '<svg viewBox="0 0 24 24" width="14" height="14"><path fill="currentColor" d="M21,7L9,19L3.5,13.5L4.91,12.09L9,16.17L19.59,5.59L21,7Z"/></svg> Copied!';
      setTimeout(() => {
        btn.innerHTML = originalText;
      }, 2000);
    } catch (e) {
      console.error("Failed to copy:", e);
    }
  }

  _escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
  }

  disconnectedCallback() {
    this._pollIntervals.forEach((interval) => clearInterval(interval));
    this._pollIntervals.clear();
    if (this._liveInterval) {
      clearInterval(this._liveInterval);
    }
  }
}

customElements.define("nabla-panel", NablaPanel);
