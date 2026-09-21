// Run with Playwright installed: node tests/panel-browser.cjs
const {chromium}=require('playwright');
const http=require('node:http'),fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
(async()=>{
 const root=path.resolve(__dirname,'../custom_components/nabla_control/frontend');
 const fixture=`<!doctype html><meta charset="utf-8"><style>body{margin:0;font:16px Arial;--primary-color:#1976d2;--divider-color:#ddd;--card-background-color:#fff;--primary-text-color:#222;--secondary-text-color:#666}</style><nabla-panel></nabla-panel><script type="module">
 import '/nabla-panel.js';
 const devices=[{device_id:'panel',name:'Panel salón',host:'192.0.2.10',available:true,width:480,height:320,format:'rgb565',kind:'mirror',has_input:true,has_touch:true},{device_id:'webcam',name:'Dashcam',host:'192.0.2.11',available:true,kind:'web',has_camera:true,camera_url:'/mjpeg'},{device_id:'offline',name:'Reloj',host:'192.0.2.12',available:false,width:240,height:240,kind:'mirror'}];
 window.calls={};document.querySelector('nabla-panel').hass={auth:{data:{access_token:'fixture-only'}},callWS:async msg=>{window.calls[msg.type]=(window.calls[msg.type]||0)+1;if(msg.type==='nabla_control/touch'){window.lastTouch=msg;return {queued:true};}if(msg.type==='nabla_control/devices')return devices;if(msg.type==='lovelace/dashboards/list')return [];if(msg.type==='nabla_control/discovery')return msg.operation==='adopt'?{status:'linked'}:{known:3,partial:false,devices:[{source_entry_id:'sample',name:'Panel salón',host:'192.0.2.10',configured:true,linked:false}]};if(msg.type==='nabla_control/cameras')return [{entity_id:'camera.example',name:'Entrada',interval:1}];if(msg.type==='nabla_control/mqtt_log')return {enabled:false,active:false,topics:[],limit:200,rows:[],dropped:0};}};
 </script>`;
 let images=0;
 const png=Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIHWP4z8DwHwAFgAI/ScLbtAAAAABJRU5ErkJggg==','base64');
 const server=http.createServer((req,res)=>{
  const url=new URL(req.url,'http://localhost');
  if(url.pathname==='/'){res.setHeader('Content-Type','text/html');res.end(fixture);return;}
  if(url.pathname.startsWith('/api/')||url.pathname==='/mjpeg'){
   images++;res.setHeader('Content-Type','image/png');res.setHeader('X-Nabla-Generation','1');res.setHeader('X-Nabla-Age','0.1');res.end(png);return;
  }
  const file=path.join(root,path.basename(url.pathname));
  if(!fs.existsSync(file)){res.writeHead(404);res.end();return;}
  res.setHeader('Content-Type','text/javascript');res.end(fs.readFileSync(file));
 });
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 let browser;
 try{
  browser=await chromium.launch({headless:true});const page=await browser.newPage({viewport:{width:1200,height:900}});
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(`http://127.0.0.1:${server.address().port}/`);
  await page.getByRole('table',{name:'Detalles de dispositivos'}).waitFor();
  assert.equal(await page.locator('tbody tr').count(),3);
  await page.getByRole('button',{name:'Buscar nuevos',exact:true}).click();
  await page.getByRole('button',{name:'Vincular IP',exact:true}).click();
  await page.getByRole('button',{name:'Vinculado',exact:true}).waitFor();
  await page.getByRole('searchbox',{name:'Buscar dispositivos'}).fill('salon');
  assert.equal(await page.locator('tbody tr').count(),1);
  await page.getByRole('searchbox',{name:'Buscar dispositivos'}).fill('192.0.2.12');
  assert.equal(await page.locator('tbody tr').count(),1);
  await page.locator('#device-status').selectOption('online');
  await page.getByText('No hay coincidencias',{exact:true}).waitFor();
  await page.getByRole('searchbox',{name:'Buscar dispositivos'}).fill('');
  assert.equal(await page.locator('tbody tr').count(),2);
  await page.locator('#device-status').selectOption('all');
  await page.getByRole('button',{name:'Pantallas',exact:true}).click();
  await page.locator('.device-card').first().waitFor();
  await page.screenshot({path:'/tmp/nabla-tabs-screens.png'});
  await page.getByRole('button',{name:'Detalles',exact:true}).click();
  assert.equal(await page.locator('#device-grid').evaluate(e=>e.classList.contains('details')),true);
  assert.equal(await page.locator('.device-preview').count(),0);
  assert.equal(await page.locator('tbody tr').count(),3);
  let before=images;await page.waitForTimeout(2200);assert.equal(images,before,'details must stop preview requests');
  await page.screenshot({path:'/tmp/nabla-tabs-details.png'});
  await page.locator('tbody tr').filter({hasText:'Panel salón'}).getByRole('button',{name:'Ver',exact:true}).click();
  await page.locator('#live-modal.active').waitFor();
  await page.locator('#live-frame[src^="blob:"]').waitFor();
  await page.locator('#live-frame').evaluate(async img=>{await img.decode();img.style.width='400px';img.style.height='400px';});
  const bounds=await page.locator('#live-frame').boundingBox();
  await page.locator('#live-frame').evaluate(img=>{const b=img.getBoundingClientRect();img.dispatchEvent(new MouseEvent('click',{bubbles:true,clientX:b.left+b.width/2,clientY:b.top+b.height/2}));});
  await page.waitForFunction(()=>window.lastTouch);
  assert.equal(await page.evaluate(()=>window.lastTouch.x),240);
  assert.ok(Math.abs(await page.evaluate(()=>window.lastTouch.y)-160)<=1,'center coordinate rounded to a logical pixel');
  const taps=await page.evaluate(()=>window.calls['nabla_control/touch']);
  await page.locator('#live-frame').evaluate(img=>{const b=img.getBoundingClientRect();img.dispatchEvent(new MouseEvent('click',{bubbles:true,clientX:b.left+b.width/2,clientY:b.top+10}));});
  assert.equal(await page.evaluate(()=>window.calls['nabla_control/touch']),taps,'letterbox must not send a tap');
  await page.locator('#live-modal-close').click();
  await page.getByRole('tab',{name:'Cámaras',exact:true}).click();
  await page.locator('nabla-cameras img[src^="blob:"]').waitFor();
  await page.screenshot({path:'/tmp/nabla-tabs-cameras.png'});
  await page.getByRole('tab',{name:'MQTT',exact:true}).click();
  await page.getByText('Registro desactivado',{exact:false}).waitFor();
  before=images;await page.waitForTimeout(2200);assert.equal(images,before,'hidden cameras must stop fetching');
  await page.screenshot({path:'/tmp/nabla-tabs-mqtt.png'});
  await page.getByRole('tab',{name:'Dispositivos',exact:true}).click();
  const polls=await page.evaluate(()=>window.calls['nabla_control/mqtt_log']);
  await page.waitForTimeout(2200);assert.equal(await page.evaluate(()=>window.calls['nabla_control/mqtt_log']),polls,'hidden MQTT panel must stop polling');
  await page.getByRole('button',{name:'Pantallas',exact:true}).click();
  await page.locator('#preview-panel[src^="blob:"]').waitFor();
  await page.setViewportSize({width:390,height:844});
  await page.screenshot({path:'/tmp/nabla-tabs-mobile.png'});
  await page.getByRole('button',{name:'Detalles',exact:true}).click();
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth),true,'mobile table must scroll within its container');
  await page.evaluate(()=>{document.body.style.cssText='--primary-color:#009cbe;--divider-color:#383838;--card-background-color:#1c1c1c;--primary-background-color:#111;--secondary-background-color:#222;--primary-text-color:#eee;--secondary-text-color:#aaa;color:#eee';});
  await page.screenshot({path:'/tmp/nabla-table-mobile-dark.png'});
  assert.deepEqual(errors,[]);console.log('PASS: screen/detail views, camera/MQTT tabs, hidden request suspension, resume, mobile render');
 }finally{if(browser)await browser.close();server.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
