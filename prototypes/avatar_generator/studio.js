'use strict';
const $ = id => document.getElementById(id);
const state = { route: null, sourceImage: null, imageReady: false, routeVersion: 0, examples: [], artifact: null, avatars: [], busy: false, generating: false, planning: false, pending: null, animation: 0, nativeAllowed: !window.NuntiNative };
let extractionEpoch = 0, viewEpoch = 0, collectionEpoch = 0, fileEpoch = 0, uploadData = null, staticDisplay = null;
let reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
const skins = window.NuntiSkins;
const skinRecord = artifact => skins?.isSkin(artifact) === true;
const wardrobeRecord = artifact => artifact?.mediaOrigin === 'OPENAI_WARDROBE';
const usesSkinMotion = artifact => skinRecord(artifact) || wardrobeRecord(artifact);
const motionSpec = artifact => skinRecord(artifact) ? artifact.design.skinSpec : {
  version: skins.version,
  skinId: artifact.design?.wardrobe?.look === 'default' ? 'default' : 'wardrobe-' + (['formal', 'medical', 'football', 'hiking', 'seaside', 'personal'].includes(artifact.design?.wardrobe?.look) ? artifact.design.wardrobe.look : 'personal') + '-' + (artifact.visual?.sha256 || '0'),
  animationPreset: { sweep: artifact.design?.wardrobe?.road === 'highway' ? 'diagonal' : 'forward' }
};
const polishedSkin = spec => spec && spec.version === skins.version && spec.skinId !== 'default' ? spec.skinId : null;
const skinPhaseText = { DEFAULT_IDLE: '여행 준비 중', ROUTE_ENERGY: '여행 준비 중', OUTFIT_SWAP: '여행 준비 중', HEAD_AND_EYES_TRANSFORM: '여행 준비 중', SKIN_REVEAL: '거의 다 됐어요', FINAL_IDLE: '출발 준비 완료' };

window.NuntiSkinMotion = window.NuntiSkinRenderer?.create({
  canvas: $('birth-canvas'), allowed: () => state.nativeAllowed, visible: () => !document.hidden && !$('result-view').hidden,
  onFrame: frame => {
    if (!frame.active || !usesSkinMotion(state.artifact)) return;
    const spec = motionSpec(state.artifact);
    const settled = ['COMPLETE', 'STATIC', 'REDUCED', 'SKIPPED'].includes(frame.reason);
    window.NuntiCompanionPlayer?.setResult(settled && (spec.version === skins.version || spec.skinId === 'default') ? spec.skinId : null);
    const checkbox = $('reduced-motion');
    if (checkbox) { checkbox.checked = frame.reducedMotion; checkbox.disabled = frame.systemReducedMotion; }
    if ($('motion-skip')) $('motion-skip').hidden = !frame.running && frame.reason !== 'LOADING';
    $('birth-progress').hidden = !frame.running;
    const bar = $('birth-progress').firstElementChild;
    if (bar) {
      if (bar.style.width !== '100%') { bar.style.width = '100%'; bar.style.transformOrigin = 'left center'; }
      bar.style.transform = 'scaleX(' + (frame.elapsedMs / 4000) + ')';
    }
    const text = frame.reason === 'LAYER_ASSET_FAILURE' ? '변신 없이 준비된 모습으로 만나요' : skinPhaseText[frame.phase];
    if ($('birth-status').textContent !== text) $('birth-status').textContent = text;
    const label = '눈티 · ' + (frame.phase === 'FINAL_IDLE' ? state.artifact.displayName : text);
    if ($('birth-canvas').getAttribute('aria-label') !== label) $('birth-canvas').setAttribute('aria-label', label);
  }
});

window.NuntiCompanionPlayer = window.NuntiCompanion?.create({
  preview: $('canonical-portrait'), result: $('result-portrait'), inputView: $('input-view'), resultView: $('result-view'),
  allowed: () => state.nativeAllowed && !window.NuntiSkinMotion?.diagnostics().reducedMotion,
});

if ($('motion-skip')) $('motion-skip').onclick = () => window.NuntiSkinMotion?.stop('SKIPPED');
if ($('reduced-motion')) $('reduced-motion').onchange = event => {
  window.NuntiSkinMotion?.setReduced(event.target.checked);
  window.NuntiCompanionPlayer?.sync();
};
window.addEventListener('nunti:appearance', event => {
  window.NuntiSkinMotion?.appearance(event.detail || {});
  window.NuntiCompanionPlayer?.sync();
  reduced = !!event.detail?.systemReducedMotion || matchMedia('(prefers-reduced-motion: reduce)').matches;
  drawRoute();
});

