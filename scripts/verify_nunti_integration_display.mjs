#!/usr/bin/env node
// Actual native day/night, window size, background and resource observations.
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import {spawn} from 'node:child_process';
import {root, packageName, adb, pause, save, capture, connectWebView, vehicleSession} from './nunti_integration_runtime_lib.mjs';

const argument = name => process.argv.find(value => value.startsWith('--' + name + '='))?.slice(name.length + 3);
const source = argument('artifacts'); assert(source, '--artifacts=<studio-run/artifacts.json> is required');
const artifact = JSON.parse(await fs.readFile(source, 'utf8')).find(item => item.slug === 'coast-curious').artifact;
const out = path.resolve(argument('output') || path.join(root, 'docs/redesign/integration-v1/runtime-display-' + Date.now()));
const report = {status: 'RUNNING', surface: 'ACTUAL_PRODUCTION_ANDROID', checks: []};
let vehicle, web, taskId, oldNight, oldAnimator, originalReduced;
const check = (name, condition, details) => {assert(condition, name); report.checks.push({name, status: 'PASS', ...(details ? {details} : {})}); console.log('PASS', name);};
async function show() {await web.evaluate(`message('');window.nuntiTest.showArtifact(${JSON.stringify(artifact)},false)`); await web.wait('window.NuntiBirth.diagnostics().finalReady');}
async function restoreAnimator() {
  if (oldAnimator === 'null') {
    // Settings deletion alone leaves the emulator's ValueAnimator cache at its
    // last explicit value. Restore its observed enabled default, then unset.
    await adb(['shell', 'settings', 'put', 'global', 'animator_duration_scale', '1']);
    await pause(500);
    await adb(['shell', 'settings', 'delete', 'global', 'animator_duration_scale']);
  } else if (oldAnimator) await adb(['shell', 'settings', 'put', 'global', 'animator_duration_scale', oldAnimator]);
}
async function screen(name) {
  await save(out, name + '-state.json', await web.evaluate('({motion:window.NuntiBirth.diagnostics(),allowed:state.nativeAllowed,theme:document.documentElement.dataset.theme,width:innerWidth,height:innerHeight})'));
  await capture(out, name);
}
async function currentTask() {
  const activities = await adb(['shell', 'dumpsys', 'activity', 'activities']);
  const id = activities.match(/topResumedActivity=ActivityRecord\{[^\n]*ai\.nunti\.avatar\.demo\/[^\n]* t(\d+)\}/)?.[1];
  assert(id, 'Foreground app task was not found'); return id;
}
async function replay() {await web.click('#replay-button'); await web.wait('window.NuntiBirth.diagnostics().status==="RUNNING"');}
try {
  vehicle = await vehicleSession(out); oldNight = vehicle.originalNight.match(/Night mode:\s*(\w+)/i)?.[1];
  assert(oldNight && ['yes', 'no', 'auto', 'custom'].includes(oldNight), 'Recognized original Android night setting');
  oldAnimator = vehicle.originalAnimator;
  await adb(['shell', 'am', 'start', '-W', '--user', '10', '-n', packageName + '/ai.nunti.app.MainActivity']);
  web = await connectWebView(); await web.wait('window.NuntiBirth && state.nativeAllowed');
  originalReduced = await web.evaluate('localStorage.getItem("nunti-reduced-motion")');
  await web.evaluate('window.NuntiBirth.setReduced(false)'); await show(); taskId = await currentTask();
  await adb(['shell', 'cmd', 'uimode', 'night', 'yes']);
  await web.wait('document.documentElement.dataset.theme==="night"'); await show(); await screen('night-reveal');
  await web.click('#new-button'); await screen('night-pre-trip');
  check('native-configuration-drives-night-theme', await web.evaluate('document.documentElement.dataset.theme==="night"'));
  await adb(['shell', 'cmd', 'uimode', 'night', 'no']); await web.wait('document.documentElement.dataset.theme==="day"');
  await show(); taskId = await currentTask();
  await adb(['shell', 'am', 'task', 'resize', taskId, '853', '90', '1683', '1300']);
  await web.wait('Math.abs(innerWidth-830)<1.1'); await screen('compact-reveal'); await web.click('#new-button'); await screen('compact-pre-trip');
  check('actual-narrow-window-calibrates-830-physical-pixels', await web.evaluate('Math.abs(innerWidth-830)<1.1'));
  await adb(['shell', 'am', 'task', 'resize', taskId, '853', '90', '2535', '1300']);
  await web.wait('Math.abs(innerWidth-1682)<1.1'); await show();
  await replay(); await pause(700);
  await adb(['shell', 'am', 'start', '-W', '--user', '10', '-n', 'ai.umos.maps.android.navigation.app/.MainActivity']);
  await pause(500); const background = await web.evaluate('({allowed:state.nativeAllowed,hidden:document.hidden,motion:window.NuntiBirth.diagnostics()})');
  await save(out, 'background-state.json', background);
  await save(out, 'background-activities.txt', await adb(['shell', 'dumpsys', 'activity', 'activities']));
  check('actual-background-stops-motion', background.motion.status !== 'RUNNING' && (!background.allowed || background.hidden), background);
  await adb(['shell', 'am', 'start', '-W', '--user', '10', '-n', packageName + '/ai.nunti.app.MainActivity']);
  await web.wait('state.nativeAllowed && !document.hidden'); await pause(500);
  check('foreground-return-remains-static', await web.evaluate('window.NuntiBirth.diagnostics().status==="SETTLED"')); await screen('foreground-return');
  await replay(); await pause(500); await adb(['shell', 'settings', 'put', 'global', 'animator_duration_scale', '0']);
  await web.wait('window.NuntiBirth.diagnostics().reducedMotion');
  check('native-system-reduced-setting-stops-motion', await web.evaluate('window.NuntiBirth.diagnostics().status==="SETTLED"'));
  await screen('system-reduced');
  await restoreAnimator();
  await web.wait('!window.NuntiBirth.diagnostics().reducedMotion');
  check('system-reduced-restoration-does-not-autoplay', await web.evaluate('window.NuntiBirth.diagnostics().status==="SETTLED"'));
  await adb(['shell', 'dumpsys', 'gfxinfo', packageName, 'reset']);
  const pid = (await adb(['shell', 'pidof', packageName])).trim();
  const cpu = adb(['shell', 'top', '-b', '-n', '6', '-d', '1', '-p', pid]);
  await replay(); await web.wait('window.NuntiBirth.diagnostics().status==="SETTLED"');
  await save(out, 'performance-motion.json', await web.evaluate('window.NuntiBirth.diagnostics()'));
  await save(out, 'performance-top.txt', await cpu);
  await save(out, 'performance-gfxinfo-unrecorded.txt', await adb(['shell', 'dumpsys', 'gfxinfo', packageName]));
  await save(out, 'performance-meminfo.txt', await adb(['shell', 'dumpsys', 'meminfo', packageName]));
  // Video is a separate run; it is not mixed with the unrecorded measurement.
  const deviceVideo = '/sdcard/nunti-integration-motion.mp4';
  const recorder = spawn(path.join(root, '.local/pm-tools/sdk/platform-tools/adb'), ['-s', 'emulator-5554', 'shell', 'screenrecord', '--time-limit', '7', '--bit-rate', '5000000', deviceVideo], {stdio: 'ignore'});
  const recordingDone = new Promise((resolve, reject) => {recorder.on('error', reject); recorder.on('exit', code => code === 0 ? resolve() : reject(new Error('screenrecord failed ' + code)));});
  await pause(700); await replay(); await web.wait('window.NuntiBirth.diagnostics().status==="SETTLED"'); await recordingDone;
  await adb(['pull', deviceVideo, path.join(out, 'production-motion.mp4')]);
  check('actual-production-motion-recorded', (await fs.stat(path.join(out, 'production-motion.mp4'))).size > 10000);
  await screen('final-wide-day'); report.status = 'PASS';
} catch (error) {report.status = 'FAIL'; report.error = String(error.stack || error); console.error(report.error);}
finally {
  if (oldNight) await adb(['shell', 'cmd', 'uimode', 'night', oldNight]).catch(() => {});
  if (oldAnimator) await restoreAnimator().catch(() => {});
  if (taskId) await adb(['shell', 'am', 'task', 'resize', taskId, '853', '90', '2535', '1300']).catch(() => {});
  if (web) {
    await web.evaluate(`window.NuntiBirth.setReduced(${originalReduced === 'true'});${originalReduced === null ? 'localStorage.removeItem("nunti-reduced-motion")' : ''}`).catch(() => {});
    web.close();
  }
  if (vehicle) try {await vehicle.restore(); report.vehicleRestored = true;} catch (error) {report.status = 'FAIL'; report.restorationError = String(error);}
  await save(out, 'final-night.txt', await adb(['shell', 'cmd', 'uimode', 'night']));
  await save(out, 'final-animator.txt', await adb(['shell', 'settings', 'get', 'global', 'animator_duration_scale']));
  await save(out, 'final-activities.txt', await adb(['shell', 'dumpsys', 'activity', 'activities']));
  await save(out, 'report.json', report);
}
console.log(JSON.stringify({status: report.status, checks: report.checks.length, out}));
if (report.status !== 'PASS') process.exitCode = 1;
