#!/usr/bin/env node
// Actual Android UI -> one local image -> first generated voice -> saved collection.
// Run only after the shared GPU batch has finished. No recording or new route lookup.
import fs from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
import {execFileSync} from 'node:child_process';
import {createHash, randomUUID} from 'node:crypto';
import {isDeepStrictEqual} from 'node:util';
import {fileURLToPath} from 'node:url';

if (!process.argv.includes('--run')) {
  console.log('Usage: node scripts/verify_avatar_v6_live.mjs --run');
  console.log('Wait for the AI batch to finish, then keep Nunti open in the parked Pleos emulator.');
  process.exit(0);
}
assert(process.argv.slice(2).every(value => value === '--run'), 'Only --run is supported.');
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const out = path.join(root, '.local/avatar-v6/live');
const attempt = path.join(out, 'attempts', new Date().toISOString().replaceAll(':', '-'));
await fs.mkdir(attempt, {recursive: true, mode: 0o700});
const adb = path.join(root, '.local/pm-tools/sdk/platform-tools/adb');
const serial = 'emulator-5554';
const origin = 'http://127.0.0.1:8768';
const sha = bytes => createHash('sha256').update(bytes).digest('hex');
const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
const json = value => JSON.stringify(value, null, 2) + '\n';
const adbRun = args => execFileSync(adb, ['-s', serial, ...args], {encoding: 'utf8', timeout: 15000, maxBuffer: 12 * 1024 * 1024});
const proof = {
  status: 'FAIL', surface: 'ACTUAL_ANDROID_WEBVIEW', startedAt: new Date().toISOString(),
  scope: 'ONE_ADDITIONAL_LIVE_INTEGRATION_CASE_SEPARATE_FROM_AI_30_MATRIX',
  checks: [], network: [], blockedRequests: [], exceptions: [],
  paidApiCalls: 0, externalRouteRequests: 0, videoRecorded: false, audioRecorded: false,
  humanQualityApproved: false, humanListeningVerified: false,
};
const check = (label, condition) => { assert(condition, label); proof.checks.push(label); };
let socket, pid, sequence = 0;
const pending = new Map();
let generationBody;

function call(method, params = {}, timeout = 20000) {
  return new Promise((resolve, reject) => {
    const id = ++sequence;
    const timer = setTimeout(() => { pending.delete(id); reject(new Error('CDP timeout: ' + method)); }, timeout);
    pending.set(id, {
      resolve: value => { clearTimeout(timer); resolve(value); },
      reject: error => { clearTimeout(timer); reject(error); },
    });
    socket.send(JSON.stringify({id, method, params}));
  });
}

async function evaluate(expression) {
  const result = await call('Runtime.evaluate', {expression, returnByValue: true, awaitPromise: true});
  if (result.exceptionDetails) throw new Error(JSON.stringify(result.exceptionDetails));
  return result.result?.value;
}

async function wait(expression, timeout = 30000, failure = null) {
  const end = Date.now() + timeout;
  while (Date.now() < end) {
    assert(proof.blockedRequests.length === 0, 'A prohibited request was blocked.');
    try {
      const value = await evaluate(expression);
      if (value) return value;
      if (failure) {
        const problem = await evaluate(failure);
        if (problem) throw new Error(String(problem));
      }
    } catch (error) {
      if (!/Execution context was destroyed|Cannot find context|Inspected target navigated/.test(error.message)) throw error;
    }
    await pause(250);
  }
  const notice = await evaluate('document.getElementById("notice")?.textContent').catch(() => 'page unavailable');
  throw new Error('Timed out: ' + expression + '; ' + notice);
}

async function reloadPage() {
  const previousDocument = await evaluate('performance.timeOrigin');
  await call('Page.reload', {ignoreCache: true});
  // Page.reload acknowledges before navigation. Never accept the old page's ready state.
  await wait(`performance.timeOrigin!==${JSON.stringify(previousDocument)} && document.readyState==='complete'`);
}

