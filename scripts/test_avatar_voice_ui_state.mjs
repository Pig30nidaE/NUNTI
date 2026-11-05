#!/usr/bin/env node
/**
 * Execute the production studio.js voice/lifecycle block with controlled boundaries.
 * This is a state/race regression, NOT a browser, native MediaPlayer or GPU test.
 * Stubs: DOM nodes, visibility events, HTTP promises, Audio and native bridge calls.
 * All cancellation, epoch checks, and media callbacks are read from studio.js.
 */
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import {randomUUID} from 'node:crypto';
import {fileURLToPath} from 'node:url';

const root=path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const source=fs.readFileSync(path.join(root,'prototypes/avatar_generator/studio.js'),'utf8');
const start=source.indexOf('let speaking=false, voiceEpoch=0');
const end=source.indexOf('async function init()',start);
assert.ok(start>=0&&end>start,'Production voice block markers must still identify the real handlers.');
const production=source.slice(start,end);

function deferred(){let resolve,reject;const promise=new Promise((yes,no)=>{resolve=yes;reject=no;});return {promise,resolve,reject};}
function artifact(id,ready=false){return {characterId:id,displayName:id,destination:{name:'서울역'},voice:{provider:'LOCAL_QWEN_VOICE_DESIGN',...(ready?{audio:{path:'/v3/assets/'+id}}:{})}};}
function generated(id){return {provider:'LOCAL_QWEN_VOICE_DESIGN',audio:{path:'/v3/assets/'+id}};}

function harness({ready=true,native=false}={}){
  const nodes=new Map(),events=new Map(),requests=[],audios=[],nativePlayed=[];
  const $=id=>{if(!nodes.has(id))nodes.set(id,{textContent:'',hidden:false});return nodes.get(id);};
  class ControlledAudio {
    constructor(url){this.src=url;this.paused=false;this.playCalls=0;audios.push(this);}
    pause(){this.paused=true;}
    play(){this.playCalls++;return Promise.resolve();}
  }
  const box={
    crypto:{randomUUID},
    viewEpoch:0,
    state:{artifact:artifact('A',ready),nativeAllowed:true,animation:0},
    document:{hidden:false,addEventListener:(name,fn)=>events.set(name,fn)},
    window:{addEventListener:()=>{}},
    $,Audio:ControlledAudio,
    api:(url,body)=>{const pending=deferred();requests.push({url,body,...pending});return pending.promise;},
    message:()=>{},enableCreate:()=>{},drawRoute:()=>{},cancelAnimationFrame:()=>{},
    showArtifact:async()=>{},
  };
  if(native)box.window.NuntiNative={stopSpeaking:()=>{},playVoice:(url,requestId)=>nativePlayed.push({url,requestId}),isSpeechAvailable:()=>true,speak:(text,rate,pitch,requestId)=>nativePlayed.push({text,requestId})};
  vm.createContext(box);
  vm.runInContext(production,box,{filename:'studio.js:production-voice-block'});
  return {
    box,nodes,events,requests,audios,nativePlayed,
    click:()=>$('listen-button').onclick(),
    speaking:()=>vm.runInContext('speaking',box),
    activeAudio:()=>vm.runInContext('voiceAudio',box),
    stop:()=>vm.runInContext('stopVoice()',box),
  };
}

const results=[];
async function check(name,run){
  try{await run();results.push({name,status:'PASS'});}
  catch(error){results.push({name,status:'FAIL',error:error.message});}
}

await check('late error from cancelled Audio cannot stop its successor',async()=>{
  const h=harness();await h.click();const old=h.audios[0],queuedError=old.onerror;
  await h.click();h.box.state.artifact=artifact('B',true);await h.click();
  const current=h.audios[1];assert.equal(current.paused,false);
  queuedError?.(); // Already queued before removal; the handler also needs an ownership check.
  assert.equal(current.paused,false,'Old Audio error interrupted the current avatar.');
  assert.equal(h.speaking(),true);
  assert.equal(h.activeAudio(),current);
});

await check('late ended event cannot mark a newer Audio as stopped',async()=>{
  const h=harness();await h.click();const old=h.audios[0],queuedEnd=old.onended;
  await h.click();h.box.state.artifact=artifact('B',true);await h.click();
  const current=h.audios[1];queuedEnd?.();
  assert.equal(h.speaking(),true,'Old completion replaced the new playback state.');
  await h.click(); // This must stop B, rather than create overlapping audio C.
  assert.equal(current.paused,true);
  assert.equal(h.audios.length,2);
});

