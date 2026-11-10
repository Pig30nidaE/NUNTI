#!/usr/bin/env node
// Execute production UI handlers with controlled HTTP, Canvas and image decoding.
// This verifies consumer behavior; real browser layout and Android rendering are separate checks.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import {webcrypto} from 'node:crypto';

const source=fs.readFileSync(new URL('../prototypes/avatar_generator/studio.js',import.meta.url),'utf8');
const skinDeclarations=source.slice(source.indexOf('const skins='),source.indexOf('window.NuntiBirth ='));
const html=fs.readFileSync(new URL('../prototypes/avatar_generator/index.html',import.meta.url),'utf8');
function block(from,to){const a=source.indexOf(from),b=source.indexOf(to,a);assert.ok(a>=0&&b>a,from);return source.slice(a,b);}
const production=[
  block('function canvasSize(', 'function drawRoute()'),
  block('function enableCreate()', 'function viewExample('),
  block("$('render-mode').onchange=", 'function waitingAnimation()'),
  block('async function showArtifact(', 'function legacyBirthAnimation('),
  block('async function init()', "$('session-form').onsubmit="),
].join('\n');
const route={points:[[0.1,0.2],[0.4,0.6],[0.8,0.9]],inputOrigin:'TEST_ROUTE',sourceLabel:'시험 경로'};
function artifact(input={}){return {
  characterId:'nunti-00000000-0000-4000-8000-000000000001',displayName:'눈티 A',
  destination:{name:'서울'},purpose:'산책',route:input.route??null,
  visual:{path:'/v3/assets/test'},mediaOrigin:input.renderMode||'LOCAL_LAYERS',
  design:{personality:'여정을 함께해요',staticOnly:true,motifs:[],avatarSpec:{accessibilityLabel:'차분한 눈티'}},
  voice:{description:'차분한 목소리',provider:'LOCAL_QWEN_VOICE_DESIGN'},
};}
function harness({mode='LOCAL_LAYERS',sourceRoute=route,allowed=true,confirmed=true,canGenerate=true,caps={layeredRenderAvailable:true},digest}={}){
  const nodes=new Map(),requests=[],notices=[],draws=[],arcs=[],options=new Map();
  let rafCount=0,waitingCount=0,legacyCount=0,sequence=0,failNext=false;
  const context={setTransform(){},clearRect(){},beginPath(){},moveTo(){},lineTo(){},stroke(){},fill(){},arc(...args){arcs.push(args);},drawImage(...args){draws.push(args);}};
  function node(){return {value:'',hidden:false,checked:confirmed,disabled:false,children:[],textContent:'',width:0,height:0,
    style:{setProperty(){}},dataset:{},firstElementChild:{style:{}},classList:{toggle(){}},
    replaceChildren(){this.children=[];},append(...values){this.children.push(...values);},
    setAttribute(key,value){this[key]=value;},getBoundingClientRect:()=>({width:400,height:300}),getContext:()=>context,close(){},showModal(){},
  };}
  const $=id=>{if(!nodes.has(id))nodes.set(id,node());return nodes.get(id);};
  for(const id of ['LOCAL_RENDER','LOCAL_LAYERS','LOCAL_MODEL','IMAGE_API'])options.set(id,node());
  $('render-mode').querySelector=selector=>options.get(selector.match(/value="([^"]+)"/)[1]);
  Object.defineProperty($('render-mode'),'selectedOptions',{get:()=>[options.get($('render-mode').value)]});
  $('render-mode').value=mode;$('destination').value='서울';$('purpose').value='산책';
  $('layer-destination').value='city';$('layer-road').value='urban';$('layer-mood').value='curious';
  const box={$,viewEpoch:0,state:{nativeAllowed:allowed,imageReady:!!sourceRoute,route:sourceRoute,animation:77,busy:false,planning:false,pending:null},
    window:{NuntiNavigation:{canGenerate:()=>canGenerate,updateButtons(){},setCapabilities(){}}},
    document:{hidden:false,createElement:node,querySelector:()=>node()},devicePixelRatio:1,
    crypto:{randomUUID:()=>String(++sequence),subtle:{digest:digest||webcrypto.subtle.digest.bind(webcrypto.subtle)}},TextEncoder,Uint8Array,
    Image:class {naturalWidth=800;naturalHeight=1200;decode(){return Promise.resolve();}},
    requestAnimationFrame(){rafCount++;return rafCount;},cancelAnimationFrame(){},
    screen(which){$('result-view').hidden=which!=='result';},message:text=>notices.push(text),errorText:e=>e.message,
    waitingAnimation(){waitingCount++;},legacyBirthAnimation(){legacyCount++;},
    prepareVoiceButton:node(),preparingJourneyVoice:false,journeyVoiceReady:new Set(),reduced:false,
    examples:async()=>{},loadCollection:async()=>{},
    api:async(path,body)=>{if(path==='/v3/capabilities')return caps;requests.push(body);if(failNext){failNext=false;throw new Error('CONNECTION_LOST');}return artifact(body);},
  };
  vm.createContext(box);vm.runInContext(skinDeclarations+production,box,{filename:'studio.js:layer-consumer-handlers'});
  return {box,$,requests,notices,draws,arcs,options,
    submit:()=>$('journey-form').onsubmit({preventDefault(){}}),
    show:value=>box.showArtifact(value,true),
    failNext:()=>{failNext=true;},stats:()=>({rafCount,waitingCount,legacyCount}),
  };
}
const results=[];
async function check(name,run){try{await run();results.push({name,status:'PASS'});}catch(error){results.push({name,status:'FAIL',error:error.stack});}}