const message = text => {
  $('notice').textContent = text;
  $('notice').hidden = !text;
  requestAnimationFrame(() => { window.NuntiCompanionPlayer?.sync(); window.NuntiSkinMotion?.redraw(); });
};
const errorText = error => ({
  INVALID_ROUTE_IMAGE: '사진을 읽지 못했어요. PNG 또는 JPG 경로 사진을 선택해 주세요.',
  ROUTE_NOT_FOUND: '경로선을 찾지 못했어요. 다른 색을 고르거나 좌표 파일을 넣어 주세요.',
  AMBIGUOUS_ROUTE: '여러 경로가 보여요. 한 경로만 보이도록 사진을 잘라 주세요.',
}[error.message] || error.message || '연결을 확인한 뒤 다시 시도해 주세요.');

async function api(path, body, method = 'GET', signal) {
  skins?.assertRequest(path);
  const response = await fetch(path, {
    method: body ? 'POST' : method,
    credentials: 'same-origin',
    headers: body ? { 'Content-Type': 'application/json' } : {},
    body: body ? JSON.stringify(body) : undefined,
    signal,
  });
  const value = await response.json();
  if (!response.ok) {
    const e = new Error(value.error?.message || value.detail?.message || value.error?.code || (typeof value.detail === 'string' ? value.detail : '요청을 처리하지 못했어요.'));
    e.status = response.status;
    throw e;
  }
  return value.data ?? value;
}

async function createWardrobe(input) {
  const epoch = viewEpoch, button = $('create-button');
  state.generating = state.busy = true;
  enableCreate();
  button.textContent = '오늘의 옷을 만들고 있어요…';
  message('OpenAI API로 눈티의 새 모습을 만들고 있어요. 보통 1~2분 걸리며, 완성되면 내 눈티에 보관합니다.');
  try {
    const artifact = await api('/v3/wardrobe', {
      destination: input.destination,
      purpose: input.purpose,
      route: input.route,
      mood: $('layer-mood').value,
      scenery: $('layer-destination').value,
      road: $('layer-road').value,
    });
    if (state.nativeAllowed && !document.hidden && viewEpoch === epoch) await showArtifact(artifact, true);
    await loadCollection();
  } catch (e) {
    const hints = {
      IMAGE_API_BUDGET_REACHED: '설정한 30달러 한도에 도달했어요. 보관한 눈티를 선택하거나 한도를 조정해 주세요.',
      WARDROBE_NOT_CONFIGURED: '서버에 OPENAI_API_KEY가 연결되지 않았어요. .env 파일에 OPENAI_API_KEY를 설정한 뒤 서버를 다시 시작해 주세요.',
      WARDROBE_HTTP_401: 'OPENAI_API_KEY 인증에 실패했어요. .env 파일의 키를 확인해 주세요.',
      WARDROBE_HTTP_403: '이 API 키의 이미지 모델(gpt-image-1.5) 사용 권한을 확인해 주세요.',
      WARDROBE_HTTP_429: 'OpenAI 사용 한도 또는 잔액을 확인해 주세요.',
      WARDROBE_RESULT_UNKNOWN: '응답을 받지 못했어요. 중복 결제를 피하려고 자동 재시도하지 않았어요.',
    };
    message(hints[e.message] || errorText(e));
  } finally {
    state.generating = state.busy = false;
    button.textContent = '눈티 만들기 →';
    enableCreate();
  }
}

function screen(which) {
  window.NuntiCompanionPlayer?.setResult(null);
  window.NuntiSkinMotion?.clear();
  cancelAnimationFrame(state.animation); state.animation = 0;
  viewEpoch++;
  for (const name of ['input', 'result', 'collection']) $(name + '-view').hidden = name !== which;
  $('examples-section').hidden = which !== 'input';
  $('heading').textContent = which === 'result' ? '이번 여행의 눈티' : which === 'collection' ? '함께 다녀온 길' : '어디로 떠날까요?';
  $('subheading').textContent = which === 'result' ? '준비가 끝나면 함께 출발하세요.' : which === 'collection' ? '눈티에 남은 여행을 다시 만나보세요.' : '길을 고르면, 눈티도 여행을 준비해요.';
  for (let i = 1; i <= 3; i++) $('step-' + i).classList.toggle('active', i === (which === 'result' ? 2 : 1));
  stopVoice();
  if (which === 'input') requestAnimationFrame(drawRoute);
}

function canvasSize(canvas) {
  const rect = canvas.getBoundingClientRect(), dpr = Math.min(devicePixelRatio || 1, 2);
  const width = Math.max(1, rect.width), height = Math.max(1, rect.height);
  if (canvas.width !== Math.round(width * dpr) || canvas.height !== Math.round(height * dpr)) {
    canvas.width = Math.round(width * dpr); canvas.height = Math.round(height * dpr);
  }
  const ctx = canvas.getContext('2d');
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, width, height);
  return { ctx, width, height };
}

function fitPoints(points, w, h, pad = 20) {
  const xs = points.map(p => p[0]), ys = points.map(p => p[1]);
  const x0 = Math.min(...xs), y0 = Math.min(...ys), dx = Math.max(...xs) - x0 || .01, dy = Math.max(...ys) - y0 || .01;
  const scale = Math.min((w - pad * 2) / dx, (h - pad * 2) / dy);
  return points.map(p => [(w - dx * scale) / 2 + (p[0] - x0) * scale, (h - dy * scale) / 2 + (p[1] - y0) * scale]);
}

