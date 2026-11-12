#!/usr/bin/env node
// Run the real UI scripts with in-memory DOM, native bridge and HTTP responses.
// No device, network, image generation, audio or recording is used.
import assert from 'node:assert/strict';
import {createHash, randomUUID} from 'node:crypto';
import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import vm from 'node:vm';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const sources = {};
for (const name of ['studio.js', 'navigation.js']) {
  sources[name] = await fs.readFile(path.join(root, 'prototypes/avatar_generator', name), 'utf8');
}
const clone = value => JSON.parse(JSON.stringify(value));
const flush = async () => { for (let i = 0; i < 30; i++) await Promise.resolve(); };

function element() {
  const listeners = new Map();
  return {
    get value() { return this._value || ''; },
    set value(value) { this._value = String(value); },
    checked: false, disabled: false, hidden: false, textContent: '', dataset: {},
    parentElement: {before() {}},
    selectedOptions: [{disabled: false}], classList: {add() {}, toggle() {}},
    addEventListener(type, listener) {
      if (!listeners.has(type)) listeners.set(type, []);
      listeners.get(type).push(listener);
    },
    dispatchEvent(event) {
      for (const listener of listeners.get(event.type) || []) listener(event);
      this['on' + event.type]?.(event);
    },
    getBoundingClientRect: () => ({width: 0, height: 0}),
    removeAttribute() {}, replaceChildren() {}, append() {}, close() {}, showModal() {},
    querySelector() { return element(); },
  };
}

function makePlan(input) {
  const planId = createHash('sha256').update(JSON.stringify(input)).digest('hex');
  const points = [[0.05, 0.95], [0.45, 0.35], [0.95, 0.05]];
  return {
    planId, origin: clone(input.origin), destination: clone(input.destination),
    nativeSnapshot: input.nativeSnapshot ? clone(input.nativeSnapshot) : null,
    geometry: {distanceMeters: 27000, durationSeconds: 1740, coordinates: [[127.0953, 37.4051], [126.9283, 37.5259]]},
    retrieval: {externalRequestMade: false},
    route: {points, inputOrigin: 'API_ROUTE', apiPlanId: planId, sourceLabel: 'In-memory OSRM test response'},
  };
}

