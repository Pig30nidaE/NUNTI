#!/usr/bin/env node
// Real Pleos window, day/night and score integration. Restores owned test state.
import assert from 'node:assert/strict';
import path from 'node:path';
import {root,packageName,adb,pause,save,capture,connectWebView,vehicleSession,consoleRequest,readJourney,writeFinishedJourney} from './nunti_integration_runtime_lib.mjs';

const out=path.resolve(process.argv[2] || 'artifacts/nunti-atelier-v3/display-'+Date.now());
const live=process.argv.includes('--live');
const report={status:'RUNNING',checks:[]};
let web,vehicle,storage,owned,task,night,heartbeat;
const client='atelier-display-'+Date.now();
const before=await consoleRequest('/vehicle/state');
const check=(name,passed,details)=>{assert(passed,name);report.checks.push({name,status:'PASS',details});console.log('PASS',name)};
const launch=()=>adb(['shell','am','start','-W','--user','10','-n',packageName+'/ai.nunti.app.MainActivity']);
async function taskId(){const s=await adb(['shell','dumpsys','activity','activities']);const id=s.match(/topResumedActivity=ActivityRecord\{[^\n]*ai\.nunti\.avatar\.demo\/[^\n]* t(\d+)\}/)?.[1];assert(id);return id}
async function resize(compact){task=await taskId();await adb(['shell','am','task','resize',task,'853','90',compact?'1683':'2535','1300']);await pause(650)}
async function waitJourney(predicate){for(let i=0;i<100;i++){const x=await readJourney();if(predicate(x))return x;await pause(150)}throw Error('Journey condition timed out')}
async function shot(name){await capture(out,name,{xml:false})}
async function showSea(){
  if(await web.evaluate('!document.querySelector("#result-view").hidden'))await web.click('#new-button');
  await web.evaluate(`(()=>{const x=document.querySelector('#skin-demo');x.value='sea';x.dispatchEvent(new Event('change',{bubbles:true}));document.querySelector('#destination').value='안목해변';document.querySelector('#purpose').value='바다 산책';})()`);
  await web.click('#create-button');
  await web.wait('window.NuntiSkinMotion.diagnostics().skinId==="sea" && window.NuntiSkinMotion.diagnostics().running');
  await web.wait('!window.NuntiSkinMotion.diagnostics().running && window.NuntiSkinMotion.diagnostics().phase==="FINAL_IDLE"');
}
async function layout(name){
  const value=await web.evaluate(`(()=>{const ids=['.topbar','.intro','.result-grid','.birth-stage','.identity-panel','.result-actions','#create-button'];return {width:innerWidth,height:innerHeight,scrollWidth:document.documentElement.scrollWidth,theme:document.documentElement.dataset.theme,nodes:Object.fromEntries(ids.map(id=>{const e=document.querySelector(id),r=e?.getBoundingClientRect();return [id,r?{x:r.x,y:r.y,width:r.width,height:r.height}:null]}))};})()`);
  await save(out,name+'-layout.json',value);check(name+'-no-horizontal-overflow',value.scrollWidth<=value.width+1,value);return value;
}
try{
  assert.notEqual((await readJourney()).state,'ACTIVE','Do not interrupt an existing active journey');
  await save(out,'console-before-connection.json',before);
  await consoleRequest('/browser/session',{client},'POST');
  heartbeat=setInterval(()=>consoleRequest('/browser/session',{client},'POST').catch(()=>{}),900);
  for(let i=0;i<60;i++){const state=await consoleRequest('/vehicle/state');if(state.gear.actual&&state.gear.bridge_ready)break;await pause(250)}
  vehicle=await vehicleSession(out);night=vehicle.originalNight.match(/Night mode:\s*(\w+)/i)?.[1];
  assert.equal(vehicle.original.gear.actual.value,'Park');await vehicle.parked();await launch();
  web=await connectWebView();await web.wait('window.NuntiSkinMotion && state.nativeAllowed');
  storage=await web.evaluate(`Object.fromEntries(['nunti.skin-v2.records','nunti.skin-v2.reduced'].map(k=>[k,localStorage.getItem(k)]))`);
  await adb(['shell','cmd','uimode','night','no']);await web.wait('document.documentElement.dataset.theme==="day"');
  await resize(false);await showSea();await layout('wide-day');await shot('01-result-wide-day');
  const artifact=await web.evaluate('window.nuntiTest.getArtifact()');await save(out,'artifact.json',artifact);
  await resize(true);await web.wait('Math.abs(innerWidth-830)<2');await layout('compact-day');await shot('02-result-compact-day');
  await web.click('#new-button');await shot('03-pretrip-compact-top');
  await web.evaluate('document.querySelector("#journey-form").scrollIntoView({block:"end"})');await shot('04-pretrip-compact-form');
  await adb(['shell','cmd','uimode','night','yes']);await web.wait('document.documentElement.dataset.theme==="night"');await shot('05-pretrip-compact-night');
  await showSea();await shot('06-result-compact-night');await resize(false);await shot('07-result-wide-night');
  await adb(['shell','cmd','uimode','night','no']);await web.wait('document.documentElement.dataset.theme==="day"');
  await web.click('#new-button');await shot('08-pretrip-wide-day');await showSea();
  await adb(['shell','dumpsys','gfxinfo',packageName,'reset']);
  await web.click('#replay-button');const motion=await web.wait('window.NuntiSkinMotion.diagnostics().running && window.NuntiSkinMotion.diagnostics()');
  check('native-materialization-renderer-used',motion.renderer==='NATIVE_CANVAS',motion);await pause(5500);
  await save(out,'performance-gfxinfo.txt',await adb(['shell','dumpsys','gfxinfo',packageName]));
  await save(out,'performance-memory.txt',await adb(['shell','dumpsys','meminfo',packageName]));
  const pid=(await adb(['shell','pidof',packageName])).trim();
  const cpu=adb(['shell','top','-b','-n','5','-d','1','-p',pid]);await web.click('#replay-button');await pause(5500);await save(out,'performance-cpu.txt',await cpu);
  await web.click('#journey-options-open');await web.evaluate(`document.querySelector("#journey-source").value=${JSON.stringify(live?'LIVE':'DEMO')}`);await web.click('#journey-options-dialog button[data-close-dialog]');
  owned={characterId:artifact.characterId};await web.click('#journey-button');
  const active=await waitJourney(x=>x.state==='ACTIVE'&&x.characterId===artifact.characterId&&x.canFinish);owned.sessionId=active.sessionId;
  await shot('09-journey-wide-parked');await resize(true);await shot('10-journey-compact-parked');
  await vehicle.drive(30);const driving=await waitJourney(x=>x.sessionId===active.sessionId&&!x.canFinish);
  check('driving-disables-finishing-journey',driving.state==='ACTIVE'&&!driving.canFinish);await shot('11-journey-compact-driving');
  if(live){
    const signal=await waitJourney(x=>x.gear==='D'&&x.speedKmh>=29&&x.speedKmh<=31);
    check('official-console-speed-reaches-live-scoring-service',signal.source==='LIVE',{gear:signal.gear,speedKmh:signal.speedKmh});
    await consoleRequest('/vehicle/controls',{speed:65,accelerator:60,brake:0,steering:0});await pause(3500);
    await consoleRequest('/vehicle/controls',{speed:8,accelerator:0,brake:85,steering:0});await pause(3500);
    await save(out,'live-after-speed-changes.json',await readJourney());
  }
  await adb(['shell','cmd','uimode','night','yes']);await shot('12-journey-compact-driving-night');
  await resize(false);await shot('13-journey-wide-driving-night');await vehicle.parked();await waitJourney(x=>x.canFinish);
  await adb(['shell','cmd','uimode','night','no']);await pause(500);
  const activities=await adb(['shell','dumpsys','activity','activities']);assert.match(activities,/topResumedActivity=.*ai\.nunti\.app\.journey\.JourneyActivity/);assert.match(activities,/mBounds=Rect\(853, 90 - 2535, 1300\)/);
  // Center observed in runtime-core-2/09-skin-journey-active.png. Accessibility dump
  // currently selects the background Studio window on this Pleos system image.
  await adb(['shell','input','tap','2270','1220']);
  const finished=await waitJourney(x=>x.sessionId===active.sessionId&&x.state==='FINISHED');
  check('teammate-score-engine-produces-stored-report',typeof finished.total==='number'&&finished.total>=0&&finished.total<=100&&finished.staticOnly===true,{total:finished.total,coverage:finished.coverage});
  await save(out,'journey-finished.json',finished);await shot('14-report-wide-day');await resize(true);await shot('15-report-compact-day');
  await adb(['shell','cmd','uimode','night','yes']);await shot('16-report-compact-night');
  await save(out,'native-motion-log.txt',await adb(['logcat','-d','-s','NuntiAtelier:I','NuntiVfx:I','NuntiCanvas:I','AndroidRuntime:E']));
  report.status='PASS';
}catch(error){report.status='FAIL';report.error=String(error.stack||error);console.error(report.error)}
finally{
  const restore=async(name,action)=>{try{await action()}catch(error){report.status='FAIL';(report.restorationErrors??=[]).push({name,error:String(error)})}};
  if(night)await restore('night',()=>adb(['shell','cmd','uimode','night',night]));
  if(task)await restore('window',()=>adb(['shell','am','task','resize',task,'853','90','2535','1300']));
  if(web&&storage)await restore('local records',()=>web.evaluate(`(()=>{for(const [k,v] of Object.entries(${JSON.stringify(storage)})){if(v===null)localStorage.removeItem(k);else localStorage.setItem(k,v)}})()`));
  web?.close();
  if(owned&&vehicle)await restore('owned journey',async()=>{
    const current=await readJourney();assert.equal(current.characterId,owned.characterId);
    await adb(['shell','am','force-stop','--user','10',packageName]);await writeFinishedJourney(vehicle.originalLatest);
    await adb(['shell','run-as',packageName,'--user','10','rm','-f',`files/journeys/${current.sessionId}-input.json`,`files/journeys/${current.sessionId}-report.json`]);
  });
  if(vehicle)await restore('vehicle',()=>vehicle.restore());
  await restore('console connection',async()=>{await consoleRequest('/vehicle/hvac',{power:before.hvac.power_on?1:0});clearInterval(heartbeat);await consoleRequest('/browser/session',{client,closing:1},'POST')});
  if(owned)await restore('return to Studio',launch);
  await save(out,'report.json',report);
}
console.log(JSON.stringify({status:report.status,checks:report.checks.length,out}));if(report.status!=='PASS')process.exitCode=1;
