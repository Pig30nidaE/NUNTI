#!/usr/bin/env node
// Exercise the installed app; restore vehicle state and window bounds even on failure.
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import {root,adb,packageName,connectWebView,vehicleSession,pause,save,capture} from './nunti_integration_runtime_lib.mjs';
const out=path.resolve(process.argv[2]||'artifacts/nunti-life-v5/gates-'+Date.now());
let web,vehicle,task,wasReduced;
const checks=[];
try {
 vehicle=await vehicleSession(out);await vehicle.parked();web=await connectWebView();await web.wait('state.nativeAllowed');
 const artifact=JSON.parse(await fs.readFile(path.join(root,'artifacts/nunti-context-v4/wardrobe/formal.json'),'utf8'));
 await web.evaluate(`window.nuntiTest.showArtifact(${JSON.stringify(artifact)},false)`);
 wasReduced=await web.evaluate('document.querySelector("#reduced-motion").checked');
 if(wasReduced)await web.click('label[for="reduced-motion"]');
 await web.wait('document.querySelector("#result-portrait").hasAttribute("data-nunti-companion-ready")');
 await web.click('label[for="reduced-motion"]');
 await web.wait('!document.querySelector("#result-portrait").hasAttribute("data-nunti-companion-ready")&&window.NuntiSkinMotion.diagnostics().reducedMotion');
 await capture(out,'01-reduced',{xml:false});checks.push('reduced-motion-stops-native-companion');
 await web.click('label[for="reduced-motion"]');
 await web.wait('document.querySelector("#result-portrait").hasAttribute("data-nunti-companion-ready")');
 const activities=await adb(['shell','dumpsys','activity','activities']);
 task=activities.match(/topResumedActivity=ActivityRecord\{[^\n]*ai\.nunti\.avatar\.demo\/[^\n]* t(\d+)\}/)?.[1];assert(task);
 await adb(['shell','am','task','resize',task,'853','90','1683','1300']);
 await web.wait('innerWidth<900');
 assert(await web.evaluate('document.documentElement.scrollWidth<=innerWidth+1'));
 await capture(out,'02-compact',{xml:false});checks.push('830px-window-without-horizontal-overflow');
 await adb(['shell','am','task','resize',task,'853','90','2535','1300']);
 await web.wait('innerWidth>1400');
 await web.click('#replay-button');await vehicle.drive(30);
 const restricted=await web.wait('!state.nativeAllowed&&!window.NuntiSkinMotion.diagnostics().running&&window.NuntiSkinMotion.diagnostics()');
 assert(await web.evaluate('!document.querySelector("#result-portrait").hasAttribute("data-nunti-companion-ready")'));
 await save(out,'restricted.json',restricted);await capture(out,'03-driving',{xml:false});checks.push('D-30kph-stops-transformation-and-companion');
 await vehicle.parked();await web.wait('state.nativeAllowed');
 assert(!(await web.evaluate('window.NuntiSkinMotion.diagnostics().running')));checks.push('P-return-does-not-replay-transformation');
 await web.wait('document.querySelector("#result-portrait").hasAttribute("data-nunti-companion-ready")');
 await adb(['shell','dumpsys','gfxinfo',packageName,'reset']);await pause(8000);
 await save(out,'gfxinfo.txt',await adb(['shell','dumpsys','gfxinfo',packageName]));
 await save(out,'memory.txt',await adb(['shell','dumpsys','meminfo',packageName]));
 await save(out,'cpu.txt',await adb(['shell','dumpsys','cpuinfo']));
 await capture(out,'04-restored',{xml:false});
 await save(out,'verification.json',{status:'PASS',checks});console.log('PASS',checks);
} finally {
 if(task)await adb(['shell','am','task','resize',task,'853','90','2535','1300']);
 if(web&&wasReduced!==undefined){const now=await web.evaluate('document.querySelector("#reduced-motion").checked');if(now!==wasReduced)await web.click('label[for="reduced-motion"]');}
 web?.close();if(vehicle)await vehicle.restore();
}
