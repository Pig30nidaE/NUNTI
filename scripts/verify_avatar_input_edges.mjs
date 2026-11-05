#!/usr/bin/env node
// Real-Chrome boundary regressions. Only timing and one GET failure are injected.
// No recording, audio playback, provider call, or changes to the 9223/9224 sessions.
import fs from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
import {spawn} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const base='http://127.0.0.1:8768';
const port=9225;
const out=path.join(root,'.local/avatar-generator/input-edge-verification');
const profile=path.join(root,'.local/avatar-generator/chrome-edge-qa');
await fs.mkdir(out,{recursive:true});
const config=JSON.parse(await fs.readFile(path.join(root,'.local/avatar-generator/connection.json'),'utf8'));
const pause=ms=>new Promise(resolve=>setTimeout(resolve,ms));
let chrome,socket,nextId=1;
const pending=new Map(),pausedImages=[];
const proof={status:'FAIL',surface:'ACTUAL_HEADLESS_CHROME_9225',recordings:false,audioPlayed:false,
  providerApiCalls:0,injection:'actual HTTP responses held; one actual collection GET replaced with 503',checks:[]};
proof.sourceSha256={};
for(const name of ['prototypes/avatar_generator/studio.js','prototypes/avatar_generator/formation.js'])proof.sourceSha256[name]=createHash('sha256').update(await fs.readFile(path.join(root,name))).digest('hex');
function check(name,condition,detail){assert(condition,name);proof.checks.push({name,...(detail?{detail}:{})});}
async function endpoint(){return (await fetch(`http://127.0.0.1:${port}/json/list`)).json();}
function command(method,params={}){return new Promise((resolve,reject)=>{const id=nextId++;pending.set(id,{resolve,reject});socket.send(JSON.stringify({id,method,params}));});}
async function evaluate(expression){const r=await command('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(r.exceptionDetails)throw new Error('Browser evaluation failed');return r.result?.value;}
async function wait(expression,timeout=30000){const end=Date.now()+timeout;while(Date.now()<end){try{const r=await evaluate(expression);if(r)return r;}catch{}await pause(80);}throw new Error('Browser condition timed out');}
async function click(selector){const rect=await evaluate(`(()=>{const e=document.querySelector(${JSON.stringify(selector)});e.scrollIntoView({block:'center'});const r=e.getBoundingClientRect();return{x:r.x+r.width/2,y:r.y+r.height/2};})()`);await command('Input.dispatchMouseEvent',{type:'mousePressed',button:'left',clickCount:1,...rect});await command('Input.dispatchMouseEvent',{type:'mouseReleased',button:'left',clickCount:1,...rect});}
async function upload(id,file){const doc=await command('DOM.getDocument');const r=await command('DOM.querySelector',{nodeId:doc.root.nodeId,selector:'#'+id});await command('DOM.setFileInputFiles',{nodeId:r.nodeId,files:[file]});}

try{
  let alreadyRunning=false;try{await endpoint();alreadyRunning=true;}catch{}
  assert(!alreadyRunning,'Port 9225 is already in use; leave the existing session untouched');
  chrome=spawn('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',[
    '--headless=new',`--remote-debugging-port=${port}`,'--remote-debugging-address=127.0.0.1',
    `--user-data-dir=${profile}`,'--no-first-run','--no-default-browser-check','about:blank',
  ],{stdio:'ignore'});
  let targets;
  for(let i=0;i<100;i++){try{targets=await endpoint();if(targets.length)break;}catch{}await pause(100);}
  const target=targets?.find(x=>x.type==='page');assert(target,'Dedicated Chrome did not start');
  socket=new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((resolve,reject)=>{socket.onopen=resolve;socket.onerror=reject;});
  socket.onmessage=event=>{const m=JSON.parse(event.data);if(m.id){const item=pending.get(m.id);pending.delete(m.id);if(m.error)item?.reject(new Error('CDP command failed'));else item?.resolve(m.result);}else if(m.method==='Fetch.requestPaused')pausedImages.push(m.params.requestId);};
  await command('Runtime.enable');await command('Page.enable');await command('Network.enable');
  await command('Network.setCacheDisabled',{cacheDisabled:true});
  await command('Emulation.setDeviceMetricsOverride',{width:1280,height:950,deviceScaleFactor:1,mobile:false});
  await command('Page.navigate',{url:base});await wait('document.readyState === "complete"');
  // Never log the expression or config: the bootstrap token stays inside this process/browser.
  await evaluate(`fetch('/session',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({token:${JSON.stringify(config.token)}})}).then(r=>{if(!r.ok)throw new Error('session');return true})`);
  await command('Page.reload',{ignoreCache:true});
  await wait('document.querySelectorAll(".example").length===3 && !document.getElementById("route-confirmed").disabled');
  await evaluate(`(()=>{const realFetch=window.fetch.bind(window);window.__edge={holdExtraction:true,extractionReady:false,extractionReturned:false,failCollectionOnce:false,collectionFailureInjected:false,holdCollectionOnce:false,collectionHeld:false,collectionReturned:false,posts:[]};window.fetch=async(...args)=>{const url=new URL(typeof args[0]==='string'?args[0]:args[0].url,location.href),opts=args[1]||{};if(url.pathname==='/v3/avatars'&&opts.method==='POST')window.__edge.posts.push(JSON.parse(opts.body).requestId);const response=await realFetch(...args);if(url.pathname==='/v3/route-extractions'&&window.__edge.holdExtraction){window.__edge.extractionReady=true;await new Promise(resolve=>window.__edge.releaseExtraction=resolve);window.__edge.extractionReturned=true;}if(url.pathname==='/v3/avatars'&&(!opts.method||opts.method==='GET')&&window.__edge.holdCollectionOnce){window.__edge.holdCollectionOnce=false;window.__edge.collectionHeld=true;await new Promise(resolve=>window.__edge.releaseCollection=resolve);window.__edge.collectionReturned=true;}if(url.pathname==='/v3/avatars'&&(!opts.method||opts.method==='GET')&&window.__edge.failCollectionOnce){window.__edge.failCollectionOnce=false;window.__edge.collectionFailureInjected=true;return new Response(JSON.stringify({error:{code:'INJECTED_COLLECTION_503',message:'collection refresh unavailable'}}),{status:503,headers:{'Content-Type':'application/json'}});}return response;};return true;})()`);

  await upload('image-upload',path.join(root,'prototypes/avatar_generator/examples/synthetic-coast.png'));
  await wait('window.__edge.extractionReady');
  await click('.example:nth-child(3)');
  await wait('!document.getElementById("route-confirmed").disabled');
  const selected=await evaluate('JSON.stringify(window.nuntiTest.getRoute())');
  await evaluate('window.__edge.holdExtraction=false;window.__edge.releaseExtraction();true');
  await wait('window.__edge.extractionReturned');await pause(250);
  check('late-extraction-does-not-overwrite-new-example',await evaluate(`JSON.stringify(window.nuntiTest.getRoute())===${JSON.stringify(selected)}`));
  await click('#route-confirmed');await wait('!document.getElementById("create-button").disabled');
  check('stale-extraction-does-not-leave-busy-state',true);
  await click('#route-confirmed');

  // Hold the actual image response, so this tests loading rather than a fake image object.
  await command('Fetch.enable',{patterns:[{urlPattern:base+'/v3/assets/*',resourceType:'Image',requestStage:'Response'}]});
  await click('.example:nth-child(1)');
  for(let i=0;i<200&&!pausedImages.length;i++)await pause(25);
  assert(pausedImages.length,'No original image response was intercepted');
  check('confirmation-disabled-before-original-image-load',await evaluate('document.getElementById("route-confirmed").disabled && document.getElementById("create-button").disabled'));
  for(const requestId of pausedImages.splice(0))await command('Fetch.continueRequest',{requestId});
  await command('Fetch.disable');
  await wait('!document.getElementById("route-confirmed").disabled');
  check('confirmation-enabled-after-original-image-load',true);

  await evaluate(`document.getElementById('render-mode').value='LOCAL_RENDER';window.__edge.failCollectionOnce=true;true`);
  await click('#route-confirmed');await wait('!document.getElementById("create-button").disabled');
  await click('#create-button');
  const artifact=await wait('window.nuntiTest.getArtifact()',45000);
  await wait('window.__edge.collectionFailureInjected');
  await wait('document.getElementById("notice").textContent.includes("보관 목록")');
  check('successful-result-survives-collection-refresh-failure',await evaluate('!document.getElementById("result-view").hidden && !document.getElementById("result-details").hidden'));
  await pause(300);
  check('collection-failure-does-not-submit-new-uuid',await evaluate('window.__edge.posts.length===1 && new Set(window.__edge.posts).size===1'));
  proof.generated={requestId:artifact.requestId,characterId:artifact.characterId,mediaOrigin:artifact.mediaOrigin};
  assert.equal(artifact.mediaOrigin,'LOCAL_RENDER');

  await click('#replay-button');await pause(650);
  check('gate-test-starts-during-birth',await evaluate('document.getElementById("birth-status").textContent!=="이 길에서 태어난 눈티예요"'));
  await evaluate('window.nuntiVehicleAllowed(false);true');
  await pause(200);
  check('gate-denial-disables-creation',await evaluate('document.getElementById("create-button").disabled'));
  await evaluate('window.nuntiVehicleAllowed(true);true');
  await wait('document.getElementById("birth-status").textContent === "이 길에서 태어난 눈티예요"',5000);
  check('gate-return-restores-complete-static-artifact',await evaluate(`window.nuntiTest.getArtifact().characterId===${JSON.stringify(artifact.characterId)} && document.getElementById('birth-progress').hidden`));
  check('gate-return-does-not-generate-or-speak',await evaluate('window.__edge.posts.length===1 && document.getElementById("listen-button").textContent==="▷"'));

  await click('#new-button');
  await evaluate('window.__edge.holdCollectionOnce=true;true');
  await click('#create-button');
  await wait('window.__edge.collectionHeld && !document.getElementById("result-details").hidden',45000);
  await click('#new-button');
  await evaluate('window.__edge.holdExtraction=true;window.__edge.extractionReady=false;window.__edge.extractionReturned=false;true');
  await upload('image-upload',path.join(root,'prototypes/avatar_generator/examples/synthetic-coast.png'));
  await wait('window.__edge.extractionReady',5000);
  check('new-photo-extracts-while-previous-collection-refresh-is-held',await evaluate('!window.__edge.collectionReturned'));
  await evaluate('window.__edge.failCollectionOnce=true;window.__edge.releaseCollection();true');
  await wait('window.__edge.collectionReturned');await pause(150);
  check('late-collection-finally-does-not-release-photo-busy-state',await evaluate('document.getElementById("create-button").disabled && !window.__edge.extractionReturned'));
  check('late-collection-error-does-not-overwrite-photo-progress',await evaluate('document.getElementById("notice").textContent.includes("사진에서 경로선")'));
  await evaluate('window.__edge.holdExtraction=false;window.__edge.releaseExtraction();true');
  await wait('window.nuntiTest.getRoute()?.inputOrigin === "NAVIGATION_SCREENSHOT"',5000);
  check('new-photo-requires-fresh-confirmation',await evaluate('!document.getElementById("route-confirmed").checked && document.getElementById("create-button").disabled'));
  check('late-collection-refresh-does-not-generate-or-speak',await evaluate('window.__edge.posts.length===2 && document.getElementById("listen-button").textContent==="▷"'));
  proof.status='PASS_AVATAR_INPUT_EDGES';
}catch(error){proof.error=error.message;process.exitCode=1;}
finally{
  await fs.writeFile(path.join(out,'verification.json'),JSON.stringify(proof,null,2)+'\n');
  socket?.close();chrome?.kill('SIGTERM');
  console.log(JSON.stringify({status:proof.status,checks:proof.checks.length,report:path.join(out,'verification.json'),error:proof.error}));
}