function strokeRoute(ctx, points, color = '#638970', width = 4, progress = 1) {
  if (points.length < 2) return;
  ctx.beginPath(); ctx.moveTo(...points[0]);
  const distances = [0];
  for (let i = 1; i < points.length; i++) distances.push(distances[i - 1] + Math.hypot(points[i][0] - points[i - 1][0], points[i][1] - points[i - 1][1]));
  const end = Math.max(0, Math.min(1, progress)) * distances.at(-1);
  for (let i = 1; i < points.length; i++) {
    if (distances[i] <= end) ctx.lineTo(...points[i]);
    else {
      const span = distances[i] - distances[i - 1], t = span ? (end - distances[i - 1]) / span : 0;
      ctx.lineTo(points[i - 1][0] + (points[i][0] - points[i - 1][0]) * t, points[i - 1][1] + (points[i][1] - points[i - 1][1]) * t);
      break;
    }
  }
  ctx.strokeStyle = color; ctx.lineWidth = width; ctx.lineCap = 'round'; ctx.lineJoin = 'round'; ctx.stroke();
}

function pins(ctx, points) {
  for (let i = 0; i < 2; i++) {
    const p = points[i ? points.length - 1 : 0];
    ctx.beginPath(); ctx.arc(...p, i ? 6 : 4, 0, Math.PI * 2);
    ctx.fillStyle = i ? '#ee7952' : '#42695a'; ctx.fill();
    ctx.lineWidth = 2; ctx.strokeStyle = '#fff'; ctx.stroke();
  }
}

function drawRoute() {
  const canvas = $('route-canvas');
  if (!canvas.getBoundingClientRect().width) return;
  const { ctx, width: w, height: h } = canvasSize(canvas);
  $('map-empty').hidden = !!state.route;
  if (!state.route || !state.imageReady) return;
  let points;
  if (state.sourceImage) {
    const img = $('route-image'), iw = img.naturalWidth, ih = img.naturalHeight, scale = Math.min(w / iw, h / ih);
    points = state.route.points.map(p => [(w - iw * scale) / 2 + p[0] * iw * scale, (h - ih * scale) / 2 + p[1] * ih * scale]);
  } else {
    points = fitPoints(state.route.points, w, h, 24);
  }
  if (state.sourceImage) strokeRoute(ctx, points, '#fffefa', 9);
  strokeRoute(ctx, points, window.NuntiAppearance?.config?.theme === 'night' ? '#B6D0A0' : '#355C4B', 4);
  pins(ctx, points);
}

function setRoute(route, imagePath, confirmed = false) {
  extractionEpoch++; fileEpoch++; state.busy = state.generating;
  const version = ++state.routeVersion;
  state.route = route; state.sourceImage = imagePath || null; state.imageReady = !imagePath;
  $('route-image').hidden = !imagePath;
  $('route-confirmed').disabled = !!imagePath;
  if (imagePath) {
    const img = $('route-image');
    img.onload = () => { if (version !== state.routeVersion) return; state.imageReady = true; $('route-confirmed').disabled = false; drawRoute(); enableCreate(); };
    img.onerror = () => { if (version !== state.routeVersion) return; state.imageReady = false; message('경로 원본 사진을 불러오지 못했어요. 사진을 다시 선택해 주세요.'); enableCreate(); };
    img.src = imagePath;
  } else {
    $('route-image').removeAttribute('src');
  }
  $('route-confirmed').checked = confirmed; state.pending = null;
  const confirmRow = $('route-confirmed').closest?.('.confirm-row') || $('route-confirmed').parentElement;
  if (confirmRow) confirmRow.hidden = !route;
  const origin = route?.inputOrigin;
  $('source-tag').textContent = origin === 'API_ROUTE' ? '선택한 경로' : origin === 'NAVIGATION_SCREENSHOT' ? '내비 경로 사진' : origin === 'ROUTE_FILE' ? '좌표 파일' : route ? '예시 경로' : '경로 선택';
  $('map-caption').textContent = origin === 'TEST_ROUTE' ? '예시 경로' : route ? '표시된 선을 확인해 주세요' : '경로 추가는 선택이에요';
  $('route-warning').textContent = route?.warnings?.join(' ') || (route ? '표시된 선을 확인한 뒤 체크해 주세요.' : '내비에서 불러오거나 경로를 직접 추가할 수 있어요.');
  drawRoute(); enableCreate();
  window.NuntiNavigation?.routeChanged(route);
}

function enableCreate() {
  const routeReady = state.route ? state.imageReady && $('route-confirmed').checked : true;
  $('create-button').disabled = state.busy || state.planning || !state.nativeAllowed || !routeReady || !$('destination').value.trim();
  window.NuntiNavigation?.updateButtons();
}

