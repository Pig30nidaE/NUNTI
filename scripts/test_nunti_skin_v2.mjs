#!/usr/bin/env node
import assert from 'node:assert/strict';
import {webcrypto} from 'node:crypto';
import {readFileSync} from 'node:fs';
import {test} from 'node:test';
import {runInNewContext} from 'node:vm';

const site=new URL('../prototypes/avatar_generator/',import.meta.url);
const script=name=>readFileSync(new URL(name,site),'utf8');
const stub=()=>{};
function harness({storage=new Map(),missing=null,native=false}={}){
  const queue=new Map(),draws=[],requests=[],nativeStarts=[],nativeStops=[],clips=[];
  let clock=0,nextFrame=0;
  const ctx={setTransform:stub,clearRect:stub,save:stub,restore:stub,translate:stub,rotate:stub,scale:stub,beginPath:stub,
    moveTo:stub,lineTo:stub,closePath:stub,clip:()=>clips.push(clock),quadraticCurveTo:stub,bezierCurveTo:stub,fill:stub,fillRect:stub,
    createRadialGradient:()=>({addColorStop:stub}),
    drawImage:img=>draws.push(img.src)};
  const canvas={getContext:()=>ctx,getBoundingClientRect:()=>({left:22,top:40,width:640,height:640})};
  const env={window:{},crypto:webcrypto,TextEncoder,setTimeout,clearTimeout,
    document:{createElement:()=>({getContext:()=>ctx,src:'composed-wardrobe'})},
    localStorage:{getItem:key=>storage.get(key)??null,setItem:(key,value)=>storage.set(key,value)},
    Image:class{
      async decode(){
        requests.push(this.src);
        if(this.src===missing)throw new Error('404');
        const data=readFileSync(new URL(this.src.slice(1),site));
        assert.equal(data.subarray(1,4).toString(),'PNG');
        this.naturalWidth=data.readUInt32BE(16);this.naturalHeight=data.readUInt32BE(20);
      }
    },
    matchMedia:()=>({matches:false,addEventListener:stub}),
    performance:{now:()=>clock},
    requestAnimationFrame:fn=>{queue.set(++nextFrame,fn);return nextFrame;},
    cancelAnimationFrame:id=>queue.delete(id)};
  if(native)env.window.NuntiNative={
    startCharacterMotion:(...args)=>nativeStarts.push(args),
    stopCharacterMotion:id=>nativeStops.push(id),
  };
  runInNewContext(script('nunti-skins.js')+'\n'+script('nunti-skin-motion.js'),env);
  let allowed=true,visible=true;
  const {NuntiSkins:skins,NuntiSkinRenderer:renderer}=env.window;
  const motion=renderer.create({canvas,allowed:()=>allowed,visible:()=>visible,onFrame:stub});
  return {skins,renderer,motion,draws,requests,queue,storage,nativeStarts,nativeStops,clips,
    setCompanionPlayer:player=>{env.window.NuntiCompanionPlayer=player;},
    nativeReady:(id,ready)=>env.window.nuntiCharacterMotionReady(id,ready),
    nativeFinished:id=>env.window.nuntiCharacterMotionFinished(id),
    restrict:()=>{allowed=false;},background:()=>{visible=false;},
    step(ms){clock=ms;const callbacks=[...queue.values()];queue.clear();for(const cb of callbacks)cb(ms);},
    async play(id='sea'){const f=skins.fixtures[id],spec=skins.resolve(f);await motion.show(spec,await renderer.image(id),{points:f.points},true);}};
}

test('destination sets wardrobe; confirmed route and explicit mood set deterministic motion',()=>{
  const {skins}=harness();
  const specs=['sea','city','mountain'].map(id=>skins.resolve({...skins.fixtures[id],routeId:'confirmed-route'}));
  assert.deepEqual(specs.map(s=>s.skinId),['sea','city','mountain']);
  for(const field of ['outfit','headStyle','earStyle','palette','pattern'])assert.equal(new Set(specs.map(s=>s[field])).size,3,field);
  const source={destinationCategory:'mountain',mood:'excited',roadType:'rural',routeId:'route'};
  assert.equal(JSON.stringify(skins.resolve(source)),JSON.stringify(skins.resolve({...source})));
  assert.equal(skins.resolve(source).mood,'adventurous');
  assert.equal(skins.resolve(source).animationPreset.ribbon,'dotted');
  assert.equal(skins.resolve({destinationCategory:'__proto__',mood:'driver inferred'}).skinId,'default');
  assert.equal(skins.resolve({mood:'driver inferred'}).mood,'unset');
});

