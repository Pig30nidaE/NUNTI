'use strict';
// Native metadata and externally calculated road geometry have separate provenance.
(() => {
  const presets = {
    pangyo: {origin:[37.4051,127.0953,'판교'],destination:[37.5259,126.9283,'더현대서울'],traits:'도심, 한강, 여의도의 산책',purpose:'새로운 곳에서 쉬어가기'},
    seoul: {origin:[37.5547,126.9707,'서울역'],destination:[37.5663,126.9779,'서울시청'],traits:'도심 광장과 오래된 거리',purpose:'도시 산책'},
    coast: {origin:[37.7644,128.8996,'강릉역'],destination:[37.7736,128.9480,'안목해변'],traits:'파란 바다, 파도와 커피 향',purpose:'바다를 보며 쉬기'},
  };
  let caps={}, native=null, context=null, plan=null, lastPlanId=null, originName='출발지', importing=false, nativeStale=false;
  try{const id=localStorage.getItem('nunti.lastRoutePlan');if(/^[a-f0-9]{64}$/.test(id||''))lastPlanId=id;}catch{}
  const hasNative=()=>typeof window.NuntiNative?.getNavigationSnapshot==='function';
  const pause=ms=>new Promise(resolve=>setTimeout(resolve,ms));
  const coord=prefix=>({latitude:Number($(prefix+'-lat').value),longitude:Number($(prefix+'-lon').value)});
  const validCoord=p=>Number.isFinite(p.latitude)&&Number.isFinite(p.longitude)&&Math.abs(p.latitude)<=90&&Math.abs(p.longitude)<=180;
  const fieldsFilled=()=>['nav-origin-lat','nav-origin-lon','nav-destination-lat','nav-destination-lon'].every(id=>$(id).value.trim()!=='');
  const signature=s=>JSON.stringify([s?.sessionId,s?.revision,s?.destination?.latitude,s?.destination?.longitude,s?.destination?.name,s?.currentLocation?.routeId,s?.routeState?.routeOption,s?.routeState?.isRouting]);
  function inputsMatch(){return !nativeStale&&!!plan&&fieldsFilled()&&['latitude','longitude'].every(key=>coord('nav-origin')[key]===plan.origin[key]&&coord('nav-destination')[key]===plan.destination[key])&&$('destination').value.trim()===plan.destination.name;}
  function feedback(text=''){
    for(const id of ['route-feedback','route-tool-feedback']){
      const node=$(id);
      if(node.textContent!==text)node.textContent=text;
      node.hidden=!text;
    }
  }
  function revealRoute(control){
    const dialog=$('route-tools-dialog');
    if(dialog?.open)dialog.close();
    if(control&&!control.disabled){
      control.focus?.({preventScroll:true});
      (control.closest?.('.confirm-row')||control).scrollIntoView?.({block:'nearest'});
    }
  }
  function updateButtons(){
    const blocked=state.busy||state.planning||importing||!state.nativeAllowed;
    if($('route-destination-input').value!==$('destination').value)$('route-destination-input').value=$('destination').value;
    if(importing)$('create-button').disabled=true;
    $('nav-calculate').disabled=blocked||!caps.routeApiAvailable||!fieldsFilled()||!$('destination').value.trim();
    $('nav-calculate-inline').disabled=$('nav-calculate').disabled;
    $('route-next').hidden=!(caps.routeApiAvailable&&context&&!state.route);
    $('nav-replay').disabled=blocked||!lastPlanId||!caps.routeApiAvailable;
    $('nav-import').disabled=blocked||importing||!native?.connected;
    for(const id of ['nav-send','nav-open','nav-overview'])$(id).disabled=blocked||!native?.connected;
    if(state.route?.inputOrigin==='API_ROUTE'){
      const matches=inputsMatch();$('route-confirmed').disabled=!matches;
      if(!matches){$('route-confirmed').checked=false;$('create-button').disabled=true;}
    }
  }
  function routeChanged(route){
    feedback();
    const active=route?.inputOrigin==='API_ROUTE';$('route-attribution').hidden=!active;
    if(active){$('map-caption').textContent='OSRM 자동차 경로';$('route-warning').textContent='출발·목적지와 선 전체를 확인해 주세요. 이 선은 OSRM이 계산했으며 현대 내비의 선택 경로와 다를 수 있어요.';}
    else $('api-route-summary').textContent='';
  }
  function snapshot(raw){
    let next;try{next=typeof raw==='string'?JSON.parse(raw):raw;}catch{return;}
    if(!next||typeof next!=='object')return;native=next;
    $('navigation-status').textContent=next.connected?(next.receivedCallbackCount===0?'내비 서비스 연결됨 · 홈의 내비 앱에서 초기 화면·경로 복원을 마친 뒤 불러와 주세요.':'현대 내비 연결됨 · 목적지와 현재 위치를 가져올 수 있어요.'):next.status==='CONNECTING'?'현대 내비에 연결하고 있어요.':'현대 내비를 연결하지 못했어요. 아래 시험 입력으로 경로 API를 사용할 수 있어요.';
    const d=next.destination,r=next.routeState;
    $('native-route-summary').textContent=d?.name?`현대 내비: ${d.name}${Number.isFinite(d.remainDistance)?' · 남은 '+(d.remainDistance/1000).toFixed(1)+' km':''}${r?.routeOption?' · '+r.routeOption:''}`:'현대 내비에 목적지를 설정한 다음 불러와 주세요.';
    if(!nativeStale&&plan?.nativeSnapshot&&signature(next)!==signature(plan.nativeSnapshot)&&state.route?.apiPlanId===plan.planId){
      nativeStale=true;
      $('route-confirmed').checked=false;
      feedback('내비의 경로가 바뀌었어요. 내비 목적지를 다시 불러와 주세요.');
    }
    enableCreate();
  }
  function readNative(){if(hasNative())snapshot(window.NuntiNative.getNavigationSnapshot());return native;}
  function command(name,payload={}){
    if(!hasNative()||!state.nativeAllowed)throw new Error('주차 상태에서 Android 앱의 현대 내비 연결을 확인해 주세요.');
    const ack=JSON.parse(window.NuntiNative.navigationCommand(name,JSON.stringify(payload)));
    if(!ack.accepted)throw new Error('현대 내비가 요청을 받지 못했어요. '+(ack.error||''));return ack;
  }
  async function importNative(){
    if(importing||state.busy||state.planning||!state.nativeAllowed)return;const epoch=++fileEpoch;extractionEpoch++;importing=true;updateButtons();
    feedback('내비에서 목적지를 확인하고 있어요…');
    let imported=false;
    try{
      const before=readNative()?.sequence||0;command('refresh');const end=Date.now()+7000;let observed=false;
      while(Date.now()<end){await pause(150);if(epoch!==fileEpoch||!state.nativeAllowed)return;const s=readNative();const kinds=new Set((s?.events||[]).filter(e=>e.sequence>before).map(e=>e.type));if(['onDestinationInfo','onCurrentLocationInfo','onRouteStateInfo'].every(kind=>kinds.has(kind))){observed=true;break;}}
      if(!observed)throw new Error('현재 목적지·위치 응답을 아직 받지 못했어요. 현대 내비에 목적지를 설정한 뒤 다시 눌러 주세요.');
      const d=native.destination,o=native.currentLocation;
      if(!d?.name||!validCoord(d)||!validCoord(o)||(!o.latitude&&!o.longitude))throw new Error('현대 내비에서 유효한 목적지와 현재 위치를 확인하지 못했어요.');
      context=JSON.parse(JSON.stringify(Object.fromEntries(Object.entries(native).filter(([key])=>key!=='events'&&key!=='tbt'&&key!=='trip'))));
      for(const [prefix,p] of [['nav-origin',o],['nav-destination',d]]){for(const key of ['latitude','longitude'])$(prefix+(key==='latitude'?'-lat':'-lon')).value=p[key];}
      originName='현대 내비 현재 위치';$('destination').value=d.name;
      $('nav-case').value='';
      setRoute(null,null);
      imported=true;
    }catch(e){if(epoch===fileEpoch&&state.nativeAllowed)feedback(errorText(e));}
    finally{
      importing=false;enableCreate();
      if(imported)revealRoute($('route-next').hidden?$('destination'):$('nav-calculate-inline'));
    }
  }
  function invalidateInput(){
    fileEpoch++;extractionEpoch++;state.busy=state.generating;state.pending=null;$('route-confirmed').checked=false;feedback();enableCreate();
  }
  function preset(name){
    const p=presets[name];if(!p)return;context=null;originName=p.origin[2];
    for(const [prefix,v] of [['nav-origin',p.origin],['nav-destination',p.destination]]){$(prefix+'-lat').value=v[0];$(prefix+'-lon').value=v[1];}
    $('destination').value=p.destination[2];$('traits').value=p.traits;$('purpose').value=p.purpose;invalidateInput();
    $('api-route-summary').textContent='예시 좌표를 입력했어요.';
  }
  function applyPlan(value){
    plan=value;lastPlanId=value.planId;try{localStorage.setItem('nunti.lastRoutePlan',lastPlanId);}catch{}nativeStale=!!value.nativeSnapshot&&signature(native)!==signature(value.nativeSnapshot);setRoute({...value.route,confirmed:false},null,false);$('image-options').hidden=true;const g=value.geometry;
    $('api-route-summary').textContent=`${value.origin.name||'출발지'} → ${value.destination.name} · ${(g.distanceMeters/1000).toFixed(1)} km · 약 ${Math.ceil(g.durationSeconds/60)}분`;
    if(nativeStale)feedback('저장한 길과 현재 내비가 달라요. 내비 목적지를 다시 불러와 주세요.');
    enableCreate();
  }
  async function calculate(replay=false){
    if(state.busy||state.planning||importing||!state.nativeAllowed)return;
    const origin={...coord('nav-origin'),name:originName},destination={...coord('nav-destination'),name:$('destination').value.trim()};
    if(!replay&&(!fieldsFilled()||!validCoord(origin)||!validCoord(destination)||!destination.name)){feedback('출발·목적지 위경도와 목적지 이름을 입력해 주세요.');return;}
    const epoch=++fileEpoch;extractionEpoch++;state.planning=true;state.pending=null;enableCreate();feedback(replay?'저장한 길을 불러오고 있어요…':'길을 불러오고 있어요…');
    try{
      const value=replay?await api('/v3/route-plans/'+encodeURIComponent(lastPlanId)):await api('/v3/route-plans',{origin,destination,...(context?{nativeSnapshot:context}:{})});
      if(epoch!==fileEpoch||!state.nativeAllowed||(!replay&&
        ($('destination').value.trim()!==destination.name||!fieldsFilled()||
          ['latitude','longitude'].some(key=>coord('nav-origin')[key]!==origin[key]||coord('nav-destination')[key]!==destination[key]))))return;
      if(replay){for(const [prefix,p] of [['nav-origin',value.origin],['nav-destination',value.destination]]){$(prefix+'-lat').value=p.latitude;$(prefix+'-lon').value=p.longitude;}$('destination').value=value.destination.name;originName=value.origin.name;context=value.nativeSnapshot;$('nav-case').value='';}
      applyPlan(value);
      revealRoute($('route-confirmed'));
    }catch(e){if(epoch===fileEpoch&&state.nativeAllowed)feedback(errorText(e));}
    finally{state.planning=false;enableCreate();}
  }
  function setCapabilities(value,{prefill=true}={}){
    caps=value;$('navigation-tools').hidden=!(caps.routeApiAvailable||hasNative());$('legacy-route-tools').hidden=!!caps.routeApiAvailable;
    if(prefill&&caps.routeApiAvailable&&!fieldsFilled())preset('pangyo',false);
    if(!hasNative())$('navigation-status').textContent='현대 내비 목적지 가져오기는 Android 앱에서, 경로 API 시험은 이 화면에서 할 수 있어요.';
    updateButtons();
  }
  $('nav-case').onchange=()=>preset($('nav-case').value);
  for(const id of ['nav-origin-lat','nav-origin-lon','nav-destination-lat','nav-destination-lon'])$(id).addEventListener('input',()=>{context=null;originName='출발지';$('nav-case').value='';invalidateInput();});
  $('destination').addEventListener('input',()=>{
    if(state.planning||((context||state.route?.inputOrigin==='API_ROUTE')&&$('destination').value.trim()!==(context?.destination?.name||plan?.destination.name))){
      context=null;invalidateInput();
    }
    updateButtons();
  });
  $('route-destination-input').addEventListener('input',()=>{
    $('destination').value=$('route-destination-input').value;
    $('destination').dispatchEvent(new Event('input',{bubbles:true}));
  });
  $('nav-import').onclick=importNative;$('nav-calculate').onclick=$('nav-calculate-inline').onclick=()=>calculate();$('nav-replay').onclick=()=>calculate(true);
  $('nav-send').onclick=()=>{try{const d=coord('nav-destination');if(!fieldsFilled()||!validCoord(d)||!$('destination').value.trim())throw new Error('목적지 이름과 위경도를 입력해 주세요.');command('requestRoute',{...d,name:$('destination').value.trim()});feedback('현대 내비에 목적지 설정을 요청했어요.');}catch(e){feedback(errorText(e));}};
  $('nav-open').onclick=()=>{try{command('foreground');}catch(e){feedback(errorText(e));}};
  $('nav-overview').onclick=()=>{try{command('overview',{durationMs:15000});}catch(e){feedback(errorText(e));}};
  window.NuntiNavigation={setCapabilities,updateButtons,routeChanged,readNative,importNative,getPlan:()=>plan,getNative:()=>native,canGenerate:()=>!importing&&(state.route?.inputOrigin!=='API_ROUTE'||inputsMatch())};window.nuntiNavigationChanged=snapshot;
  readNative();setCapabilities(window.nuntiCapabilities||{});
})();
