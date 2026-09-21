// Explicit discovery settings and identity binding, separate from traffic logging.
class NablaMqttPresence extends HTMLElement {
  constructor(){super();this.attachShadow({mode:'open'});}
  set hass(value){this._hass=value;}
  connectedCallback(){
    this.shadowRoot.innerHTML=`<style>
      section{padding:16px;border:1px solid var(--divider-color);border-radius:10px;margin:12px 0}
      label{display:block;margin:10px 0}button,input,select{font:inherit}button{margin:6px}
      .row{display:flex;flex-wrap:wrap;align-items:center;gap:8px;margin:12px 0}
      p{color:var(--secondary-text-color)}
    </style><section><h3>Descubrimiento y cambios de IP</h3>
    <p>Usa el broker MQTT de Home Assistant. Vincula cada anuncio a su dispositivo una vez: se comprobará su identidad por HTTP antes de cambiar la IP. No hace falta activar el registro de mensajes.</p>
    <label><input type="checkbox" id="enabled"> Activar descubrimiento MQTT</label>
    <label>Prefijo de temas <input id="prefix" value="nabla/discovery" maxlength="128"></label>
    <button id="apply">Aplicar</button><button id="refresh">Actualizar anuncios</button>
    <p id="status" role="status"></p><div id="rows"></div></section>`;
    this.q('apply').onclick=()=>this.load('configure',{enabled:this.q('enabled').checked,topic_prefix:this.q('prefix').value},true);
    this.q('refresh').onclick=()=>this.load();
  }
  q(id){return this.shadowRoot.getElementById(id);}
  open(){this.load('get',{},true);clearInterval(this.timer);this.timer=setInterval(()=>{if(!document.hidden)this.load();},5000);}
  close(){clearInterval(this.timer);}
  disconnectedCallback(){this.close();}
  async load(operation='get',args={},settings=false){
    if(this.busy||!this._hass||!this.isConnected)return;
    this.busy=true;this.q('apply').disabled=true;
    try{
      const data=await this._hass.callWS({type:'nabla_control/mqtt_presence',operation,...args});
      if(!this.isConnected)return;
      if(settings){this.q('enabled').checked=data.enabled;this.q('prefix').value=data.topic_prefix;}
      this.q('status').textContent=data.error||(data.active?`Escuchando · ${data.announcements.length} anuncios recientes`:'Descubrimiento desactivado');
      // Do not replace focused controls during periodic refresh.
      if(operation==='get'&&this.shadowRoot.activeElement?.closest('#rows'))return;
      const rows=this.q('rows');rows.replaceChildren();
      for(const a of data.announcements){
        const row=document.createElement('div');row.className='row';
        const text=document.createElement('span');text.textContent=`${a.name} · ${a.host} · ${a.device_id}`;row.append(text);
        const linked=data.devices.find(d=>d.identity===a.device_id);
        if(linked?.following){const note=document.createElement('span');note.textContent=`Vinculado a ${linked.name}`;row.append(note);}
        else{
          const select=document.createElement('select');select.setAttribute('aria-label',`Vincular ${a.name} a un dispositivo`);
          const placeholder=document.createElement('option');placeholder.value='';placeholder.textContent='Selecciona el dispositivo';select.append(placeholder);
          const add=document.createElement('option');add.value='__new__';add.textContent='Añadir dispositivo nuevo';select.append(add);
          for(const d of data.devices.filter(d=>!d.disabled&&(!d.identity||d.identity===a.device_id))){
            const option=document.createElement('option');option.value=d.entry_id;option.textContent=d.name;select.append(option);
          }
          const button=document.createElement('button');button.textContent='Vincular y seguir IP';button.disabled=true;
          select.onchange=()=>button.disabled=!select.value;
          button.onclick=()=>this.load('bind',{identity:a.device_id,entry_id:select.value==='__new__'?'':select.value});row.append(select,button);
        }
        rows.append(row);
      }
      if(!data.announcements.length)rows.textContent='Los dispositivos necesitan nabla_presence en su YAML. Los anuncios aparecen al conectar y cada minuto.';
    }catch(e){this.q('status').textContent=e.message||String(e);}
    finally{this.busy=false;this.q('apply').disabled=false;}
  }
}
customElements.define('nabla-mqtt-presence',NablaMqttPresence);
