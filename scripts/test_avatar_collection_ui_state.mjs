#!/usr/bin/env node
/**
 * Production collection/screen/lifecycle functions with controlled HTTP promises.
 * DOM nodes, image display, and animation scheduling are stubs. No UI/GPU is used.
 * The production ownership checks are read from studio.js, never reimplemented.
 */
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import {fileURLToPath} from 'node:url';

const root=path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const source=fs.readFileSync(path.join(root,'prototypes/avatar_generator/studio.js'),'utf8');
const skinDeclarations=source.slice(source.indexOf('const skins='),source.indexOf('window.NuntiBirth ='));
function block(from,to){const a=source.indexOf(from),b=source.indexOf(to,a);assert.ok(a>=0&&b>a,from);return source.slice(a,b);}
const production=[
  'let viewEpoch=0, collectionEpoch=0;',
  block('function screen(which)','function canvasSize('),
  block('async function loadCollection()',"$('collection-button').onclick"),
  block('function restoreVisibleResult()','async function init()'),
].join('\n');
function deferred(){let resolve,reject;const promise=new Promise((yes,no)=>{resolve=yes;reject=no;});return {promise,resolve,reject};}
function avatar(id){return {characterId:id,displayName:id,destination:{name:'서울역'},visual:{path:'/v3/assets/'+id}};}
function node(){return {dataset:{},children:[],hidden:false,textContent:'',classList:{toggle:()=>{}},append(...children){this.children.push(...children);},replaceChildren(){this.children=[];}};}
function harness(){
  const nodes=new Map(),requests=[],events=new Map(),shown=[],notices=[];
  const $=id=>{if(!nodes.has(id))nodes.set(id,node());return nodes.get(id);};
  const box={
    state:{busy:false,avatars:[],artifact:null,nativeAllowed:true,animation:0},
    $,document:{hidden:false,createElement:node,querySelectorAll:()=>[],addEventListener:(name,fn)=>events.set(name,fn)},
    window:{addEventListener:()=>{}},
    api:url=>{const pending=deferred();requests.push({url,...pending});return pending.promise;},
    message:text=>notices.push(text),errorText:e=>e.message,
    stopVoice:()=>{},requestAnimationFrame:()=>0,cancelAnimationFrame:()=>{},drawRoute:()=>{},enableCreate:()=>{},
    showArtifact:async artifact=>{vm.runInContext("screen('result')",box);box.state.artifact=artifact;shown.push(artifact.characterId);},
  };
  vm.createContext(box);vm.runInContext(skinDeclarations+production,box,{filename:'studio.js:production-collection-block'});
  return {box,nodes,requests,events,shown,notices,
    show:()=>vm.runInContext('showCollection()',box),
    screen:name=>vm.runInContext(`screen(${JSON.stringify(name)})`,box),
    buttons:()=>$('collection').children,
  };
}
async function populated(){const h=harness(),show=h.show();h.requests[0].resolve([avatar('A'),avatar('B')]);await show;return h;}
const results=[];
async function check(name,run){try{await run();results.push({name,status:'PASS'});}catch(error){results.push({name,status:'FAIL',error:error.message});}}

await check('latest selection B survives late response for older selection A',async()=>{
  const h=await populated(),[a,b]=h.buttons(),first=a.onclick(),second=b.onclick();
  h.requests[2].resolve(avatar('B'));await second;
  h.requests[1].resolve(avatar('A'));await first;
  assert.deepEqual(h.shown,['B']);assert.equal(h.box.state.artifact.characterId,'B');
});
await check('older selection cannot display while the latest selection is still loading',async()=>{
  const h=await populated(),[a,b]=h.buttons(),first=a.onclick(),second=b.onclick();
  h.requests[1].resolve(avatar('A'));await first;assert.deepEqual(h.shown,[]);
  h.requests[2].resolve(avatar('B'));await second;assert.deepEqual(h.shown,['B']);
});
await check('leaving collection cancels a pending selected avatar display',async()=>{
  const h=await populated(),pending=h.buttons()[0].onclick();h.screen('input');
  h.requests[1].resolve(avatar('A'));await pending;
  assert.deepEqual(h.shown,[]);assert.equal(h.nodes.get('input-view').hidden,false);
});
await check('new collection request survives an older list response arriving last',async()=>{
  const h=harness(),old=h.show(),latest=h.show();
  h.requests[1].resolve([avatar('NEW')]);await latest;
  h.requests[0].resolve([avatar('OLD')]);await old;
  assert.equal(h.box.state.avatars[0].characterId,'NEW');
  assert.equal(h.buttons()[0].children[1].textContent,'NEW');
});
await check('leaving collection before list response does not build an obsolete list',async()=>{
  const h=harness(),pending=h.show();h.screen('input');h.requests[0].resolve([avatar('A')]);await pending;
  assert.equal(h.buttons().length,0);assert.equal(h.nodes.get('input-view').hidden,false);
});
await check('vehicle revocation invalidates a selected avatar even if permission later returns',async()=>{
  const h=await populated(),pending=h.buttons()[0].onclick();
  h.box.window.nuntiVehicleAllowed(false);h.box.window.nuntiVehicleAllowed(true);
  h.requests[1].resolve(avatar('A'));await pending;
  assert.deepEqual(h.shown,[]);
});
await check('background invalidates a selected avatar even after foreground returns',async()=>{
  const h=await populated(),pending=h.buttons()[0].onclick();
  h.box.document.hidden=true;h.events.get('visibilitychange')();
  h.box.document.hidden=false;h.events.get('visibilitychange')();
  h.requests[1].resolve(avatar('A'));await pending;
  assert.deepEqual(h.shown,[]);
});
await check('an obsolete selection failure cannot overwrite the current notice',async()=>{
  const h=await populated(),[a,b]=h.buttons(),old=a.onclick(),latest=b.onclick();
  h.requests[2].resolve(avatar('B'));await latest;
  h.requests[1].reject(new Error('OLD_FAILURE'));await old;
  assert.equal(h.notices.includes('OLD_FAILURE'),false);
});

console.log(JSON.stringify({source:'prototypes/avatar_generator/studio.js',
  boundary:'Node VM with controlled DOM and HTTP, no real browser navigation or model inference',
  checks:results.length,passed:results.filter(r=>r.status==='PASS').length,results},null,2));
if(results.some(r=>r.status==='FAIL'))process.exitCode=1;
