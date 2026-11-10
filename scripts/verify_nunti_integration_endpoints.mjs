#!/usr/bin/env node
// Reuse the nine saved local results and verify final pixels on the final APK.
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import {root, packageName, adb, save, connectWebView, vehicleSession} from './nunti_integration_runtime_lib.mjs';
const arg = name => process.argv.find(value => value.startsWith('--' + name + '='))?.slice(name.length + 3);
assert(arg('artifacts'));const artifacts = JSON.parse(await fs.readFile(arg('artifacts'), 'utf8'));assert.equal(artifacts.length, 9);
const out = path.resolve(arg('output') || path.join(root, 'docs/redesign/integration-v1/runtime-endpoints-' + Date.now()));
const report = {status: 'RUNNING', surface: 'ACTUAL_FINAL_PRODUCTION_WEBVIEW', generationCalls: 0, checks: []};
let web, vehicle;
try {
  vehicle = await vehicleSession(out);
  await adb(['shell', 'am', 'start', '-W', '--user', '10', '-n', packageName + '/ai.nunti.app.MainActivity']);
  web = await connectWebView();await web.wait('window.NuntiBirth && state.nativeAllowed');
  for (const {slug, artifact} of artifacts) {
    await web.evaluate(`window.nuntiTest.showArtifact(${JSON.stringify(artifact)},true)`);
    await web.wait('window.NuntiBirth.diagnostics().finalReady && window.NuntiBirth.diagnostics().layerReady && window.NuntiBirth.diagnostics().status==="RUNNING"');
    const final = await web.evaluate('window.NuntiBirth.capture(4000)');assert.ok(final?.startsWith('data:image/png;base64,'));
    const reference = await web.evaluate(`(async()=>{const i=new Image();i.src=${JSON.stringify(artifact.visual.path)};await i.decode();const c=document.createElement('canvas');c.width=c.height=768;c.getContext('2d').drawImage(i,0,0,768,768);return c.toDataURL('image/png')})()`);
    assert.equal(final, reference, slug);await save(out, slug + '-final.png', Buffer.from(final.split(',')[1], 'base64'));
    await save(out, slug + '-browser-reference.png', Buffer.from(reference.split(',')[1], 'base64'));
    report.checks.push({name: slug, status: 'PASS', browserDecodedPixelsExact: true, serverImageSha256: artifact.visual.sha256});console.log('PASS', slug);
  }
  await save(out, 'artifacts.json', artifacts);
  await web.evaluate(`window.nuntiTest.showArtifact(${JSON.stringify(artifacts.find(item => item.slug === 'coast-curious').artifact)},false)`);
  report.status = 'PASS';
} catch (error) {report.status = 'FAIL';report.error = String(error.stack || error);console.error(report.error);}
finally {web?.close();if(vehicle)try{await vehicle.restore();report.vehicleRestored=true;}catch(error){report.status='FAIL';report.restorationError=String(error);}await save(out,'report.json',report);}
console.log(JSON.stringify({status:report.status,checks:report.checks.length,out}));if(report.status!=='PASS')process.exitCode=1;
