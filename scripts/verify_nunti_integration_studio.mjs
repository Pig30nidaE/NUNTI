#!/usr/bin/env node
// Actual production Studio/WebView acceptance. Run only after the integration APK
// is installed. Creates identified LOCAL_LAYERS records, never model/voice calls.
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import {root, packageName, adb, pause, save, sha, capture, connectWebView, vehicleSession} from './nunti_integration_runtime_lib.mjs';

const stamp = new Date().toISOString().replaceAll(/[-:.]/g, '');
const outArg = process.argv.find(value => value.startsWith('--output='))?.slice(9);
const out = path.resolve(outArg || path.join(root, 'docs/redesign/integration-v1/runtime-studio-' + stamp));
const reuseArg = process.argv.find(value => value.startsWith('--reuse='))?.slice(8);
const generateFirst = process.argv.includes('--generate-first');
const continueAfter = process.argv.find(value => value.startsWith('--continue-after='))?.slice(17);
await fs.mkdir(out, {recursive: true});
const report = {status: 'RUNNING', surface: 'ACTUAL_PRODUCTION_ANDROID_WEBVIEW', startedAt: new Date().toISOString(),
  paidApiCalls: 0, imageModelCalls: 0, voiceGenerationCalls: 0, checks: [], artifacts: [], requests: []};
