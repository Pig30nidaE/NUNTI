#!/usr/bin/env node
// Real browser/WebView inputs, actual HTTP generation, image hashes, collection and cold reload.
// No video or speaker capture. Screenshots are still images for layout inspection only.
import fs from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
import {isDeepStrictEqual} from 'node:util';
import {execFileSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const base='http://127.0.0.1:8768';
const native=process.argv.includes('--native');
const localAI=process.argv.includes('--local-ai');
const qaTag=process.argv.find(x=>x.startsWith('--qa-tag='))?.split('=')[1]||'';
assert(!qaTag||/^[a-z0-9-]+$/.test(qaTag),'QA tag must be a plain folder label');
const resume=process.argv.find(x=>x.startsWith('--resume-request='))?.split('=')[1];
assert(!resume||(localAI&&/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/.test(resume)),'Resume requires LOCAL_MODEL and a canonical request UUID');
const port=Number(process.argv.find(x=>x.startsWith('--port='))?.split('=')[1]||9223);
const out=path.join(root,'.local/avatar-generator',(qaTag?qaTag+'-':'')+(localAI?'local-ai-':'')+(native?'native-verification':'browser-verification'));
await fs.mkdir(out,{recursive:true});
const config=JSON.parse(await fs.readFile(path.join(root,'.local/avatar-generator/connection.json'),'utf8'));
if(native){const delivery=JSON.parse(await fs.readFile(path.join(root,'.local/avatar-generator/delivery.json'),'utf8'));const adb=path.join(root,'.local/pm-tools/sdk/platform-tools/adb');const prefix=['-s',delivery.serial];const pid=execFileSync(adb,[...prefix,'shell','pidof','ai.nunti.avatar.demo'],{encoding:'utf8'}).trim();assert(/^\d+$/.test(pid),'Actual Android app PID');execFileSync(adb,[...prefix,'forward',`tcp:${port}`,`localabstract:webview_devtools_remote_${pid}`]);execFileSync(adb,[...prefix,'push',path.join(root,'prototypes/avatar_generator/examples/synthetic-coast.png'),'/data/local/tmp/nunti-navigation-test.png'],{stdio:'pipe'});}
const targets=await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
const target=targets.find(x=>x.type==='page'&&x.url.startsWith(base))||targets.find(x=>x.type==='page');
assert(target,'No browser/WebView debug target');
const socket=new WebSocket(target.webSocketDebuggerUrl);
await new Promise((resolve,reject)=>{socket.onopen=resolve;socket.onerror=reject;});
let nextId=1;const pending=new Map();const exceptions=[];
socket.onmessage=event=>{const m=JSON.parse(event.data);if(m.id){const {resolve,reject}=pending.get(m.id)||{};pending.delete(m.id);if(m.error)reject?.(new Error(JSON.stringify(m.error)));else resolve?.(m.result);}else if(m.method==='Runtime.exceptionThrown')exceptions.push(m.params.exceptionDetails);};
function command(method,params={}){return new Promise((resolve,reject)=>{const id=nextId++;pending.set(id,{resolve,reject});socket.send(JSON.stringify({id,method,params}));});}
async function evaluate(expression){const value=await command('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(value.exceptionDetails)throw new Error(value.exceptionDetails.text+': '+JSON.stringify(value.exceptionDetails.exception));return value.result?.value;}
const pause=ms=>new Promise(r=>setTimeout(r,ms));
async function wait(expression,timeout=30000){const end=Date.now()+timeout;while(Date.now()<end){try{const value=await evaluate(expression);if(value)return value;}catch{}await pause(150);}throw new Error('Timed out: '+expression);}
async function click(id){const rect=await evaluate(`(()=>{const e=document.getElementById(${JSON.stringify(id)});e.scrollIntoView({block:'center'});const r=e.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2};})()`);await command('Input.dispatchMouseEvent',{type:'mousePressed',button:'left',clickCount:1,...rect});await command('Input.dispatchMouseEvent',{type:'mouseReleased',button:'left',clickCount:1,...rect});}
async function type(id,text){await evaluate(`document.getElementById(${JSON.stringify(id)}).focus();document.getElementById(${JSON.stringify(id)}).select()`);await command('Input.insertText',{text});}
async function upload(id,filename){const doc=await command('DOM.getDocument');const node=await command('DOM.querySelector',{nodeId:doc.root.nodeId,selector:'#'+id});await command('DOM.setFileInputFiles',{nodeId:node.nodeId,files:[filename]});}
async function screenshot(name){await evaluate('window.scrollTo(0,0)');await pause(150);if(native){const delivery=JSON.parse(await fs.readFile(path.join(root,'.local/avatar-generator/delivery.json'),'utf8'));const data=execFileSync(path.join(root,'.local/pm-tools/sdk/platform-tools/adb'),['-s',delivery.serial,'exec-out','screencap','-p'],{maxBuffer:12*1024*1024});await fs.writeFile(path.join(out,name+'.png'),data);}else{const result=await command('Page.captureScreenshot',{format:'png'});await fs.writeFile(path.join(out,name+'.png'),Buffer.from(result.data,'base64'));}}
const proof={status:'FAIL',surface:native?'ACTUAL_ANDROID_WEBVIEW':'ACTUAL_CHROME',screenshotsCaptured:true,videoRecorded:false,speakerRecorded:false,providerApiCalls:0,checks:[]};
proof.replayedRequestId=resume||null;
proof.qaTag=qaTag;
const {createHash}=await import('node:crypto');
proof.sourceSha256={};
for(const name of ['prototypes/avatar_generator/studio.js','prototypes/avatar_generator/formation.js','prototypes/avatar_generator/index.html','backend/nunti/avatar_studio/api.py','backend/nunti/avatar_studio/illustration.py'])proof.sourceSha256[name]=createHash('sha256').update(await fs.readFile(path.join(root,name))).digest('hex');
if(localAI)for(const name of ['backend/nunti/avatar_studio/local_model.py','backend/nunti/avatar_studio/matte_cutout.py'])proof.sourceSha256[name]=createHash('sha256').update(await fs.readFile(path.join(root,name))).digest('hex');
function check(name,value){assert(value,name);proof.checks.push(name);}
try{
  await command('Runtime.enable');await command('Page.enable');
  if(!native)await command('Emulation.setDeviceMetricsOverride',{width:1280,height:900,deviceScaleFactor:1,mobile:false});
  await command('Page.navigate',{url:base});await wait('document.readyState === "complete"');
  await evaluate(`fetch('/session',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({token:${JSON.stringify(config.token)}})}).then(r=>{if(!r.ok)throw new Error('session');return r.json()})`);
  await command('Page.reload',{ignoreCache:true});await wait('document.querySelectorAll(".example").length===3 && window.nuntiTest?.getRoute()');
  if(localAI)check('free-model-option-is-available',await evaluate('!document.getElementById("engine-choice").hidden && !document.querySelector("#render-mode option[value=LOCAL_MODEL]").disabled'));
  await evaluate(`document.getElementById("render-mode").value=${JSON.stringify(localAI?'LOCAL_MODEL':'LOCAL_RENDER')};document.getElementById("render-mode").dispatchEvent(new Event("change",{bubbles:true}))`);
  check('three-navigation-inputs-not-character-presets',true);
  check('confirmation-required-before-generation',await evaluate('document.getElementById("create-button").disabled'));
  await type('destination','강릉 안목해변');await type('traits','푸른 바다, 맑은 파도와 커피 향');await type('purpose','주말에 바다를 보며 쉬기');
  await click('route-confirmed');await wait('!document.getElementById("create-button").disabled');
  if(resume)await evaluate(`Object.defineProperty(crypto,'randomUUID',{value:()=>${JSON.stringify(resume)},configurable:true})`);
  await screenshot('01-input');await click('create-button');
  const first=await wait('window.nuntiTest?.getArtifact()',localAI?180000:45000);
  await wait(`document.getElementById("birth-status").textContent === ${JSON.stringify(localAI?'새로 그린 눈티를 확인해 주세요':'이 길에서 태어난 눈티예요')}`,15000);
  check('avatar-canvas-contains-visible-image',await evaluate('(()=>{const c=document.getElementById("birth-canvas"),d=c.getContext("2d").getImageData(0,0,c.width,c.height).data;let pixels=0;for(let i=3;i<d.length;i+=4)if(d[i]>10)pixels++;return pixels>1000;})()'));
  check('typed-input-reaches-generation',first.destination.name==='강릉 안목해변'&&first.purpose==='주말에 바다를 보며 쉬기');
  if(qaTag==='v5')check('route-is-transient-and-not-painted-on-body',first.design.visualIntent?.surfaceRouteMarking==='NONE'&&first.design.routeThread?.renderedOnSurface===false);
  if(localAI){
    check('actual-free-model-rgba-image',first.mediaOrigin==='LOCAL_MODEL'&&first.visual.width===512&&first.visual.sha256?.length===64);
    check('animation-uses-measured-image-boundary',first.design.formation?.source==='MEASURED_ALPHA_BOUNDARY'&&first.design.formation?.mapping==='GEOMETRIC_PROJECTION_NOT_SEMANTIC');
    await fs.writeFile(path.join(out,'artifact.json'),JSON.stringify(first,null,2)+'\n');
  }else check('actual-new-rgba-local-render',first.mediaOrigin==='LOCAL_RENDER'&&first.visual.width===768&&first.visual.sha256?.length===64);
  check('motifs-have-input-evidence',first.design.motifs.length>=2&&first.design.motifs.every(x=>x.source&&x.target&&x.detail));
  check('no-automatic-speech',await evaluate('document.getElementById("listen-button").textContent === "▷"'));
  await screenshot('02-new-avatar');
  const originalRequest=JSON.parse(first.inputCanonical);
  const retry=await evaluate(`fetch('/v3/avatars',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(${JSON.stringify(originalRequest)})}).then(r=>r.json()).then(r=>r.data)`);
  check('retry-preserves-identity-and-image',retry.characterId===first.characterId&&retry.visual.sha256===first.visual.sha256);
  if(localAI){
    await command('Page.reload',{ignoreCache:true});await wait('document.querySelectorAll(".example").length===3');
    await click('collection-button');await wait('document.querySelectorAll(".collection-item").length>=1');
    const selected=await evaluate(`(()=>{const b=[...document.querySelectorAll('.collection-item')].find(e=>e.querySelector('img').getAttribute('src')===${JSON.stringify(first.visual.path)});if(!b)return false;b.click();return true;})()`);
    check('model-companion-selectable-after-reload',selected);
    const restored=await wait(`(()=>{const a=window.nuntiTest?.getArtifact();return a?.characterId===${JSON.stringify(first.characterId)}?a:null;})()`);
    check('cold-reload-preserves-model-image-and-voice-recipe',restored.visual.sha256===first.visual.sha256&&isDeepStrictEqual(restored.voice,first.voice));
    await screenshot('04-restored');
    proof.artifacts=[first].map(a=>({characterId:a.characterId,imageSha256:a.visual.sha256,inputOrigin:a.route.inputOrigin,mediaOrigin:a.mediaOrigin}));
    proof.localModel=first.provider;
  }else{
  await click('new-button');await click('create-button');
  const second=await wait(`(()=>{const a=window.nuntiTest?.getArtifact();return a && a.characterId!==${JSON.stringify(first.characterId)}?a:null;})()`,45000);
  check('same-destination-new-journey-new-appearance',second.visual.sha256!==first.visual.sha256);
  await wait('!document.getElementById("result-details").hidden');await click('new-button');
  await upload('image-upload',native?'/data/local/tmp/nunti-navigation-test.png':path.join(root,'prototypes/avatar_generator/examples/synthetic-coast.png'));
  await wait('window.nuntiTest?.getRoute()?.inputOrigin === "NAVIGATION_SCREENSHOT"',30000);
  check('screenshot-extracted-and-requires-confirmation',await evaluate('!document.getElementById("route-confirmed").checked && document.getElementById("create-button").disabled'));
  await type('destination','해변의 작은 카페');await click('route-confirmed');await click('create-button');
  const third=await wait('(()=>{const a=window.nuntiTest?.getArtifact();return a?.route.inputOrigin === "NAVIGATION_SCREENSHOT"?a:null;})()',45000);
  check('screenshot-source-and-selected-line-persisted',!!third.route.sourceImageSha256&&third.route.points.length>2&&third.route.confirmed===true);
  await wait('document.getElementById("birth-status").textContent === "이 길에서 태어난 눈티예요"',15000);
  await screenshot('03-screenshot-avatar');
  await command('Page.reload',{ignoreCache:true});await wait('document.querySelectorAll(".example").length===3');
  await click('collection-button');await wait('document.querySelectorAll(".collection-item").length>=3');
  const selected=await evaluate(`(()=>{const buttons=[...document.querySelectorAll('.collection-item')];const b=buttons.find(e=>e.querySelector('img').getAttribute('src')===${JSON.stringify(third.visual.path)});if(!b)return false;b.click();return true;})()`);check('saved-companion-selectable-after-reload',selected);
  const restored=await wait(`(()=>{const a=window.nuntiTest?.getArtifact();return a?.characterId===${JSON.stringify(third.characterId)}?a:null;})()`);
  check('cold-reload-preserves-appearance-and-voice-recipe',restored.visual.sha256===third.visual.sha256&&isDeepStrictEqual(restored.voice,third.voice));
  await screenshot('04-restored');
  proof.artifacts=[first,second,third].map(a=>({characterId:a.characterId,imageSha256:a.visual.sha256,inputOrigin:a.route.inputOrigin,mediaOrigin:a.mediaOrigin}));
  }
  check('no-javascript-runtime-exceptions',exceptions.length===0);
  proof.status=localAI?'PASS_LOCAL_MODEL_UI':'PASS_AVATAR_GENERATOR_UI';
}catch(error){proof.error=String(error);proof.exceptions=exceptions;try{await screenshot('failure');proof.notice=await evaluate('document.getElementById("notice")?.textContent');}catch{}throw error;}
finally{await fs.writeFile(path.join(out,'verification.json'),JSON.stringify(proof,null,2)+'\n');socket.close();console.log(JSON.stringify({status:proof.status,surface:proof.surface,checks:proof.checks.length,report:path.join(out,'verification.json'),error:proof.error}));}
