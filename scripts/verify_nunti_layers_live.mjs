// Actual parked WebView verification against an isolated local Studio store.
// Never selects or invokes an image API, model inference, routing API or voice.
import fs from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
import {execFileSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const out=path.join(root,'docs/redesign/route-variants-v1/runtime');
await fs.mkdir(out,{recursive:true});
const adb=path.join(root,'.local/pm-tools/sdk/platform-tools/adb');
const serial='emulator-5554',base='http://127.0.0.1:8768';
const connection=JSON.parse(await fs.readFile('/private/tmp/nunti-layers-test-connection.json','utf8'));
const targets=await (await fetch('http://127.0.0.1:9237/json/list')).json();
const target=targets.find(t=>t.type==='page'&&t.url.startsWith(base));
assert(target,'Actual Studio WebView must be open');
const socket=new WebSocket(target.webSocketDebuggerUrl);
await new Promise((resolve,reject)=>{socket.onopen=resolve;socket.onerror=reject;});
let nextId=1;
const pending=new Map();
socket.onmessage=e=>{const value=JSON.parse(e.data);if(value.id){const p=pending.get(value.id);pending.delete(value.id);if(value.error)p?.reject(new Error(JSON.stringify(value.error)));else p?.resolve(value.result);}};
const command=(method,params={})=>new Promise((resolve,reject)=>{const id=nextId++;pending.set(id,{resolve,reject});socket.send(JSON.stringify({id,method,params}));});
async function evaluate(expression){const r=await command('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(r.exceptionDetails)throw new Error('WebView evaluation failed: '+r.exceptionDetails.text);return r.result?.value;}
const pause=ms=>new Promise(resolve=>setTimeout(resolve,ms));
async function wait(expression,ms=15000){const deadline=Date.now()+ms;while(Date.now()<deadline){try{const r=await evaluate(expression);if(r)return r;}catch{}await pause(150);}throw new Error('Timed out waiting for parked UI state');}
async function screenshot(name){
  await evaluate('window.scrollTo(0,0)');
  await evaluate('document.fonts.ready.then(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))))');
  // DOM state can precede Android WebView compositor output. Allow the native
  // surface to present the selected state before taking the device screenshot.
  await pause(1200);
  const png=execFileSync(adb,['-s',serial,'exec-out','screencap','-p'],{maxBuffer:12*1024*1024});
  await fs.writeFile(path.join(out,name+'.png'),png);
}
const report={status:'RUNNING',surface:'ACTUAL_PLEOS_ANDROID_WEBVIEW',serial,isolatedStore:true,providerApiCalls:0,voiceSynthesisCalls:0,checks:[],artifacts:[]};
function check(name,condition){assert(condition,name);report.checks.push(name);}
let priorCookies;
try{
  await command('Network.enable');await command('Page.enable');await command('Runtime.enable');
  priorCookies=(await command('Network.getCookies',{urls:[base]})).cookies;
  await evaluate(`fetch('/session',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({token:${JSON.stringify(connection.token)}})}).then(r=>{if(!r.ok)throw new Error('session rejected');return true})`);
  await command('Page.reload',{ignoreCache:true});
  await wait('window.nuntiCapabilities?.layeredRenderAvailable && document.querySelectorAll(".example").length===3');
  await evaluate(`(()=>{window.nuntiTest.viewExample(1);const set=(id,value)=>{const e=document.getElementById(id);e.value=value;e.dispatchEvent(new Event('change',{bubbles:true}));e.dispatchEvent(new Event('input',{bubbles:true}));};set('render-mode','LOCAL_LAYERS');set('destination','검증용 바다 여행');set('traits','합성 경로로 확인하는 바다');set('purpose','눈티와 편안한 여행');set('layer-destination','coast');set('layer-road','highway');set('layer-mood','curious');const c=document.getElementById('route-confirmed');c.checked=true;c.dispatchEvent(new Event('change'));})()`);
  await wait('!document.getElementById("create-button").disabled');
  check('parked-native-gate-allows-user-generation',true);
  check('layered-input-controls-hold-selected-values',await evaluate('document.getElementById("render-mode").value==="LOCAL_LAYERS" && !document.getElementById("layer-options").hidden && document.getElementById("layer-destination").value==="coast" && document.getElementById("layer-road").value==="highway" && document.getElementById("layer-mood").value==="curious"'));
  await screenshot('01-layered-input');
  await evaluate('document.getElementById("journey-form").requestSubmit()');
  const first=await wait('window.nuntiTest.getArtifact()?.mediaOrigin==="LOCAL_LAYERS" && !document.getElementById("result-details").hidden && window.nuntiTest.getArtifact()');
  await wait('document.getElementById("birth-status").textContent==="선택한 모습으로 만나는 눈티예요"');
  check('selected-motifs-and-mood-reach-real-renderer',first.design.avatarSpec.destinationMotif==='coast'&&first.design.avatarSpec.roadMotif==='highway'&&first.design.avatarSpec.expression==='curious');
  check('layered-result-is-static',first.design.staticOnly===true && await evaluate('document.getElementById("replay-button").hidden && document.getElementById("birth-progress").hidden && window.nuntiTest.getFormation()===null'));
  const canvasBefore=await evaluate('document.getElementById("birth-canvas").toDataURL()');await pause(900);
  check('canvas-stays-identical-without-idle-motion',canvasBefore===await evaluate('document.getElementById("birth-canvas").toDataURL()'));
  await screenshot('02-layered-result');
  const originalRequest=JSON.parse(first.inputCanonical);
  const second=await evaluate(`fetch('/v3/avatars',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...${JSON.stringify(originalRequest)},requestId:crypto.randomUUID()})}).then(r=>r.json()).then(r=>r.data)`);
  check('new-request-id-keeps-the-same-image',second.visual.sha256===first.visual.sha256);
  await evaluate('window.nuntiTest.showCollection()');await wait('document.querySelectorAll(".collection-item").length>=2');
  await screenshot('03-layered-collection');
  await evaluate(`[...document.querySelectorAll('.collection-item')].find(e=>e.querySelector('img')?.getAttribute('src')===${JSON.stringify(first.visual.path)}).click()`);
  await wait('!document.getElementById("result-view").hidden && !document.getElementById("result-details").hidden');
  check('saved-collection-reopens-same-image',await evaluate(`window.nuntiTest.getArtifact().visual.sha256===${JSON.stringify(first.visual.sha256)}`));
  const missing=await evaluate(`fetch('/v3/avatars',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({requestId:crypto.randomUUID(),renderMode:'LOCAL_LAYERS',destination:{name:'경로 미수신'},route:null,variantContext:{}})}).then(r=>r.json()).then(r=>r.data)`);
  await evaluate(`window.nuntiTest.showArtifact(${JSON.stringify(missing)},true)`);
  await wait('document.getElementById("birth-status").textContent==="경로가 없어 기본 눈티로 만나요"');
  check('missing-route-shows-complete-base',missing.route===null&&missing.design.avatarSpec.expression==='base'&&missing.design.avatarSpec.destinationMotif==='none');
  check('missing-route-receipt-does-not-crash',await evaluate('document.getElementById("receipt-source").textContent.includes("경로")'));
  await screenshot('04-no-route-base');
  for(const a of [first,missing]){report.artifacts.push({characterId:a.characterId,imageSha256:a.visual.sha256,variantId:a.design.avatarSpec.variantId,mediaOrigin:a.mediaOrigin});}
  report.status='PASS';
}catch(error){report.status='FAIL';report.error=String(error);await screenshot('failure').catch(()=>{});throw error;}
finally{
  if(priorCookies){
    await command('Network.deleteCookies',{name:'nunti_studio_session',url:base}).catch(()=>{});
    if(priorCookies.length)await command('Network.setCookies',{cookies:priorCookies}).catch(()=>{});
  }
  execFileSync(adb,['-s',serial,'reverse','tcp:8768','tcp:8768']);
  report.originalAdbReverseRestored=true;
  await fs.writeFile(path.join(out,'report.json'),JSON.stringify(report,null,2)+'\n');
  socket.close();
}
console.log(JSON.stringify({status:report.status,checks:report.checks.length,screenshots:4,originalAdbReverseRestored:report.originalAdbReverseRestored}));
