'use strict';
(() => {
  const byId = id => document.getElementById(id);
  const dialogs = ['route-tools-dialog', 'journey-options-dialog'];
  let activeView;
  let appearance = { theme: matchMedia('(prefers-color-scheme: dark)').matches ? 'night' : 'day', systemReducedMotion: false };
  let nativeAppearanceReceived = false;
  const setText = (node, value) => { if (node && node.textContent !== value) node.textContent = value; };

  function closePanels() {
    for (const id of dialogs) if (byId(id)?.open) byId(id).close();
    window.NuntiSkinMotion?.redraw();
    window.NuntiCompanionPlayer?.sync();
  }
  function openPanel(id) {
    if (document.body.dataset.vehicleAllowed === 'false') return;
    closePanels();
    const dialog = byId(id);
    dialog?.showModal();
    window.NuntiSkinMotion?.redraw();
    window.NuntiCompanionPlayer?.sync();
    if (id === 'journey-options-dialog') window.dispatchEvent(new Event('resize'));
  }
  for (const [button, dialog] of [['route-tools-open', 'route-tools-dialog'], ['journey-options-open', 'journey-options-dialog']]) {
    byId(button)?.addEventListener('click', () => openPanel(dialog));
  }
  for (const button of document.querySelectorAll('[data-close-dialog]')) button.addEventListener('click', () => button.closest('dialog').close());

  const journeyOptions = document.querySelector('.journey-options');
  if (journeyOptions) byId('journey-options-content').prepend(journeyOptions);
  const story = document.querySelector('.generation-info');
  story.append(byId('motifs-heading'), byId('character-story'));
  byId('source-tag').after(byId('map-caption'));

  const compact = matchMedia('(max-width:1199px)');
  function reflowControls() {
    const routeTools = byId('route-tools-open');
    const skip = byId('motion-skip');
    const options = byId('journey-options-open');
    if (compact.matches) {
      document.querySelector('.route-panel').append(routeTools);
      byId('listen-button').before(skip);
      byId('result-details').append(options);
    } else {
      document.querySelector('.route-panel').append(routeTools);
      byId('journey-button').before(skip);
      byId('listen-button').after(options);
    }
  }
  compact.addEventListener('change', reflowControls);
  reflowControls();

  function syncMood() {
    const select = byId('layer-mood');
    for (const button of byId('mood-choices').querySelectorAll('button')) {
      button.setAttribute('aria-pressed', String(button.dataset.mood === select.value));
      button.disabled = select.disabled;
      button.setAttribute('aria-describedby', 'mood-selection-help');
    }
  }
  byId('mood-choices').addEventListener('click', event => {
    const button = event.target.closest('button[data-mood]');
    if (!button || button.disabled) return;
    const select = byId('layer-mood');
    select.value = select.value === button.dataset.mood ? 'unset' : button.dataset.mood;
    select.dispatchEvent(new Event('change', { bubbles: true }));
  });
  byId('layer-mood').addEventListener('change', syncMood);
  new MutationObserver(syncMood).observe(byId('layer-mood'), { attributes: true, attributeFilter: ['disabled'] });

  function syncRoute() {
    setText(byId('route-destination-label'), byId('destination').value.trim() || '아직 정하지 않은 길');
  }
  for (const type of ['input', 'change']) byId('destination').addEventListener(type, syncRoute);
  for (const id of ['source-tag', 'route-warning', 'native-route-summary']) new MutationObserver(syncRoute).observe(byId(id), { childList: true, subtree: true, characterData: true });

  function syncView() {
    const view = ['input', 'result', 'collection'].find(name => !byId(name + '-view').hidden) || 'input';
    document.body.dataset.view = view;
    if (view !== activeView) {
      activeView = view;
      closePanels();
      const titles = {
        input: ['출발 전', '어디로 떠날까요?', '길을 고르면, 눈티도 여행을 준비해요.'],
        result: ['출발 준비', '이번 여행의 눈티', '준비가 끝나면 함께 출발하세요.'],
        collection: ['내 눈티', '함께 다녀온 길', '눈티에 남은 여행을 다시 만나보세요.'],
      };
      const [label, heading, subheading] = titles[view];
      setText(byId('app-state-label'), label);
      setText(byId('heading'), heading);
      setText(byId('subheading'), subheading);
      if (view === 'input') { syncRoute(); syncMood(); }
    }
  }
  const viewObserver = new MutationObserver(syncView);
  for (const name of ['input', 'result', 'collection']) viewObserver.observe(byId(name + '-view'), { attributes: true, attributeFilter: ['hidden'] });

  function voiceLabel() {
    const button = byId('listen-button');
    const raw = button.textContent.trim();
    if (raw === '▷') setText(button, '목소리 듣기');
    else if (raw === '□') setText(button, '듣기 멈추기');
  }
  new MutationObserver(voiceLabel).observe(byId('listen-button'), { childList: true, subtree: true, characterData: true });

  const birthStage = document.querySelector('.birth-stage');
  function syncStageSummary() {
    const names = [...byId('character-story').querySelectorAll('b')].map(n => n.textContent.trim()).filter(Boolean);
    const summary = birthStage.dataset.skinSummary || names.slice(0, 3).join(' · ');
    setText(byId('stage-summary'), summary || byId('result-destination').textContent.trim() || '기본 눈티 A');
  }
  const storyObserver = new MutationObserver(syncStageSummary);
  storyObserver.observe(byId('character-story'), { childList: true, subtree: true, characterData: true });
  storyObserver.observe(byId('result-destination'), { childList: true, subtree: true, characterData: true });
  storyObserver.observe(birthStage, { attributes: true, attributeFilter: ['data-skin-summary'] });

  function applyAppearance(config = {}, native = true) {
    if (typeof config === 'string') { try { config = JSON.parse(config); } catch { return; } }
    if (!config || typeof config !== 'object') return;
    if (native) nativeAppearanceReceived = true;
    const theme = String(config.theme || '').toLowerCase();
    if (theme === 'day' || theme === 'night') appearance.theme = theme;
    if (typeof config.systemReducedMotion === 'boolean') appearance.systemReducedMotion = config.systemReducedMotion;
    if (native && Number.isInteger(config.viewportWidth) && config.viewportWidth > 0 &&
        Number.isInteger(config.viewportHeight) && config.viewportHeight > 0) {
      const density = Number(window.devicePixelRatio) || 1;
      const content = `width=${config.viewportWidth},initial-scale=${(1 / density).toFixed(6)}`;
      const viewport = document.querySelector('meta[name="viewport"]');
      if (viewport && viewport.content !== content) viewport.content = content;
      appearance.viewportWidth = config.viewportWidth;
      appearance.viewportHeight = config.viewportHeight;
    }
    document.documentElement.dataset.theme = appearance.theme;
    document.documentElement.dataset.systemReducedMotion = String(appearance.systemReducedMotion);
    window.dispatchEvent(new CustomEvent('nunti:appearance-applied', { detail: { ...appearance } }));
  }
  window.NuntiAppearance = { apply: applyAppearance, get config() { return { ...appearance }; } };
  window.NuntiUI = { closePanels, sync: () => { syncView(); syncRoute(); syncMood(); }, setVehicleAllowed(allowed) { document.body.dataset.vehicleAllowed = String(allowed); if (!allowed) closePanels(); } };
  window.addEventListener('nunti:appearance', event => applyAppearance(event.detail));
  window.addEventListener('nunti:vehicle-allowed', event => window.NuntiUI.setVehicleAllowed(event.detail?.allowed !== false));
  matchMedia('(prefers-color-scheme: dark)').addEventListener('change', event => { if (!nativeAppearanceReceived) applyAppearance({ theme: event.matches ? 'night' : 'day' }, false); });
  syncView(); syncMood(); syncRoute(); voiceLabel(); syncStageSummary(); applyAppearance(appearance, false);
})();
