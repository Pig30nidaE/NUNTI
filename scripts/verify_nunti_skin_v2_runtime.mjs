#!/usr/bin/env node
// Drives the real pre-trip controls on Pleos. The backend route is disconnected
// before launching the new APK. A CDP allowlist independently guards the page.
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import {spawn} from 'node:child_process';
import {root, serial, packageName, adb, pause, save, sha, capture, connectWebView, vehicleSession, consoleRequest,
  readJourney, tapNative, writeFinishedJourney} from './nunti_integration_runtime_lib.mjs';

const argument = name => process.argv.find(value => value.startsWith(`--${name}=`))?.slice(name.length + 3);
const apk = path.resolve(argument('apk') ?? path.join(root, 'android/build/app/outputs/apk/debug/app-debug.apk'));
const out = path.resolve(argument('output') ?? path.join(root, 'artifacts/nunti-skin-v2/run-' + Date.now()));
const resumeJourney = argument('resume-journey');
const artifactDir = path.join(root, 'artifacts');
const mainActivity = `${packageName}/ai.nunti.app.MainActivity`;
const localOrigin = 'http://127.0.0.1:8768';
const recordKey = 'nunti.skin-v2.records';
const reducedKey = 'nunti.skin-v2.reduced';
const guardPath = '/v3/avatars?skin-v2-native-guard-probe=1';
const diagnostics = 'window.NuntiSkinMotion.diagnostics()';
const phases = ['DEFAULT_IDLE', 'ROUTE_ENERGY', 'OUTFIT_SWAP', 'HEAD_AND_EYES_TRANSFORM', 'SKIN_REVEAL', 'FINAL_IDLE'];
const report = {status: 'RUNNING', surface: 'PLEOS_ANDROID_WEBVIEW', checks: [], requests: [], blockedRequests: [], guardErrors: []};
let web;
let vehicle;
let restoreReverse = false;
let originalStorage;
let restoringAnimator = false;
let nativeGuardProbeActive = false;
let advertiseModelCapability = false;
let ownedJourney;

function check(name, passed, evidence) {
  report.checks.push({name, status: passed ? 'PASS' : 'FAIL', ...(evidence === undefined ? {} : {evidence})});
  console.log(passed ? 'PASS' : 'FAIL', name);
  assert.ok(passed, name);
}

async function launch() {
  await adb(['shell', 'am', 'start', '-W', '--user', '10', '-n', mainActivity]);
}

async function motion() {
  return web.evaluate(diagnostics);
}

async function settled(id) {
  return web.wait(`!${diagnostics}.running && ${diagnostics}.phase==='FINAL_IDLE' && ${diagnostics}.skinId===${JSON.stringify(id)} && ${diagnostics}`);
}

async function waitRunning() {
  return web.wait(`${diagnostics}.running && ${diagnostics}`);
}

async function take(name) {
  const before = await motion();
  const screenshot = await adb(['exec-out', 'screencap', '-p'], true);
  const after = await motion();
  await save(out, name + '.png', screenshot);
  await save(out, name + '-state.json', {before, after, allowed: await web.evaluate('state.nativeAllowed')});
  return {before, after};
}

async function currentResult() {
  return web.wait(`(()=>{const artifact=window.nuntiTest.getArtifact();return !document.querySelector('#result-view').hidden&&artifact?.design?.skinSpec&&{
    characterId:artifact.characterId,skinSpec:artifact.design.skinSpec,visual:artifact.visual
  };})()`);
}

async function canvasDigest() {
  const png = await web.evaluate('document.querySelector("#birth-canvas").toDataURL("image/png")');
  assert.match(png, /^data:image\/png;base64,/);
  return sha(Buffer.from(png.split(',')[1], 'base64'));
}

async function matchesFinalAsset(assetPath) {
  return web.evaluate(`(async()=>{const shown=document.querySelector('#birth-canvas');
    const source=new Image();source.src=${JSON.stringify(assetPath)};await source.decode();
    const expected=document.createElement('canvas');expected.width=shown.width;expected.height=shown.height;
    const fit=Math.min(expected.width,expected.height)/768,context=expected.getContext('2d');
    context.setTransform(fit,0,0,fit,(expected.width-768*fit)/2,(expected.height-768*fit)/2);
    context.drawImage(source,0,0,768,768);
    return shown.toDataURL('image/png')===expected.toDataURL('image/png');})()`);
}

