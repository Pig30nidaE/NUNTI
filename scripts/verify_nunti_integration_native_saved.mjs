#!/usr/bin/env node
// Reopen one already-finished owned review for native visual/fallback checks.
// The original latest bytes are backed up and restored; no new journey starts.
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import {root, packageName, adb, pause, save, sha, readJourney, writeFinishedJourney, capture, connectWebView, vehicleSession} from './nunti_integration_runtime_lib.mjs';
const arg = name => process.argv.find(value => value.startsWith('--' + name + '='))?.slice(name.length + 3);
assert(arg('review') && arg('artifacts'), '--review and --artifacts are required');
const reviewBytes = await fs.readFile(arg('review')), review = JSON.parse(reviewBytes);
assert.equal(review.state, 'FINISHED'); assert.equal(review.muted, true);
const artifact = JSON.parse(await fs.readFile(arg('artifacts'), 'utf8')).find(item => item.slug === 'coast-curious').artifact;
const out = path.resolve(arg('output') || path.join(root, 'docs/redesign/integration-v1/runtime-native-saved-' + Date.now()));
const fallbackOnly = process.argv.includes('--fallback-only');
const report = {status: 'RUNNING', surface: 'ACTUAL_PRODUCTION_JOURNEY_SAVED_REPORT', sourceSessionId: review.sessionId,
  sourceReportSha256: sha(reviewBytes), checks: [], newJourneyStarted: false};
let vehicle, originalNight, taskId, web;
const check = (name, condition) => {assert(condition, name);report.checks.push({name, status: 'PASS'});console.log('PASS', name);};
async function openSaved(bytes) {
  web?.close(); web = null;
  await adb(['shell', 'am', 'force-stop', '--user', '10', packageName]); await writeFinishedJourney(bytes);
  await adb(['shell', 'am', 'start', '-W', '--user', '10', '-n', packageName + '/ai.nunti.app.MainActivity']);
  web = await connectWebView(); await web.wait('window.NuntiBirth && state.nativeAllowed');
  await web.evaluate(`window.nuntiTest.showArtifact(${JSON.stringify(artifact)},false)`);
  await web.click('#journey-options-open'); await web.click('#previous-journey'); await pause(1200);
}
async function screen(name) {
  await capture(out, name); await save(out, name + '-latest.json', await readJourney());
  await save(out, name + '-activities.txt', await adb(['shell', 'dumpsys', 'activity', 'activities']));
}
try {
  vehicle = await vehicleSession(out); originalNight = vehicle.originalNight.match(/Night mode:\s*(\w+)/i)?.[1];
  if (!fallbackOnly) {
  await openSaved(reviewBytes); await screen('01-post-trip-day');
  check('existing-finished-owned-review-reopens', (await readJourney()).sessionId === review.sessionId);
  await adb(['shell', 'cmd', 'uimode', 'night', 'yes']); await pause(1000); await screen('02-post-trip-night');
  const activities = await adb(['shell', 'dumpsys', 'activity', 'activities']);
  taskId = activities.match(/topResumedActivity=ActivityRecord\{[^\n]*ai\.nunti\.avatar\.demo\/[^\n]* t(\d+)\}/)?.[1];assert(taskId);
  await adb(['shell', 'am', 'task', 'resize', taskId, '853', '90', '1683', '1300']); await pause(800); await screen('03-post-trip-compact-night');
  await adb(['shell', 'cmd', 'uimode', 'night', 'no']); await pause(800); await screen('04-post-trip-compact-day');
  await adb(['shell', 'am', 'task', 'resize', taskId, '853', '90', '2535', '1300']); await pause(500);
  }
  const broken = {...review, imageFile: '/data/user/10/' + packageName + '/files/journeys/assets/integration-missing-image.png'};
  await save(out, 'controlled-missing-image-report.json', broken);
  await openSaved(Buffer.from(JSON.stringify(broken))); await screen('05-native-image-fallback');
  const xml = await fs.readFile(path.join(out, '05-native-image-fallback.xml'), 'utf8');
  check('native-missing-image-exposes-approved-base-description', xml.includes('여정 그림을 사용할 수 없어 기본 모습을 보여줘요'));
  report.status = 'PASS';
} catch (error) {report.status = 'FAIL';report.error = String(error.stack || error);console.error(report.error);}
finally {
  web?.close();
  if (originalNight) await adb(['shell', 'cmd', 'uimode', 'night', originalNight]).catch(() => {});
  if (taskId) await adb(['shell', 'am', 'task', 'resize', taskId, '853', '90', '2535', '1300']).catch(() => {});
  if (vehicle) try {
    await adb(['shell', 'am', 'force-stop', '--user', '10', packageName]); await writeFinishedJourney(vehicle.originalLatest);
    check('original-latest-exactly-restored', sha(await readJourney(true)) === sha(vehicle.originalLatest));
    await vehicle.restore(); await adb(['shell', 'am', 'start', '-W', '--user', '10', '-n', packageName + '/ai.nunti.app.MainActivity']);
    report.vehicleRestored = true;
  } catch (error) {report.status = 'FAIL';report.restorationError = String(error.stack || error);console.error(report.restorationError);}
  await save(out, 'report.json', report);
}
console.log(JSON.stringify({status: report.status, checks: report.checks.length, out}));
if (report.status !== 'PASS') process.exitCode = 1;
