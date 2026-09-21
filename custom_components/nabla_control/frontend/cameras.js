// Only the visible camera panel requests images. Each backend capture is shared.
class NablaCameras extends HTMLElement {
  constructor() { super(); this.attachShadow({mode:'open'}); this._generation=0; }
  set hass(value) { this._hass=value; }
  set active(value) { this._active=value; this.stop(); if(value) this.load(); }
  connectedCallback() {
    this.shadowRoot.innerHTML=`<style>
      .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:16px}
      article{padding:16px;border:1px solid var(--divider-color);border-radius:12px}
      img{width:100%;height:240px;object-fit:contain;background:#000}button,select{font:inherit}
      header{display:flex;justify-content:space-between;gap:12px;margin-bottom:16px}
      small{display:block;color:var(--secondary-text-color);margin:8px 0}
    </style><header><span>Imágenes compartidas · bajo demanda</span>
    <a href="/config/integrations/integration/nabla_control">Configurar cámaras</a></header>
    <p role="status"></p><div class="grid"></div>`;
    this._visibility=()=>{this.stop();if(this._active&&!document.hidden)this.load();};
    document.addEventListener('visibilitychange',this._visibility);
  }
  stop() {
    this._generation++; clearTimeout(this._timer); this._abort?.abort();
    this.shadowRoot.querySelectorAll('img').forEach(img=>{
      if(img.src.startsWith('blob:'))URL.revokeObjectURL(img.src);
      img.removeAttribute('src');
    });
  }
  async load() {
    if(!this._hass||!this.isConnected||document.hidden)return;
    const generation=this._generation;
    const status=this.shadowRoot.querySelector('[role=status]');
    try {
      const cameras=await this._hass.callWS({type:'nabla_control/cameras'});
      if(generation!==this._generation)return;
      status.textContent=cameras.length?'':'Añade Camera Cache desde Configurar cámaras → Añadir entrada → Cámaras.';
      const grid=this.shadowRoot.querySelector('.grid');grid.replaceChildren();
      const rows=cameras.map(camera=>{
        const card=document.createElement('article'),name=document.createElement('h3'),img=document.createElement('img'),info=document.createElement('small'),select=document.createElement('select');
        name.textContent=camera.name;img.alt=camera.name;
        for(const [value,label] of [['view','Imagen · hasta 480 px'],['icon','Icono · 64 × 64']]){const option=document.createElement('option');option.value=value;option.textContent=label;select.append(option);}
        info.textContent=camera.entity_id;card.append(name,img,select,info);grid.append(card);
        return {camera,img,info,select,next:0};
      });
      const tick=async()=>{
        if(generation!==this._generation||!this._active||document.hidden)return;
        this._abort=new AbortController();
        await Promise.all(rows.map(async row=>{
          if(Date.now()<row.next)return;
          try {
            const response=await fetch(`/api/nabla_control/camera/${encodeURIComponent(row.camera.entity_id)}?size=${row.select.value}`,{
              headers:{Authorization:`Bearer ${this._hass.auth.data.access_token}`},cache:'no-store',signal:this._abort.signal});
            if(!response.ok)throw new Error('Imagen no disponible');
            const blob=await response.blob();if(generation!==this._generation)return;
            const old=row.img.src;row.img.src=URL.createObjectURL(blob);if(old.startsWith('blob:'))URL.revokeObjectURL(old);
            row.info.textContent=`${row.camera.entity_id} · imagen ${response.headers.get('X-Nabla-Generation')||'—'} · ${response.headers.get('X-Nabla-Age')||'0'} s`;
          }catch(e){if(e.name!=='AbortError'&&generation===this._generation){row.info.textContent='Imagen no disponible; reintentando';if(row.img.src.startsWith('blob:'))URL.revokeObjectURL(row.img.src);row.img.removeAttribute('src');}}
          row.next=Date.now()+Math.max(1000,row.camera.interval*1000);
        }));
        if(generation===this._generation)this._timer=setTimeout(tick,250);
      };tick();
    }catch(e){if(generation===this._generation)status.textContent='No se pudo consultar la configuración de cámaras.';}
  }
  disconnectedCallback(){this.stop();document.removeEventListener('visibilitychange',this._visibility);}
}
customElements.define('nabla-cameras',NablaCameras);