function viewExample(example) {
  message('');
  $('destination').value = example.destination.name;
  $('traits').value = example.destination.traits || '';
  $('purpose').value = example.purpose || '';
  setRoute({ ...example.route, confirmed: false }, example.imagePath, false);
  $('image-options').hidden = true;
  document.querySelectorAll('.example').forEach(x => x.classList.toggle('selected', x.dataset.id === example.id));
}

async function examples() {
  const response = await api('/v3/examples');
  state.examples = Array.isArray(response) ? response : response.examples;
  $('examples').replaceChildren();
  for (const ex of state.examples) {
    const b = document.createElement('button'); b.className = 'example'; b.dataset.id = ex.id;
    const c = document.createElement('canvas'); c.width = 106; c.height = 90;
    const ctx = c.getContext('2d'); strokeRoute(ctx, fitPoints(ex.route.points, 106, 90, 16), '#5a876d', 4);
    const text = document.createElement('div'), strong = document.createElement('strong'), small = document.createElement('small');
    strong.textContent = ex.title; small.textContent = ex.destination.name;
    text.append(strong, small); b.append(c, text); b.onclick = () => viewExample(ex);
    $('examples').append(b);
  }
}

async function extract() {
  if (!uploadData || state.generating) return;
  const epoch = ++extractionEpoch, imageBase64 = uploadData;
  state.busy = true; enableCreate(); message('사진에서 경로선을 찾고 있어요…');
  try {
    const data = await api('/v3/route-extractions', { imageBase64, ...($('route-color').value ? { colorHint: $('route-color').value } : {}) });
    if (epoch !== extractionEpoch) return;
    setRoute({ points: data.points, inputOrigin: 'NAVIGATION_SCREENSHOT', sourceLabel: '사용자가 불러온 내비 경로 사진', confirmed: false, extractionId: data.extractionId, warnings: data.warnings }, data.imagePath);
    message('사진 위에 표시된 선을 확인해 주세요. 다른 길이 선택되면 경로선 색상을 바꾸거나 한 경로만 남도록 사진을 잘라 주세요.');
  } catch (e) {
    if (epoch !== extractionEpoch) return;
    state.route = null; $('route-confirmed').checked = false; message(errorText(e));
  } finally {
    if (epoch === extractionEpoch) state.busy = false;
    enableCreate();
  }
}

$('image-upload').onchange = async event => {
  const file = event.target.files[0];
  if (!file) return;
  if (file.size > 6 * 1024 * 1024) { message('6MB 이하의 경로 사진을 선택해 주세요.'); return; }
  const version = ++fileEpoch; extractionEpoch++; state.busy = true; enableCreate();
  const reader = new FileReader();
  reader.onload = () => { if (version !== fileEpoch) return; uploadData = String(reader.result).split(',')[1]; $('image-options').hidden = false; $('route-color').value = ''; extract(); };
  reader.onerror = () => { if (version !== fileEpoch) return; state.busy = false; enableCreate(); message('사진 파일을 읽지 못했어요. PNG 또는 JPG를 다시 선택해 주세요.'); };
  reader.readAsDataURL(file); event.target.value = '';
};
$('extract-again').onclick = extract;
$('route-upload').onchange = async event => {
  const file = event.target.files[0];
  if (!file) return;
  fileEpoch++; extractionEpoch++;
  try {
    if (file.size > 65536) throw new Error('64KB 이하의 경로 JSON을 선택해 주세요.');
    const value = JSON.parse(await file.text()), r = value.route || value, points = r.points;
    if (!Array.isArray(points) || points.length < 2 || points.length > 512 || !points.every(p => Array.isArray(p) && p.length === 2 && p.every(n => typeof n === 'number' && Number.isFinite(n) && n >= 0 && n <= 1)))
      throw new Error('points에 0부터 1 사이의 [x,y] 좌표를 2~512개 넣어 주세요.');
    if (value.destination) { $('destination').value = value.destination.name || ''; $('traits').value = value.destination.traits || ''; }
    if (value.purpose) $('purpose').value = value.purpose;
    setRoute({ points, inputOrigin: 'ROUTE_FILE', sourceLabel: file.name, confirmed: false }, null);
    $('image-options').hidden = true; message('좌표 파일을 불러왔어요. 선을 확인한 뒤 생성할 수 있어요.');
  } catch (e) { message(errorText(e)); }
  event.target.value = '';
};

$('route-confirmed').onchange = enableCreate;
for (const id of ['destination', 'traits', 'purpose', 'layer-destination', 'layer-road', 'layer-mood']) $(id)?.addEventListener('input', enableCreate);
for (const id of ['layer-destination', 'layer-road', 'layer-mood']) $(id)?.addEventListener('change', enableCreate);

