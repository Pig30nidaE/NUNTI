#!/usr/bin/env node
// Exercises the shipped WebView/native app. Reuses an already generated brief, never requests a new look.
import assert from 'node:assert/strict';
import path from 'node:path';
import {root,packageName,adb,pause,save,capture,connectWebView,vehicleSession,readJourney} from './nunti_integration_runtime_lib.mjs';

const out=path.resolve(process.argv[2]||'artifacts/nunti-context-v4/runtime-'+Date.now());
let web,vehicle,task,night;
const report={status:'RUNNING',checks:[]};
const check=(name,details)=>{report.checks.push({name,details});console.log('PASS',name)};
async function resize(narrow){
 const activities=await adb(['shell','dumpsys','activity','activities']);
 task=activities.match(/topResumedActivity=ActivityRecord\{[^\n]*ai\.nunti\.avatar\.demo\/[^\n]* t(\d+)\}/)?.[1];assert(task);
 await adb(['shell','am','task','resize',task,'853','90',narrow?'1683':'2535','1300']);await pause(800);
}
async function waitJourney(fn){for(let i=0;i<120;i++){const s=await readJourney();if(fn(s))return s;await pause(500)}throw Error('Journey timeout')}
async function shot(name){await capture(out,name,{xml:false})}
try {
 vehicle=await vehicleSession(out);night=vehicle.originalNight.match(/Night mode:\s*(\w+)/i)?.[1];
 await vehicle.parked();await adb(['shell','cmd','uimode','night','no']);
 await adb(['shell','am','start','-W','--user','10','-n',packageName+'/ai.nunti.app.MainActivity']);
 web=await connectWebView();await web.wait('state.nativeAllowed&&window.nuntiCapabilities?.wardrobeAvailable');await resize(false);
 if(await web.evaluate('!document.querySelector("#result-view").hidden'))await web.click('#new-button');
 assert.equal(await web.evaluate('state.route'),null,'Use the empty pretrip form so the known cached brief is identical');
 const budgetBefore=await web.evaluate('api("/v3/wardrobe/budget")');
 await web.evaluate(`(()=>{for(const [id,value] of Object.entries({destination:'회사',traits:'차분하고 단정한 분위기',purpose:'면접','layer-mood':'calm','layer-destination':'city','layer-road':'urban'})){const e=document.getElementById(id);e.value=value;e.dispatchEvent(new Event('input',{bubbles:true}));e.dispatchEvent(new Event('change',{bubbles:true}))}document.querySelector('#wardrobe-enabled').checked=true;enableCreate();})()`);
 await web.click('#create-button');
 const artifact=await web.wait('!state.busy&&state.artifact?.mediaOrigin==="OPENAI_WARDROBE"&&state.artifact');
 assert.equal(artifact.design.wardrobe.look,'formal');
 await web.wait('document.querySelector("#result-portrait").hasAttribute("data-nunti-companion-ready")');
 const budgetAfter=await web.evaluate('api("/v3/wardrobe/budget")');assert.equal(budgetBefore.reservedUsd,budgetAfter.reservedUsd);
 check('cached-outfit-created-through-real-form-with-no-extra-spend',budgetAfter);
 await shot('01-formal-companion');
 await adb(['shell','dumpsys','gfxinfo',packageName,'reset']);
 const recording=adb(['shell','screenrecord','--time-limit','12','--bit-rate','4000000','/sdcard/nunti-context-face.mp4']);
 await pause(5200);await web.click('#result-portrait');await pause(2400);await web.click('#result-portrait');
 await recording;await save(out,'02-face-touch.mp4',await adb(['exec-out','cat','/sdcard/nunti-context-face.mp4'],true));
 await save(out,'face-gfxinfo.txt',await adb(['shell','dumpsys','gfxinfo',packageName]));
 await save(out,'memory.txt',await adb(['shell','dumpsys','meminfo',packageName]));
 check('generated-native-companion-and-touch-playback');
 await resize(true);await web.wait('innerWidth<900');
 assert(await web.evaluate('document.documentElement.scrollWidth<=innerWidth+1'));
 await shot('03-result-compact');await resize(false);
 await web.click('#journey-options-open');await web.evaluate('document.querySelector("#journey-source").value="DEMO"');await web.click('#journey-options-dialog button[data-close-dialog]');
 await web.click('#journey-button');
 const active=await waitJourney(x=>x.state==='ACTIVE'&&x.source==='DEMO'&&x.characterId===artifact.characterId);
 check('real-app-started-context-driving-simulation',{sessionId:active.sessionId,faceRig:active.faceRig});
 await shot('04-journey-simulation');
 const completed=await waitJourney(x=>x.sessionId===active.sessionId&&x.sampleCount===151);
 assert(completed.events.some(e=>e.label==='급회전'));
 assert(completed.events.every(e=>e.position?.space==='SIMULATION'));
 await adb(['shell','input','tap','2270','1220']);
 const finished=await waitJourney(x=>x.sessionId===active.sessionId&&x.state==='FINISHED');
 assert(finished.habits.some(h=>h.positive)&&finished.habits.some(h=>!h.positive));
 await save(out,'journey-finished.json',finished);
 check('route-events-score-reasons-and-habit-feedback',{score:finished.total,events:finished.events.map(e=>({label:e.label,t:e.tMs})),track:finished.track.length,habits:finished.habits.length});
 await shot('05-report-wide');await resize(true);await shot('06-report-compact');
 await adb(['shell','cmd','uimode','night','yes']);await pause(600);await shot('07-report-compact-night');
 await resize(false);await shot('08-report-wide-night');
 report.status='PASS';
} catch(error){report.status='FAIL';report.error=String(error.stack||error);console.error(report.error)}
finally {
 web?.close();
 if(night)await adb(['shell','cmd','uimode','night',night]);
 if(task)await adb(['shell','am','task','resize',task,'853','90','2535','1300']);
 if(vehicle)await vehicle.restore().catch(e=>{report.status='FAIL';report.restoreError=String(e)});
 await save(out,'verification.json',report);
}
console.log(JSON.stringify({status:report.status,out,checks:report.checks.length}));if(report.status!=='PASS')process.exitCode=1;