async function demo(id) {
  if (await web.evaluate('!document.querySelector("#result-view").hidden')) await web.click('#new-button');
  await web.click('#route-tools-open');
  await web.evaluate(`(()=>{const select=document.querySelector('#skin-demo');select.value=${JSON.stringify(id)};
    if(select.value!==${JSON.stringify(id)}||select.closest('[hidden]'))throw new Error('Missing visible demo input');
    select.dispatchEvent(new Event('change',{bubbles:true}));})()`);
  await web.click('#route-tools-dialog button[data-close-dialog]');
  await web.wait('!document.querySelector("#create-button").disabled');
}

async function manualCityInput() {
  await web.click('#new-button');
  const routeFile = {points: [[0.15, 0.8], [0.15, 0.5], [0.63, 0.5], [0.82, 0.23]],
    destination: {name: '스킨 검증 · 골목길', traits: '도시 구간'}, purpose: '직접 입력한 경로로 만나기'};
  await web.evaluate(`(()=>{document.querySelector('#skin-demo').value='';
    const input=document.querySelector('#route-upload'),transfer=new DataTransfer();
    transfer.items.add(new File([${JSON.stringify(JSON.stringify(routeFile))}],'skin-qa-route.json',{type:'application/json'}));
    input.files=transfer.files;input.dispatchEvent(new Event('change',{bubbles:true}));})()`);
  await web.wait('window.nuntiTest.getRoute()?.inputOrigin==="ROUTE_FILE"');
  await web.evaluate(`(()=>{for(const [id,value] of [['layer-destination','city'],['layer-road','urban']]){
    const field=document.getElementById(id);field.value=value;field.dispatchEvent(new Event('change',{bubbles:true}));}})()`);
  if (!(await web.evaluate('document.querySelector(\'[data-mood="curious"]\').getAttribute("aria-pressed")==="true"')))
    await web.click('[data-mood="curious"]');
  if (!(await web.evaluate('document.querySelector("#route-confirmed").checked')))
    await web.click('label[for="route-confirmed"]');
  await web.wait('!document.querySelector("#create-button").disabled');
}

async function replay() {
  await web.click('#replay-button');
  return waitRunning();
}

async function record() {
  const deviceFile = '/sdcard/nunti-skin-v2-' + Date.now() + '.mp4';
  const recorder = spawn(path.join(root, '.local/pm-tools/sdk/platform-tools/adb'),
    ['-s', serial, 'shell', 'screenrecord', '--time-limit', '8', '--bit-rate', '6000000', deviceFile], {stdio: 'ignore'});
  const finished = new Promise((resolve, reject) => {
    recorder.on('error', reject);
    recorder.on('exit', code => code === 0 ? resolve() : reject(new Error(`screenrecord exited ${code}`)));
  });
  // The promise is also awaited by finish(), after the action has run.
  finished.catch(() => {});
  await pause(650);
  return async () => {
    try {
      await finished;
      const file = path.join(out, 'nunti-skin-transform-demo.mp4');
      await adb(['pull', deviceFile, file]);
      return {file, bytes: (await fs.stat(file)).size};
    } finally {
      await adb(['shell', 'rm', '-f', deviceFile]).catch(() => {});
    }
  };
}

async function requestGuard() {
  web.on('Network.requestWillBeSent', event => {
    const url = new URL(event.request.url);
    if (['http:', 'https:'].includes(url.protocol)) {
      report.requests.push({origin: url.origin, path: url.pathname, method: event.request.method,
        ...(nativeGuardProbeActive && url.pathname + url.search === guardPath ? {nativeGuardProbe: true} : {})});
    }
  });
  web.on('Fetch.requestPaused', event => {
    void (async () => {
      const url = new URL(event.request.url);
      const probe = nativeGuardProbeActive && url.origin === localOrigin && url.pathname + url.search === guardPath;
      const localRead = url.origin === localOrigin && event.request.method === 'GET';
      const nonNetwork = ['data:', 'blob:', 'about:'].includes(url.protocol);
      if (!localRead && !nonNetwork && !probe) {
        report.blockedRequests.push({origin: url.origin, path: url.pathname, method: event.request.method});
        await web.command('Fetch.failRequest', {requestId: event.requestId, errorReason: 'BlockedByClient'});
      } else if (advertiseModelCapability && localRead && url.pathname === '/v3/capabilities') {
        const advertised = {data: {imageApiAvailable: true, localImageModelAvailable: true, layeredRenderAvailable: true}};
        await web.command('Fetch.fulfillRequest', {requestId: event.requestId, responseCode: 200,
          responseHeaders: [{name: 'Content-Type', value: 'application/json'}], body: Buffer.from(JSON.stringify(advertised)).toString('base64')});
        report.syntheticModelCapabilityResponse = true;
      } else {
        await web.command('Fetch.continueRequest', {requestId: event.requestId});
      }
    })().catch(error => report.guardErrors.push(String(error)));
  });
  await web.command('Fetch.enable', {patterns: [{urlPattern: '*', requestStage: 'Request'}]});
}

