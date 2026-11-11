#!/usr/bin/env node
// Exercise the real parked WebView button. No recording or new image generation.
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import {execFileSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const characterId=process.argv.find(x=>x.startsWith('--character='))?.slice(12);
const source=process.argv.includes('--live')?'LIVE':'DEMO';
assert(/^nunti-[0-9a-f-]{36}$/.test(characterId||''),'--character=<stored character id> required');
const adb=path.join(root,'.local/pm-tools/sdk/platform-tools/adb');
const prefix=['-s','emulator-5554'];
const pid=execFileSync(adb,[...prefix,'shell','pidof','ai.nunti.avatar.demo'],{encoding:'utf8'}).trim();
assert(/^\d+$/.test(pid));
execFileSync(adb,[...prefix,'forward','tcp:9224',`localabstract:webview_devtools_remote_${pid}`]);
const targets=await (await fetch('http://127.0.0.1:9224/json/list')).json();
const target=targets.find(t=>t.type==='page'&&t.url.startsWith('http://127.0.0.1:8768'));
assert(target,'Open the parked Nunti generator first');
const socket=new WebSocket(target.webSocketDebuggerUrl);
await new Promise((resolve,reject)=>{socket.onopen=resolve;socket.onerror=reject;});
let sequence=0;const pending=new Map();
socket.onmessage=event=>{const result=JSON.parse(event.data);if(result.id){const item=pending.get(result.id);pending.delete(result.id);result.error?item.reject(new Error(JSON.stringify(result.error))):item.resolve(result.result);}};
function command(method,params={}){return new Promise((resolve,reject)=>{const id=++sequence;pending.set(id,{resolve,reject});socket.send(JSON.stringify({id,method,params}));});}
async function evaluate(expression){const r=await command('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});assert(!r.exceptionDetails,JSON.stringify(r.exceptionDetails));return r.result?.value;}
const pause=ms=>new Promise(resolve=>setTimeout(resolve,ms));
try{
  await command('Runtime.enable');
  await command('Page.reload',{ignoreCache:true});
  const deadline=Date.now()+20000;
  while(!(await evaluate('!!window.nuntiTest && !!window.NuntiNative?.startJourney && JSON.parse(window.NuntiNative.getNavigationSnapshot()).status !== "GATE_BLOCKED"'))){assert(Date.now()<deadline,'Parked WebView ready timeout');await pause(200);}
  await evaluate(`fetch('/v3/avatars/${characterId}').then(r=>r.json()).then(r=>window.nuntiTest.showArtifact(r.data,false))`);
  await evaluate(`document.getElementById('journey-source').value=${JSON.stringify(source)}`);
  const bounds=await evaluate(`(()=>{const e=document.getElementById('journey-button');e.scrollIntoView({block:'center'});const r=e.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2};})()`);
  await pause(250);
  await command('Input.dispatchMouseEvent',{type:'mousePressed',button:'left',clickCount:1,...bounds});
  await command('Input.dispatchMouseEvent',{type:'mouseReleased',button:'left',clickCount:1,...bounds});
  console.log(JSON.stringify({status:'BUTTON_CLICKED',characterId,source,mediaCaptured:false}));
}finally{socket.close();}