$('journey-form').onsubmit = async event => {
  event.preventDefault();
  if (state.busy || state.planning || !state.nativeAllowed || (state.route && (!state.imageReady || !$('route-confirmed').checked)) || window.NuntiNavigation?.canGenerate() === false || !$('destination').value.trim()) return;
  const sourceRoute = state.route, { points, inputOrigin, sourceLabel, extractionId, apiPlanId } = sourceRoute || {};
  const input = {
    destination: { name: $('destination').value.trim(), traits: $('traits').value.trim() },
    purpose: $('purpose').value.trim(),
    route: sourceRoute ? { points, inputOrigin, sourceLabel, confirmed: true, ...(extractionId ? { extractionId } : {}), ...(apiPlanId ? { apiPlanId } : {}) } : null,
  };
  await createWardrobe(input);
};

async function showArtifact(artifact, animate = false) {
  message('');
  screen('result');
  const displayEpoch = viewEpoch;
  state.artifact = artifact; staticDisplay = null;
  cancelAnimationFrame(state.animation); state.animation = 0;
  const stage = document.querySelector('.birth-stage');
  const skinSpec = skinRecord(artifact) ? artifact.design.skinSpec : null;
  if (stage) {
    stage.classList.toggle('skin-v2-stage', !!skinSpec);
    delete stage.dataset.skin;
    delete stage.dataset.skinSummary;
  }
  canvasSize($('birth-canvas'));
  const cachedImage = window.nuntiLastDecoded?.path === artifact.visual.path ? window.nuntiLastDecoded.image : null;
  let img = cachedImage, imageFailed = false;
  try {
    if (!img && skinSpec) img = await window.NuntiSkinRenderer.image(skinSpec.skinId, 'final', skinSpec.version);
    if (!img) { img = new Image(); img.src = artifact.visual.path; await img.decode(); }
    window.nuntiLastDecoded = { path: artifact.visual.path, image: img };
  } catch {
    imageFailed = true;
    img = new Image(); img.src = '/nunti-motion/base.png'; await img.decode();
    message('그림을 불러오지 못해 기본 눈티를 보여드려요. 저장된 원본은 그대로 보관돼요.');
  }
  if (state.artifact !== artifact || viewEpoch !== displayEpoch) return;
  if (skinSpec && stage) {
    stage.dataset.skinSummary = imageFailed ? '기본 눈티 A' : skinSpec.name;
    const theme = polishedSkin(skinSpec);
    if (!imageFailed && theme) stage.dataset.skin = theme;
  }
  if (stage) stage.style.setProperty('--journey-color', '#ACDABF');
  $('avatar-name').textContent = artifact.displayName;
  $('avatar-personality').textContent = artifact.design.personality;
  $('character-story').replaceChildren();
  const mood = { calm: '차분하게', curious: '호기심 있게', adventurous: '씩씩하게', unset: '고르지 않았어요' };
  const items = wardrobeRecord(artifact)
    ? [['오늘의 옷', artifact.design.wardrobe.label], ['가는 이유', artifact.purpose || '가벼운 외출'], ['고른 기분', mood[artifact.design.wardrobe.mood] || '고르지 않았어요']]
    : skinRecord(artifact)
      ? [['여행복', artifact.design.skinSpec.outfit], ['모자와 머리', artifact.design.skinSpec.headStyle], ['여행 소품', artifact.design.skinSpec.accessories.join(' · ')]]
      : [['목적지', artifact.destination.name], ['방문 이유', artifact.purpose || '나만의 여정']];
  for (const [label, detail] of items) {
    const row = document.createElement('div'), title = document.createElement('span'), value = document.createElement('b');
    title.textContent = label; value.textContent = detail;
    row.append(title, value); $('character-story').append(row);
  }
  $('result-destination').textContent = artifact.destination.name;
  $('result-purpose').textContent = artifact.purpose || '나만의 여정';
  $('voice-description').textContent = artifact.voice?.description || artifact.design.voice?.description || '작고 차분한 동반자';
  $('voice-notice').textContent = '누르면 기기에 설치된 한국어 음성으로 눈티의 인사를 들을 수 있어요.';
  $('origin-label').textContent = 'OpenAI API로 새로 생성한 이미지';
  $('edition-label').textContent = 'JOURNEY ' + artifact.characterId.slice(-8).toUpperCase();
  $('motifs-heading').textContent = '여행에서 가져온 것';
  $('motifs-notice').hidden = usesSkinMotion(artifact);
  $('motifs').replaceChildren();
  for (const [i, m] of (artifact.design.motifs || []).slice(0, 3).entries()) {
    const row = document.createElement('div'); row.className = 'motif';
    const dot = document.createElement('span'); dot.className = 'dot'; dot.textContent = String(i + 1).padStart(2, '0');
    const content = document.createElement('div'), title = document.createElement('b'), desc = document.createElement('p');
    title.textContent = m.label; desc.textContent = m.detail || m.source + ' → ' + m.target;
    content.append(title, desc); row.append(dot, content); $('motifs').append(row);
  }
  const transformable = !imageFailed && usesSkinMotion(artifact) && motionSpec(artifact).skinId !== 'default';
  $('result-details').hidden = false;
  $('replay-button').hidden = !transformable;
  $('save-status').textContent = '내 눈티에 저장됨';
  $('replay-button').onclick = !transformable ? null : () => {
    const current = window.NuntiSkinMotion?.diagnostics();
    if (!current?.running && current?.reason !== 'LOADING') birthAnimation(img, artifact, true);
  };
  if (imageFailed) {
    staticDisplay = { img, artifact, fallback: true };
    drawStaticArtifact();
    $('birth-progress').hidden = true;
    if ($('motion-skip')) $('motion-skip').hidden = true;
    $('birth-status').textContent = '그림을 불러오지 못해 기본 눈티로 만나요';
  } else {
    birthAnimation(img, artifact, animate && !reduced);
  }
  drawReceipt(artifact);
}