async function restoreAnimator() {
  if (!restoringAnimator) return;
  if (vehicle.originalAnimator === 'null') {
    await adb(['shell', 'settings', 'put', 'global', 'animator_duration_scale', '1']);
    await pause(500);
    await adb(['shell', 'settings', 'delete', 'global', 'animator_duration_scale']);
  } else await adb(['shell', 'settings', 'put', 'global', 'animator_duration_scale', vehicle.originalAnimator]);
  restoringAnimator = false;
}

async function switchReduced(on) {
  const checked = await web.evaluate('document.querySelector("#reduced-motion").checked');
  if (checked !== on) await web.click('label[for="reduced-motion"]');
  assert.equal(await web.evaluate('document.querySelector("#reduced-motion").checked'), on);
}

async function waitJourney(condition) {
  const deadline = Date.now() + 15000;
  while (Date.now() < deadline) {
    const snapshot = await readJourney();
    if (condition(snapshot)) return snapshot;
    await pause(180);
  }
  throw new Error('JourneyService state did not match the expected owned session');
}

async function smokeJourney(seaCard, firstSea) {
  await web.click('#collection-button');
  await web.wait(`document.querySelector(${JSON.stringify(seaCard)})`);
  await web.click(seaCard);
  await settled('sea');
  await web.click('#journey-options-open');
  await web.evaluate('document.querySelector("#journey-source").value="DEMO"');
  await web.click('#journey-options-dialog button[data-close-dialog]');
  ownedJourney = {characterId: firstSea.characterId, sessionId: null};
  await web.click('#journey-button');
  const active = await waitJourney(value => value.state === 'ACTIVE' && value.characterId === firstSea.characterId);
  ownedJourney.sessionId = active.sessionId;
  assert.match(active.sessionId, /^[a-f0-9-]{36}$/);
  const image = await fs.readFile(path.join(root, 'prototypes/avatar_generator', firstSea.visual.path.replace(/^\//, '')));
  const expectedHash = sha(image);
  assert.equal(path.posix.basename(active.imageFile), expectedHash + '.png');
  const copied = await adb(['exec-out', 'run-as', packageName, '--user', '10', 'cat', active.imageFile], true);
  check('actual-offline-journey-uses-bundled-static-skin-and-no-voice-assets', active.source === 'DEMO' && active.staticOnly === true &&
    Object.keys(active.voices).length === 0 && copied.equals(image), {sessionId: active.sessionId, sha256: expectedHash});
  await save(out, 'journey-active.json', active);
  await capture(out, '09-skin-journey-active');
  await waitJourney(value => value.sessionId === active.sessionId && value.canFinish);
  if (resumeJourney || process.argv.includes('--observed-wide-finish')) {
    // The earlier uiautomator dump selected the other multi-window pane. Use
    // the button center measured in the actual screenshot of this exact window.
    const activities = await adb(['shell', 'dumpsys', 'activity', 'activities']);
    assert.match(activities, /topResumedActivity=.*ai\.nunti\.avatar\.demo\/ai\.nunti\.app\.journey\.JourneyActivity/);
    assert.match(activities, /mBounds=Rect\(853, 90 - 2535, 1300\)/);
    await adb(['shell', 'input', 'tap', '2270', '1220']);
    report.nativeFinishTap = {x: 2270, y: 1220, source: 'Actual 2560×1440 parked Journey screenshot'};
  } else await tapNative('여정 마치기');
  const finished = await waitJourney(value => value.sessionId === active.sessionId && value.state === 'FINISHED');
  check('offline-journey-finishes-through-existing-native-control', finished.staticOnly === true && finished.characterId === firstSea.characterId);
  await save(out, 'journey-finished.json', finished);
  await capture(out, '10-skin-journey-finished');
}

async function continueJourneyOnly(priorDir) {
  const prior = JSON.parse(await fs.readFile(path.join(priorDir, 'report.json'), 'utf8'));
  assert.equal(prior.apk.sha256, report.apk.sha256, 'The earlier proof must be from this exact APK');
  assert.ok(prior.checks.every(item => item.status === 'PASS') && prior.checks.some(item => item.name.startsWith('controlled-final-decode-failure')));
  assert.ok(prior.error.includes('Native control unavailable: 여정 마치기') && prior.vehicleAndJourneyRestored);
  assert.deepEqual(prior.blockedRequests, []);
  assert.deepEqual(prior.guardErrors, []);
  assert.deepEqual(prior.requests.filter(request => !request.nativeGuardProbe && (request.origin !== localOrigin || request.method !== 'GET')), []);
  const previous = prior.checks.find(item => item.name === 'sea-SkinSpec-and-timeline-final').evidence;
  await demo('sea');
  await web.click('#create-button');
  await waitRunning();
  await web.click('#motion-skip');
  await settled('sea');
  const result = await currentResult();
  check('same-APK-continuation-recreates-the-identical-sea-record', JSON.stringify(result) === JSON.stringify(previous));
  await smokeJourney(`button[data-character-id="${result.characterId}"]`, result);
  const file = path.resolve(priorDir, 'nunti-skin-transform-demo.mp4');
  report.video = {file, bytes: (await fs.stat(file)).size};
  report.priorCoreChecks = prior.checks.length;
  report.priorEvidence = path.resolve(priorDir, 'report.json');
}

try {
  report.apk = {path: apk, sha256: sha(await fs.readFile(apk))};
  vehicle = await vehicleSession(out);
  assert.equal(vehicle.original.gear.actual.value, 'Park');
  assert.equal(vehicle.original.controls.speed_kph, 0);
  const reverse = await adb(['reverse', '--list']);
  await save(out, 'original-adb-reverse.txt', reverse);
  if (/\btcp:8768\s+tcp:8768\b/.test(reverse)) {
    await adb(['reverse', '--remove', 'tcp:8768']);
    restoreReverse = true;
  }
  check('host-Studio-transport-disconnected', !(await adb(['reverse', '--list'])).includes('tcp:8768'));
  const installed = await adb(['install', '-r', '--user', '10', apk]);
  const installedPath = (await adb(['shell', 'pm', 'path', packageName])).trim().replace(/^package:/, '');
  const deviceSha = (await adb(['shell', 'sha256sum', installedPath])).trim().split(/\s+/)[0];
  check('installed-APK-matches-reviewed-build', installed.includes('Success') && report.apk.sha256 === deviceSha, deviceSha);
  await vehicle.parked();
  await launch();
  web = await connectWebView();
  report.webView = web.target;
  await requestGuard();
  await web.wait('window.NuntiSkinMotion && window.nuntiTest && state.nativeAllowed && document.querySelector("#skin-demo")');
  originalStorage = await web.evaluate(`Object.fromEntries(${JSON.stringify([recordKey, reducedKey])}.map(key=>[key,localStorage.getItem(key)]))`);
  await save(out, 'original-local-preferences.json', {recordBytes: originalStorage[recordKey]?.length ?? 0, reduced: originalStorage[reducedKey]});
  check('cold-start-actual-pre-trip-UI-offline', await web.evaluate('!document.querySelector("#input-view").hidden'));

  // This harmless probe has no generation input and cannot reach the host.
  // It distinguishes a deliberate WebView rejection from a connection error.
  nativeGuardProbeActive = true;
  try {
    const denial = await web.evaluate(`fetch(${JSON.stringify(guardPath)},{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'})
      .then(async r=>{const body=await r.json();return {status:r.status,code:body.error?.code||body.code||body.error};})`);
    check('native-WebView-denies-avatar-mutation', denial.status === 403 && denial.code === 'MOCK_SKIN_MODE', denial);
  } finally {
    nativeGuardProbeActive = false;
  }

  async function verifyCore() {
  await demo('sea');
  await capture(out, '01-pre-trip-sea-ready');
  const finishRecord = await record();
  let recorded;
  let firstSea;
  let seaFinal;
  try {
    await web.click('#create-button');
    check('existing-create-control-starts-visible-transform', (await waitRunning()).running);
    firstSea = await currentResult();
    seaFinal = await settled('sea');
  } finally {
    recorded = await finishRecord();
  }
  check('video-recorded-from-real-create-interaction', recorded.bytes > 10000, recorded);
  check('all-six-phases-visited-in-order', JSON.stringify(seaFinal.visited) === JSON.stringify(phases), seaFinal);
  check('sea-SkinSpec-and-timeline-final', firstSea.skinSpec.skinId === 'sea' && seaFinal.elapsedMs === 4000, firstSea);
  check('sea-terminal-canvas-equals-bundled-final-PNG', await matchesFinalAsset(firstSea.visual.path));
  const seaDigest = await canvasDigest();
  await take('04-sea-final');

  await replay();
  const initial = await take('02-sea-default-idle');
  check('live-start-screenshot-captured-before-outfit', initial.after.elapsedMs < 1200 && initial.before.phase === 'DEFAULT_IDLE', initial);
  await web.wait(`${diagnostics}.phase==='OUTFIT_SWAP' && ${diagnostics}.elapsedMs>=1790`);
  const mid = await take('03-sea-outfit-swap');
  check('live-mid-screenshot-captured-during-transformation', mid.before.phase === 'OUTFIT_SWAP' && mid.after.elapsedMs < 3300, mid);
  await settled('sea');

  await replay();
  await web.click('#motion-skip');
  const skipped = await settled('sea');
  check('Skip-displays-the-identical-final-pixels', skipped.reason === 'SKIPPED' && await canvasDigest() === seaDigest, skipped);
  await replay();
  await switchReduced(true);
  const reduced = await settled('sea');
  check('in-app-reduced-motion-settles-to-identical-final-pixels', reduced.reason === 'REDUCED' && await canvasDigest() === seaDigest, reduced);
  await switchReduced(false);

  advertiseModelCapability = true;
  await web.command('Page.reload', {ignoreCache: true});
  await web.wait('window.NuntiSkinMotion && state.nativeAllowed && !document.querySelector("#input-view").hidden');
  await web.wait('!!window.nuntiCapabilities');
  advertiseModelCapability = false;
  check('advertised-image-and-local-model-capability-cannot-enable-generation', report.syntheticModelCapabilityResponse && await web.evaluate(`
    window.NuntiSkins.MOCK_SKIN_MODE && !window.nuntiCapabilities.imageApiAvailable && !window.nuntiCapabilities.localImageModelAvailable &&
    Array.from(document.querySelector('#render-mode').options).filter(option=>!option.hidden&&!option.disabled).map(option=>option.value).join()==='MOCK_SKIN'`));
  await web.click('#collection-button');
  const seaCard = `button[data-character-id="${firstSea.characterId}"]`;
  await web.wait(`document.querySelector(${JSON.stringify(seaCard)})`);
  await web.click(seaCard);
  const reopened = await currentResult();
  await settled('sea');
  check('offline-save-reopen-matches-SkinSpec-and-final-pixels',
    JSON.stringify(reopened) === JSON.stringify(firstSea) && await canvasDigest() === seaDigest, reopened);
  await take('05-sea-reopened');

  const appearances = new Set([seaDigest]);
  for (const id of ['default', 'city', 'mountain']) {
    await demo(id);
    await web.click('#create-button');
    const artifact = await currentResult();
    const final = await settled(id);
    const digest = await canvasDigest();
    check(`actual-demo-${id}-distinct-and-matches-bundled-PNG`, artifact.skinSpec.skinId === id && !appearances.has(digest) &&
      await matchesFinalAsset(artifact.visual.path), {artifact, final, digest});
    appearances.add(digest);
    await take(`06-${id}-final`);
  }

  await manualCityInput();
  await web.click('#create-button');
  await waitRunning();
  const manual = await currentResult();
  await settled('city');
  check('normal-route-file-and-form-create-the-matching-skin-offline', manual.skinSpec.skinId === 'city' &&
    manual.skinSpec.mood === 'curious' && manual.skinSpec.road === 'urban' && await matchesFinalAsset(manual.visual.path), manual);
  await take('06-manual-city-final');

  await demo('sea');
  const beforeRapid = await web.evaluate(`localStorage.getItem(${JSON.stringify(recordKey)})`);
  await web.evaluate(`(()=>{const button=document.querySelector('#create-button');button.click();button.click();button.click();})()`);
  const sameInput = await currentResult();
  await settled('sea');
  const afterRapid = await web.evaluate(`localStorage.getItem(${JSON.stringify(recordKey)})`);
  check('identical-input-and-rapid-taps-keep-one-record-and-the-same-result',
    sameInput.characterId === firstSea.characterId && JSON.stringify(sameInput.skinSpec) === JSON.stringify(firstSea.skinSpec) &&
    JSON.stringify(Object.keys(JSON.parse(beforeRapid)).sort()) === JSON.stringify(Object.keys(JSON.parse(afterRapid)).sort()) &&
    await canvasDigest() === seaDigest, {characterId: sameInput.characterId});

  await replay();
  await adb(['shell', 'am', 'start', '-W', '--user', '10', '-n', 'ai.umos.maps.android.navigation.app/.MainActivity']);
  const background = await web.wait(`!${diagnostics}.running && (!state.nativeAllowed || document.hidden) && ${diagnostics}`);
  check('app-background-stops-motion', !background.running, background);
  await launch();
  await web.wait('state.nativeAllowed && !document.hidden');
  check('foreground-return-does-not-replay', !(await motion()).running);

  await replay();
  restoringAnimator = true;
  await adb(['shell', 'settings', 'put', 'global', 'animator_duration_scale', '0']);
  const systemReduced = await settled('sea');
  check('OS-reduced-motion-stops-the-transform', systemReduced.reason === 'REDUCED' && await canvasDigest() === seaDigest, systemReduced);
  await restoreAnimator();
  await web.wait(`!${diagnostics}.systemReducedMotion`);

  await replay();
  await vehicle.drive(30);
  const restricted = await web.wait(`!state.nativeAllowed && !${diagnostics}.running && ${diagnostics}`);
  const driven = await consoleRequest('/vehicle/state');
  check('Virtual-Console-D-at-30-stops-motion', (restricted.reason === 'RESTRICTED' || restricted.reason === 'BACKGROUNDED') &&
    driven.gear.actual.value === 'Drive' && driven.controls.speed_kph === 30, {motion: restricted, gear: driven.gear.actual, speedKph: driven.controls.speed_kph});
  await capture(out, '07-actual-driving-restriction');
  await vehicle.parked();
  await web.wait('state.nativeAllowed');
  await settled('sea');
  check('return-to-P-keeps-static-final', !(await motion()).running && await canvasDigest() === seaDigest);

  // Measure a replay without screenrecord, screencap, or UI dumps running.
  await adb(['shell', 'dumpsys', 'gfxinfo', packageName, 'reset']);
  await replay();
  await settled('sea');
  await save(out, 'performance-gfxinfo-unrecorded.txt', await adb(['shell', 'dumpsys', 'gfxinfo', packageName]));
  await save(out, 'performance-memory.txt', await adb(['shell', 'dumpsys', 'meminfo', packageName]));

  await web.command('Page.reload', {ignoreCache: true});
  await web.wait('window.NuntiSkinMotion && state.nativeAllowed');
  // Android supplies bundled PNG responses before CDP's request-stage interception.
  // Inject a decode error at the actual browser boundary for just one bundled asset.
  await web.evaluate(`(()=>{window.__skinQaDecode=Image.prototype.decode;window.__skinQaDecodeFaults=0;
    Image.prototype.decode=function(){if(new URL(this.src,location.href).pathname==='/skin-v2/atelier/mountain/final.png'){
      window.__skinQaDecodeFaults++;return Promise.reject(new DOMException('Controlled mountain decode failure','EncodingError'));}
    return window.__skinQaDecode.call(this);};})()`);
  try {
    await demo('mountain');
    await web.click('#create-button');
    const fallback = await currentResult();
    const fallbackMotion = await settled('default');
    check('controlled-final-decode-failure-uses-approved-default-and-saves-fallback-SkinSpec',
      await web.evaluate('window.__skinQaDecodeFaults===1') &&
      fallback.skinSpec.requestedSkinId === 'mountain' && fallback.skinSpec.fallback === 'FINAL_ASSET_MISSING' &&
      !fallbackMotion.running && await matchesFinalAsset(fallback.visual.path), fallback);
    await take('08-controlled-asset-fallback');
  } finally {
    await web.evaluate('Image.prototype.decode=window.__skinQaDecode;delete window.__skinQaDecode;delete window.__skinQaDecodeFaults;');
  }

  if (process.argv.includes('--with-journey')) await smokeJourney(seaCard, firstSea);

  report.video = recorded;
  }

  if (resumeJourney) await continueJourneyOnly(resumeJourney);
  else await verifyCore();

  const unexpected = report.requests.filter(request => !request.nativeGuardProbe &&
    (request.origin !== localOrigin || request.method !== 'GET'));
  check('no-remote-or-mutating-network-request-during-app-scenarios', unexpected.length === 0 &&
    report.blockedRequests.length === 0 && report.guardErrors.length === 0, unexpected);
  report.externalGenerationCalls = 0;
  report.productionGenerationRequests = 0;
  report.nativeGuardProbeWasLocallyRejected = true;
  report.status = 'PASS';
} catch (error) {
  report.status = 'FAIL';
  report.error = String(error.stack || error);
  console.error(report.error);
  if (web) await take('failed-check').catch(() => {});
} finally {
  const restore = async (name, action) => {
    try {await action();}
    catch (error) {report.status = 'FAIL'; (report.restorationErrors ??= []).push({name, error: String(error)});}
  };
  await restore('system animator scale', restoreAnimator);
  if (web) {
    if (originalStorage) await restore('owned local storage keys', async () => {
      const restored = await web.evaluate(`(()=>{for(const [key,value] of Object.entries(${JSON.stringify(originalStorage)})){
        if(value===null)localStorage.removeItem(key);else localStorage.setItem(key,value);
      }return ${JSON.stringify(Object.keys(originalStorage))}.map(key=>localStorage.getItem(key));})()`);
      assert.deepEqual(restored, Object.values(originalStorage));
      report.localStorageRestored = true;
    });
    await restore('CDP guard', () => web.command('Fetch.disable'));
    web.close();
  }
  if (ownedJourney) await restore('owned DEMO journey', async () => {
    const current = await readJourney();
    if (current.sessionId === JSON.parse(vehicle.originalLatest).sessionId) return;
    assert.equal(current.characterId, ownedJourney.characterId);
    if (ownedJourney.sessionId !== null) assert.equal(current.sessionId, ownedJourney.sessionId);
    assert.match(current.sessionId, /^[a-f0-9-]{36}$/);
    await adb(['shell', 'am', 'force-stop', '--user', '10', packageName]);
    await pause(250);
    await writeFinishedJourney(vehicle.originalLatest);
    const deadline = Date.now() + 4000;
    while (Date.now() < deadline && !(await readJourney(true)).equals(vehicle.originalLatest)) await pause(100);
    assert.ok((await readJourney(true)).equals(vehicle.originalLatest));
    await adb(['shell', 'run-as', packageName, '--user', '10', 'rm', '-f',
      `files/journeys/${current.sessionId}-input.json`, `files/journeys/${current.sessionId}-report.json`]);
    report.ownedJourneyRestored = true;
  });
  if (restoreReverse) await restore('local Studio ADB reverse', async () => {
    await adb(['reverse', 'tcp:8768', 'tcp:8768']);
    report.adbReverseRestored = (await adb(['reverse', '--list'])).includes('tcp:8768 tcp:8768');
    assert.ok(report.adbReverseRestored);
  });
  if (vehicle) await restore('Vehicle Console and existing journey report', async () => {
    await vehicle.restore();
    assert.equal(JSON.parse(await fs.readFile(path.join(out, 'restoration.json'), 'utf8')).latestUnchanged, true);
    report.vehicleAndJourneyRestored = true;
  });
  if (ownedJourney) await restore('return to Studio', launch);
  if (report.status === 'PASS') {
    const publicVideo = path.join(artifactDir, 'nunti-skin-transform-demo.mp4');
    await fs.copyFile(report.video.file, publicVideo);
    report.video.publicFile = publicVideo;
  }
  await save(out, 'report.json', report);
}
console.log(JSON.stringify({status: report.status, checks: report.checks.length, out}));
if (report.status !== 'PASS') process.exitCode = 1;
