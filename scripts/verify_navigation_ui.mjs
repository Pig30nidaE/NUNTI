#!/usr/bin/env node
// Actual Android WebView, real native SDK and routing HTTP. No photo input or recording.
import fs from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
import {execFileSync} from 'node:child_process';
import {createHash} from 'node:crypto';
import {isDeepStrictEqual} from 'node:util';
import {fileURLToPath} from 'node:url';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const localAI=process.argv.includes('--local-ai');
const out=path.join(root,'.local/navigation-integration',localAI?'ui-local-ai':'ui');await fs.mkdir(out,{recursive:true});
const adb=path.join(root,'.local/pm-tools/sdk/platform-tools/adb');
const pid=execFileSync(adb,['-s','emulator-5554','shell','pidof','ai.nunti.avatar.demo'],{encoding:'utf8'}).trim();assert(/^\d+$/.test(pid));
execFileSync(adb,['-s','emulator-5554','forward','tcp:9224',`localabstract:webview_devtools_remote_${pid}`]);
const target=(await(await fetch('http://127.0.0.1:9224/json/list')).json()).find(v=>v.type==='page'&&v.url.startsWith('http://127.0.0.1:8768'));assert(target);
const socket=new WebSocket(target.webSocketDebuggerUrl);await new Promise((resolve,reject)=>{socket.onopen=resolve;socket.onerror=reject;});
let id=0;const pending=new Map(),exceptions=[];
socket.onmessage=e=>{const m=JSON.parse(e.data);if(m.id){const p=pending.get(m.id);pending.delete(m.id);m.error?p?.reject(new Error(JSON.stringify(m.error))):p?.resolve(m.result);}else if(m.method==='Runtime.exceptionThrown')exceptions.push(m.params.exceptionDetails);};
const call=(method,params={})=>new Promise((resolve,reject)=>{const n=++id;pending.set(n,{resolve,reject});socket.send(JSON.stringify({id:n,method,params}));});
async function evaluate(expression){const r=await call('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(r.exceptionDetails)throw new Error(JSON.stringify(r.exceptionDetails));return r.result?.value;}
const pause=ms=>new Promise(resolve=>setTimeout(resolve,ms));
async function wait(expression,timeout=30000){const end=Date.now()+timeout;while(Date.now()<end){const v=await evaluate(expression);if(v)return v;await pause(150);}throw new Error('Timed out: '+expression+'; '+await evaluate('document.getElementById("notice").textContent'));}
async function click(elementId){const r=await evaluate(`(()=>{const e=document.getElementById(${JSON.stringify(elementId)});if(e.disabled)throw new Error('disabled: '+e.id);e.scrollIntoView({block:'center'});const r=e.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2};})()`);await call('Input.dispatchMouseEvent',{type:'mousePressed',button:'left',clickCount:1,...r});await call('Input.dispatchMouseEvent',{type:'mouseReleased',button:'left',clickCount:1,...r});}
const proof={status:'FAIL',surface:'ACTUAL_ANDROID_WEBVIEW',checks:[],cases:[],paidApiCalls:0,photoExtractionCalls:0,videoRecorded:false,speakerRecorded:false};
const check=(name,value)=>{assert(value,name);proof.checks.push(name);};
const identity=a=>({id:a.characterId,image:a.visual.sha256,voice:a.voice});
async function generate(name){
  const mode=localAI&&name==='native'?'LOCAL_MODEL':'LOCAL_RENDER';
  await evaluate(`document.getElementById('render-mode').value=${JSON.stringify(mode)};document.getElementById('render-mode').dispatchEvent(new Event('change',{bubbles:true}))`);
  check(name+'-requires-explicit-confirmation',await evaluate('!document.getElementById("route-confirmed").checked&&document.getElementById("create-button").disabled'));
  await click('route-confirmed');await wait('!document.getElementById("create-button").disabled');await click('create-button');
  const artifact=await wait('window.nuntiTest?.getArtifact()',mode==='LOCAL_MODEL'?180000:50000);await wait('!document.getElementById("result-details").hidden');
  check(name+'-real-api-route-generates-avatar',artifact.route.inputOrigin==='API_ROUTE'&&artifact.route.apiRoute?.planId===artifact.route.apiPlanId&&artifact.visual.sha256.length===64&&artifact.mediaOrigin===mode);
  check(name+'-external-route-source-honest',artifact.route.apiRoute.geometryMatchesHyundaiRoute===false&&artifact.route.apiRoute.geometry.provider==='OSRM_FOSSGIS');
  check(name+'-no-automatic-speech',await evaluate('document.getElementById("listen-button").textContent==="▷"'));
  await fs.writeFile(path.join(out,name+'-artifact.json'),JSON.stringify(artifact,null,2)+'\n');return artifact;
}
try{
  await call('Runtime.enable');await call('Page.enable');await call('Page.reload',{ignoreCache:true});
  await wait('window.NuntiNavigation&&window.nuntiCapabilities?.routeApiAvailable&&document.querySelectorAll(".example").length===3');
  const initial=await wait('window.NuntiNavigation.readNative()?.connected&&window.NuntiNavigation.getNative()');
  check('actual-navihelper-connected',initial.source==='PLEOS_NAVI_HELPER_API'&&initial.receivedCallbackCount>0);
  check('empty-preview-requires-route',await evaluate('window.nuntiTest.getRoute()===null&&document.getElementById("create-button").disabled'));
  await click('nav-import');await wait('document.getElementById("notice").textContent.includes("현재 위치와 목적지를 가져왔어요")',12000);
  check('native-destination-imported-from-callback',await evaluate('document.getElementById("destination").value===window.NuntiNavigation.getNative().destination.name'));
  await click('nav-calculate');const plan=await wait('window.NuntiNavigation.getPlan()',45000);
  check('full-road-geometry-not-summary',plan.geometry.coordinates.length>20&&plan.route.points.length>2&&plan.nativeSnapshot?.source==='PLEOS_NAVI_HELPER_API');
  const first=await generate('native');proof.cases.push({name:'native',planId:plan.planId,rawPoints:plan.geometry.coordinates.length,normalizedPoints:plan.route.points.length,identity:identity(first)});
  await click('new-button');await click('nav-replay');await wait('document.getElementById("api-route-summary").textContent.includes("저장 경로")');
  const replay=await evaluate('window.NuntiNavigation.getPlan()');check('saved-route-replay-no-provider-call',replay.retrieval.externalRequestMade===false&&isDeepStrictEqual(plan.geometry,replay.geometry)&&isDeepStrictEqual(plan.route.points,replay.route.points));
  check('route-replay-preserves-existing-companion',isDeepStrictEqual(identity(first),identity(await evaluate('window.nuntiTest.getArtifact()'))));
  for(const name of ['seoul','coast']){
    await evaluate(`document.getElementById('nav-case').value=${JSON.stringify(name)};document.getElementById('nav-case').dispatchEvent(new Event('change',{bubbles:true}))`);
    const oldId=await evaluate('window.NuntiNavigation.getPlan().planId');await pause(1200);await click('nav-calculate');
    const current=await wait(`window.NuntiNavigation.getPlan()?.planId!==${JSON.stringify(oldId)}&&window.NuntiNavigation.getPlan()`,45000);
    const avatar=await generate(name);proof.cases.push({name,planId:current.planId,rawPoints:current.geometry.coordinates.length,normalizedPoints:current.route.points.length,identity:identity(avatar)});
    await click('new-button');
  }
  check('three-geometries-and-new-identities',new Set(proof.cases.map(c=>c.planId)).size===3&&new Set(proof.cases.map(c=>c.identity.id)).size===3&&new Set(proof.cases.map(c=>c.identity.image)).size===3);
  const last=localAI?first:await evaluate('window.nuntiTest.getArtifact()');
  await call('Page.reload',{ignoreCache:true});await wait('window.NuntiNavigation&&document.querySelectorAll(".example").length===3');
  check('saved-route-replay-available-after-cold-reload',await evaluate('!document.getElementById("nav-replay").disabled'));
  await click('collection-button');await wait('document.querySelectorAll(".collection-item").length>=3');
  check('companion-selectable-after-cold-reload',await evaluate(`(()=>{const b=[...document.querySelectorAll('.collection-item')].find(b=>b.querySelector('img').getAttribute('src')===${JSON.stringify(last.visual.path)});if(!b)return false;b.click();return true;})()`));
  const restored=await wait(`window.nuntiTest.getArtifact()?.characterId===${JSON.stringify(last.characterId)}&&window.nuntiTest.getArtifact()`);
  check('cold-reload-preserves-image-and-voice',isDeepStrictEqual(identity(last),identity(restored)));
  await wait('!document.getElementById("result-details").hidden');await pause(6000);await evaluate('window.scrollTo(0,0)');
  await fs.writeFile(path.join(out,'actual-android-result.png'),execFileSync(adb,['-s','emulator-5554','exec-out','screencap','-p'],{maxBuffer:12*1024*1024}));
  check('no-javascript-exceptions',exceptions.length===0);proof.status='PASS';
}catch(e){proof.error=e.stack;throw e;}finally{
  proof.exceptions=exceptions;proof.sourceSha256={};for(const name of ['prototypes/avatar_generator/navigation.js','prototypes/avatar_generator/studio.js','android/app/src/main/kotlin/ai/nunti/app/navigation/PleosNavigationAdapter.kt'])proof.sourceSha256[name]=createHash('sha256').update(await fs.readFile(path.join(root,name))).digest('hex');
  await fs.writeFile(path.join(out,'verification.json'),JSON.stringify(proof,null,2)+'\n');socket.close();console.log(JSON.stringify({status:proof.status,checks:proof.checks.length,cases:proof.cases.map(c=>({name:c.name,planId:c.planId,rawPoints:c.rawPoints,normalizedPoints:c.normalizedPoints})),error:proof.error,report:path.join(out,'verification.json')}));
}