test('identical inputs keep the same saved identity and reopen; missing final stores actual fallback',async()=>{
  const a=harness(),input={destination:{name:'도시'},purpose:'산책',route:null},context=a.skins.fixtures.city;
  const first=await a.skins.createRecord(input,context,true);
  const second=await a.skins.createRecord(input,context,true);
  assert.equal(first.characterId,second.characterId);
  a.skins.save(first);a.skins.save(second);
  const reopened=harness({storage:a.storage}).skins.list();
  assert.equal(reopened.length,1);assert.equal(reopened[0].visual.path,'/skin-v2/atelier/city/final.png');
  const fallback=await a.skins.createRecord(input,context,false);
  assert.equal(fallback.design.skinSpec.requestedSkinId,'city');
  assert.equal(fallback.visual.path,'/skin-v2/default/final.png');
  assert.throws(()=>a.skins.path('../city'));
});

for (const [version,directory] of [['skin-v2.0','skin-v2'],['skin-v2.1','skin-v2/polish']]) test(`${version} save reopens its own asset and rejects a mismatched version path`,async()=>{
  const a=harness();
  const input={destination:{name:'도시'},purpose:'산책',route:null};
  const current=await a.skins.createRecord(input,a.skins.fixtures.city,true);
  const legacy={...current,characterId:'nunti-skin-'+'a'.repeat(32),visual:{path:`/${directory}/city/final.png`},
    design:{...current.design,skinSpec:{...current.design.skinSpec,version}}};
  assert.equal(a.skins.isSkin({...legacy,visual:current.visual}),false);
  a.skins.save(legacy);a.skins.save(current);
  assert.equal(a.skins.list().length,2);
  const spec=legacy.design.skinSpec;
  const image=await a.renderer.image(spec.skinId,'final',spec.version);
  await a.motion.show(spec,image,legacy.route,false);
  assert.equal(a.draws.at(-1),legacy.visual.path);
});

test('mock gate rejects direct model/voice writes and cross-origin paths',()=>{
  const {skins}=harness();
  assert.equal(skins.MOCK_SKIN_MODE,true);
  for(const [url,method] of [['/v3/avatars','POST'],['/v3/avatars/x/voice','POST'],['/v3/avatars/x/feedback-voice/JOY','POST'],
    ['https://example.invalid/','GET'],['//example.invalid/','GET'],['/\\example.invalid/','GET']]){
    assert.throws(()=>skins.assertRequest(url,method),/MOCK_SKIN_MODE/);
  }
  assert.doesNotThrow(()=>skins.assertRequest('/v3/avatars','GET'));
  assert.doesNotThrow(()=>skins.assertRequest('/v3/route-extractions','POST'));
});

test('real PNG lookup; all phases; distinct outfit/head draw and final path',async()=>{
  const a=harness();await a.play('city');
  for(const ms of [0,500,1200,1820,2000,2440,3300,3850,4000])a.step(ms);
  const d=a.motion.diagnostics();
  assert.equal(Array.from(d.visited).join('|'),'DEFAULT_IDLE|ROUTE_ENERGY|OUTFIT_SWAP|HEAD_AND_EYES_TRANSFORM|SKIN_REVEAL|FINAL_IDLE');
  assert.equal(d.reason,'COMPLETE');assert.equal(d.elapsedMs,4000);assert.equal(a.queue.size,0);
  assert.equal(a.draws[0],'/skin-v2/default/final.png');
  assert.ok(a.draws.includes('/skin-v2/atelier/city/outfit.png'));
  assert.ok(a.draws.includes('/skin-v2/atelier/city/head.png'));
  assert.ok(a.draws.includes('composed-wardrobe'));
  assert.equal(a.draws.at(-1),'/skin-v2/atelier/city/final.png');
  for(const id of ['default','sea','city','mountain'])for(const part of ['final','outfit','head','eyes','accessory'])await a.renderer.image(id,part);
  assert.equal(new Set(a.requests).size,20);
});