async function harness({mockSkinMode, companionRigVersion} = {}) {
  const elements = new Map(), timers = [], calls = [], commands = [], plans = new Map();
  const get = id => {
    if (!elements.has(id)) elements.set(id, element());
    return elements.get(id);
  };
  let native = {
    source: 'PLEOS_NAVI_HELPER_API', sessionId: 'test-session', revision: 1,
    sequence: 10, status: 'CONNECTED', connected: true, routeLifecycle: 'READY',
    destination: {latitude: 37.5259, longitude: 126.9283, name: '더현대서울', remainDistance: 27000},
    currentLocation: {latitude: 37.4051, longitude: 127.0953, routeId: 'native-route-1'},
    routeState: {naviMode: 'ROUTE_GUIDING', routeOption: 'RECOMMENDED', isRouting: false},
    events: [],
  };
  let deferredPlan = null;
  const context = {
    console, crypto: {randomUUID}, devicePixelRatio: 1, performance: {now: () => 0},
    matchMedia: () => ({matches: true}), requestAnimationFrame: () => 1, cancelAnimationFrame() {},
    setTimeout(callback) { timers.push(callback); return timers.length; }, clearTimeout() {},
    localStorage: {getItem: () => null, setItem() {}},
    document: {hidden: false, getElementById: get, querySelectorAll: () => [], addEventListener() {}, createElement: element},
    window: {
      addEventListener() {},
      ...(typeof mockSkinMode === 'boolean' ? {NuntiSkins: {MOCK_SKIN_MODE: mockSkinMode, assertRequest() {}}} : {}),
      NuntiNative: {
        getNavigationSnapshot: () => JSON.stringify(native),
        navigationCommand(command, payload) {
          commands.push({command, payload: JSON.parse(payload)});
          return JSON.stringify({accepted: true, status: 'QUEUED', requestId: randomUUID()});
        },
        stopSpeaking() {},
      },
    },
    async fetch(url, options = {}) {
      const body = options.body ? JSON.parse(options.body) : null;
      calls.push({url, body, method: options.method || 'GET'});
      let data;
      if (url === '/v3/capabilities') data = {routeApiAvailable: true, companionRigVersion};
      else if (url === '/v3/examples' || (url === '/v3/avatars' && !body)) data = [];
      else if (url === '/v3/route-plans' && body) {
        data = makePlan(body);
        plans.set(data.planId, data);
        if (deferredPlan) await new Promise(resolve => { deferredPlan.resolve = resolve; deferredPlan.plan = data; });
      } else if (url.startsWith('/v3/route-plans/')) data = plans.get(url.split('/').at(-1));
      else if ((url === '/v3/avatars' || url === '/v3/wardrobe') && body) throw new Error('TEST_GENERATION_STOP');
      else throw new Error('Unexpected in-memory request: ' + url);
      return {ok: true, async json() { return {data: clone(data)}; }};
    },
  };
  vm.createContext(context);
  for (const [name, code] of Object.entries(sources)) vm.runInContext(code, context, {filename: name});
  await flush();
  // The real native host starts fail-closed, then reports the observed parked gate.
  assert.equal(get('create-button').disabled, true);
  context.window.nuntiVehicleAllowed(true);
  assert.equal(get('destination').value, '더현대서울', 'Real initialization selects the first API input');
  const nav = context.window.NuntiNavigation;
  const h = {
    context, get, nav, calls, commands,
    route: () => context.window.nuntiTest.getRoute(),
    apiCalls: () => calls.filter(call => call.url === '/v3/route-plans' && call.body),
    generationCalls: () => calls.filter(call => (call.url === '/v3/avatars' || call.url === '/v3/wardrobe') && call.body),
    async tick() { assert(timers.length, 'Expected an awaited poll'); timers.shift()(); await flush(); },
    refreshCallbacks() {
      for (const type of ['onDestinationInfo', 'onCurrentLocationInfo', 'onRouteStateInfo']) native.events.push({sequence: ++native.sequence, type});
      context.window.nuntiNavigationChanged(clone(native));
    },
    nativeChange(changes) { native = {...native, ...clone(changes)}; context.window.nuntiNavigationChanged(clone(native)); },
    nativeSnapshot: () => clone(native),
    preset(name) { get('nav-case').value = name; get('nav-case').onchange(); },
    edit(id, value) { get(id).value = value; get(id).dispatchEvent({type: 'input'}); },
    confirm() { get('route-confirmed').checked = true; get('route-confirmed').dispatchEvent({type: 'change'}); },
    async submit() { await get('journey-form').onsubmit({preventDefault() {}}); await flush(); },
    async calculate() { await get('nav-calculate').onclick(); await flush(); },
    deferPlan() { deferredPlan = {}; return deferredPlan; },
    async importCurrent() { const pending = nav.importNative(); h.refreshCallbacks(); await h.tick(); await pending; },
  };
  return h;
}

const checks = [];
async function test(name, run, options) { await run(await harness(options)); checks.push(name); }

