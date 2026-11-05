#!/usr/bin/env node
// Actual Android avatar / generated voice / purpose motion integration. No recording.
import fs from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
import {execFileSync} from 'node:child_process';
import {createHash} from 'node:crypto';
import {fileURLToPath} from 'node:url';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const out=path.join(root,'.local/avatar-v6/ui');await fs.mkdir(out,{recursive:true});
const adb=path.join(root,'.local/pm-tools/sdk/platform-tools/adb');
execFileSync(adb,['-s','emulator-5554','shell','am','start','--user','10','-n','ai.nunti.avatar.demo/ai.nunti.app.MainActivity']);
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
const proof={status:'FAIL',surface:'ACTUAL_ANDROID_WEBVIEW',checks:[],cases:[],videoRecorded:false,audioRecorded:false};
proof.sourceSha256={};
for(const file of ['prototypes/avatar_generator/studio.js','prototypes/avatar_generator/formation.js','prototypes/avatar_generator/journey_effects.js','android/app/src/main/kotlin/ai/nunti/app/studio/AvatarStudioActivity.kt'])proof.sourceSha256[file]=createHash('sha256').update(await fs.readFile(path.join(root,file))).digest('hex');
proof.apkSha256=JSON.parse(await fs.readFile(path.join(root,'.local/avatar-generator/delivery.json'))).sha256;
const check=(label,result)=>{assert(result,label);proof.checks.push(label);};
const logs=()=>execFileSync(adb,['-s','emulator-5554','logcat','-d','-s','NuntiStudio:I','*:S'],{encoding:'utf8',maxBuffer:8*1024*1024});
try{
  await call('Runtime.enable');await call('Page.enable');await call('Page.reload',{ignoreCache:true});
  await wait('window.nuntiCapabilities?.voice?.mode==="LOCAL_VOICE_DESIGN"&&window.NuntiJourneyEffects&&state.nativeAllowed&&!document.hidden');
  check('native-generated-player-installed',await evaluate('typeof window.NuntiNative.playVoice==="function"'));
  const voiceArtifact=JSON.parse(await fs.readFile(path.join(root,'.local/avatar-v6/integration/artifact.json')));
  await evaluate(`window.nuntiTest.showArtifact(${JSON.stringify(voiceArtifact)},true)`);
  await wait('window.nuntiTest.getFormation()');
  const before=logs();await click('listen-button');await wait('document.getElementById("listen-button").textContent==="▷"',20000);
  const after=logs();
  check('actual-generated-wav-starts-and-completes',after.split('STUDIO_GENERATED_VOICE_STARTED').length>before.split('STUDIO_GENERATED_VOICE_STARTED').length&&after.split('STUDIO_GENERATED_VOICE_COMPLETED').length>before.split('STUDIO_GENERATED_VOICE_COMPLETED').length);
  const id=voiceArtifact.characterId;
  const saved=await evaluate(`fetch('/v3/avatars/${id}').then(r=>r.json()).then(v=>v.data)`);
  check('saved-generated-voice-identity',saved.voice.audio.sha256===voiceArtifact.voice.audio.sha256&&saved.visual.sha256===voiceArtifact.visual.sha256);
  const oldRequest=await evaluate('nativeVoiceRequestId()');
  await click('listen-button');await pause(400);
  await evaluate(`window.nuntiSpeechFinished(${JSON.stringify(oldRequest)})`);
  check('late-native-completion-keeps-current-playback',await evaluate('speaking&&document.getElementById("listen-button").textContent==="□"'));
  await evaluate(`window.nuntiSpeechFailed(${JSON.stringify(oldRequest)})`);
  check('late-native-error-keeps-current-playback',await evaluate('speaking&&document.getElementById("listen-button").textContent==="□"'));
  const navigationAck=await evaluate('JSON.parse(window.NuntiNative.navigationCommand("foreground","{}"))');assert(navigationAck.accepted);
  await wait('!state.nativeAllowed',15000);
  check('voice-ui-stops-at-gate',await evaluate('document.getElementById("listen-button").textContent==="▷"'));
  // Restore the UI through the actual host callback after re-entering the Activity.
  await pause(300);
  execFileSync(adb,['-s','emulator-5554','shell','am','start','--user','10','-n','ai.nunti.avatar.demo/ai.nunti.app.MainActivity']);
  await wait('state.nativeAllowed&&window.nuntiTest.getArtifact()');
  for(const [destination,purpose,role] of [['서울역','출장 미팅','BUSINESS'],['수원역','연인과 데이트','DATE'],['을왕리 해수욕장','수영과 물놀이','SWIM']]){
    await click('new-button');
    await evaluate(`window.nuntiTest.viewExample(0);document.getElementById('destination').value=${JSON.stringify(destination)};document.getElementById('traits').value='';document.getElementById('purpose').value=${JSON.stringify(purpose)};document.getElementById('render-mode').value='LOCAL_RENDER';document.getElementById('purpose').dispatchEvent(new Event('input',{bubbles:true}))`);
    await wait('!document.getElementById("route-confirmed").disabled');
    await click('route-confirmed');await wait('!document.getElementById("create-button").disabled');
    await click('create-button');const a=await wait(`window.nuntiTest.getArtifact()?.destination.name===${JSON.stringify(destination)}&&window.nuntiTest.getArtifact()`);
    await wait('window.nuntiTest.getFormation()&& !document.getElementById("result-details").hidden');
    const expectedVoice={BUSINESS:'professional',DATE:'celebration',SWIM:'swimmer'}[role];
    check(role+'-purpose-controls-outfit-and-voice',a.design.characterPlan.purpose.role===role&&a.voice.plan.role===expectedVoice);
    const frames=[];
    for(const p of [.12,.40,.68,1]){
      const f=await evaluate(`window.nuntiTest.captureFormation(${p})`);
      check(role+'-formation-'+p,f&&f.progress===p&&Number.isFinite(f.area));
      frames.push(f);
    }
    await fs.writeFile(path.join(out,role+'-artifact.json'),JSON.stringify(a,null,2));
    const data=await evaluate('document.getElementById("birth-canvas").toDataURL("image/png")');
    await fs.writeFile(path.join(out,role+'-canvas.png'),Buffer.from(data.split(',')[1],'base64'));
    proof.cases.push({destination,purpose,role,characterId:a.characterId,image:a.visual.sha256,structure:a.design.characterPlan.structuralSignature,voiceRole:a.voice.plan.role,frames:frames.map(f=>({progress:f.progress,area:f.area}))});
  }
  check('three-distinct-structures-and-pixels',new Set(proof.cases.map(c=>c.structure)).size===3&&new Set(proof.cases.map(c=>c.image)).size===3);
  await evaluate(`window.nuntiTest.showArtifact(${JSON.stringify(voiceArtifact)},false)`);
  await pause(400);await evaluate('window.scrollTo(0,0)');
  await fs.writeFile(path.join(out,'actual-android.png'),execFileSync(adb,['-s','emulator-5554','exec-out','screencap','-p'],{maxBuffer:12*1024*1024}));
  check('no-javascript-errors',exceptions.length===0);proof.status='PASS';
}catch(e){proof.error=e.stack;throw e;}finally{
  proof.exceptions=exceptions;
  await fs.writeFile(path.join(out,'verification.json'),JSON.stringify(proof,null,2));socket.close();
  console.log(JSON.stringify({status:proof.status,checks:proof.checks.length,error:proof.error,report:path.join(out,'verification.json')}));
}