function drawReceipt(artifact) {
  const route = artifact.route, hasRoute = Array.isArray(route?.points) && route.points.length >= 2;
  $('receipt-source').textContent = hasRoute
    ? (route.sourceLabel || '선택한 경로') + ' · ' + (route.inputOrigin === 'NAVIGATION_SCREENSHOT' ? '사용자가 확인한 경로' : '함께 갈 경로')
    : '목적지와 방문 이유에 맞춘 옷이에요. 경로선은 사용하지 않았어요.';
  const canvas = $('receipt-canvas'); canvas.hidden = !hasRoute;
  const { ctx, width, height } = canvasSize(canvas);
  if (!hasRoute) return;
  const pts = fitPoints(route.points, width, height, 15);
  strokeRoute(ctx, pts, '#6c9275', 3);
  pins(ctx, pts);
}

function drawStaticArtifact() {
  if (!staticDisplay || document.hidden || !state.nativeAllowed || $('result-view').hidden) return;
  const { img, artifact, fallback } = staticDisplay, { ctx, width, height } = canvasSize($('birth-canvas'));
  const scale = Math.min(width / img.naturalWidth, height / img.naturalHeight), w = img.naturalWidth * scale, h = img.naturalHeight * scale;
  ctx.drawImage(img, (width - w) / 2, (height - h) / 2, w, h);
  $('birth-canvas').setAttribute('aria-label', fallback ? '기본 눈티. 여정 그림을 불러오지 못해 기본 모습을 보여줘요' : artifact.displayName);
}

function birthAnimation(img, artifact, animate) {
  window.NuntiCompanionPlayer?.setResult(null);
  if (usesSkinMotion(artifact) && window.NuntiSkinMotion) {
    staticDisplay = null;
    window.NuntiSkinMotion.show(motionSpec(artifact), img, artifact.route, animate);
    return;
  }
  staticDisplay = { img, artifact };
  $('birth-progress').hidden = true;
  $('replay-button').hidden = true;
  $('birth-status').textContent = '함께할 눈티가 준비됐어요';
  drawStaticArtifact();
}

async function loadCollection() {
  const epoch = ++collectionEpoch, r = await api('/v3/avatars');
  if (epoch !== collectionEpoch) return;
  state.avatars = Array.isArray(r) ? r : (r.avatars || r.items || []);
  $('collection-count').textContent = state.avatars.length;
}

function drawCollection(records) {
  $('collection').replaceChildren();
  if (!records.length) { $('collection').textContent = '아직 눈티가 없어요. 첫 여정을 담아보세요.'; return; }
  for (const a of records) {
    const b = document.createElement('button'); b.className = 'collection-item card'; b.dataset.characterId = a.characterId;
    const img = document.createElement('img'); img.alt = a.displayName;
    if (skinRecord(a)) {
      const theme = polishedSkin(a.design.skinSpec);
      if (theme) b.dataset.skin = theme;
      img.onerror = () => { delete b.dataset.skin; img.onerror = null; img.alt = '기본 눈티 A'; img.src = '/nunti-motion/base.png'; };
    }
    img.src = a.visual.path;
    const title = document.createElement('h3'), desc = document.createElement('p');
    title.textContent = a.displayName; desc.textContent = a.destination.name;
    b.append(img, title, desc);
    b.onclick = async () => {
      const selection = ++viewEpoch; message('');
      try {
        const artifact = skinRecord(a) ? a : await api('/v3/avatars/' + encodeURIComponent(a.characterId));
        if (selection !== viewEpoch || !state.nativeAllowed) return;
        await showArtifact(artifact, false);
      } catch (e) { if (selection === viewEpoch) message(errorText(e)); }
    };
    $('collection').append(b);
  }
}

async function showCollection() {
  if (state.busy) return;
  message(''); screen('collection');
  const epoch = viewEpoch;
  drawCollection(state.avatars);
  try { await loadCollection(); } catch { if (epoch === viewEpoch) message('보관함을 새로 불러오지 못했어요.'); return; }
  if (epoch === viewEpoch && state.nativeAllowed) drawCollection(state.avatars);
}