test('skip, driving, background and system reduced stop scheduling and draw the same endpoint',async()=>{
  for(const reason of ['SKIPPED','RESTRICTED','BACKGROUNDED','REDUCED']){
    const a=harness();await a.play();a.step(1700);
    if(reason==='SKIPPED')a.motion.stop(reason);
    if(reason==='RESTRICTED'){a.restrict();a.step(1750);}
    if(reason==='BACKGROUNDED'){a.background();a.step(1750);}
    if(reason==='REDUCED')a.motion.appearance({systemReducedMotion:true});
    assert.equal(a.motion.diagnostics().reason,reason);assert.equal(a.queue.size,0);
    assert.equal(a.draws.at(-1),'/skin-v2/atelier/sea/final.png');
  }
});

test('a broken independent layer settles without a partial costume or scheduled frame',async()=>{
  const a=harness({missing:'/skin-v2/atelier/mountain/head.png'});
  await a.play('mountain');
  assert.equal(a.motion.diagnostics().reason,'LAYER_ASSET_FAILURE');
  assert.equal(a.draws.at(-1),'/skin-v2/atelier/mountain/final.png');
  assert.equal(a.queue.size,0);
});

test('the ready native renderer owns the actor until Skip hands back the exact still',async()=>{
  const a=harness({native:true}),playing=a.play();
  await new Promise(resolve=>setImmediate(resolve));
  const [[id,...payload]]=a.nativeStarts;
  assert.deepEqual(payload.slice(0,5),['sea',22,40,640,640]);
  assert.ok(Math.abs(payload[5]+.46)<1e-9,'confirmed route supplies the VFX direction');
  assert.equal(a.motion.diagnostics().reason,'LOADING');
  a.nativeReady(id,true);
  await playing;
  assert.equal(a.motion.diagnostics().renderer,'NATIVE_CANVAS');
  const drawn=a.draws.length;
  a.step(1800);
  assert.equal(a.draws.length,drawn);
  a.motion.stop('SKIPPED');
  assert.deepEqual(a.nativeStops,[id]);
  assert.equal(a.draws.at(-1),'/skin-v2/atelier/sea/final.png');
});

test('a late native acknowledgement cannot restart an interrupted transformation',async()=>{
  const a=harness({native:true}),playing=a.play();
  await new Promise(resolve=>setImmediate(resolve));
  const [[id]]=a.nativeStarts;
  a.motion.appearance({systemReducedMotion:true});
  a.nativeReady(id,true);
  await playing;
  assert.deepEqual(a.nativeStops,[id]);
  assert.equal(a.motion.diagnostics().reason,'REDUCED');
  assert.equal(a.queue.size,0);
});

test('native playback waits for its own finish event rather than cutting off at four seconds',async()=>{
  const a=harness({native:true}),playing=a.play();
  await new Promise(resolve=>setImmediate(resolve));
  const [[id]]=a.nativeStarts;
  a.nativeReady(id,true);
  await playing;
  a.step(4100);
  assert.equal(a.motion.diagnostics().running,true);
  const handoffs=[];
  a.setCompanionPlayer({setResult:skin=>handoffs.push({skin,priorStops:a.nativeStops.length})});
  a.nativeFinished(id);
  assert.equal(a.motion.diagnostics().reason,'COMPLETE');
  assert.deepEqual(handoffs,[{skin:'sea',priorStops:0}]);
  assert.deepEqual(a.nativeStops,[id]);
  assert.equal(a.draws.at(-1),'/skin-v2/atelier/sea/final.png');
});

test('wardrobe-v4 skins cross-dissolve as a unified scene without horizontal clip slicing',async()=>{
  const a=harness();
  const spec=a.skins.resolve({destinationCategory:'city',mood:'curious',roadType:'urban',routeId:'r1'});
  const wardrobeSpec={...spec,skinId:'wardrobe-city',summary:'도시 외출복 · 오늘의 눈티'};
  await a.motion.show(wardrobeSpec,{src:'/v3/assets/wardrobe-city.png'},{points:[[0.1,0.8],[0.9,0.2]]},true);
  for(const ms of [0,1200,2750,3000,3310,4000])a.step(ms);
  assert.equal(a.clips.length,0,'wardrobe-* skins must not slice head/body horizontally');
  assert.equal(a.draws.at(-1),'/v3/assets/wardrobe-city.png');
});
