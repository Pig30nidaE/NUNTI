#!/usr/bin/env node
// Execute the production controller with real packaged bytes and deterministic
// clocks. Canvas/Image are boundaries; these tests do not prove rendered pixels.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import {createHash, webcrypto} from 'node:crypto';
import {fileURLToPath} from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const source = fs.readFileSync(path.join(root, 'prototypes/avatar_generator/nunti-transformation.js'), 'utf8');
const assetRoot = path.join(root, 'prototypes/avatar_generator/nunti-motion');
const manifest = JSON.parse(fs.readFileSync(path.join(assetRoot, 'manifest.json'), 'utf8'));
const sampleRoot = path.join(root, 'docs/redesign/route-variants-v1/samples');
const clone = value => JSON.parse(JSON.stringify(value));
const sample = (name = 'coast-curious') => {
  const design = JSON.parse(fs.readFileSync(path.join(sampleRoot, name, 'render-metadata.json'), 'utf8'));
  return {mediaOrigin: 'LOCAL_LAYERS', displayName: '눈티', design};
};
function deferred() {
  let resolve, reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return {promise, resolve, reject};
}

function harness({fetchOverride, persistedReduced = false} = {}) {
  const frames = new Map(), events = new Map(), draws = [], requests = [], published = [];
  let time = 0, sequence = 0, permitted = true, foreground = true;
  const finalImage = {name: 'EXACT_SERVER_FINAL'};
  const store = new Map([['nunti-reduced-motion', String(persistedReduced)]]);
  const media = {matches: false, addEventListener(name, fn) {events.set(name, fn);}};
  const ctx = {
    globalAlpha: 1, save() {}, restore() {}, setTransform() {}, clearRect() {},
    translate() {}, scale() {}, beginPath() {}, rect() {}, clip() {}, arc() {}, fill() {},
    drawImage(image, ...args) {draws.push({image, args, alpha: this.globalAlpha});},
  };
  const canvas = {width: 0, height: 0, getBoundingClientRect: () => ({width: 768, height: 768}),
    getContext: () => ctx, setAttribute() {}, toDataURL: () => 'data:image/png;base64,BOUNDARY_STUB'};
  const box = {
    window: {NuntiMotionManifest: clone(manifest)}, console, crypto: webcrypto, Blob,
    URL: {createObjectURL: () => 'blob:test/' + ++sequence, revokeObjectURL() {}},
    Image: class {naturalWidth = 768; naturalHeight = 768; async decode() {}},
    localStorage: {getItem: key => store.get(key), setItem: (key, value) => store.set(key, value)},
    matchMedia: () => media, devicePixelRatio: 1, performance: {now: () => time},
    requestAnimationFrame(fn) {const id = ++sequence; frames.set(id, fn); return id;},
    cancelAnimationFrame(id) {frames.delete(id);},
    document: {createElement: () => canvas},
    async fetch(url) {
      requests.push(url);
      if (fetchOverride) {
        const result = fetchOverride(url);
        if (result !== undefined) return result;
      }
      assert.ok(url.startsWith('/nunti-motion/'));
      const relative = url.slice('/nunti-motion/'.length);
      assert.ok(manifest.files[relative], 'Only packaged manifest paths may be fetched');
      const bytes = fs.readFileSync(path.join(assetRoot, relative));
      return {ok: true, arrayBuffer: async () => bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength)};
    },
  };
  vm.createContext(box);
  vm.runInContext(source, box, {filename: 'nunti-transformation.js'});
  const api = box.window.NuntiTransformation;
  const controller = api.create({canvas, allowed: () => permitted, visible: () => foreground,
    onFrame: state => published.push(clone(state))});
  return {api, controller, draws, requests, frames, published, finalImage, store, media,
    allow(value) {permitted = value;}, visible(value) {foreground = value;},
    tick(ms) {time = ms; const waiting = [...frames.values()]; frames.clear(); for (const fn of waiting) fn(ms);},
    systemReduced(value) {media.matches = value; events.get('change')?.();},
    show(value = sample(), play = true) {return controller.show(value, finalImage, play);},
  };
}

const results = [];
async function check(name, run) {
  try {await run(); results.push({name, status: 'PASS'});}
  catch (error) {results.push({name, status: 'FAIL', error: String(error.stack || error)});}
}

