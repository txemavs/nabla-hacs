// Optional MQTT monitor; payloads are rendered as text, never markup.
class NablaMqttLog extends HTMLElement {
  constructor() { super(); this.attachShadow({mode: 'open'}); this._paused = false; }
  set hass(value) { this._hass = value; }
  connectedCallback() {
    this.shadowRoot.innerHTML = `<style>
      details{margin:12px 0;padding:12px;border:1px solid var(--divider-color);border-radius:10px}
      label{display:block;margin:8px 0}textarea{width:95%;min-height:65px}button,input,textarea{font:inherit}
      button{margin:6px}pre{white-space:pre-wrap;overflow-wrap:anywhere;max-height:320px;overflow:auto}
      #status{color:var(--secondary-text-color)}
      </style><details><summary>MQTT · visor opcional</summary>
      <p>Solo lectura. Usa el broker configurado en Home Assistant. Desactivado inicialmente.</p>
      <label><input id="enabled" type="checkbox"> Activar registro</label>
      <label>Temas MQTT (uno por línea, máximo ocho)<textarea id="topics" placeholder="nabla/ha/+/ui/#"></textarea></label>
      <label>Mensajes en memoria <input id="limit" type="number" min="50" max="1000" value="200"></label>
      <button id="apply">Aplicar</button><button id="pause">Pausar vista</button><button id="clear">Limpiar</button>
      <label>Filtrar vista <input id="filter" type="search"></label>
      <p id="status" role="status"></p><pre id="rows"></pre></details>`;
    const q = id => this.shadowRoot.getElementById(id);
    this.shadowRoot.querySelector('details').addEventListener('toggle', async e => {
      clearInterval(this._timer);
      if (e.target.open) {
        await this.refresh(true);
        if (!this.isConnected || !e.target.open) return;
        this._timer = setInterval(() => { if (!this._paused && !document.hidden) this.refresh(); }, 2000);
      }
    });
    q('apply').onclick = async () => {
      if (this._busy) return;
      this._busy = true; q('apply').disabled = true;
      try {
        this.show(await this._hass.callWS({type:'nabla_control/mqtt_log',operation:'configure',
          enabled:q('enabled').checked,topics:q('topics').value.split('\n').map(x=>x.trim()).filter(Boolean),
          limit:Number(q('limit').value)}), true);
      } catch(e) { q('status').textContent = e.message || String(e); }
      finally { this._busy = false; q('apply').disabled = false; }
    };
    q('pause').onclick = () => { this._paused = !this._paused; q('pause').textContent = this._paused ? 'Reanudar vista' : 'Pausar vista'; };
    q('clear').onclick = async () => {
      try { this.show(await this._hass.callWS({type:'nabla_control/mqtt_log',operation:'clear'})); }
      catch(e) { q('status').textContent = e.message || String(e); }
    };
    q('filter').oninput = () => this.renderRows();
  }
  async refresh(settings=false) {
    if (this._busy || !this._hass || !this.isConnected) return;
    this._busy=true;
    try { const data=await this._hass.callWS({type:'nabla_control/mqtt_log'}); if(this.isConnected)this.show(data,settings); }
    catch(e) { this.shadowRoot.getElementById('status').textContent=e.message || String(e); }
    finally { this._busy=false; }
  }
  show(data, settings=false) {
    const q=id=>this.shadowRoot.getElementById(id);
    if(settings){q('enabled').checked=data.enabled;q('topics').value=data.topics.join('\n');q('limit').value=data.limit;}
    q('status').textContent=data.error || `${data.active?'Registro activo':'Registro desactivado'} · últimos ${data.rows.length} mensajes · ${data.dropped} omitidos por límite de tráfico`;
    this._rows=data.rows;this.renderRows();
  }
  renderRows() {
    const filter=this.shadowRoot.getElementById('filter').value.toLowerCase();
    this.shadowRoot.getElementById('rows').textContent=(this._rows||[])
      .filter(r=>(r.topic+' '+r.payload).toLowerCase().includes(filter))
      .map(r=>`${r.time}  ${r.topic}  QoS ${r.qos}${r.retain?' · RETENIDO':''}\n${r.payload}${r.truncated?' [recortado]':''}`)
      .join('\n\n');
  }
  disconnectedCallback(){clearInterval(this._timer);}
}
customElements.define('nabla-mqtt-log',NablaMqttLog);
