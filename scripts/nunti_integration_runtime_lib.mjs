// Actual-device helpers. Importing this file has no runtime side effects.
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import {execFile, spawn} from 'node:child_process';
import {promisify} from 'node:util';
import {fileURLToPath} from 'node:url';
import {createHash, randomUUID} from 'node:crypto';

export const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
export const packageName = 'ai.nunti.avatar.demo';
export const serial = 'emulator-5554';
export const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
const exec = promisify(execFile);
export const sha = bytes => createHash('sha256').update(bytes).digest('hex');
export async function adb(args, binary = false) {
  const result = await exec(path.join(root, '.local/pm-tools/sdk/platform-tools/adb'), ['-s', serial, ...args.map(String)],
    {encoding: binary ? 'buffer' : 'utf8', timeout: 30000, maxBuffer: 16 * 1024 * 1024});
  return result.stdout;
}
export async function save(out, name, value) {
  await fs.mkdir(out, {recursive: true});
  await fs.writeFile(path.join(out, name), typeof value === 'string' || Buffer.isBuffer(value) ? value : JSON.stringify(value, null, 2) + '\n');
}
export async function consoleRequest(endpoint, values, method) {
  const response = await fetch('http://127.0.0.1:8088' + endpoint + (values ? '?' + new URLSearchParams(values) : ''),
    {method: method || (values ? 'PUT' : 'GET'), signal: AbortSignal.timeout(8000)});
  assert(response.ok, 'Official Console request: ' + response.status); return response.json();
}
export async function readJourney(binary = false) {
  const raw = await adb(['exec-out', 'run-as', packageName, '--user', '10', 'cat', 'files/journeys/latest.json'], true);
  return binary ? raw : JSON.parse(raw);
}
export async function writeFinishedJourney(bytes) {
  assert.notEqual(JSON.parse(bytes).state, 'ACTIVE', 'Only finished owned fixtures or original finished reports may be restored');
  const child = spawn(path.join(root, '.local/pm-tools/sdk/platform-tools/adb'), ['-s', serial, 'exec-in', 'run-as', packageName, '--user', '10', 'sh', '-c', 'cat > files/journeys/latest.json'], {stdio: ['pipe', 'ignore', 'pipe']});
  const done = new Promise((resolve, reject) => {child.on('error', reject);child.on('exit', code => code === 0 ? resolve() : reject(new Error('Latest restore failed ' + code)));});
  child.stdin.end(bytes); await done;
}
export async function capture(out, name, {xml = true} = {}) {
  if (xml) {
    await adb(['shell', 'uiautomator', 'dump', '/sdcard/nunti-integration-ui.xml']);
    await save(out, name + '.xml', await adb(['shell', 'cat', '/sdcard/nunti-integration-ui.xml']));
  }
  await pause(300);
  await save(out, name + '.png', await adb(['exec-out', 'screencap', '-p'], true));
  await save(out, name + '-car-ux.txt', await adb(['shell', 'dumpsys', 'car_service', '--services', 'CarUxRestrictionsManagerService']));
}
export async function tapNative(text) {
  await adb(['shell', 'uiautomator', 'dump', '/sdcard/nunti-integration-ui.xml']);
  const xml = await adb(['shell', 'cat', '/sdcard/nunti-integration-ui.xml']);
  for (const match of xml.matchAll(/<node\s[^>]*>/g)) {
    const node = match[0];
    if (!node.includes('text="' + text + '"') || !node.includes('enabled="true"')) continue;
    const bounds = node.match(/bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"/);
    assert(bounds, 'Native bounds missing'); const [, l, t, r, b] = bounds.map(Number);
    await adb(['shell', 'input', 'tap', Math.round((l + r) / 2), Math.round((t + b) / 2)]); return;
  }
  throw new Error('Native control unavailable: ' + text);
}
export async function connectWebView() {
  const pid = (await adb(['shell', 'pidof', packageName])).trim(); assert(/^\d+$/.test(pid));
  await adb(['forward', 'tcp:9224', 'localabstract:webview_devtools_remote_' + pid]);
  let target;
  for (let i = 0; i < 40; i++) {
    const targets = await (await fetch('http://127.0.0.1:9224/json/list')).json();
    target = targets.find(item => item.type === 'page' && item.url.startsWith('http://127.0.0.1:8768'));
    if (target) break; await pause(250);
  }
  assert(target, 'Actual production Studio WebView is missing');
  const socket = new WebSocket(target.webSocketDebuggerUrl), pending = new Map(), handlers = new Map(); let sequence = 0;
  await new Promise((resolve, reject) => {socket.onopen = resolve; socket.onerror = reject;});
  socket.onmessage = event => {
    const value = JSON.parse(event.data);
    if (value.id) {
      const item = pending.get(value.id); if (!item) return; pending.delete(value.id); clearTimeout(item.timeout);
      if (value.error) item.reject(new Error(JSON.stringify(value.error))); else item.resolve(value.result);
    } else for (const handler of handlers.get(value.method) || []) handler(value.params);
  };
  const command = (method, params = {}) => new Promise((resolve, reject) => {
    const id = ++sequence, timeout = setTimeout(() => {pending.delete(id); reject(new Error('CDP timed out: ' + method));}, 30000);
    pending.set(id, {resolve, reject, timeout}); socket.send(JSON.stringify({id, method, params}));
  });
  async function evaluate(expression) {
    // Chromium can collect an otherwise unowned Image.decode() promise while
    // CDP awaits it. Retain only this test evaluation, then remove the handle.
    const token = 'eval-' + randomUUID();
    const owned = `window.__nuntiRuntimePending??={};window.__nuntiRuntimePending[${JSON.stringify(token)}]=Promise.resolve((0,eval)(${JSON.stringify(expression)}))`;
    try {
      const result = await command('Runtime.evaluate', {expression: owned, returnByValue: true, awaitPromise: true});
      if (result.exceptionDetails) throw new Error(JSON.stringify(result.exceptionDetails)); return result.result?.value;
    } finally {
      await command('Runtime.evaluate', {expression: `if(window.__nuntiRuntimePending){delete window.__nuntiRuntimePending[${JSON.stringify(token)}];if(!Object.keys(window.__nuntiRuntimePending).length)delete window.__nuntiRuntimePending;}`}).catch(() => {});
    }
  }
  async function wait(expression, timeout = 20000) {
    const deadline = Date.now() + timeout;
    while (Date.now() < deadline) {try {const value = await evaluate(expression); if (value) return value;} catch {} await pause(100);}
    throw new Error('WebView condition timed out: ' + expression);
  }
  async function click(selector) {
    const point = await evaluate(`(()=>{const e=document.querySelector(${JSON.stringify(selector)});if(!e||e.disabled)throw new Error('Control unavailable');e.scrollIntoView({block:'center'});const r=e.getBoundingClientRect();if(!r.width||!r.height)throw new Error('Control hidden');return {x:r.x+r.width/2,y:r.y+r.height/2};})()`);
    await command('Input.dispatchMouseEvent', {type: 'mousePressed', button: 'left', clickCount: 1, ...point});
    await command('Input.dispatchMouseEvent', {type: 'mouseReleased', button: 'left', clickCount: 1, ...point});
  }
  await command('Runtime.enable'); await command('Page.enable'); await command('Network.enable');
  return {command, evaluate, wait, click, pid, target: {url: target.url, id: target.id},
    on(method, handler) {handlers.set(method, [...(handlers.get(method) || []), handler]);}, close() {socket.close();}};
}

export async function vehicleSession(out) {
  const prior = await fs.stat(path.join(out, 'original-console.json')).catch(error => {
    if (error.code === 'ENOENT') return null; throw error;
  });
  assert(!prior, 'Use a new output directory; preserve the previous evidence and original-state backup');
  const original = await consoleRequest('/vehicle/state'), originalLatest = await readJourney(true);
  assert.notEqual(JSON.parse(originalLatest).state, 'ACTIVE', 'Never interrupt a pre-existing active journey');
  await save(out, 'original-console.json', original); await save(out, 'original-latest.json', originalLatest);
  const originalNight = await adb(['shell', 'cmd', 'uimode', 'night']);
  const originalAnimator = (await adb(['shell', 'settings', 'get', 'global', 'animator_duration_scale'])).trim();
  await save(out, 'original-night.txt', originalNight); await save(out, 'original-animator.txt', originalAnimator);
  await save(out, 'original-activities.txt', await adb(['shell', 'dumpsys', 'activity', 'activities']));
  let heartbeat = null, client = null;
  return {original, originalLatest, originalNight, originalAnimator,
    async activate() {
      if (heartbeat) return;
      client = 'nunti-integration-' + randomUUID();
      await consoleRequest('/browser/session', {client}, 'POST');
      heartbeat = setInterval(() => consoleRequest('/browser/session', {client}, 'POST').catch(() => {}), 900);
      for (let i = 0; i < 60; i++) {
        if ((await consoleRequest('/vehicle/state')).gear.bridge_ready) {
          await consoleRequest('/vehicle/hvac', {power: original.hvac.power_on ? 1 : 0});
          return;
        }
        await pause(200);
      }
      throw new Error('Official Console DDS not ready');
    },
    async parked() {
      await this.activate();
      await consoleRequest('/vehicle/controls', {speed: 0, accelerator: 0, brake: 0, steering: 0});
      await consoleRequest('/vehicle/gear', {gear: 'Park'}); await pause(500);
    },
    async drive(speed = 30) {
      await this.activate();
      await consoleRequest('/vehicle/gear', {gear: 'Drive'});
      await consoleRequest('/vehicle/controls', {speed, accelerator: 0, brake: 0, steering: 0});
    },
    async restore() {
      // Any owned journey must be finished before restoring its persisted report.
      if (heartbeat) {
        const controls = original.controls;
        await consoleRequest('/vehicle/controls', {speed: controls.speed_kph, accelerator: controls.accelerator_pct, brake: controls.brake_pct, steering: controls.steering_deg});
        await consoleRequest('/vehicle/gear', {gear: original.gear.actual.value});
        await consoleRequest('/vehicle/hvac', {power: original.hvac.power_on ? 1 : 0});
        clearInterval(heartbeat); heartbeat = null;
        await consoleRequest('/browser/session', {client, closing: 1}, 'POST'); await pause(3500);
      }
      const current = await consoleRequest('/vehicle/state');
      await save(out, 'restored-console.json', current);
      assert.equal(current.gear.actual.value, original.gear.actual.value);
      for (const name of ['speed_kph', 'accelerator_pct', 'brake_pct', 'steering_deg']) assert.equal(current.controls[name], original.controls[name]);
      assert.equal(current.hvac.power_on, original.hvac.power_on);
      assert.equal(current.browser.clients, original.browser.clients);
      await save(out, 'restoration.json', {vehicle: true, hvacPower: true,
        latestUnchanged: sha(await readJourney(true)) === sha(originalLatest), originalLatestSha256: sha(originalLatest)});
    },
  };
}
