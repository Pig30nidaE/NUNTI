import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {test} from 'node:test';
import {runInNewContext} from 'node:vm';

const source=readFileSync(new URL('../prototypes/avatar_generator/nunti-companion.js',import.meta.url),'utf8');
function harness(){
  const calls=[], observers=[], unavailable=[];
  let clock=0,allowed=true;
  const element=id=>({id,hidden:false,disabled:true,dataset:{},listeners:new Map(),
    setAttribute(){},getBoundingClientRect:()=>({left:0,top:0,width:640,height:640}),
    addEventListener(name,fn){this.listeners.set(name,fn);},
    emit(name,event={}){this.listeners.get(name)?.(event);}});
  const preview=element('preview'),result=element('result'),inputView=element('input'),resultView=element('result-view');
  resultView.hidden=true;
  const env={window:{devicePixelRatio:1,addEventListener(){},NuntiNative:{
    startCharacterCompanion:(...args)=>calls.push(['start',...args]),
    stopCharacterCompanion:id=>calls.push(['stop',id]),
    reactCharacterCompanion:(...args)=>calls.push(['react',...args]),
    focusCharacterCompanion:(...args)=>calls.push(['focus',...args]),
  }},document:{hidden:false,body:{dataset:{}},querySelector:()=>null,querySelectorAll:()=>[],getElementById:()=>null,addEventListener(){}},
  IntersectionObserver:class{constructor(fn){observers.push(fn);}observe(){}},
  ResizeObserver:class{observe(){}},MutationObserver:class{observe(){}},
  matchMedia:()=>({addEventListener(){}}),performance:{now:()=>clock},setTimeout:()=>1,clearTimeout(){},queueMicrotask};
  runInNewContext(source,env);
  const player=env.window.NuntiCompanion.create({preview,result,inputView,resultView,allowed:()=>allowed,onUnavailable:skin=>unavailable.push(skin)});
  observers[0]([{target:preview,isIntersecting:true,intersectionRatio:1},{target:result,isIntersecting:true,intersectionRatio:1}]);
  const ready=()=>env.window.nuntiCharacterCompanionReady(calls.findLast(c=>c[0]==='start')[1],true);
  ready();
  return {calls,preview,result,player,env,ready,unavailable,advance(ms=500){clock+=ms;},
    restrict(){allowed=false;player.sync();},
    showSkin(skin){inputView.hidden=true;resultView.hidden=false;player.setResult(skin);ready();}};
}

test('head, hands, and keyboard invoke meaningful gestures rather than a rotating list',()=>{
  const h=harness();
  h.preview.emit('click',{clientX:320,clientY:180,detail:1});
  assert.equal(h.calls.at(-1)[2],'pat');
  h.advance();h.preview.emit('click',{clientX:160,clientY:350,detail:1});
  assert.equal(h.calls.at(-1)[2],'wave-left');
  h.advance();h.preview.emit('click',{detail:0});
  assert.equal(h.calls.at(-1)[2],'wave-right');
});

test('new shared-rig skins receive the same touch vocabulary as the base',()=>{
  const h=harness();h.showSkin('wardrobe-shared1-'+'a'.repeat(64)+'-'+'b'.repeat(64));
  h.result.emit('click',{clientX:320,clientY:180,detail:1});
  assert.equal(h.calls.at(-1)[2],'pat');
});

test('a pointer outside the character artboard is not mistaken for a keyboard greeting',()=>{
  const h=harness(),count=h.calls.length;
  h.preview.emit('click',{clientX:-20,clientY:100,detail:1});
  assert.equal(h.calls.length,count);
});

test('attention is bounded and rate limited; leaving resets gaze',()=>{
  const h=harness();
  h.preview.emit('pointermove',{clientX:640,clientY:0});
  assert.deepEqual(h.calls.at(-1).slice(2),[1,-.8]);
  const count=h.calls.length;
  h.preview.emit('pointermove',{clientX:0,clientY:640});
  assert.equal(h.calls.length,count);
  h.preview.emit('pointerleave');
  assert.deepEqual(h.calls.at(-1).slice(2),[0,0]);
});

test('restriction stops the native actor and rejects late acknowledgements and touch',()=>{
  const h=harness(), id=h.calls[0][1];
  h.restrict();const count=h.calls.length;
  assert.equal(h.calls.at(-1)[0],'stop');
  h.env.window.nuntiCharacterCompanionReady(id,true);
  h.preview.emit('click',{clientX:320,clientY:180,detail:1});
  h.preview.emit('pointermove',{clientX:320,clientY:180});
  assert.equal(h.calls.length,count);
  assert.equal(h.preview.disabled,true);
});

test('asset preparation failure restores the still and reports unavailability instead of hiding the error',()=>{
  const h=harness(),id=h.calls[0][1];
  h.env.window.nuntiCharacterCompanionReady(id,false);
  assert.equal(h.preview.disabled,true);
  assert.equal('nuntiCompanionReady' in h.preview.dataset,false);
  assert.deepEqual(h.unavailable,['default']);
  const count=h.calls.length;h.player.sync();
  assert.equal(h.calls.length,count,'a failed asset is not fetched again in a retry loop');
});