async function clickExpression(expression, label) {
  const point = await evaluate(`(()=>{const e=${expression};if(!e||e.disabled||e.closest('[hidden]'))throw new Error(${JSON.stringify('Not clickable: ' + label)});e.scrollIntoView({block:'center'});const r=e.getBoundingClientRect();if(!r.width||!r.height)throw new Error('Empty click target');return {x:r.x+r.width/2,y:r.y+r.height/2};})()`);
  await call('Input.dispatchMouseEvent', {type: 'mousePressed', button: 'left', clickCount: 1, ...point});
  await call('Input.dispatchMouseEvent', {type: 'mouseReleased', button: 'left', clickCount: 1, ...point});
}
const click = id => clickExpression(`document.getElementById(${JSON.stringify(id)})`, id);

// CDP observes and blocks disallowed requests before the HTTP request is sent.
// It never substitutes a response, artwork, model, audio clip or production handler.
async function guardRequest(event) {
  const {requestId, request} = event;
  const url = new URL(request.url);
  let allowed = url.origin === origin && ['GET', 'HEAD'].includes(request.method);
  if (url.origin === origin && request.method === 'POST') {
    if (url.pathname === '/v3/avatars') {
      let body;
      try { body = JSON.parse(request.postData); } catch { body = null; }
      allowed = !!generationBody && isDeepStrictEqual(body, generationBody) && body.renderMode === 'LOCAL_MODEL';
    } else if (url.pathname === `/v3/avatars/nunti-${generationBody?.requestId}/voice`) {
      allowed = request.postData === '{}' || request.postData === undefined;
    }
  }
  proof.network.push({method: request.method, origin: url.origin, path: url.pathname, allowed});
  if (!allowed) {
    proof.blockedRequests.push({method: request.method, origin: url.origin, path: url.pathname});
    await call('Fetch.failRequest', {requestId, errorReason: 'BlockedByClient'});
  } else {
    await call('Fetch.continueRequest', {requestId});
  }
}

async function readApi(urlPath, allowMissing = false) {
  assert(urlPath.startsWith('/v3/'), 'Only local v3 reads are allowed.');
  const response = await evaluate(`fetch(${JSON.stringify(urlPath)},{credentials:'same-origin'}).then(async r=>({status:r.status,body:await r.json()}))`);
  if (allowMissing && response.status === 404) return null;
  assert.equal(response.status, 200, `GET ${urlPath}: ${response.status}`);
  return response.body.data;
}

async function downloadAsset(asset, name) {
  assert(/^\/v3\/assets\/[a-f0-9]{64}$/.test(asset.path), 'Unexpected asset path.');
  const encoded = await evaluate(`(async()=>{const r=await fetch(${JSON.stringify(asset.path)},{credentials:'same-origin'});if(!r.ok)throw new Error('Asset HTTP '+r.status);const a=new Uint8Array(await r.arrayBuffer());let s='';for(let i=0;i<a.length;i+=32768)s+=String.fromCharCode(...a.subarray(i,i+32768));return btoa(s);})()`);
  const bytes = Buffer.from(encoded, 'base64');
  check(name + '-download-matches-stored-sha256', sha(bytes) === asset.sha256);
  await fs.writeFile(path.join(out, name), bytes, {mode: 0o600});
  return bytes;
}

function nativeCounts() {
  const logs = adbRun(['logcat', '-d', `--pid=${pid}`, '-s', 'NuntiStudio:I', '*:S']);
  return {
    started: (logs.match(/STUDIO_GENERATED_VOICE_STARTED/g) || []).length,
    completed: (logs.match(/STUDIO_GENERATED_VOICE_COMPLETED/g) || []).length,
  };
}

async function sourceHashes() {
  const names = [
    'backend/nunti/avatar_studio/local_model.py', 'backend/nunti/avatar_studio/semantic_reference.py',
    'backend/nunti/avatar_studio/matte_cutout.py', 'backend/nunti/avatar_studio/voice_service.py',
    'prototypes/avatar_generator/studio.js', 'prototypes/avatar_generator/navigation.js',
    'android/app/src/main/kotlin/ai/nunti/app/studio/AvatarStudioActivity.kt',
  ];
  return Object.fromEntries(await Promise.all(names.map(async name => [name, sha(await fs.readFile(path.join(root, name)))])));
}

