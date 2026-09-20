// Nabla Display Lovelace card for Home Assistant.
// Displays ESP device screen mirror with optional encoder controls.
// Frame decoding happens server-side; this card just renders the PNG.

class NablaDisplayCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = null;
    this._hass = null;
    this._pollInterval = null;
    this._width = 0;
    this._height = 0;
    this._hasInput = false;
    this._available = false;
  }

  setConfig(config) {
    if (!config.device_id) {
      throw new Error("You need to define a device_id");
    }
    this._config = {
      type: "custom:nabla-display-card",
      device_id: config.device_id,
      name: config.name || "Nabla Display",
      poll_interval: config.poll_interval || 1000,
      scale: config.scale || 2,
      show_controls: config.show_controls !== false,
    };
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._startPolling();
  }

  _render() {
    this.shadowRoot.innerHTML = `
      <style>
        :host {
          display: block;
        }
        .card {
          padding: 16px;
          background: var(--ha-card-background, var(--card-background-color, white));
          border-radius: var(--ha-card-border-radius, 4px);
          box-shadow: var(--ha-card-box-shadow, 0 2px 2px rgba(0,0,0,.14));
        }
        .header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 12px;
        }
        .title {
          font-size: 1.1em;
          font-weight: 500;
          color: var(--primary-text-color);
        }
        .status {
          font-size: 0.85em;
          padding: 2px 8px;
          border-radius: 4px;
        }
        .status.online {
          background: #4caf50;
          color: white;
        }
        .status.offline {
          background: #f44336;
          color: white;
        }
        .display-container {
          display: flex;
          justify-content: center;
          margin-bottom: 12px;
        }
        .display-frame {
          image-rendering: pixelated;
          image-rendering: crisp-edges;
          border: 1px solid var(--divider-color, #e0e0e0);
          background: #000;
        }
        .controls {
          display: flex;
          justify-content: center;
          gap: 8px;
          flex-wrap: wrap;
        }
        .control-btn {
          display: flex;
          align-items: center;
          justify-content: center;
          width: 48px;
          height: 48px;
          border: none;
          border-radius: 50%;
          background: var(--primary-color);
          color: white;
          cursor: pointer;
          transition: background 0.2s;
        }
        .control-btn:hover {
          background: var(--primary-color);
          filter: brightness(1.1);
        }
        .control-btn:active {
          filter: brightness(0.9);
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
        .info {
          text-align: center;
          font-size: 0.8em;
          color: var(--secondary-text-color);
          margin-top: 8px;
        }
        .error-message {
          text-align: center;
          padding: 20px;
          color: var(--error-color, #f44336);
        }
      </style>
      <div class="card">
        <div class="header">
          <span class="title">${this._config.name}</span>
          <span class="status ${this._available ? "online" : "offline"}">
            ${this._available ? "Live" : "Offline"}
          </span>
        </div>
        <div class="display-container">
          <img class="display-frame" id="frame" alt="Display" />
        </div>
        ${this._config.show_controls && this._hasInput ? this._renderControls() : ""}
        <div class="info" id="info"></div>
      </div>
    `;
    this._setupControls();
  }

  _renderControls() {
    return `
      <div class="controls">
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
    `;
  }

  _setupControls() {
    const buttons = this.shadowRoot.querySelectorAll(".control-btn");
    buttons.forEach((btn) => {
      btn.addEventListener("click", () => {
        const action = btn.dataset.action;
        this._sendAction(action);
      });
    });
  }

  async _sendAction(action) {
    if (!this._hass || !this._config) return;

    try {
      await this._hass.callService("nabla_display", "send_action", {
        device_id: this._config.device_id,
        action: action,
      });
    } catch (e) {
      console.error("Failed to send action:", e);
    }
  }

  _startPolling() {
    if (this._pollInterval) {
      clearInterval(this._pollInterval);
    }
    this._fetchFrame();
    this._pollInterval = setInterval(() => {
      this._fetchFrame();
    }, this._config.poll_interval);
  }

  async _fetchFrame() {
    if (!this._hass || !this._config) return;

    const frameImg = this.shadowRoot.getElementById("frame");
    const infoDiv = this.shadowRoot.getElementById("info");
    const statusSpan = this.shadowRoot.querySelector(".status");

    try {
      const url = `/api/nabla_display/${this._config.device_id}/frame`;
      const response = await fetch(url, {
        headers: {
          Authorization: `Bearer ${this._hass.auth.data.access_token}`,
        },
      });

      if (response.ok) {
        const blob = await response.blob();
        const imgUrl = URL.createObjectURL(blob);

        const oldUrl = frameImg.src;
        frameImg.src = imgUrl;
        if (oldUrl && oldUrl.startsWith("blob:")) {
          URL.revokeObjectURL(oldUrl);
        }

        this._width = parseInt(response.headers.get("X-Nabla-Width") || "0");
        this._height = parseInt(response.headers.get("X-Nabla-Height") || "0");
        this._hasInput = response.headers.get("X-Nabla-Input") === "1";
        const format = response.headers.get("X-Nabla-Format") || "unknown";

        if (this._width && this._height) {
          frameImg.style.width = `${this._width * this._config.scale}px`;
          frameImg.style.height = `${this._height * this._config.scale}px`;
        }

        infoDiv.textContent = `${this._width}×${this._height} ${format}`;

        if (!this._available) {
          this._available = true;
          this._render();
        }

        statusSpan.className = "status online";
        statusSpan.textContent = "Live";
      } else {
        this._setOffline(statusSpan, infoDiv);
      }
    } catch (e) {
      console.error("Frame fetch error:", e);
      this._setOffline(statusSpan, infoDiv);
    }
  }

  _setOffline(statusSpan, infoDiv) {
    if (statusSpan) {
      statusSpan.className = "status offline";
      statusSpan.textContent = "Offline";
    }
    if (infoDiv) {
      infoDiv.textContent = "Device unavailable";
    }
    if (this._available) {
      this._available = false;
    }
  }

  disconnectedCallback() {
    if (this._pollInterval) {
      clearInterval(this._pollInterval);
      this._pollInterval = null;
    }
  }

  getCardSize() {
    return 4;
  }

  static getConfigElement() {
    return document.createElement("nabla-display-card-editor");
  }

  static getStubConfig() {
    return {
      type: "custom:nabla-display-card",
      device_id: "",
      name: "Nabla Display",
      poll_interval: 1000,
      scale: 2,
      show_controls: true,
    };
  }
}