await check('layer fields and mode are present in the real HTML with explicit fallback choices',()=>{
  for(const [id,values] of [['layer-destination',['city','coast','mountain','unknown']],['layer-road',['urban','highway','rural','mixed','unknown']],['layer-mood',['calm','curious','adventurous','unset']]]){
    const select=html.match(new RegExp(`<select\\b[^>]*\\bid="${id}"[^>]*>([\\s\\S]*?)</select>`));assert.ok(select,id);
    for(const value of values)assert.ok(select[1].includes(`value="${value}"`),value);
  }
  assert.ok(html.includes('value="LOCAL_LAYERS" hidden disabled'));
});
await check('available layer capability selects the approved A renderer as the UI default',async()=>{
  const h=harness({mode:'LOCAL_RENDER'});await h.box.init();
  assert.equal(h.$('engine-choice').hidden,false);assert.equal(h.options.get('LOCAL_LAYERS').disabled,false);
  assert.equal(h.$('render-mode').value,'LOCAL_LAYERS');assert.equal(h.$('layer-options').hidden,false);
  h.$('render-mode').value='LOCAL_LAYERS';h.$('render-mode').onchange();assert.equal(h.$('layer-options').hidden,false);
});
await check('server without layer capability keeps the new option unavailable',async()=>{
  const h=harness({mode:'LOCAL_RENDER',caps:{}});await h.box.init();assert.equal(h.options.get('LOCAL_LAYERS').disabled,true);assert.equal(h.$('engine-choice').hidden,true);
});
await check('no route is accepted only by LOCAL_LAYERS and shows a static default receipt',async()=>{
  for(const mode of ['LOCAL_RENDER','LOCAL_MODEL','IMAGE_API','LOCAL_LAYERS']){
    const h=harness({mode,sourceRoute:null,confirmed:false});h.box.enableCreate();assert.equal(h.$('create-button').disabled,mode!=='LOCAL_LAYERS');
    await h.submit();assert.equal(h.requests.length,mode==='LOCAL_LAYERS'?1:0);
    if(mode==='LOCAL_LAYERS'){
      assert.equal(h.requests[0].route,null);assert.equal(h.requests[0].variantContext.routeId,undefined);
      assert.equal(h.$('receipt-canvas').hidden,true);assert.ok(h.$('receipt-source').textContent.includes('경로 정보를 받지 못해'));
      assert.equal(h.arcs.length,0);assert.deepEqual(h.stats(),{rafCount:0,waitingCount:0,legacyCount:0});
    }
  }
});
await check('existing route still needs image readiness, confirmation, vehicle permission and current API plan',async()=>{
  for(const setup of [{confirmed:false},{allowed:false},{canGenerate:false}]){const h=harness(setup);await h.submit();assert.equal(h.requests.length,0);}
  const h=harness();h.box.state.imageReady=false;await h.submit();assert.equal(h.requests.length,0);
});
await check('explicit choices produce stable route identity, seed and correctly sourced context',async()=>{
  const h=harness();await h.submit();await h.submit();
  const a=h.requests[0].variantContext,b=h.requests[1].variantContext;
  assert.equal(a.routeId,b.routeId);assert.match(a.routeId,/^route-[0-9a-f]{64}$/);assert.equal(a.seed,'0');
  assert.equal(a.destinationCategory,'city');assert.equal(a.roadType,'urban');assert.equal(a.userSelectedMood,'curious');
  assert.equal(a.provenance.routeId,'app-derived');
  for(const key of ['destinationCategory','roadType','userSelectedMood'])assert.equal(a.provenance[key],'user-selected');
  h.box.state.route={...route,points:[[0.1,0.2],[0.6,0.3],[0.8,0.9]]};await h.submit();assert.notEqual(h.requests[2].variantContext.routeId,a.routeId);
});
await check('API plan identity is reused and unknown choices remain explicit fallbacks',async()=>{
  const h=harness({sourceRoute:{...route,apiPlanId:'a'.repeat(64)}});
  h.$('layer-destination').value='unknown';h.$('layer-road').value='unknown';h.$('layer-mood').value='unset';await h.submit();
  const c=h.requests[0].variantContext;assert.equal(c.routeId,'api-'+'a'.repeat(64));
  for(const key of ['destinationCategory','roadType','userSelectedMood'])assert.equal(c.provenance[key],'fallback');
});
await check('legacy rendering still submits without a variantContext',async()=>{
  const h=harness({mode:'LOCAL_RENDER'});await h.submit();assert.equal(h.requests[0].variantContext,undefined);assert.equal(h.stats().waitingCount,1);
});
await check('identical layer retry reuses requestId after an uncertain API failure',async()=>{
  const h=harness();h.failNext();await h.submit();await h.submit();assert.equal(h.requests[0].requestId,h.requests[1].requestId);
});
await check('vehicle permission revoked during route hashing prevents a generation request',async()=>{
  let release;const pending=new Promise(resolve=>{release=resolve;});const h=harness({digest:()=>pending});
  const submit=h.submit();h.box.state.nativeAllowed=false;release(new Uint8Array(32).buffer);await submit;
  assert.equal(h.requests.length,0);assert.equal(h.box.state.busy,false);
});
await check('staticOnly and LOCAL_LAYERS each bypass formation, idle RAF and replay',async()=>{
  for(const [origin,staticOnly] of [['LOCAL_LAYERS',false],['LOCAL_RENDER',true]]){
    const h=harness(),value=artifact({route});value.mediaOrigin=origin;value.design.staticOnly=staticOnly;
    h.box.window.NuntiFormation={prepare(){throw new Error('Static artwork must not enter formation');}};
    await h.show(value);assert.equal(h.$('replay-button').hidden,true);assert.equal(h.$('replay-button').onclick,null);
    assert.equal(h.$('birth-progress').hidden,true);assert.equal(h.box.state.animation,0);assert.equal(h.draws.length,1);
    assert.deepEqual(h.stats(),{rafCount:0,waitingCount:0,legacyCount:0});
    assert.equal(h.$('birth-canvas')['aria-label'],'차분한 눈티');
    h.box.drawStaticArtifact();assert.equal(h.draws.length,2);assert.equal(h.stats().rafCount,0);
  }
});
await check('normal artifact retains the existing animation entry and route receipt',async()=>{
  const h=harness(),value=artifact({route});value.mediaOrigin='LOCAL_RENDER';value.design.staticOnly=false;await h.show(value);
  assert.equal(h.$('replay-button').hidden,false);assert.equal(h.stats().legacyCount,1);assert.equal(h.$('receipt-canvas').hidden,false);assert.equal(h.arcs.length,2);
});
await check('static drawing respects visibility and native vehicle permission',async()=>{
  const h=harness({allowed:false});await h.show(artifact());assert.equal(h.draws.length,0);
  h.box.state.nativeAllowed=true;h.box.document.hidden=true;h.box.drawStaticArtifact();assert.equal(h.draws.length,0);
  h.box.document.hidden=false;h.box.drawStaticArtifact();assert.equal(h.draws.length,1);
});
console.log(JSON.stringify({source:'prototypes/avatar_generator/studio.js',boundary:'Node VM executing production handlers; no HTTP, browser layout, GPU or Android runtime',checks:results.length,passed:results.filter(r=>r.status==='PASS').length,results},null,2));
if(results.some(r=>r.status==='FAIL'))process.exitCode=1;
