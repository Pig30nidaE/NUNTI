#!/usr/bin/env node
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import {spawn} from 'node:child_process';
import {root,packageName,adb,pause,save,capture,connectWebView,vehicleSession,consoleRequest,readJourney} from './nunti_integration_runtime_lib.mjs';

const out=path.resolve(process.argv[2]||'artifacts/nunti-context-v4/live-'+Date.now());
const report={status:'RUNNING',checks:[]};let vehicle,web,gpsDone,owned;
async function waitFor(fn){for(let i=0;i<60;i++){const s=await readJourney();if(fn(s))return s;await pause(500)}throw Error('Live snapshot condition timed out')}
const check=(name,details)=>{report.checks.push({name,details});console.log('PASS',name)};
try{
 vehicle=await vehicleSession(out);await vehicle.parked();
 await adb(['shell','pm','grant','--user','10',packageName,'pleos.car.permission.FUSED_LOCATION']);
 await adb(['shell','am','start','-W','--user','10','-n',packageName+'/ai.nunti.app.MainActivity']);
 const top=await adb(['shell','dumpsys','activity','activities']);
 if(/topResumedActivity=ActivityRecord\{[^\n]*ai\.nunti\.app\.journey\.JourneyActivity/.test(top)) {
  assert.notEqual((await readJourney()).state,'ACTIVE');
  await adb(['shell','input','tap','2270','1220']);await pause(800);
 }
 web=await connectWebView();await web.wait('state.nativeAllowed');
 const artifact=JSON.parse(await fs.readFile(path.join(root,'artifacts/nunti-context-v4/wardrobe/formal.json'),'utf8'));
 await web.evaluate(`window.nuntiTest.showArtifact(${JSON.stringify(artifact)},false)`);
 await web.click('#journey-options-open');await web.evaluate('document.querySelector("#journey-source").value="LIVE"');await web.click('#journey-options-dialog button[data-close-dialog]');
 const child=spawn(path.join(root,'.local/voice-runtime/venv/bin/python'),[path.join(root,'scripts/replay_nunti_journey_gps.py'),path.join(root,'.local/navigation-integration/live/seoul-plan.json'),path.join(out,'gps')],{cwd:root});
 let log='';child.stdout.on('data',x=>log+=x);child.stderr.on('data',x=>log+=x);
 gpsDone=new Promise((resolve,reject)=>{child.on('error',reject);child.on('exit',async code=>{await save(out,'gps.log',log);code===0?resolve():reject(Error('GPS replay exited '+code))})});
 await pause(2500);await web.click('#journey-button');owned=await waitFor(x=>x.state==='ACTIVE'&&x.source==='LIVE');
 await capture(out,'01-live-parked',{xml:false});
 await pause(1500);await vehicle.drive(10);await pause(1300);
 await consoleRequest('/vehicle/controls',{speed:20,accelerator:15,brake:0,steering:0});await pause(1300);
 await consoleRequest('/vehicle/controls',{speed:30,accelerator:15,brake:0,steering:0});
 const driving=await waitFor(x=>!x.canFinish&&x.gear==='D'&&x.speedKmh>=29&&x.speedKmh<=31);
 check('official-console-speed-and-drive-restrictions',{speed:driving.speedKmh,canFinish:driving.canFinish});
 await capture(out,'02-live-driving',{xml:false});
 await consoleRequest('/vehicle/controls',{speed:55,accelerator:60,brake:0,steering:0});await pause(3000);
 await consoleRequest('/vehicle/controls',{speed:55,accelerator:0,brake:0,steering:160});await pause(3000);
 await consoleRequest('/vehicle/controls',{speed:20,accelerator:0,brake:85,steering:160});await pause(3500);
 const observed=await readJourney();await save(out,'live-observed.json',observed);
 assert.equal(Math.abs(observed.steeringAngleDeg),160);
 check('official-steering-signal-received',{steeringAngleDeg:observed.steeringAngleDeg,consoleAngleDeg:160,note:'The SDK and console use opposite direction signs.'});
 await vehicle.parked();await waitFor(x=>x.canFinish);await pause(600);
 await adb(['shell','input','tap','2270','1220']);const finished=await waitFor(x=>x.sessionId===owned.sessionId&&x.state==='FINISHED');
 await save(out,'journey-finished.json',finished);await capture(out,'03-live-report',{xml:false});
 assert(finished.events.some(e=>e.label==='급가속'));
 assert(finished.events.some(e=>/급제동|급감속/.test(e.label)));
 assert(finished.events.some(e=>e.label==='급회전'));
 check('vehicle-signal-events-reach-report',finished.events.map(e=>({label:e.label,position:e.position})));
 const positions=finished.track.map(x=>x.position);assert(positions.every(p=>p.space==='WGS84'));
 const distinct=new Set(positions.map(p=>p.latitude.toFixed(6)+','+p.longitude.toFixed(6)));
 assert(distinct.size>=3,'Official location callbacks must contain changing GPS coordinates');
 assert(finished.events.some(e=>e.position?.space==='WGS84'));
 check('official-fused-location-event-route',{points:positions.length,distinct:distinct.size,locationStatus:finished.locationStatus});
 await gpsDone;gpsDone=null;
 report.status='PASS';
}catch(error){report.status='FAIL';report.error=String(error.stack||error);console.error(report.error)}
finally{
 web?.close();if(gpsDone)await gpsDone.catch(e=>report.gpsError=String(e));
 if(vehicle){await vehicle.parked();if(owned){const current=await readJourney();if(current.sessionId===owned.sessionId&&current.state==='ACTIVE'){await pause(600);await adb(['shell','input','tap','2270','1220']);await pause(600)}}await vehicle.restore().catch(e=>report.restoreError=String(e))}
 await save(out,'verification.json',report);
}
console.log(JSON.stringify({status:report.status,out,checks:report.checks.length}));if(report.status!=='PASS')process.exitCode=1;