class NablaDisplayCardEditor extends HTMLElement {
  constructor() {
    super();
    this._config = {};
  }

  setConfig(config) {
    this._config = config;
    this._render();
  }

  _render() {
    this.innerHTML = `
      <style>
        .form-row {
          margin-bottom: 12px;
        }
        .form-row label {
          display: block;
          margin-bottom: 4px;
          font-weight: 500;
        }
        .form-row input, .form-row select {
          width: 100%;
          padding: 8px;
          border: 1px solid var(--divider-color, #e0e0e0);
          border-radius: 4px;
        }
      </style>
      <div class="form-row">
        <label>Device ID (host with dots as underscores, e.g., 192_168_1_100)</label>
        <input type="text" id="device_id" value="${this._config.device_id || ""}" />
      </div>
      <div class="form-row">
        <label>Name</label>
        <input type="text" id="name" value="${this._config.name || "Nabla Display"}" />
      </div>
      <div class="form-row">
        <label>Poll interval (ms)</label>
        <input type="number" id="poll_interval" value="${this._config.poll_interval || 1000}" min="200" max="10000" />
      </div>
      <div class="form-row">
        <label>Scale factor</label>
        <input type="number" id="scale" value="${this._config.scale || 2}" min="1" max="5" />
      </div>
      <div class="form-row">
        <label>
          <input type="checkbox" id="show_controls" ${this._config.show_controls !== false ? "checked" : ""} />
          Show controls
        </label>
      </div>
    `;

    this.querySelectorAll("input").forEach((input) => {
      input.addEventListener("change", () => this._valueChanged());
    });
  }

  _valueChanged() {
    const config = {
      type: "custom:nabla-display-card",
      device_id: this.querySelector("#device_id").value,
      name: this.querySelector("#name").value || "Nabla Display",
      poll_interval: parseInt(this.querySelector("#poll_interval").value) || 1000,
      scale: parseInt(this.querySelector("#scale").value) || 2,
      show_controls: this.querySelector("#show_controls").checked,
    };
    this._config = config;
    const event = new CustomEvent("config-changed", { detail: { config } });
    this.dispatchEvent(event);
  }
}

customElements.define("nabla-display-card", NablaDisplayCard);
customElements.define("nabla-display-card-editor", NablaDisplayCardEditor);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "nabla-display-card",
  name: "Nabla Display Card",
  description: "Display mirror for Nabla ESP-UI devices with optional encoder controls",
  preview: false,
});
