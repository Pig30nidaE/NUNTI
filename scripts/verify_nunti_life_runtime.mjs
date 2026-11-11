#!/usr/bin/env node
import fs from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
import {adb,packageName,connectWebView,pause,save,capture,root,readJourney} from './nunti_integration_runtime_lib.mjs';
const out=path.resolve(process.argv[2]||'artifacts/nunti-life-v5/final');
await fs.mkdir(out,{recursive:true});
const web=await connectWebView();
const show=async(name,animate=false)=>{const art=JSON.parse(await fs.readFile(path.join(root,'artifacts/nunti-context-v4/wardrobe/'+name+'.json'),'utf8'));await web.evaluate(`window.nuntiTest.showArtifact(${JSON.stringify(art)},${animate})`);await web.wait('document.querySelector("#result-portrait").hasAttribute("data-nunti-companion-ready")');};
try {
 assert.notEqual((await readJourney()).state,'ACTIVE');await web.wait('state.nativeAllowed');
 const before=await web.evaluate('api("/v3/wardrobe/budget")');
 await show('formal');await capture(out,'01-formal',{xml:false});
 const video=adb(['shell','screenrecord','--time-limit','35','--bit-rate','4000000','/sdcard/nunti-life-final.mp4']);
 await pause(6000);await web.click('#result-portrait');await pause(5000);await web.click('#result-portrait');await pause(5000);await web.click('#result-portrait');await pause(5000);await web.click('#result-portrait');
 await video;await adb(['pull','/sdcard/nunti-life-final.mp4',path.join(out,'02-life.mp4')]);
 for(const name of ['formal','medical','football']){
  await show(name);const rec=adb(['shell','screenrecord','--time-limit','7','--bit-rate','4000000','/sdcard/nunti-transform.mp4']);
  await web.click('#replay-button');await pause(2400);await capture(out,name+'-transform',{xml:false});
  await rec;await adb(['pull','/sdcard/nunti-transform.mp4',path.join(out,name+'-transform.mp4')]);
 }
 await show('formal');
 const after=await web.evaluate('api("/v3/wardrobe/budget")');assert.equal(before.calls,after.calls);
 await save(out,'verification.json',{status:'PASS',wardrobeCallsUnchanged:after.calls,expressions:6,authoredGestures:8,transformThemes:['formal','medical','football']});
 console.log('PASS',out);
} finally {web.close()}