try {
  const savedPlanBytes = await fs.readFile(path.join(root, '.local/navigation-integration/live/coast-plan.json'));
  const savedPlan = JSON.parse(savedPlanBytes);
  assert(/^[a-f0-9]{64}$/.test(savedPlan.planId), 'Invalid saved plan ID.');
  assert(savedPlan.geometry.provider === 'OSRM_FOSSGIS', 'Expected stored OSRM geometry.');
  assert(!savedPlan.nativeSnapshot, 'The fixed replay must not depend on a changing native route.');
  const fixedInput = {
    destination: {name: savedPlan.destination.name, traits: '푸른 바다, 모래해변'},
    purpose: '어린이 캐릭터가 해변에서 책 읽기',
    route: {
      points: savedPlan.route.points, inputOrigin: savedPlan.route.inputOrigin,
      sourceLabel: savedPlan.route.sourceLabel, confirmed: true, apiPlanId: savedPlan.planId,
    },
    renderMode: 'LOCAL_MODEL',
  };
  const requestPath = path.join(out, 'request.json');
  try {
    generationBody = {requestId: randomUUID(), ...fixedInput};
    await fs.writeFile(requestPath, json(generationBody), {flag: 'wx', mode: 0o600});
  } catch (error) {
    if (error.code !== 'EEXIST') throw error;
    generationBody = JSON.parse(await fs.readFile(requestPath));
    const {requestId, ...input} = generationBody;
    assert(/^[0-9a-f-]{36}$/.test(requestId), 'Invalid persisted request UUID.');
    assert.deepEqual(input, fixedInput, 'Saved request input changed; do not generate a new UUID.');
  }
  proof.requestId = generationBody.requestId;
  proof.savedPlan = {planId: savedPlan.planId, sourceFileSha256: sha(savedPlanBytes)};
  proof.sourceSha256 = await sourceHashes();
  pid = adbRun(['shell', 'pidof', 'ai.nunti.avatar.demo']).trim();
  assert(/^\d+$/.test(pid), 'Keep the actual Nunti Android application open.');
  adbRun(['forward', 'tcp:9224', `localabstract:webview_devtools_remote_${pid}`]);
  const targets = await (await fetch('http://127.0.0.1:9224/json/list', {signal: AbortSignal.timeout(10000)})).json();
  const target = targets.find(item => item.type === 'page' && item.url.startsWith(origin));
  assert(target, 'No Nunti Android WebView found.');
  socket = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error('CDP connection timeout')), 10000);
    socket.onopen = () => { clearTimeout(timer); resolve(); };
    socket.onerror = error => { clearTimeout(timer); reject(error); };
  });
  socket.onmessage = event => {
    const message = JSON.parse(event.data);
    if (message.id) {
      const task = pending.get(message.id); pending.delete(message.id);
      message.error ? task?.reject(new Error(JSON.stringify(message.error))) : task?.resolve(message.result);
    } else if (message.method === 'Runtime.exceptionThrown') {
      proof.exceptions.push(message.params.exceptionDetails);
    } else if (message.method === 'Fetch.requestPaused') {
      guardRequest(message.params).catch(error => proof.blockedRequests.push({guardError: error.message}));
    }
  };
  socket.onclose = () => {
    for (const task of pending.values()) task.reject(new Error('CDP disconnected.'));
    pending.clear();
  };
  await call('Runtime.enable'); await call('Page.enable');
  await call('Fetch.enable', {patterns: [
    {urlPattern: 'http://*', requestStage: 'Request'},
    {urlPattern: 'https://*', requestStage: 'Request'},
  ]});
  await evaluate(`localStorage.setItem('nunti.lastRoutePlan',${JSON.stringify(savedPlan.planId)})`);
  await reloadPage();
  await wait('window.nuntiCapabilities?.localImageModelAvailable && window.nuntiCapabilities?.voice?.available && window.NuntiNavigation && window.nuntiTest && typeof window.NuntiNative?.playVoice==="function"');
  await wait('state.nativeAllowed && !document.hidden && !document.getElementById("nav-replay").disabled');
  check('actual-native-player-and-models-ready', await evaluate('window.nuntiCapabilities.voice.mode==="LOCAL_VOICE_DESIGN" && !document.getElementById("session-dialog").open'));

  await click('nav-replay');
  const replay = await wait(`window.NuntiNavigation.getPlan()?.planId===${JSON.stringify(savedPlan.planId)} && !state.planning && window.NuntiNavigation.getPlan()`);
  check('saved-route-get-without-external-request', replay.retrieval?.externalRequestMade === false);
  check('saved-road-coordinates-unchanged', isDeepStrictEqual(replay.geometry, savedPlan.geometry) && isDeepStrictEqual(replay.route.points, savedPlan.route.points));
  await fs.writeFile(path.join(attempt, 'route-plan.json'), json(replay));
  const existing = await readApi('/v3/avatars/nunti-' + generationBody.requestId, true);
  proof.imageAlreadyStoredAtStart = !!existing;
  proof.voiceAlreadyStoredAtStart = existing?.voice?.status === 'READY';
  await evaluate(`(()=>{for(const [id,value] of Object.entries(${JSON.stringify({traits: fixedInput.destination.traits, purpose: fixedInput.purpose})})){const e=document.getElementById(id);e.value=value;e.dispatchEvent(new Event('input',{bubbles:true}));}const mode=document.getElementById('render-mode');mode.value='LOCAL_MODEL';mode.dispatchEvent(new Event('change',{bubbles:true}));const descriptor=Object.getOwnPropertyDescriptor(crypto,'randomUUID');Object.defineProperty(crypto,'randomUUID',{configurable:true,value:()=>${JSON.stringify(generationBody.requestId)}});window.__nuntiLiveRestoreUUID=()=>{if(descriptor)Object.defineProperty(crypto,'randomUUID',descriptor);else delete crypto.randomUUID;delete window.__nuntiLiveRestoreUUID;};})()`);
  check('correct-ui-purpose-destination-and-mode', await evaluate(`document.getElementById('destination').value===${JSON.stringify(fixedInput.destination.name)} && document.getElementById('render-mode').value==='LOCAL_MODEL'`));
  await wait('!document.getElementById("route-confirmed").disabled');
  check('route-requires-confirmation', await evaluate('!document.getElementById("route-confirmed").checked && document.getElementById("create-button").disabled'));
  await click('route-confirmed'); await wait('!document.getElementById("create-button").disabled');
  const logsBeforeCreation = nativeCounts();
  console.log(JSON.stringify({stage: 'image-ui-submit', requestId: generationBody.requestId, reusingStoredImage: !!existing}));
  await click('create-button');
  const artifact = await wait(`window.nuntiTest.getArtifact()?.requestId===${JSON.stringify(generationBody.requestId)} && !state.busy && window.nuntiTest.getArtifact()`, 210000,
    '!state.busy && !window.nuntiTest.getArtifact() && !document.getElementById("input-view").hidden && document.getElementById("notice").textContent');
  await evaluate('window.__nuntiLiveRestoreUUID?.()');
  await wait('!document.getElementById("result-details").hidden && window.nuntiTest.getFormation()');
  await wait('document.getElementById("birth-progress").hidden', 20000);
  check('one-real-local-ai-image-with-fixed-request', artifact.mediaOrigin === 'LOCAL_MODEL' && artifact.requestId === generationBody.requestId);
  check('image-model-is-offline-without-paid-calls', artifact.provider?.offline === true && artifact.provider?.paidApiCalls === 0);
  check('input-and-stored-osrm-route-preserved', isDeepStrictEqual(JSON.parse(artifact.inputCanonical), generationBody));
  check('current-v6-ai-pipeline', artifact.provider?.promptVersion === 'local-journey-character-8' && artifact.provider?.steps === 4 && artifact.visual.width === 512 && artifact.visual.height === 512);
  check('current-cutout-keeps-original-rgb', artifact.provider.cutout?.version === 'flat-border-cutout-2' && artifact.provider.cutout.rgbChannelsPreserved === true && artifact.provider.cutout.cropApplied === false);
  check('study-and-shell-intent-match-the-journey', artifact.design.characterPlan.purpose.role === 'STUDY' && artifact.design.characterPlan.outfit.id === 'KNIT_VEST' && artifact.design.characterPlan.destination.landmark === 'SHELL');
  check('explicit-child-character-has-a-youthful-reading-voice-plan', artifact.voice.plan.characterAge?.value === 'CHILD' && artifact.voice.plan.ageImpression === 'youthful-fictional' && artifact.voice.plan.instruct.includes('bookish'));
  check('image-does-not-auto-play-voice', isDeepStrictEqual(nativeCounts(), logsBeforeCreation));
  if (!existing) check('first-voice-is-lazy', artifact.voice.status === 'PLANNED' && !artifact.voice.audio);
  await fs.writeFile(path.join(attempt, 'artifact-before-voice.json'), json(artifact));
  await downloadAsset(artifact.visual, 'avatar.png');
  if (artifact.provider.originalRgb) await downloadAsset(artifact.provider.originalRgb, 'original-rgb.png');
  check('structure-then-face-reference-order', isDeepStrictEqual(artifact.provider.referenceImages.map(reference => reference.name), ['structure-reference.png', 'style-reference.png']));
  for (const [index, reference] of artifact.provider.referenceImages.entries()) {
    const content = await downloadAsset(reference, reference.name);
    const edge = index === 0 ? 512 : 256;
    check(reference.name + '-expected-png-dimensions', content.subarray(0, 8).equals(Buffer.from([137, 80, 78, 71, 13, 10, 26, 10])) && content.readUInt32BE(16) === edge && content.readUInt32BE(20) === edge);
  }

  const beforeVoice = nativeCounts();
  proof.nativePlaybackBefore = beforeVoice;
  console.log(JSON.stringify({stage: 'voice-ui-listen', requestId: generationBody.requestId, reusingStoredVoice: proof.voiceAlreadyStoredAtStart}));
  await click('listen-button');
  const end = Date.now() + 420000;
  let voiceArtifact, afterVoice;
  while (Date.now() < end) {
    assert(proof.blockedRequests.length === 0, 'Unexpected network request.');
    const view = await evaluate('({allowed:state.nativeAllowed,hidden:document.hidden,artifact:window.nuntiTest.getArtifact(),button:document.getElementById("listen-button").textContent,notice:document.getElementById("voice-notice").textContent})');
    assert(view.allowed && !view.hidden, 'Vehicle or foreground gate interrupted playback.');
    afterVoice = nativeCounts();
    if (view.artifact?.voice?.status === 'READY' && afterVoice.started > beforeVoice.started && afterVoice.completed > beforeVoice.completed && view.button === '▷') {
      voiceArtifact = view.artifact; break;
    }
    if (view.button === '▷' && afterVoice.completed === beforeVoice.completed) throw new Error('Voice did not complete: ' + view.notice);
    await pause(1000);
  }
  assert(voiceArtifact, 'Timed out waiting for actual native WAV completion.');
  proof.nativePlaybackAfter = afterVoice;
  check('native-generated-wav-started-and-completed', afterVoice.started > beforeVoice.started && afterVoice.completed > beforeVoice.completed);
  const ready = await readApi('/v3/avatars/' + artifact.characterId);
  check('actual-local-qwen-voice-is-ready-and-saved', ready.voice.status === 'READY' && ready.voice.newVoiceGenerated === true && ready.voice.provider === 'LOCAL_QWEN_VOICE_DESIGN' && ready.voice.model === 'mlx-community/Qwen3-TTS-12Hz-1.7B-VoiceDesign-8bit' && !!ready.voice.audio.sha256);
  check('first-listen-keeps-the-original-image', ready.visual.sha256 === artifact.visual.sha256);
  const wav = await downloadAsset(ready.voice.audio, 'voice.wav');
  check('downloaded-audio-is-a-real-wav-file', wav.toString('ascii', 0, 4) === 'RIFF' && wav.toString('ascii', 8, 12) === 'WAVE' && wav.length > 44);
  await fs.writeFile(path.join(out, 'artifact.json'), json(ready), {mode: 0o600});
  proof.identity = {characterId: ready.characterId, imageSha256: ready.visual.sha256, voiceSha256: ready.voice.audio.sha256, voiceDurationMs: ready.voice.audio.durationMs};

  await reloadPage();
  await wait('window.nuntiCapabilities?.voice?.available && state.nativeAllowed && !document.hidden && window.nuntiTest');
  await click('collection-button');
  await wait(`!document.getElementById('collection-view').hidden && state.avatars.some(a=>a.characterId===${JSON.stringify(ready.characterId)}) && document.querySelectorAll('.collection-item').length===state.avatars.length`);
  await clickExpression(`document.querySelectorAll('.collection-item')[state.avatars.findIndex(a=>a.characterId===${JSON.stringify(ready.characterId)})]`, 'saved companion');
  const restored = await wait(`window.nuntiTest.getArtifact()?.characterId===${JSON.stringify(ready.characterId)} && !document.getElementById('result-details').hidden && window.nuntiTest.getArtifact()`);
  check('reload-and-collection-preserve-image-and-voice', restored.visual.sha256 === ready.visual.sha256 && restored.voice.audio.sha256 === ready.voice.audio.sha256 && isDeepStrictEqual(restored.voice.plan, ready.voice.plan));
  const voicePosts = () => proof.network.filter(request => request.method === 'POST' && request.path.endsWith('/voice')).length;
  const postsBeforeCachedListen = voicePosts();
  const cachedBefore = nativeCounts();
  await click('listen-button');
  await wait('document.getElementById("listen-button").textContent==="▷"', 30000);
  const cachedAfter = nativeCounts();
  proof.cachedNativePlayback = {before: cachedBefore, after: cachedAfter};
  check('restored-native-voice-replays-without-new-synthesis', cachedAfter.started > cachedBefore.started && cachedAfter.completed > cachedBefore.completed && voicePosts() === postsBeforeCachedListen);
  const afterRestore = await readApi('/v3/avatars/' + ready.characterId);
  check('saved-image-and-voice-hashes-remain-unchanged', afterRestore.visual.sha256 === ready.visual.sha256 && afterRestore.voice.audio.sha256 === ready.voice.audio.sha256);
  await fs.writeFile(path.join(out, 'restored-artifact.json'), json(afterRestore), {mode: 0o600});
  await evaluate('document.getElementById("listen-button").scrollIntoView({block:"center"})');
  await pause(400);
  await fs.writeFile(path.join(out, 'actual-android.png'), execFileSync(adb, ['-s', serial, 'exec-out', 'screencap', '-p'], {timeout: 15000, maxBuffer: 12 * 1024 * 1024}));
  check('stored-route-used-get-only', proof.network.some(request => request.path === '/v3/route-plans/' + savedPlan.planId && request.method === 'GET') && !proof.network.some(request => request.path === '/v3/route-plans' && request.method !== 'GET'));
  check('no-prohibited-network-or-javascript-errors', proof.blockedRequests.length === 0 && proof.exceptions.length === 0);
  proof.sourceSha256After = await sourceHashes();
  check('production-source-unchanged-during-proof', isDeepStrictEqual(proof.sourceSha256, proof.sourceSha256After));
  proof.status = 'PASS';
} catch (error) {
  proof.error = error.stack || String(error);
  process.exitCode = 1;
} finally {
  if (socket?.readyState === WebSocket.OPEN) {
    await evaluate('window.__nuntiLiveRestoreUUID?.()').catch(() => {});
    await call('Fetch.disable').catch(() => {});
    socket.close();
  }
  proof.finishedAt = new Date().toISOString();
  await fs.writeFile(path.join(attempt, 'verification.json'), json(proof), {mode: 0o600});
  await fs.writeFile(path.join(out, 'verification.json'), json(proof), {mode: 0o600});
  console.log(JSON.stringify({status: proof.status, checks: proof.checks.length, requestId: proof.requestId, error: proof.error, report: path.join(out, 'verification.json')}));
}