await check('stop detaches both callbacks before clearing the old source',async()=>{
  const h=harness();await h.click();const old=h.audios[0];h.stop();
  assert.equal(old.onended,null);assert.equal(old.onerror,null);
  assert.equal(old.paused,true);assert.equal(h.activeAudio(),null);
});

for(const native of [false,true]){
  const target=native?'native bridge':'browser Audio';
  await check(`cancel pending synthesis prevents playback through ${target}`,async()=>{
    const h=harness({ready:false,native}),pending=h.click();
    assert.equal(h.requests.length,1);assert.equal(h.speaking(),true);
    await h.click();h.requests[0].resolve(generated('A'));await pending;
    assert.equal(h.audios.length,0);assert.equal(h.nativePlayed.length,0);
    assert.equal(h.speaking(),false);
    assert.equal(h.box.state.artifact.voice.audio.path,'/v3/assets/A','Completed generation may still be cached.');
  });
  await check(`avatar replacement while synthesizing prevents stale ${target} playback`,async()=>{
    const h=harness({ready:false,native}),pending=h.click();
    h.box.state.artifact=artifact('B',true);h.requests[0].resolve(generated('A'));await pending;
    assert.equal(h.audios.length,0);assert.equal(h.nativePlayed.length,0);
    assert.equal(h.box.state.artifact.characterId,'B');
  });
  await check(`vehicle gate revocation prevents deferred ${target} playback`,async()=>{
    const h=harness({ready:false,native}),pending=h.click();
    h.box.window.nuntiVehicleAllowed(false);
    h.requests[0].resolve(generated('A'));await pending;
    assert.equal(h.audios.length,0);assert.equal(h.nativePlayed.length,0);
    assert.equal(h.speaking(),false);
  });
  await check(`background transition prevents deferred ${target} playback`,async()=>{
    const h=harness({ready:false,native}),pending=h.click();
    h.box.document.hidden=true;h.events.get('visibilitychange')();
    h.requests[0].resolve(generated('A'));await pending;
    assert.equal(h.audios.length,0);assert.equal(h.nativePlayed.length,0);
    assert.equal(h.speaking(),false);
  });
}

await check('current Audio completion clears only its playback state',async()=>{
  const h=harness();await h.click();h.audios[0].onended();
  assert.equal(h.speaking(),false);
  assert.equal(h.nodes.get('listen-button').textContent,'▷');
});

for(const callback of ['nuntiSpeechFinished','nuntiSpeechFailed']){
  await check(`late native ${callback} cannot change the newer playback`,async()=>{
    const h=harness({native:true});await h.click();const old=h.nativePlayed[0].requestId;
    h.stop();h.box.state.artifact=artifact('B',true);await h.click();
    h.box.window[callback](old);assert.equal(h.speaking(),true);
    h.box.window[callback](h.nativePlayed[1].requestId);assert.equal(h.speaking(),false);
  });
  await check(`native ${callback} from before page reload is ignored`,async()=>{
    const old=harness({native:true});await old.click();
    const current=harness({native:true});await current.click();
    current.box.window[callback](old.nativePlayed[0].requestId);assert.equal(current.speaking(),true);
  });
}
await check('legacy device TTS uses the same request ownership boundary',async()=>{
  const h=harness({native:true});h.box.state.artifact.voice={provider:'DEVICE_SPEECH',rate:1,pitch:1};await h.click();
  const old=h.nativePlayed[0].requestId;assert.equal(typeof old,'string');
  h.stop();h.box.state.artifact=artifact('B',true);await h.click();
  h.box.window.nuntiSpeechFinished(old);assert.equal(h.speaking(),true);
  h.box.window.nuntiSpeechFinished(h.nativePlayed[1].requestId);assert.equal(h.speaking(),false);
});

console.log(JSON.stringify({
  source:'prototypes/avatar_generator/studio.js',
  boundary:'Node VM; controlled DOM/HTTP/Audio/native bridge; no actual playback or model inference',
  checks:results.length,passed:results.filter(r=>r.status==='PASS').length,results,
},null,2));
if(results.some(r=>r.status==='FAIL'))process.exitCode=1;