try {
  for (const mockSkinMode of [true, false]) {
    await test(`shared rig generation requires UI approval even when the server advertises it (mock=${mockSkinMode})`, async h => {
      await h.calculate(); h.confirm(); await h.submit();
      assert.equal(h.generationCalls().length, 1);
      assert.equal(h.generationCalls()[0].body.animationRig, mockSkinMode ? undefined : 'nunti-rig-1');
    }, {mockSkinMode, companionRigVersion: 'nunti-rig-1'});
  }
  await test('import blocks creation and route calculation, including direct handlers', async h => {
    await h.calculate(); h.confirm();
    assert.equal(h.get('create-button').disabled, false, 'Fixture must permit creation before import');
    const count = h.apiCalls().length, pending = h.nav.importNative();
    assert.equal(h.get('create-button').disabled, true);
    assert.equal(h.get('nav-calculate').disabled, true);
    assert.equal(h.nav.canGenerate(), false);
    await h.calculate(); await h.submit();
    assert.equal(h.apiCalls().length, count);
    assert.equal(h.generationCalls().length, 0);
    h.refreshCallbacks(); await h.tick(); await pending;
  });

  await test('a preset chosen during native import survives delayed callbacks', async h => {
    const pending = h.nav.importNative(); h.preset('coast');
    h.refreshCallbacks(); await h.tick(); await pending;
    assert.equal(h.get('destination').value, '안목해변');
    assert.equal(h.get('nav-origin-lat').value, '37.7644');
    assert.equal(h.get('nav-destination-lon').value, '128.948');
    assert.equal(h.nav.getPlan(), null);
    await h.calculate();
    assert.equal(h.apiCalls().at(-1).body.nativeSnapshot, undefined, 'Discarded import cannot attach stale native provenance');
  });

  await test('native route revision invalidates confirmation until a new plan', async h => {
    await h.importCurrent(); await h.calculate(); h.confirm();
    assert.equal(h.get('create-button').disabled, false);
    const before = h.nativeSnapshot();
    h.nativeChange({revision: before.revision + 1, routeLifecycle: 'REROUTED'});
    assert.equal(h.get('route-confirmed').checked, false);
    assert.equal(h.get('route-confirmed').disabled, true);
    h.confirm(); await h.submit();
    assert.equal(h.nav.canGenerate(), false);
    assert.equal(h.generationCalls().length, 0);
    h.nativeChange(before); h.confirm();
    assert.equal(h.nav.canGenerate(), false, 'A later old snapshot cannot clear the stale latch');
  });

  await test('new input survives a delayed road API response', async h => {
    const deferred = h.deferPlan(), pending = h.get('nav-calculate').onclick();
    h.preset('coast'); deferred.resolve(); await pending; await flush();
    assert.equal(h.get('destination').value, '안목해변');
    assert.equal(h.get('nav-origin-lat').value, '37.7644');
    assert.equal(h.route(), null);
    assert.equal(h.nav.getPlan(), null);
  });

  await test('editing an API plan coordinate prevents reconfirmation and submission', async h => {
    await h.calculate(); h.confirm();
    assert.equal(h.get('create-button').disabled, false);
    h.edit('nav-destination-lat', 37.6); h.confirm(); await h.submit();
    assert.equal(h.get('route-confirmed').disabled, true);
    assert.equal(h.get('route-confirmed').checked, false);
    assert.equal(h.get('create-button').disabled, true);
    assert.equal(h.generationCalls().length, 0);
  });

  await test('editing an API plan destination name prevents submission', async h => {
    await h.calculate(); h.confirm(); h.edit('destination', '다른 목적지'); h.confirm(); await h.submit();
    assert.equal(h.nav.canGenerate(), false);
    assert.equal(h.get('route-confirmed').disabled, true);
    assert.equal(h.generationCalls().length, 0);
  });

  await test('vehicle gate blocks a pending native import from changing inputs', async h => {
    h.preset('coast'); const pending = h.nav.importNative();
    h.context.window.nuntiVehicleAllowed(false); h.refreshCallbacks(); await h.tick(); await pending;
    assert.equal(h.get('destination').value, '안목해변');
    assert.equal(h.get('nav-calculate').disabled, true);
    assert.equal(h.get('create-button').disabled, true);
  });

  await test('vehicle gate prevents applying an awaited road API response', async h => {
    const deferred = h.deferPlan(), pending = h.get('nav-calculate').onclick();
    h.context.window.nuntiVehicleAllowed(false); deferred.resolve(); await pending; await flush();
    assert.equal(h.route(), null);
    assert.equal(h.nav.getPlan(), null);
    assert.equal(h.get('create-button').disabled, true);
  });

  console.log(JSON.stringify({
    status: 'PASS', surface: 'REAL_UI_SCRIPTS_VM_WITH_STUB_BOUNDARIES', checks,
    sourceSha256: Object.fromEntries(Object.entries(sources).map(([name, code]) => [name, createHash('sha256').update(code).digest('hex')])),
    externalRequests: 0, deviceChanges: 0, paidApiCalls: 0, videoRecorded: false, speakerRecorded: false,
  }, null, 2));
} catch (error) {
  console.error(JSON.stringify({status: 'FAIL', completedChecks: checks, error: String(error.stack || error)}, null, 2));
  process.exitCode = 1;
}