$('collection-button').onclick = () => showCollection().catch(e => message(errorText(e)));
$('collection-back').onclick = () => screen(state.artifact ? 'result' : 'input');
$('new-button').onclick = () => { screen('input'); message(''); };

const journeyOptions = document.createElement('div'); journeyOptions.className = 'journey-options';
const journeyLabel = document.createElement('label'); journeyLabel.htmlFor = 'journey-source'; journeyLabel.textContent = '함께할 여정';
const journeySource = document.createElement('select'); journeySource.id = 'journey-source';
for (const [value, label] of [['LIVE', '실제 차량 신호'], ['DEMO', '운전 습관 연습 · 약 30초']]) {
  const option = document.createElement('option'); option.value = value; option.textContent = label; journeySource.append(option);
}
const journeyHelp = document.createElement('p'); journeyHelp.className = 'helper'; journeyHelp.textContent = '주행 중 운전 습관을 기록하고, 도착 후 점수를 확인해요.';
journeySource.addEventListener('change', () => {
  journeyHelp.textContent = journeySource.value === 'DEMO'
    ? '주차 상태에서 급가속·급제동·급회전과 부드러운 운전을 재현해요. 약 30초 뒤 여정을 마치면 구간별 리포트를 볼 수 있어요.'
    : '주행 중 운전 습관을 기록하고, 도착 후 점수를 확인해요.';
});
const previousJourneyButton = document.createElement('button'); previousJourneyButton.id = 'previous-journey'; previousJourneyButton.className = 'quiet'; previousJourneyButton.textContent = '진행 중인 여정 · 마지막 리포트';
journeyOptions.append(journeyLabel, journeySource, journeyHelp, previousJourneyButton);
$('journey-button').parentElement.before(journeyOptions);

let startingJourney = false;
previousJourneyButton.onclick = () => {
  if (window.NuntiNative?.openJourney) window.NuntiNative.openJourney();
  else message('Android 눈티 앱에서 진행 중인 여정과 리포트를 열 수 있어요.');
};
window.nuntiJourneyResult = text => { startingJourney = false; $('journey-button').disabled = false; if (text) message(text); };
$('journey-button').onclick = () => {
  if (!state.artifact || !state.nativeAllowed || startingJourney) return;
  if (!window.NuntiNative?.startJourney) {
    message('Android 눈티 앱에서 이 눈티를 선택한 뒤 함께하기를 눌러 주세요.');
    return;
  }
  stopVoice(); startingJourney = true; $('journey-button').disabled = true;
  const artifact = state.artifact;
  const result = JSON.parse(skinRecord(artifact) ? window.NuntiNative.startSkinJourney(JSON.stringify({
    skinId: artifact.design.skinSpec.skinId, skinVersion: artifact.design.skinSpec.version, characterId: artifact.characterId, displayName: artifact.displayName, route: artifact.route,
    destination: artifact.destination.name, purpose: artifact.purpose, routePlanId: artifact.route?.apiPlanId
  }), journeySource.value) : window.NuntiNative.startJourney(artifact.characterId, journeySource.value));
  if (!result.accepted) { window.nuntiJourneyResult('주차 상태와 연결을 확인한 뒤 다시 눌러 주세요.'); return; }
  if (result.existing) window.nuntiJourneyResult('진행 중인 여정으로 돌아갑니다.');
  else message('눈티와 함께 출발할 준비를 하고 있어요.');
  $('step-3').classList.add('active');
};

