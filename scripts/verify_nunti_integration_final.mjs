#!/usr/bin/env node
// Focused final-APK checks: controlled POST failure/retry and motion boundaries.
import assert from 'node:assert/strict';
import path from 'node:path';
import {root, packageName, adb, pause, save, capture, connectWebView, vehicleSession} from './nunti_integration_runtime_lib.mjs';
const output = process.argv.find(value => value.startsWith('--output='))?.slice(9);
const out = path.resolve(output || path.join(root, 'docs/redesign/integration-v1/runtime-final-' + Date.now()));
const report = {status: 'RUNNING', surface: 'ACTUAL_FINAL_PRODUCTION_WEBVIEW', checks: [],
  failureSource: 'CDP request-stage controlled HTTP 503 before backend; not a real server outage', postRequests: [], paidApiCalls: 0, modelCalls: 0, voiceGenerationCalls: 0};
let web, vehicle, intercepted = false, originalReduced = null;
const faults = [], trace = [];
const check = (name, condition, details) => {assert(condition, name);report.checks.push({name, status: 'PASS', ...(details ? {details} : {})});console.log('PASS', name);};
const fields = `JSON.stringify(Object.fromEntries(['destination','traits','purpose','render-mode','layer-destination','layer-road','layer-mood'].map(id=>[id,document.getElementById(id).value])))`;
async function screen(name) {await capture(out, name);await save(out, name + '-state.json', await web.evaluate('({allowed:state.nativeAllowed,motion:window.NuntiBirth.diagnostics(),notice:document.getElementById("notice").textContent,view:document.body.dataset.view})'));}
async function replay() {await web.click('#replay-button');await web.wait('window.NuntiBirth.diagnostics().status==="RUNNING"');}
try {
  vehicle = await vehicleSession(out);
  await adb(['shell', 'am', 'start', '-W', '--user', '10', '-n', packageName + '/ai.nunti.app.MainActivity']);
  web = await connectWebView(); await web.wait('window.NuntiBirth && state.nativeAllowed && window.nuntiCapabilities?.layeredRenderAvailable');
  web.on('Network.requestWillBeSent', event => {
    if (event.request.method === 'POST' && new URL(event.request.url).pathname === '/v3/avatars') {
      const body = JSON.parse(event.request.postData || '{}');
      report.postRequests.push({requestId: body.requestId, renderMode: body.renderMode});
    }
  });
  originalReduced = await web.evaluate('localStorage.getItem("nunti-reduced-motion")');await web.evaluate('window.NuntiBirth.setReduced(false)');
  await web.evaluate(`(()=>{window.nuntiTest.viewExample(1);const set=(id,value)=>{const e=document.getElementById(id);e.value=value;e.dispatchEvent(new Event('change',{bubbles:true}));e.dispatchEvent(new Event('input',{bubbles:true}));};
    set('render-mode','LOCAL_LAYERS');set('destination','통합 검증 · 실패 후 재시도');set('traits','제어된 503 이후 같은 요청으로 복구');set('purpose','최종 APK 검증');
    set('layer-destination','coast');set('layer-road','highway');set('layer-mood','curious');const c=document.getElementById('route-confirmed');c.checked=true;c.dispatchEvent(new Event('change'));})()`);
  await web.wait('!document.getElementById("create-button").disabled');const before = await web.evaluate(fields);
  web.on('Fetch.requestPaused', event => {
    void (async () => {
      if (event.request.method === 'POST' && !intercepted) {
        intercepted = true; const input = JSON.parse(event.request.postData);assert.equal(input.renderMode, 'LOCAL_LAYERS');
        await save(out, 'controlled-503-request.json', input); await pause(300);
        await capture(out, '01-generation-loading', {xml: false});
        await web.command('Fetch.fulfillRequest', {requestId: event.requestId, responseCode: 503,
          responseHeaders: [{name: 'Content-Type', value: 'application/json'}],
          body: Buffer.from(JSON.stringify({error: {code: 'INTEGRATION_TEST_503', message: '검증용 연결 오류'}})).toString('base64')});
      } else await web.command('Fetch.continueRequest', {requestId: event.requestId});
    })().catch(error => faults.push(String(error.stack || error)));
  });
  await web.command('Fetch.enable', {patterns: [{urlPattern: 'http://127.0.0.1:8768/v3/avatars', requestStage: 'Request'}]});
  await web.click('#create-button');
  await web.wait('!document.getElementById("input-view").hidden && document.getElementById("notice").textContent.includes("검증용 연결 오류")');
  const pendingId = await web.evaluate('state.pending?.body.requestId');
  check('controlled-generation-503-retains-id-and-fields', intercepted && !!pendingId && await web.evaluate(fields) === before);
  check('failed-generation-keeps-approved-base-visible', await web.evaluate('document.getElementById("canonical-preview").naturalWidth===768 && !document.getElementById("input-view").hidden'));
  await screen('02-generation-failure');await web.command('Fetch.disable');
  await web.click('#create-button');await web.wait('window.NuntiBirth.diagnostics().status==="RUNNING"');
  const retryId = await web.evaluate('state.pending?.body.requestId');
  // The pending receipt can already be cleared after a fast response, so retain
  // the outgoing request from the server's canonical receipt as additional proof.
  report.failedRequestId = pendingId; report.retryPendingId = retryId;
  const deadline = Date.now() + 8000;
  while (Date.now() < deadline) {
    const value = await web.evaluate('window.NuntiBirth.diagnostics()');trace.push(value);
    if (value.status === 'SETTLED') break;await pause(25);
  }
  const artifact = await web.evaluate('window.nuntiTest.getArtifact()'); await save(out, 'retry-artifact.json', artifact);
  check('explicit-local-retry-succeeds', artifact?.mediaOrigin === 'LOCAL_LAYERS' && trace.at(-1).status === 'SETTLED');
  check('retry-sends-the-same-request-id', report.postRequests.length === 2 && report.postRequests.every(value => value.requestId === pendingId && value.renderMode === 'LOCAL_LAYERS'));
  check('first-frame-elapsed-never-negative', trace.every(value => value.elapsedMs >= 0 && value.elapsedMs <= 4000));
  check('final-completes-at-4000', trace.at(-1).elapsedMs === 4000); await screen('03-retry-completed');
  await replay();await pause(400);await web.click('#motion-skip');
  check('final-apk-skip-settles', await web.evaluate('window.NuntiBirth.diagnostics().reason==="SKIPPED" && window.NuntiBirth.diagnostics().elapsedMs===4000'));
  await web.click('label[for="reduced-motion"]');await web.click('#replay-button');
  check('final-apk-reduced-replay-static', await web.evaluate('window.NuntiBirth.diagnostics().reason==="REDUCED_MOTION" && window.NuntiBirth.diagnostics().status==="SETTLED"'));
  await web.click('label[for="reduced-motion"]');await replay();await web.click('#journey-options-open');
  check('parked-options-open', await web.evaluate('document.getElementById("journey-options-dialog").open'));
  await vehicle.drive(30);await web.wait('!state.nativeAllowed && !document.querySelector("dialog[open]")');
  check('actual-driving-stops-and-closes-dialog', await web.evaluate('window.NuntiBirth.diagnostics().status==="SETTLED" && !document.querySelector("dialog[open]")'));
  await screen('04-driving-restriction');await vehicle.parked();await web.wait('state.nativeAllowed');await pause(300);
  check('parked-return-does-not-restart', await web.evaluate('window.NuntiBirth.diagnostics().status==="SETTLED"'));await screen('05-final-parked');
  check('controlled-interception-completed-without-errors', faults.length === 0, faults);report.status = 'PASS';
} catch (error) {report.status = 'FAIL';report.error = String(error.stack || error);console.error(report.error);}
finally {
  if (web) {
    await web.command('Fetch.disable').catch(() => {});
    await web.evaluate(`window.NuntiBirth.setReduced(${originalReduced === 'true'});${originalReduced === null ? 'localStorage.removeItem("nunti-reduced-motion")' : ''}`).catch(() => {});web.close();
  }
  if (vehicle) try {await vehicle.restore();report.vehicleRestored = true;}catch (error){report.status = 'FAIL';report.restorationError = String(error);}
  await save(out, 'elapsed-observations.json', trace);await save(out, 'report.json', report);
}
console.log(JSON.stringify({status: report.status, checks: report.checks.length, out}));
if (report.status !== 'PASS') process.exitCode = 1;
