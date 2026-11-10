'use strict';
(() => {
  // Locked for the offline milestone. Android independently blocks model endpoints.
  const MOCK_SKIN_MODE = true;
  const legacyVersion = 'skin-v2.0';
  const version = 'skin-v2.2';
  const storageKey = 'nunti.skin-v2.records';
  const base = Object.freeze({
    skinId:'default', name:'눈티', outfit:'새싹과 작은 여행 가방', headStyle:'새싹 후드', earStyle:'둥근 후드',
    eyeStyle:'기본 눈매', accessories:Object.freeze(['기본 여행 가방']), palette:'#6B9B83', pattern:'기본'
  });
  const wardrobe = Object.freeze(Object.fromEntries(Object.entries({
    default:base,
    sea:{skinId:'sea',name:'바닷길 눈티',outfit:'바다색 코트에 나침반을 챙겼어요.',headStyle:'산호 장식 후드',earStyle:'작은 산호',eyeStyle:'웃는 눈',accessories:['유리 나침반','작은 여행 가방'],palette:'#2A6870',pattern:'파도가 남긴 자수'},
    city:{skinId:'city',name:'도시의 눈티',outfit:'헤드폰을 쓰고 새로운 골목을 찾아요.',headStyle:'새싹 후드와 헤드폰',earStyle:'남색 헤드폰',eyeStyle:'호기심 어린 눈',accessories:['길 안내 배지','여행 크로스백'],palette:'#685B91',pattern:'도시의 작은 불빛'},
    mountain:{skinId:'mountain',name:'산길 눈티',outfit:'따뜻한 옷과 튼튼한 신발을 준비했어요.',headStyle:'이끼색 니트 모자',earStyle:'새싹',eyeStyle:'웃는 눈',accessories:['등산 배낭','호박빛 나뭇잎'],palette:'#687247',pattern:'능선을 따라 놓은 자수'}
  }).map(([key,value])=>[key,Object.freeze({...value,accessories:Object.freeze(value.accessories)})])));
  const fixtures = Object.freeze({
    default:{name:'기본 눈티',destinationCategory:'unknown',roadType:'unknown',mood:'unset',points:null},
    sea:{name:'파도 해변',destinationCategory:'coast',roadType:'highway',mood:'calm',points:[[.08,.72],[.25,.54],[.46,.63],[.71,.32],[.92,.26]]},
    city:{name:'밤의 도시',destinationCategory:'city',roadType:'urban',mood:'curious',points:[[.08,.8],[.26,.8],[.26,.53],[.57,.53],[.57,.25],[.89,.25]]},
    mountain:{name:'새싹 능선',destinationCategory:'mountain',roadType:'rural',mood:'adventurous',points:[[.08,.82],[.24,.69],[.38,.72],[.51,.44],[.62,.54],[.87,.2]]}
  });
  const own = (obj,key)=>Object.hasOwn(obj,key);
  const knownVersion = value => value===version||value==='skin-v2.1'||value===legacyVersion;
  const path = (id,layer='final',assetVersion=version)=>{
    if(!own(wardrobe,id)||!['final','outfit','head','eyes','accessory'].includes(layer))throw new Error('UNKNOWN_SKIN_ASSET');
    if(!knownVersion(assetVersion))throw new Error('UNKNOWN_SKIN_VERSION');
    const directory=id==='default'||assetVersion===legacyVersion?'/skin-v2/':assetVersion===version?'/skin-v2/atelier/':'/skin-v2/polish/';
    return directory+id+'/'+layer+'.png';
  };
  function resolve({destinationCategory,roadType,mood,routeId}={}) {
    const destination = ['sea','coast','city','mountain'].includes(destinationCategory)?destinationCategory:'unknown';
    const skin = wardrobe[destination==='coast'?'sea':destination] || base;
    const road = ['urban','highway','rural','mixed'].includes(roadType)?roadType:'unknown';
    const selected = ['calm','curious','adventurous','excited'].includes(mood)?mood:'unset';
    return {...skin, version, mood:selected==='excited'?'adventurous':selected, road, routeId:typeof routeId==='string'?routeId:'none',
      animationPreset:{ribbon:road==='urban'?'segmented':road==='rural'?'dotted':'solid',
        sweep: selected==='adventurous' || selected==='excited' ? 'uphill' : selected==='curious' ? 'diagonal' : 'horizontal'}};
  }
  function phaseAt(elapsed) {
    return elapsed>=4000?'FINAL_IDLE':elapsed>=3300?'SKIN_REVEAL':elapsed>=2000?'HEAD_AND_EYES_TRANSFORM':
      elapsed>=1200?'OUTFIT_SWAP':elapsed>=500?'ROUTE_ENERGY':'DEFAULT_IDLE';
  }
  function storage() { return JSON.parse(localStorage.getItem(storageKey)||'{}'); }
  function list() {
    return Object.values(storage()).filter(isSkin).sort((a,b)=>b.savedAt-a.savedAt);
  }
  function isSkin(artifact) {
    const spec=artifact?.design?.skinSpec;
    return knownVersion(spec?.version)&&typeof spec.skinId==='string'&&own(wardrobe,spec.skinId)&&
      /^nunti-skin-[a-f0-9]{32}$/.test(artifact.characterId||'')&&artifact.visual?.path===path(spec.skinId,'final',spec.version);
  }
  async function digest(text) {
    return Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(text))),b=>b.toString(16).padStart(2,'0')).join('');
  }
  async function createRecord(input, context, finalAvailable) {
    let spec=resolve(context);
    const requested=spec.skinId;
    if(!finalAvailable)spec={...resolve({...context,destinationCategory:'unknown'}),fallback:'FINAL_ASSET_MISSING',requestedSkinId:requested};
    const characterId='nunti-skin-'+(await digest(JSON.stringify([version,input,spec]))).slice(0,32);
    return {characterId,savedAt:Date.now(),destination:input.destination,purpose:input.purpose,route:input.route,
      displayName:spec.name,mediaOrigin:'MOCK_SKIN',visual:{path:path(spec.skinId)},
      design:{skinSpec:spec,staticOnly:true,personality:spec.outfit,motifs:[]},
      voice:{provider:'DEVICE_SPEECH',description:'기기에 설치된 오프라인 음성',pitch:1.08,rate:1}};
  }
  function save(record) {
    if(!isSkin(record))throw new Error('INVALID_SKIN_RECORD');
    const records=storage();
    if(records[record.characterId])return records[record.characterId];
    records[record.characterId]=record;
    localStorage.setItem(storageKey,JSON.stringify(records));
    return record;
  }
  function assertRequest(path,method) {
    if(!MOCK_SKIN_MODE)return;
    const local=typeof path==='string'&&path.startsWith('/')&&!path.startsWith('//')&&!/[\\\r\n]/.test(path);
    // Only the existing local session and route tools may mutate server state.
    if(!local||(method!=='GET'&&!['/session','/v3/route-extractions','/v3/route-plans'].includes(path)))throw new Error('MOCK_SKIN_MODE');
  }
  window.NuntiSkins=Object.freeze({MOCK_SKIN_MODE,version,storageKey,fixtures,resolve,path,phaseAt,isSkin,list,save,createRecord,assertRequest});
})();
