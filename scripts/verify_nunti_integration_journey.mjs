#!/usr/bin/env node
// A single owned LIVE journey through the existing bridge/service. Saved image
// only; no generated/prepared voice. Original latest.json is restored exactly.
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import {spawn} from 'node:child_process';
import {root, packageName, adb, pause, save, sha, readJourney, tapNative, capture, connectWebView, vehicleSession} from './nunti_integration_runtime_lib.mjs';
const argument = name => process.argv.find(value => value.startsWith('--' + name + '='))?.slice(name.length + 3);
const source = argument('artifacts'); assert(source, '--artifacts=<studio-run/artifacts.json> is required');
const artifact = JSON.parse(await fs.readFile(source, 'utf8')).find(item => item.slug === 'coast-curious').artifact;
assert(!artifact.voice?.audio, 'Choose a saved artifact without playable greeting audio');
const out = path.resolve(argument('output') || path.join(root, 'docs/redesign/integration-v1/runtime-journey-' + Date.now()));
const report = {status: 'RUNNING', surface: 'ACTUAL_PRODUCTION_JOURNEY_ACTIVITY', characterId: artifact.characterId, checks: [], paidApiCalls: 0, voiceGenerationCalls: 0};
let vehicle, web, owned, originalNight, taskId;
const check = (name, condition, details) => {assert(condition, name);report.checks.push({name, status: 'PASS', ...(details ? {details} : {})});console.log('PASS', name);};
async function waitState(predicate, timeout = 25000) {
  const deadline = Date.now() + timeout;
  while (Date.now() < deadline) {const current = await readJourney(); if (predicate(current)) return current; await pause(200);}
  throw new Error('Native journey state timeout');
}
async function screen(name) {
  await save(out, name + '-state.json', await readJourney()); await capture(out, name);
  await save(out, name + '-activities.txt', await adb(['shell', 'dumpsys', 'activity', 'activities']));
}
async function restoreLatest(bytes) {
  const child = spawn(path.join(root, '.local/pm-tools/sdk/platform-tools/adb'), ['-s', 'emulator-5554', 'exec-in', 'run-as', packageName, '--user', '10', 'sh', '-c', 'cat > files/journeys/latest.json'], {stdio: ['pipe', 'ignore', 'pipe']});
  const done = new Promise((resolve, reject) => {child.on('error', reject);child.on('exit', code => code === 0 ? resolve() : reject(new Error('Restore latest failed ' + code)));});
  child.stdin.end(bytes); await done;
}
try {
  vehicle = await vehicleSession(out); originalNight = vehicle.originalNight.match(/Night mode:\s*(\w+)/i)?.[1];
  await vehicle.parked();
  await adb(['shell', 'am', 'start', '-W', '--user', '10', '-n', packageName + '/ai.nunti.app.MainActivity']);
  web = await connectWebView(); await web.wait('window.NuntiBirth && state.nativeAllowed');
  await web.evaluate(`window.nuntiTest.showArtifact(${JSON.stringify(artifact)},false)`);
  await web.evaluate('document.getElementById("journey-source").value="LIVE"');
  await web.click('#journey-button');
  const active = await waitState(value => value.state === 'ACTIVE' && value.characterId === artifact.characterId); owned = active.sessionId;
  check('real-native-bridge-starts-owned-live-journey', active.source === 'LIVE', {sessionId: owned});
  check('review-has-no-playable-audio', Object.keys(active.voices || {}).length === 0);
  await tapNative('음성 끄기'); await waitState(value => value.muted === true); await screen('01-active-parked');
  check('real-mute-control-updates-service', (await readJourney()).muted === true);
  await vehicle.drive(30);
  const driving = await waitState(value => value.gear === 'D' && value.speedKmh >= 29 && value.canFinish === false);
  await pause(1300); await screen('02-driving-actual');
  check('actual-driving-disables-finish', driving.canFinish === false && driving.state === 'ACTIVE');
  // Visibility is judged from the screenshot, not just the underlying hierarchy.
  report.drivingVisibility = 'SCREENSHOT_REQUIRES_VISUAL_REVIEW_PLATFORM_BLOCK_EXPECTED';
  await vehicle.parked(); await waitState(value => value.canFinish === true); await tapNative('여정 마치기');
  await waitState(value => value.state === 'FINISHED'); await screen('03-post-trip-day');
  check('actual-parked-finish-produces-report', (await readJourney()).state === 'FINISHED');
  await adb(['shell', 'cmd', 'uimode', 'night', 'yes']); await pause(1200); await screen('04-post-trip-night');
  const activities = await adb(['shell', 'dumpsys', 'activity', 'activities']);
  taskId = activities.match(/topResumedActivity=ActivityRecord\{[^\n]*ai\.nunti\.avatar\.demo\/[^\n]* t(\d+)\}/)?.[1]; assert(taskId);
  await adb(['shell', 'am', 'task', 'resize', taskId, '853', '90', '1683', '1300']); await pause(1000); await screen('05-post-trip-compact-night');
  await adb(['shell', 'cmd', 'uimode', 'night', 'no']); await pause(1000); await screen('06-post-trip-compact-day');
  await adb(['shell', 'am', 'task', 'resize', taskId, '853', '90', '2535', '1300']); await pause(500);
  report.status = 'PASS';
} catch (error) {report.status = 'FAIL';report.error = String(error.stack || error);console.error(report.error);}
finally {
  web?.close();
  if (originalNight) await adb(['shell', 'cmd', 'uimode', 'night', originalNight]).catch(() => {});
  if (taskId) await adb(['shell', 'am', 'task', 'resize', taskId, '853', '90', '2535', '1300']).catch(() => {});
  if (vehicle) {
    try {
      if (owned) {
        await vehicle.parked();
        const current = await readJourney();
        assert.equal(current.sessionId, owned, 'Never overwrite an unrelated session');
        if (current.state === 'ACTIVE') {await waitState(value => value.canFinish === true);await tapNative('여정 마치기');await waitState(value => value.state === 'FINISHED');}
        await save(out, 'owned-review-final.json', await readJourney());
        await adb(['shell', 'am', 'force-stop', '--user', '10', packageName]);
        await restoreLatest(vehicle.originalLatest);
        check('original-latest-restored-byte-for-byte', sha(await readJourney(true)) === sha(vehicle.originalLatest));
      }
      await vehicle.restore(); report.vehicleRestored = true;
      await adb(['shell', 'am', 'start', '-W', '--user', '10', '-n', packageName + '/ai.nunti.app.MainActivity']);
      await capture(out, '07-restored-pre-trip');
    } catch (error) {report.status = 'FAIL';report.restorationError = String(error.stack || error);console.error(report.restorationError);}
  }
  await save(out, 'report.json', report);
}
console.log(JSON.stringify({status: report.status, checks: report.checks.length, out}));
if (report.status !== 'PASS') process.exitCode = 1;