let vehicle, web, initialReduced = null;
const check = (name, condition, details) => {
  assert.ok(condition, name); report.checks.push({name, status: 'PASS', ...(details ? {details} : {})}); console.log('PASS', name);
};
async function state() {
  return web.evaluate(`({allowed:state.nativeAllowed,screen:['input','result','collection'].find(x=>!document.getElementById(x+'-view').hidden),
    motion:window.NuntiBirth?.diagnostics(),artifact:window.nuntiTest?.getArtifact()?.characterId,
    theme:document.documentElement.dataset.theme,viewport:{width:innerWidth,height:innerHeight},
    mode:document.getElementById('render-mode').value,notice:document.getElementById('notice').textContent})`);
}
async function screen(name, options) {
  await save(out, name + '-state.json', await state()); await capture(out, name, options);
}
async function show(artifact, animate = true) {
  await web.evaluate(`window.nuntiTest.showArtifact(${JSON.stringify(artifact)},${animate})`);
}
async function settled() {
  return web.wait('window.NuntiBirth?.diagnostics().status==="SETTLED" && window.NuntiBirth.diagnostics().finalReady && window.NuntiBirth.diagnostics()');
}
async function png(name, value) {
  assert.ok(value?.startsWith('data:image/png;base64,'), name); await save(out, name, Buffer.from(value.split(',')[1], 'base64'));
}
async function finalProof(artifact, slug) {
  const final = await web.evaluate('window.NuntiBirth.capture(4000)'); await png(slug + '-final.png', final);
  const reference = await web.evaluate(`(async()=>{const image=new Image();image.src=${JSON.stringify(artifact.visual.path)};await image.decode();
    const canvas=document.createElement('canvas');canvas.width=canvas.height=768;canvas.getContext('2d').drawImage(image,0,0,768,768);return canvas.toDataURL('image/png');})()`);
  await png(slug + '-browser-reference.png', reference);
  check(slug + '-final-exact-browser-png', final === reference);
  const raw = await web.evaluate(`fetch(${JSON.stringify(artifact.visual.path)}).then(r=>r.arrayBuffer()).then(async raw=>({bytes:raw.byteLength,sha256:Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',raw)),x=>x.toString(16).padStart(2,'0')).join('')}))`);
  check(slug + '-server-source-sha', raw.sha256 === artifact.visual.sha256, raw);
}
async function createLocal(input) {
  assert.equal(input.renderMode, 'LOCAL_LAYERS');
  return web.evaluate(`fetch('/v3/avatars',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(${JSON.stringify(input)})}).then(async r=>{const value=await r.json();if(!r.ok)throw new Error(JSON.stringify(value));return value.data})`);
}
try {
  vehicle = await vehicleSession(out);
  assert.equal(vehicle.original.gear.actual.value, 'Park', 'Start while already parked');
  assert.equal(vehicle.original.controls.speed_kph, 0, 'Start stationary');
  await adb(['shell', 'am', 'start', '-W', '--user', '10', '-n', packageName + '/ai.nunti.app.MainActivity']);
  web = await connectWebView();
  web.on('Network.requestWillBeSent', event => {
    const url = new URL(event.request.url);
    if (url.pathname.startsWith('/v3/')) report.requests.push({path: url.pathname, method: event.request.method, timestamp: event.timestamp});
  });
  await web.wait('!!window.NuntiBirth && !!window.nuntiTest && window.nuntiCapabilities?.layeredRenderAvailable && state.nativeAllowed');
  initialReduced = await web.evaluate('localStorage.getItem("nunti-reduced-motion")');
  await web.evaluate('window.NuntiBirth.setReduced(false)');
  report.originalCollectionCount = await web.evaluate('fetch("/v3/avatars").then(r=>r.json()).then(value=>(value.data??value).length)');
  report.webView = web.target;
  await save(out, 'initial-production-state.json', await state());
  await screen('01-pre-trip-day');
  check('production-layer-default', await web.evaluate('document.getElementById("render-mode").value==="LOCAL_LAYERS"'));
  const artifacts = reuseArg ? JSON.parse(await fs.readFile(path.join(path.resolve(reuseArg), 'artifacts.json'), 'utf8')) : [];
  let first;
  if (continueAfter) {
    assert.ok(reuseArg, 'Continuation requires previously saved artifacts');
    first = artifacts.find(item => item.slug === 'coast-curious').artifact;
    await show(first, false); await settled();
  } else {
  if (artifacts.length && !generateFirst) {
    first = artifacts.find(item => item.slug === 'coast-curious').artifact;
    await show(first, true);
  } else {
    // Existing test-route example feeds the production input handler. No road API
    // or navigation destination command is issued.
    await web.evaluate(`(()=>{window.nuntiTest.viewExample(1);const set=(id,value)=>{const e=document.getElementById(id);e.value=value;e.dispatchEvent(new Event('change',{bubbles:true}));e.dispatchEvent(new Event('input',{bubbles:true}));};
      set('render-mode','LOCAL_LAYERS');set('destination','통합 검증 · 바다');set('traits','통합 검증용 저장 기록');set('purpose','승인 A 모습과 실제 변신 확인');
      set('layer-destination','coast');set('layer-road','highway');set('layer-mood','curious');const confirmed=document.getElementById('route-confirmed');confirmed.checked=true;confirmed.dispatchEvent(new Event('change'));})()`);
    await web.wait('!document.getElementById("create-button").disabled');
    await screen('02-pre-trip-ready');
    await web.click('#create-button');
    first = await web.wait('window.nuntiTest.getArtifact()?.mediaOrigin==="LOCAL_LAYERS" && window.nuntiTest.getArtifact()', 30000);
    const existing = artifacts.findIndex(item => item.slug === 'coast-curious');
    if (existing >= 0) artifacts[existing] = {slug: 'coast-curious', artifact: first};
    else artifacts.push({slug: 'coast-curious', artifact: first});
    await save(out, 'artifacts.json', artifacts);
  }
  await web.wait('window.NuntiBirth.diagnostics().status==="RUNNING"');
  check('actual-ui-generation-starts-four-second-motion', true);
  await pause(1400); await screen('03-reveal-in-progress', {xml: false});
  await settled(); await screen('04-reveal-settled');
  check('motion-completes-at-4000', (await state()).motion.elapsedMs === 4000);
  await finalProof(first, 'coast-curious');
  for (const milliseconds of [0, 1000, 2200, 3000, 4000]) {
    await png('timeline-' + String(milliseconds).padStart(4, '0') + '.png', await web.evaluate(`window.NuntiBirth.capture(${milliseconds})`));
    await save(out, 'timeline-' + milliseconds + '-state.json', await state());
  }
  await web.click('#replay-button'); await web.wait('window.NuntiBirth.diagnostics().status==="RUNNING"');
  await pause(700); await web.click('#motion-skip');
  check('actual-skip-control-settles', (await settled()).reason === 'SKIPPED'); await screen('05-skip');
  await web.click('label[for="reduced-motion"]');
  check('actual-reduced-control-persists', await web.evaluate('window.NuntiBirth.diagnostics().userReducedMotion && localStorage.getItem("nunti-reduced-motion")==="true"'));
  await web.click('#replay-button'); await pause(400);
  check('reduced-replay-is-static', (await state()).motion.reason === 'REDUCED_MOTION'); await screen('06-reduced');
  await web.click('label[for="reduced-motion"]');
  await web.click('#replay-button'); await web.wait('window.NuntiBirth.diagnostics().status==="RUNNING"');
  await vehicle.drive(30); await web.wait('!state.nativeAllowed'); await pause(1100);
  const restricted = await state();
  check('actual-car-gate-stops-motion', restricted.motion.status === 'SETTLED' && restricted.motion.elapsedMs === 4000, restricted.motion);
  await screen('07-driving-restricted');
  await vehicle.parked(); await web.wait('state.nativeAllowed'); await pause(500);
  check('return-to-park-does-not-autoplay', (await state()).motion.status === 'SETTLED'); await screen('08-parked-return');
  }
  // The same canonical input with a fresh request id must retain appearance.
  if (!reuseArg) {
    const input = JSON.parse(first.inputCanonical);
    for (const destination of ['coast', 'mountain', 'city']) for (const mood of ['calm', 'curious', 'adventurous']) {
      const slug = destination + '-' + mood; if (slug === 'coast-curious') continue;
      const next = structuredClone(input); next.requestId = crypto.randomUUID(); next.destination.name = '통합 검증 · ' + slug;
      Object.assign(next.variantContext, {destinationCategory: destination, userSelectedMood: mood});
      const artifact = await createLocal(next); artifacts.push({slug, artifact}); await save(out, 'artifacts.json', artifacts);
    }
  }
  let afterReached = !continueAfter;
  for (const item of artifacts) {
    if (!afterReached) {if (item.slug === continueAfter) afterReached = true; continue;}
    if (item.slug === 'coast-curious') continue;
    await show(item.artifact, true); await settled(); await finalProof(item.artifact, item.slug);
    await save(out, item.slug + '-state.json', await state());
  }
  check('nine-actual-local-generation-results', artifacts.length === 9 && artifacts.every(item => item.artifact.mediaOrigin === 'LOCAL_LAYERS'));
  report.artifacts = artifacts.map(item => ({slug: item.slug, characterId: item.artifact.characterId, imageSha256: item.artifact.visual.sha256}));
  await show(first, false); await settled();
  await web.click('#collection-button'); await web.wait('!document.getElementById("collection-view").hidden && document.querySelectorAll(".collection-item").length>0');
  await screen('09-collection'); await show(first, false); await settled();
  // A deliberately absent stored-image URL exercises the real image-error path.
  const broken = structuredClone(first); broken.visual.path = '/v3/assets/' + '0'.repeat(64);
  await show(broken, true); await web.wait('document.getElementById("birth-status").textContent.includes("기본 눈티")');
  check('missing-final-image-shows-approved-base', await web.evaluate('document.getElementById("replay-button").hidden'));
  await screen('10-final-image-fallback'); await show(first, false); await settled();
  const beforeOffline = await web.evaluate('document.getElementById("birth-canvas").toDataURL()');
  await web.command('Network.emulateNetworkConditions', {offline: true, latency: 0, downloadThroughput: 0, uploadThroughput: 0});
  await pause(500); check('offline-keeps-current-final', beforeOffline === await web.evaluate('document.getElementById("birth-canvas").toDataURL()'));
  await screen('11-offline-saved-result');
  await web.command('Page.reload', {ignoreCache: true}); await web.wait('!!window.nuntiTest && !!window.NuntiBirth');
  await pause(1500); await screen('12-offline-pre-trip');
  check('offline-apk-shell-still-loads', await web.evaluate('!!document.getElementById("create-button") && !document.getElementById("input-view").hidden'));
  await web.command('Network.emulateNetworkConditions', {offline: false, latency: 0, downloadThroughput: -1, uploadThroughput: -1});
  await web.command('Page.reload', {ignoreCache: true}); await web.wait('window.nuntiCapabilities?.layeredRenderAvailable && state.nativeAllowed');
  await show(first, false); await settled(); await screen('13-restored-result');
  check('no-voice-or-model-generation-post', report.requests.filter(item => item.method === 'POST').every(item => item.path === '/v3/avatars'));
  report.status = 'PASS';
} catch (error) {
  report.status = 'FAIL'; report.error = String(error.stack || error); console.error(report.error);
  if (web) await screen('failure').catch(() => {});
} finally {
  if (web) {
    await web.command('Network.emulateNetworkConditions', {offline: false, latency: 0, downloadThroughput: -1, uploadThroughput: -1}).catch(() => {});
    if (initialReduced !== null) await web.evaluate(`localStorage.setItem('nunti-reduced-motion',${JSON.stringify(initialReduced)});window.NuntiBirth?.setReduced(${initialReduced === 'true'});`).catch(() => {});
    else await web.evaluate('window.NuntiBirth?.setReduced(false);localStorage.removeItem("nunti-reduced-motion")').catch(() => {});
    web.close();
  }
  if (vehicle) {
    try {await vehicle.restore(); report.vehicleRestored = true;}
    catch (error) {report.vehicleRestored = false; report.restorationError = String(error); report.status = 'FAIL';}
  }
  report.finishedAt = new Date().toISOString(); await save(out, 'report.json', report);
}
console.log(JSON.stringify({status: report.status, checks: report.checks.length, out}));
if (report.status !== 'PASS') process.exitCode = 1;