let speaking = false, voiceEpoch = 0, voiceAudio = null;
const voicePageId = crypto.randomUUID();
const nativeVoiceRequestId = () => voicePageId + ':' + voiceEpoch;
function stopVoice() {
  voiceEpoch++;
  if (voiceAudio) { voiceAudio.onended = null; voiceAudio.onerror = null; voiceAudio.pause(); voiceAudio.src = ''; voiceAudio = null; }
  if (window.NuntiNative) window.NuntiNative.stopSpeaking();
  else if ('speechSynthesis' in window) speechSynthesis.cancel();
  speaking = false; $('listen-button').textContent = '▷';
}
$('listen-button').onclick = async () => {
  if (!state.artifact || !state.nativeAllowed) return;
  if (speaking) { stopVoice(); return; }
  const a = state.artifact, v = a.voice || {};
  const legacyEpoch = ++voiceEpoch;
  const text = `안녕, 나는 ${a.displayName}. ${a.destination.name}까지 함께 갈게. 우리, 여유 있게 출발해 볼까?`;
  if (window.NuntiNative) {
    const bridge = window.NuntiNative, id = nativeVoiceRequestId();
    if (bridge.isSpeechAvailable()) bridge.speak(text, Number(v.rate || 1), Number(v.pitch || 1.08), id);
    else if (bridge.speakConversation) bridge.speakConversation(text, id);
    else { message('이 기기에 한국어 음성이 준비되지 않았어요. 기기의 TTS 설정을 확인해 주세요.'); return; }
    speaking = true; $('listen-button').textContent = '□';
  } else if ('speechSynthesis' in window) {
    const voice = speechSynthesis.getVoices().find(x => x.lang.startsWith('ko'));
    if (!voice) { message('이 브라우저에 한국어 음성이 없어요. 한국어 음성을 설치해 주세요.'); return; }
    speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(text);
    u.lang = 'ko-KR'; u.voice = voice; u.rate = Number(v.rate || 1); u.pitch = Number(v.pitch || 1.08);
    u.onend = u.onerror = () => { if (legacyEpoch === voiceEpoch) window.nuntiSpeechFinished(); };
    speechSynthesis.speak(u);
    speaking = true; $('listen-button').textContent = '□';
  } else {
    message('이 기기에서 음성 재생을 지원하지 않아요.');
  }
};
window.nuntiSpeechStarted = requestId => window.NuntiChat?.speechStarted(requestId);
window.nuntiSpeechRange = requestId => window.NuntiChat?.speechRange(requestId);
window.nuntiSpeechFinished = requestId => { if (window.NuntiChat?.speechEnded(requestId) || requestId !== undefined && requestId !== nativeVoiceRequestId()) return; speaking = false; $('listen-button').textContent = '▷'; };
window.nuntiSpeechFailed = requestId => { if (window.NuntiChat?.speechEnded(requestId, true) || requestId !== undefined && requestId !== nativeVoiceRequestId()) return; stopVoice(); $('voice-notice').textContent = '음성을 재생하지 못했어요. 연결을 확인한 뒤 다시 눌러 주세요.'; };

function restoreVisibleResult() {
  if (!state.artifact || $('result-view').hidden || !state.nativeAllowed || document.hidden) return;
  const motion = window.NuntiSkinMotion?.diagnostics();
  if (usesSkinMotion(state.artifact) && motion?.active && ['RESTRICTED', 'BACKGROUNDED'].includes(motion.reason)) {
    window.NuntiSkinMotion.stop('STATIC');
  } else if (!usesSkinMotion(state.artifact) || (!motion?.active && !staticDisplay)) {
    showArtifact(state.artifact, false).catch(e => message(errorText(e)));
  }
}

function interruptSkin(reason) {
  const current = window.NuntiSkinMotion?.diagnostics();
  if (current?.running || current?.reason === 'LOADING') window.NuntiSkinMotion.stop(reason);
}

window.nuntiVehicleAllowed = (allowed, reason) => {
  const was = state.nativeAllowed;
  state.nativeAllowed = allowed;
  window.NuntiUI?.setVehicleAllowed(allowed);
  if (!allowed) {
    viewEpoch++; window.NuntiChat?.close(false); stopVoice(); cancelAnimationFrame(state.animation);
    interruptSkin(reason || (document.hidden ? 'BACKGROUNDED' : 'RESTRICTED'));
    document.querySelectorAll('dialog[open]').forEach(dialog => dialog.close());
  } else if (!was) {
    restoreVisibleResult();
  }
  window.NuntiCompanionPlayer?.sync();
  enableCreate();
};
document.addEventListener('visibilitychange', () => {
  if (document.hidden) { viewEpoch++; stopVoice(); cancelAnimationFrame(state.animation); interruptSkin('BACKGROUNDED'); }
  else restoreVisibleResult();
});
window.addEventListener('resize', () => {
  drawRoute(); drawStaticArtifact(); window.NuntiSkinMotion?.redraw();
  if (state.artifact && !$('result-view').hidden) drawReceipt(state.artifact);
});

async function init() {
  if ($('connection-retry')) $('connection-retry').hidden = true;
  try {
    const caps = await api('/v3/capabilities');
    window.nuntiCapabilities = caps;
    window.NuntiNavigation?.setCapabilities(caps);
    $('session-dialog').close();
    if (caps.wardrobeAvailable === false) {
      message('서버에 OPENAI_API_KEY가 연결되지 않았어요. .env 파일에 OPENAI_API_KEY를 설정한 뒤 서버를 다시 시작해 주세요.');
    }
    await examples();
    await loadCollection();
    enableCreate();
  } catch (e) {
    if (e.status === 401 || e.status === 403) {
      $('session-dialog').showModal();
    } else {
      message('연결을 확인해 주세요. 기본 눈티는 여기서 기다려요.');
      if ($('connection-retry')) $('connection-retry').hidden = false;
    }
  }
}

if ($('connection-retry')) $('connection-retry').onclick = () => { message(''); init(); };
$('session-form').onsubmit = async event => {
  event.preventDefault();
  try {
    await api('/session', { token: $('session-token').value });
    $('session-token').value = ''; $('session-error').textContent = '';
    await init();
  } catch (e) { $('session-error').textContent = errorText(e); }
};

window.nuntiTest = { getArtifact: () => state.artifact, getRoute: () => state.route, showCollection, viewExample: i => viewExample(state.examples[i]), showArtifact };
init();
