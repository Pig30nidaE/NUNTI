#!/usr/bin/env node
// Record all three actual native transformations, preserving original records.
import assert from 'node:assert/strict';
import path from 'node:path';
import fs from 'node:fs/promises';
import {spawn} from 'node:child_process';
import {root,serial,packageName,adb,pause,save,capture,connectWebView} from './nunti_integration_runtime_lib.mjs';
const out=path.resolve(process.argv[2]||'artifacts/nunti-atelier-v3/motion-final');
await fs.mkdir(out,{recursive:true});
const videos=[];
await adb(['shell','am','start','-W','--user','10','-n',packageName+'/ai.nunti.app.MainActivity']);
const web=await connectWebView();await web.wait('state.nativeAllowed && window.NuntiSkinMotion');
const records=await web.evaluate('localStorage.getItem("nunti.skin-v2.records")');
try{
 for(const skin of ['sea','city','mountain']){
  if(await web.evaluate('!document.querySelector("#result-view").hidden'))await web.click('#new-button');
  await web.evaluate(`(()=>{const e=document.querySelector('#skin-demo');e.value=${JSON.stringify(skin)};e.dispatchEvent(new Event('change',{bubbles:true}));})()`);
  const device='/sdcard/nunti-atelier-'+skin+'.mp4';
  const child=spawn(path.join(root,'.local/pm-tools/sdk/platform-tools/adb'),['-s',serial,'shell','screenrecord','--time-limit','8','--bit-rate','8000000',device],{stdio:'ignore'});
  const done=new Promise((resolve,reject)=>{child.on('error',reject);child.on('exit',code=>code===0?resolve():reject(Error('recording failed')))});done.catch(()=>{});
  await pause(650);await web.click('#create-button');
  const motion=await web.wait('window.NuntiSkinMotion.diagnostics().running && window.NuntiSkinMotion.diagnostics()');
  assert.equal(motion.renderer,'NATIVE_CANVAS');
  await web.wait('!window.NuntiSkinMotion.diagnostics().running && window.NuntiSkinMotion.diagnostics().phase==="FINAL_IDLE"');
  await done;await adb(['pull',device,path.join(out,skin+'.mp4')]);await adb(['shell','rm','-f',device]);
  await capture(out,skin+'-result',{xml:false});
  const final=await web.evaluate('({motion:window.NuntiSkinMotion.diagnostics(),artifact:window.nuntiTest.getArtifact()})');
  videos.push({skin,file:skin+'.mp4',final});await save(out,skin+'-state.json',final);
 }
 const task=(await adb(['shell','dumpsys','activity','activities'])).match(/topResumedActivity=ActivityRecord\{[^\n]*ai\.nunti\.avatar\.demo\/[^\n]* t(\d+)\}/)?.[1];
 assert(task);await adb(['shell','am','task','resize',task,'853','90','1683','1300']);await pause(500);
 assert.equal(await web.evaluate('document.querySelector("#heading").textContent'),'이번 여행의 눈티');
 await adb(['shell','am','task','resize',task,'853','90','2535','1300']);await pause(500);
 await save(out,'report.json',{status:'PASS',videos,headingStableAfterWindowResize:true});
}finally{
 await web.evaluate(`(()=>{const v=${JSON.stringify(records)};if(v===null)localStorage.removeItem('nunti.skin-v2.records');else localStorage.setItem('nunti.skin-v2.records',v)})()`);web.close();
}
console.log('Recorded and verified sea, city and mountain native transformations');