await check('all nine persisted AvatarSpecs resolve their real layer contract; base has no changes', () => {
  const h = harness();
  for (const destination of ['coast', 'mountain', 'city']) for (const mood of ['calm', 'curious', 'adventurous']) {
    const value = sample(destination + '-' + mood), before = JSON.stringify(value);
    const paths = h.api.pathsFor(value);
    assert.ok(paths?.hasChanges); assert.equal(paths.expression, 'expression-' + mood + '.png');
    assert.equal(JSON.stringify(value), before, 'AvatarSpec remains immutable');
  }
  assert.equal(h.api.pathsFor(sample('base')).hasChanges, false);
});
await check('malformed, future, modified or failed renderer contracts are refused', () => {
  const h = harness();
  for (const mutate of [a => {delete a.design;}, a => {a.design.renderStatus = 'FALLBACK';},
    a => {a.mediaOrigin = 'LOCAL_RENDER';}, a => {a.design.avatarSpec.assetVersion = 'future';},
    a => {a.design.avatarSpec.routeVariant = 3;}, a => {a.design.avatarSpec.destinationMotif = '../escape';},
    a => {a.design.avatarSpec.layers.reverse();}, a => {a.design.layerAssets['core/body.png'] = 'modified';}]) {
    const value = sample(); mutate(value); assert.equal(h.api.pathsFor(value), null);
  }
});
await check('4-second timeline keeps expression last with finite monotone tracks', () => {
  const h = harness(); assert.equal(h.api.duration, 4000);
  assert.equal(h.api.timeline(2850).expression, 0); assert.equal(h.api.timeline(3050).expression, 1);
  for (const key of ['road', 'scarf', 'pocket', 'expression']) {
    let previous = 0;
    for (let t = 0; t <= 4000; t += 10) {const value = h.api.timeline(t)[key]; assert.ok(value >= previous && value <= 1); previous = value;}
    assert.equal(previous, 1);
  }
});
await check('real package hashes decode and playback settles to the exact supplied final image', async () => {
  const h = harness(); await h.controller.loading(); await h.show();
  assert.equal(h.controller.diagnostics().status, 'RUNNING'); assert.equal(h.frames.size, 1);
  for (const time of [0, 1000, 2200, 3000]) {h.tick(time); assert.ok(h.draws.at(-1));}
  h.tick(4000); assert.equal(h.controller.diagnostics().reason, 'COMPLETED');
  assert.equal(h.controller.diagnostics().elapsedMs, 4000); assert.equal(h.frames.size, 0);
  assert.equal(h.draws.at(-1).image, h.finalImage);
});
await check('an earlier first RAF timestamp cannot report negative elapsed progress', async () => {
  const h = harness(); await h.show(); h.tick(-8.5);
  assert.equal(h.controller.diagnostics().elapsedMs, 0);
  h.tick(4000); assert.equal(h.controller.diagnostics().elapsedMs, 4000);
  assert.equal(h.controller.diagnostics().status, 'SETTLED');
});
await check('park permission and foreground are checked before every next frame', async () => {
  for (const mode of ['restriction', 'background']) {
    const h = harness(); await h.show(); h.tick(1000);
    if (mode === 'restriction') h.allow(false); else h.visible(false);
    h.tick(1050); const state = h.controller.diagnostics();
    assert.equal(state.status, 'SETTLED'); assert.equal(state.reason, mode === 'restriction' ? 'RESTRICTED' : 'BACKGROUNDED');
    assert.equal(state.elapsedMs, 4000); assert.equal(h.frames.size, 0);
  }
});
await check('skip and reduced-motion controls settle and never resume automatically', async () => {
  for (const mode of ['skip', 'user', 'system']) {
    const h = harness(); await h.show(); h.tick(1000);
    if (mode === 'skip') h.controller.stop('SKIPPED');
    else if (mode === 'user') h.controller.setReduced(true); else h.systemReduced(true);
    assert.equal(h.controller.diagnostics().elapsedMs, 4000); assert.equal(h.frames.size, 0);
    if (mode === 'user') {assert.equal(h.store.get('nunti-reduced-motion'), 'true'); h.controller.setReduced(false);}
    if (mode === 'system') h.systemReduced(false);
    assert.equal(h.frames.size, 0); assert.equal(h.draws.at(-1).image, h.finalImage);
  }
});
await check('base, existing result, denied gate and persisted reduced preference start without motion', async () => {
  for (const mode of ['base', 'existing', 'denied', 'reduced']) {
    const h = harness({persistedReduced: mode === 'reduced'}); if (mode === 'denied') h.allow(false);
    await h.show(mode === 'base' ? sample('base') : sample(), mode !== 'existing');
    assert.equal(h.frames.size, 0);
    assert.ok(h.requests.every(url => url === '/nunti-motion/base.png'), 'Static display may only preload the base');
    assert.equal(h.controller.diagnostics().elapsedMs, 4000);
  }
});
await check('a corrupt or unavailable layer falls back to the supplied final without partial playback', async () => {
  for (const corrupt of [false, true]) {
    const h = harness({fetchOverride: url => url.endsWith('core.png') ?
      (corrupt ? {ok: true, arrayBuffer: async () => new Uint8Array(manifest.files['core.png'].bytes).buffer} : {ok: false}) : undefined});
    await h.show(); assert.equal(h.controller.diagnostics().reason, 'LAYER_ASSET_FAILURE');
    assert.equal(h.frames.size, 0); assert.equal(h.draws.at(-1).image, h.finalImage);
  }
});
await check('permission revoked during asynchronous loading cannot restart animation', async () => {
  const pending = deferred();
  const h = harness({fetchOverride: url => url.endsWith('core.png') ? pending.promise : undefined});
  const show = h.show(); h.allow(false);
  const bytes = fs.readFileSync(path.join(assetRoot, 'core.png'));
  pending.resolve({ok: true, arrayBuffer: async () => bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength)});
  await show; assert.equal(h.frames.size, 0); assert.equal(h.controller.diagnostics().reason, 'RESTRICTED');
});
await check('late canceled loading failure cannot overwrite a newer settled result', async () => {
  const pending = deferred();
  const h = harness({fetchOverride: url => url.endsWith('/base.png') ? pending.promise : undefined});
  const loading = h.controller.loading(); await h.show(sample(), false);
  pending.reject(new Error('owned old request failed')); await loading;
  assert.equal(h.controller.diagnostics().status, 'SETTLED'); assert.equal(h.controller.diagnostics().reason, 'STATIC');
  assert.equal(h.controller.diagnostics().finalReady, true);
});
await check('system reduced motion during layer loading cancels ownership even when toggled off again', async () => {
  const pending = deferred();
  const h = harness({fetchOverride: url => url.endsWith('core.png') ? pending.promise : undefined});
  const show = h.show();
  assert.equal(h.controller.diagnostics().status, 'LOADING');
  h.controller.appearance({systemReducedMotion: true});
  h.controller.appearance({systemReducedMotion: false});
  const bytes = fs.readFileSync(path.join(assetRoot, 'core.png'));
  pending.resolve({ok: true, arrayBuffer: async () => bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength)});
  await show;
  assert.equal(h.frames.size, 0); assert.equal(h.controller.diagnostics().status, 'SETTLED');
  assert.equal(h.controller.diagnostics().reason, 'REDUCED_MOTION');
  assert.equal(h.draws.at(-1).image, h.finalImage);
});
await check('switching renderer releases the canvas and cancels late layer drawing', async () => {
  const pending = deferred();
  const h = harness({fetchOverride: url => url.endsWith('core.png') ? pending.promise : undefined});
  const show = h.show(); h.controller.clear(); const count = h.draws.length;
  const bytes = fs.readFileSync(path.join(assetRoot, 'core.png'));
  pending.resolve({ok: true, arrayBuffer: async () => bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength)});
  await show; h.controller.redraw(); h.controller.appearance({systemReducedMotion: true});
  assert.equal(h.draws.length, count); assert.equal(h.frames.size, 0);
  assert.equal(h.controller.diagnostics().active, false); assert.equal(h.controller.capture(4000), null);
});
await check('diagnostic capture obeys the actual gate and foreground boundaries', async () => {
  const h = harness(); await h.show();
  assert.ok(h.controller.capture(2200)); assert.equal(h.controller.diagnostics().elapsedMs, 2200);
  h.allow(false); assert.equal(h.controller.capture(4000), null);
  h.allow(true); h.visible(false); assert.equal(h.controller.capture(4000), null);
});

console.log(JSON.stringify({status: results.every(item => item.status === 'PASS') ? 'PASS' : 'FAIL',
  surface: 'PRODUCTION_CONTROLLER_VM_REAL_ASSET_BYTES_STUB_CANVAS', sourceSha256: createHash('sha256').update(source).digest('hex'),
  checks: results.length, passed: results.filter(item => item.status === 'PASS').length,
  networkRequests: 0, deviceChanges: 0, paidApiCalls: 0, results}, null, 2));
if (results.some(item => item.status === 'FAIL')) process.exitCode = 1;
