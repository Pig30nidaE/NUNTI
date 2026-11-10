#!/usr/bin/env node
// Execute the real submit handler with a controlled failed generation boundary.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
const source=fs.readFileSync(new URL('../prototypes/avatar_generator/studio.js',import.meta.url),'utf8');
const skinDeclarations=source.slice(source.indexOf('const skins='),source.indexOf('window.NuntiBirth ='));
const handler=source.slice(source.indexOf("$('journey-form').onsubmit="),source.indexOf('function waitingAnimation'));
assert(handler.includes('rejectedLocalPicture'));
const results=[];
for(const [mode,error,newRequest] of [
  ['LOCAL_MODEL','LOCAL_MODEL_BACKGROUND_NOT_FLAT',true],
  ['LOCAL_MODEL','LOCAL_MODEL_MULTIPLE_LARGE_OBJECTS',true],
  ['LOCAL_MODEL','LOCAL_MODEL_BUSY',false],
  ['LOCAL_MODEL','LOCAL_MODEL_TIMEOUT',false],
  ['LOCAL_MODEL','Failed to fetch',false],
  ['IMAGE_API','LOCAL_MODEL_BACKGROUND_NOT_FLAT',false],
  ['IMAGE_API','RESULT_UNKNOWN',false],
]){
  const nodes=new Map(),requests=[],notices=[];let sequence=0;
  const $=id=>{if(!nodes.has(id))nodes.set(id,{value:'',checked:true,hidden:false});return nodes.get(id);};
  $('render-mode').value=mode;$('destination').value='서울역';$('purpose').value='출장';
  const box={$,viewEpoch:0,document:{hidden:false},state:{nativeAllowed:true,imageReady:true,route:{points:[[0,0],[1,1]],inputOrigin:'TEST_ROUTE',sourceLabel:'test'},animation:0},window:{},crypto:{randomUUID:()=>String(++sequence)},enableCreate:()=>{},message:t=>notices.push(t),screen:()=>{},waitingAnimation:()=>{},cancelAnimationFrame:()=>{},errorText:e=>e.message,showArtifact:async()=>{},loadCollection:async()=>{},api:async(url,body)=>{requests.push(body);if(requests.length===1)throw new Error(error);return {characterId:'saved'};}};
  vm.createContext(box);vm.runInContext(skinDeclarations+handler,box);
  await $('journey-form').onsubmit({preventDefault(){}});
  assert.equal(requests.length,1,'No automatic retry');assert.equal(box.state.busy,false);
  await $('journey-form').onsubmit({preventDefault(){}});
  assert.equal(requests[0].requestId!==requests[1].requestId,newRequest,mode+' '+error);
  assert.equal(box.state.artifact.characterId,'saved');
  results.push({mode,error,newRequestOnExplicitClick:newRequest,status:'PASS'});
}
console.log(JSON.stringify({status:'PASS',boundary:'production submit handler in Node VM; no inference or HTTP',checks:results.length,results},null,2));
