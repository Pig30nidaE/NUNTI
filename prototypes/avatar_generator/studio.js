'use strict';
const $ = id => document.getElementById(id);
const state = { route: null, sourceImage: null, imageReady:false, routeVersion:0, examples: [], artifact: null, avatars: [], busy: false, generating:false, planning:false, pending: null, animation: 0, nativeAllowed: true };
let extractionEpoch=0;
let viewEpoch=0, collectionEpoch=0;
const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
const message = text => { $('notice').textContent = text; $('notice').hidden = !text; };
const errorText = error => ({LOCAL_MODEL_BUSY:'목소리 생성이 끝난 뒤 다시 눌러 주세요. 같은 여정으로 이어서 만들 수 있어요.',INVALID_ROUTE_IMAGE:'사진을 읽지 못했어요. PNG 또는 JPG 경로 사진을 선택해 주세요.',ROUTE_NOT_FOUND:'경로선을 찾지 못했어요. 다른 색을 고르거나 좌표 파일을 넣어 주세요.',AMBIGUOUS_ROUTE:'여러 경로가 보여요. 한 경로만 보이도록 사진을 잘라 주세요.'}[error.message] || error.message || '연결을 확인한 뒤 다시 시도해 주세요.');
async function api(path, body, method = 'GET') {
  const response = await fetch(path, {method: body ? 'POST' : method, credentials:'same-origin', headers:body ? {'Content-Type':'application/json'} : {}, body: body ? JSON.stringify(body) : undefined});
  const value = await response.json();
  if (!response.ok) { const e = new Error(value.error?.message || value.detail?.message || value.error?.code || (typeof value.detail === 'string' ? value.detail : '요청을 처리하지 못했어요.')); e.status=response.status; throw e; }
  return value.data ?? value;
}
function screen(which) {
  viewEpoch++;
  for (const name of ['input','result','collection']) $(name+'-view').hidden = name !== which;
  $('examples-section').hidden = which !== 'input';
  $('heading').textContent = which === 'result' ? '이 길에서 태어난, 나의 눈티.' : which === 'collection' ? '우리의 여정이 모이는 곳.' : '이번 길은, 어떤 눈티가 될까요?';
  $('subheading').textContent = which === 'result' ? '이 눈티와 함께, 오늘의 운전에도 작은 변화를 만들어가요.' : '목적지와 경로에서 나만의 작은 동반자가 태어납니다. 함께 달리며 좋은 운전습관을 만들어갈 동반자를 만나세요.';
  for(let i=1;i<=3;i++) $('step-'+i).classList.toggle('active',i===(which==='result'?2:1));
  stopVoice();
  requestAnimationFrame(drawRoute);
}
function canvasSize(canvas) {
  const rect=canvas.getBoundingClientRect(),dpr=Math.min(devicePixelRatio||1,2);
  const width=Math.max(1,rect.width),height=Math.max(1,rect.height);
  if(canvas.width!==Math.round(width*dpr)||canvas.height!==Math.round(height*dpr)){canvas.width=Math.round(width*dpr);canvas.height=Math.round(height*dpr);}
  const ctx=canvas.getContext('2d');ctx.setTransform(dpr,0,0,dpr,0,0);ctx.clearRect(0,0,width,height);return {ctx,width,height};
}
function fitPoints(points,w,h,pad=20) {
  const xs=points.map(p=>p[0]),ys=points.map(p=>p[1]);const x0=Math.min(...xs),y0=Math.min(...ys),dx=Math.max(...xs)-x0||.01,dy=Math.max(...ys)-y0||.01;
  const scale=Math.min((w-pad*2)/dx,(h-pad*2)/dy);return points.map(p=>[(w-dx*scale)/2+(p[0]-x0)*scale,(h-dy*scale)/2+(p[1]-y0)*scale]);
}
function strokeRoute(ctx,points,color='#638970',width=4,progress=1) {
  if(points.length<2)return;ctx.beginPath();ctx.moveTo(...points[0]);
  const distances=[0];for(let i=1;i<points.length;i++)distances.push(distances[i-1]+Math.hypot(points[i][0]-points[i-1][0],points[i][1]-points[i-1][1]));
  const end=Math.max(0,Math.min(1,progress))*distances.at(-1);
  for(let i=1;i<points.length;i++){if(distances[i]<=end)ctx.lineTo(...points[i]);else{const span=distances[i]-distances[i-1],t=span?(end-distances[i-1])/span:0;ctx.lineTo(points[i-1][0]+(points[i][0]-points[i-1][0])*t,points[i-1][1]+(points[i][1]-points[i-1][1])*t);break;}}
  ctx.strokeStyle=color;ctx.lineWidth=width;ctx.lineCap='round';ctx.lineJoin='round';ctx.stroke();
}
function pins(ctx,points){for(let i=0;i<2;i++){const p=points[i?points.length-1:0];ctx.beginPath();ctx.arc(...p,i?6:4,0,Math.PI*2);ctx.fillStyle=i?'#ee7952':'#42695a';ctx.fill();ctx.lineWidth=2;ctx.strokeStyle='#fff';ctx.stroke();}}
function drawRoute(){
  const canvas=$('route-canvas');if(!canvas.getBoundingClientRect().width)return;const {ctx,width:w,height:h}=canvasSize(canvas);
  $('map-empty').hidden=!!state.route;
  if(!state.route||!state.imageReady)return;
  let points;
  if(state.sourceImage){const img=$('route-image');const iw=img.naturalWidth,ih=img.naturalHeight;const scale=Math.min(w/iw,h/ih);points=state.route.points.map(p=>[(w-iw*scale)/2+p[0]*iw*scale,(h-ih*scale)/2+p[1]*ih*scale]);}
  else{ctx.strokeStyle='#dde4d7';ctx.lineWidth=1;for(let x=-h;x<w;x+=45){ctx.beginPath();ctx.moveTo(x,0);ctx.lineTo(x+h,h);ctx.stroke();}points=fitPoints(state.route.points,w,h,38);}
  strokeRoute(ctx,points,'#fffefa',9);strokeRoute(ctx,points,'#4c866d',4);pins(ctx,points);
}
function setRoute(route,imagePath,confirmed=false){
  extractionEpoch++;fileEpoch++;state.busy=state.generating;const version=++state.routeVersion;
  state.route=route;state.sourceImage=imagePath||null;state.imageReady=!imagePath;$('route-image').hidden=!imagePath;
  $('route-confirmed').disabled=!!imagePath;
  if(imagePath){const img=$('route-image');img.onload=()=>{if(version!==state.routeVersion)return;state.imageReady=true;$('route-confirmed').disabled=false;drawRoute();enableCreate();};img.onerror=()=>{if(version!==state.routeVersion)return;state.imageReady=false;message('경로 원본 사진을 불러오지 못했어요. 사진을 다시 선택해 주세요.');enableCreate();};img.src=imagePath;}else $('route-image').removeAttribute('src');
  $('route-confirmed').checked=confirmed;state.pending=null;
  $('source-tag').textContent=route.inputOrigin==='API_ROUTE'?'API 경로':route.inputOrigin==='NAVIGATION_SCREENSHOT'?'내비 경로 사진':route.inputOrigin==='ROUTE_FILE'?'좌표 파일':'시험 경로';
  $('map-caption').textContent=route.inputOrigin==='TEST_ROUTE'?'합성 내비 입력 예시 · 실제 내비 연결 아님':'표시된 선을 확인해 주세요';
  $('route-warning').textContent=route.warnings?.join(' ')||'원본과 선이 일치하는지 확인한 뒤 체크해 주세요. 화면 좌표를 GPS나 주행 거리로 해석하지 않아요.';
  drawRoute();enableCreate();
  window.NuntiNavigation?.routeChanged(route);
}
function enableCreate(){$('create-button').disabled=state.busy||state.planning||!state.nativeAllowed||!state.route||!state.imageReady||!$('route-confirmed').checked||!$('destination').value.trim();window.NuntiNavigation?.updateButtons();}
function viewExample(example){
  message('');$('destination').value=example.destination.name;$('traits').value=example.destination.traits||'';$('purpose').value=example.purpose||'';
  setRoute({...example.route,confirmed:false},example.imagePath,false);$('image-options').hidden=true;
  document.querySelectorAll('.example').forEach(x=>x.classList.toggle('selected',x.dataset.id===example.id));
}
async function examples(){
  const response=await api('/v3/examples');state.examples=Array.isArray(response)?response:response.examples;
  $('examples').replaceChildren();for(const ex of state.examples){const b=document.createElement('button');b.className='example';b.dataset.id=ex.id;
    const c=document.createElement('canvas');c.width=106;c.height=90;const ctx=c.getContext('2d');strokeRoute(ctx,fitPoints(ex.route.points,106,90,16),'#5a876d',4);
    const text=document.createElement('div'),strong=document.createElement('strong'),small=document.createElement('small');strong.textContent=ex.title;small.textContent=ex.destination.name;text.append(strong,small);b.append(c,text);b.onclick=()=>viewExample(ex);$('examples').append(b);
  }
  if(state.examples[0]&&!state.route&&!window.nuntiCapabilities?.routeApiAvailable)viewExample(state.examples[0]);
}
let uploadData=null;
let fileEpoch=0;
async function extract(){
  if(!uploadData||state.generating)return;const epoch=++extractionEpoch;const imageBase64=uploadData;state.busy=true;enableCreate();message('사진에서 경로선을 찾고 있어요…');
  try{const data=await api('/v3/route-extractions',{imageBase64,...($('route-color').value?{colorHint:$('route-color').value}:{})});if(epoch!==extractionEpoch)return;
    setRoute({points:data.points,inputOrigin:'NAVIGATION_SCREENSHOT',sourceLabel:'사용자가 불러온 내비 경로 사진',confirmed:false,extractionId:data.extractionId,warnings:data.warnings},data.imagePath);
    message('사진 위에 표시된 선을 확인해 주세요. 다른 길이 선택되면 경로선 색상을 바꾸거나 한 경로만 남도록 사진을 잘라 주세요.');
  }catch(e){if(epoch!==extractionEpoch)return;state.route=null;$('route-confirmed').checked=false;message(errorText(e));}
  finally{if(epoch===extractionEpoch)state.busy=false;enableCreate();}
}
$('image-upload').onchange=async event=>{const file=event.target.files[0];if(!file)return;if(file.size>6*1024*1024){message('6MB 이하의 경로 사진을 선택해 주세요.');return;}
  const version=++fileEpoch;extractionEpoch++;state.busy=true;enableCreate();
  const reader=new FileReader();reader.onload=()=>{if(version!==fileEpoch)return;uploadData=String(reader.result).split(',')[1];$('image-options').hidden=false;$('route-color').value='';extract();};reader.onerror=()=>{if(version!==fileEpoch)return;state.busy=false;enableCreate();message('사진 파일을 읽지 못했어요. 다운로드 폴더에 저장한 PNG 또는 JPG를 다시 선택해 주세요.');};reader.readAsDataURL(file);event.target.value='';};
$('extract-again').onclick=extract;
$('route-upload').onchange=async event=>{const file=event.target.files[0];if(!file)return;fileEpoch++;extractionEpoch++;try{if(file.size>65536)throw new Error('64KB 이하의 경로 JSON을 선택해 주세요.');const value=JSON.parse(await file.text()),r=value.route||value;const points=r.points;if(!Array.isArray(points)||points.length<2||points.length>512||!points.every(p=>Array.isArray(p)&&p.length===2&&p.every(n=>typeof n==='number'&&Number.isFinite(n)&&n>=0&&n<=1)))throw new Error('points에 0부터 1 사이의 [x,y] 좌표를 2~512개 넣어 주세요.');
  if(value.destination){$('destination').value=value.destination.name||'';$('traits').value=value.destination.traits||'';}if(value.purpose)$('purpose').value=value.purpose;
  setRoute({points,inputOrigin:'ROUTE_FILE',sourceLabel:file.name,confirmed:false},null);$('image-options').hidden=true;message('좌표 파일을 불러왔어요. 선을 확인한 뒤 생성할 수 있어요.');
}catch(e){message(errorText(e));}event.target.value='';};
$('route-confirmed').onchange=enableCreate;for(const id of ['destination','traits','purpose'])$(id).addEventListener('input',enableCreate);
$('render-mode').onchange=()=>{
  $('engine-note').textContent=$('render-mode').value==='LOCAL_MODEL'?'약 1분 동안 로컬 AI로 새 그림을 그려요. 얼굴이나 형태가 어색할 수 있어 결과를 확인해 주세요.':$('render-mode').value==='IMAGE_API'?'외부 이미지 API를 사용해요. 서버의 비용 승인과 설정이 필요해요.':'경로의 굴곡으로 일러스트를 빠르게 새로 그려요. 외부 API를 사용하지 않아요.';
};
$('journey-form').onsubmit=async event=>{
  event.preventDefault();if(state.busy||state.planning||!state.nativeAllowed||!state.route||!state.imageReady||!$('route-confirmed').checked||window.NuntiNavigation?.canGenerate()===false)return;
  const {points,inputOrigin,sourceLabel,extractionId,apiPlanId}=state.route;
  const input={destination:{name:$('destination').value.trim(),traits:$('traits').value.trim()},purpose:$('purpose').value.trim(),route:{points,inputOrigin,sourceLabel,confirmed:true,...(extractionId?{extractionId}:{}),...(apiPlanId?{apiPlanId}:{})},renderMode:$('render-mode').value};
  if(!state.pending||state.pending.canonical!==JSON.stringify(input))state.pending={canonical:JSON.stringify(input),body:{requestId:crypto.randomUUID(),...input}};
  state.generating=true;state.busy=true;enableCreate();message('');state.artifact=null;screen('result');$('result-details').hidden=true;$('replay-button').hidden=true;
  $('avatar-name').textContent='눈티를 기다리는 중';$('avatar-personality').textContent=input.renderMode==='LOCAL_MODEL'?'로컬 AI가 새 그림을 그려요. 약 1분 정도 기다려 주세요.':'이번 길의 곡선과 목적지의 빛을 모으고 있어요.';
  $('origin-label').textContent=input.renderMode==='LOCAL_MODEL'?'로컬 AI 생성 중 · 외부 API 없음':'새 그림을 준비하고 있어요';
  $('birth-progress').hidden=false;
  waitingAnimation();
  let completed=null;
  try{const artifact=await api('/v3/avatars',state.pending.body);state.artifact=artifact;await showArtifact(artifact,true);state.pending=null;completed=artifact;}
  catch(e){
    cancelAnimationFrame(state.animation);screen('input');
    const rejectedLocalPicture=input.renderMode==='LOCAL_MODEL'&&['BACKGROUND_NOT_FLAT','SUBJECT_TOO_SMALL','INSUFFICIENT_BACKGROUND','MULTIPLE_LARGE_OBJECTS','SUBJECT_TOUCHES_FRAME','RECTANGULAR_PANEL','BOUNDARY_NOT_TRACEABLE','BOUNDARY_TOO_SMALL'].some(code=>e.message==='LOCAL_MODEL_'+code);
    if(rejectedLocalPicture){state.pending=null;message('완성된 그림의 배경이나 형태가 맞지 않아 보관하지 않았어요. 같은 버튼을 누르면 이 여정으로 새 그림을 그려요.');}
    else message(errorText(e)+' 같은 입력으로 다시 누르면 기존 요청을 이어서 확인해요.');
  }
  finally{state.generating=false;state.busy=false;enableCreate();}
  // The saved result is ready. A slow collection refresh must not own the next input's busy state.
  if(completed){try{await loadCollection();}catch{if(state.artifact===completed&&!$('result-view').hidden&&!state.generating)message('눈티는 저장됐어요. 보관 목록은 연결이 회복되면 다시 불러올 수 있어요.');}}
};
function waitingAnimation(){const start=performance.now();const frame=now=>{if(document.hidden||!state.nativeAllowed)return;$('birth-status').textContent=state.pending?.body.renderMode==='LOCAL_MODEL'?'로컬 AI로 새 그림을 그리는 중 · 약 1분':'이번 경로로 새 그림을 준비하고 있어요';const {ctx,width:w,height:h}=canvasSize($('birth-canvas'));const pts=fitPoints(state.route.points,w*.65,h*.6,20).map(p=>[p[0]+w*.175,p[1]+h*.13]);const t=((now-start)/1800)%1;
  strokeRoute(ctx,pts,'#dbdccc',4);ctx.save();ctx.shadowColor='#eeb56b';ctx.shadowBlur=15;strokeRoute(ctx,pts,'#d79c4c',4,t);ctx.restore();$('birth-progress').firstElementChild.style.width='35%';state.animation=requestAnimationFrame(frame);};cancelAnimationFrame(state.animation);state.animation=requestAnimationFrame(frame);}
const ease=x=>x*x*(3-2*x);const clamp=x=>Math.max(0,Math.min(1,x));
async function showArtifact(artifact,animate=false){
  screen('result');state.artifact=artifact;cancelAnimationFrame(state.animation);state.animation=0;canvasSize($('birth-canvas'));const img=new Image();img.src=artifact.visual.path;await img.decode();if(state.artifact!==artifact)return;
  $('avatar-name').textContent=artifact.displayName;$('avatar-personality').textContent=artifact.design.personality;
  const character=artifact.design.characterPlan;
  $('character-story').replaceChildren();
  if(character){
    $('avatar-personality').textContent=character.purpose.resolution==='UNKNOWN'?'방문 이유를 아직 구체적으로 읽지 못해 기본 여행복을 입었어요. 다음 여정에는 출장·물놀이처럼 활동을 더해 주세요.':`${character.bodyLabel} 모습의 ${character.purpose.label}. 오늘의 준비물은 ${character.prop.label}.`;
    const theme=window.NuntiJourneyEffects?.theme({character});
    document.querySelector('.birth-stage').style.setProperty('--journey-color',theme?.colors[0]||'#d6b97a');
    for(const [label,detail] of [['옷차림',character.outfit.label],['여정의 기념품',character.destination.landmarkLabel],['탄생 순간',theme?.name||'여정의 빛이 모이는 순간']]){
      const row=document.createElement('div'),title=document.createElement('span'),value=document.createElement('b');title.textContent=label;value.textContent=detail;row.append(title,value);$('character-story').append(row);
    }
  }
  $('result-destination').textContent=artifact.destination.name;$('result-purpose').textContent=artifact.purpose||'나만의 여정';
  $('voice-description').textContent=artifact.voice.description||artifact.design.voice?.description||'작고 차분한 동반자';
  $('voice-notice').textContent=artifact.voice.audio?'이 눈티만의 한국어 목소리가 보관됐어요. 누르면 다시 들을 수 있어요.':artifact.voice.provider==='DEVICE_SPEECH'?'이전 눈티의 기기 음성 설정이에요.':'처음 누르면 이 눈티의 목소리를 만들어요. 약 20~40초 걸리며, 이후에는 같은 목소리로 바로 들을 수 있어요.';
  $('origin-label').textContent=artifact.mediaOrigin==='LOCAL_RENDER'?'로컬에서 새로 그린 일러스트 · AI 이미지 아님':artifact.mediaOrigin==='LOCAL_MODEL'?'로컬 AI로 새로 그린 그림 · 외부 API 없음':'외부 AI로 새로 생성한 이미지';
  $('edition-label').textContent='JOURNEY '+artifact.characterId.slice(-8).toUpperCase();
  $('motifs-heading').textContent='이 여정의 작은 이야기';
  $('motifs-notice').hidden=artifact.mediaOrigin==='LOCAL_RENDER';
  $('motifs-notice').textContent=artifact.mediaOrigin==='LOCAL_MODEL'?'AI에 요청한 모티브예요. 실제 경로와 목적지의 특성이 그림에 반영됐는지는 아직 확인하지 않았어요.':'아래는 생성 요청에 담은 모티브예요. AI 이미지에 실제로 반영됐는지는 아직 확인하지 않았어요.';
  $('receipt-source').textContent=artifact.route.sourceLabel+' · '+(artifact.route.inputOrigin==='NAVIGATION_SCREENSHOT'?'사용자가 확인한 화면 좌표':'확인한 정규화 좌표');
  $('motifs').replaceChildren();for(const [i,m] of (artifact.design.motifs||[]).slice(0,3).entries()){const row=document.createElement('div');row.className='motif';const dot=document.createElement('span');dot.className='dot';dot.textContent=String(i+1).padStart(2,'0');const content=document.createElement('div'),title=document.createElement('b'),desc=document.createElement('p');title.textContent=m.label;desc.textContent=m.detail||m.source+' → '+m.target;content.append(title,desc);row.append(dot,content);$('motifs').append(row);}
  $('result-details').hidden=false;$('replay-button').hidden=false;$('save-status').textContent='내 눈티에 저장됐어요. 다시 열어도 같은 모습이에요.';
  $('replay-button').onclick=()=>birthAnimation(img,artifact,true);birthAnimation(img,artifact,animate&&!reduced);
  requestAnimationFrame(()=>{const {ctx,width,height}=canvasSize($('receipt-canvas'));const pts=fitPoints(artifact.route.points,width,height,15);strokeRoute(ctx,pts,'#6c9275',3);pins(ctx,pts);});
}
let formationDisplay=null;
function birthAnimation(img,artifact,animate){
  const plan=window.NuntiFormation?.prepare(artifact);
  const localModel=artifact.mediaOrigin==='LOCAL_MODEL';
  $('formation-notice').hidden=!localModel;
  $('formation-notice').textContent=localModel?(plan?'완성 그림의 외곽을 측정해 움직였어요. 경로와 몸체의 대응은 기하 연출이며 의미 일치는 미검증이에요.'+(plan.faceProtected?'':' 얼굴 위치가 확인되지 않아 중간 얼굴 연출은 생략했어요.'):'측정한 외곽 정보를 확인하지 못해 탄생 모션을 건너뛰었어요. 원본 그림은 그대로 보관됐어요.'):'';
  if(!plan){formationDisplay=null;
    if(localModel){cancelAnimationFrame(state.animation);state.animation=0;const {ctx,width,height}=canvasSize($('birth-canvas'));const size=Math.min(width*.82,height*.92);ctx.drawImage(img,(width-size)/2,(height-size)/2,size,size);$('birth-status').textContent='외곽 검증 정보가 없어 원본 그림을 표시해요';$('birth-progress').hidden=true;return;}
    legacyBirthAnimation(img,artifact,animate&&!reduced);return;}
  cancelAnimationFrame(state.animation);
  const renderer=window.NuntiFormation.createRenderer(img,plan),start=performance.now(),duration=animate&&!reduced?5400:0;
  const drawAt=(progress,idle=0)=>{const {ctx,width,height}=canvasSize($('birth-canvas'));const frame=renderer.draw(ctx,width,height,progress,idle);
    const story=plan.character&&window.NuntiJourneyEffects?.theme(plan).words;
    $('birth-status').textContent=story?story[progress<.28?0:progress<.78?1:2]:progress<.14?'이번 길에 작은 빛이 켜져요':progress<.28?'길을 따라 별가루가 모여요':progress<.70?'빛이 모여 눈티의 모습이 자라요':progress<1?'반짝임 속에서 눈티가 인사해요':'이 길에서 태어난 눈티예요';
    $('birth-progress').hidden=progress>=1;$('birth-progress').firstElementChild.style.width=(progress*100)+'%';
    return {progress:frame.progress,area:frame.area,finalArea:plan.finalArea,inflate:frame.inflate,imageWeight:frame.imageWeight,contour:frame.contour,spine:frame.centerline,faceCenter:frame.faceCenter};};
  formationDisplay={artifact,plan,drawAt};
  const frame=now=>{if(document.hidden||!state.nativeAllowed||$('result-view').hidden)return;const t=duration?clamp((now-start)/duration):1;
    drawAt(t,t>=1&&duration&&!reduced?Math.sin((now-start)/1600)*2:0);
    if(duration&&!reduced)state.animation=requestAnimationFrame(frame);else state.animation=0;};
  state.animation=requestAnimationFrame(frame);
}
function legacyBirthAnimation(img,artifact,animate){
  cancelAnimationFrame(state.animation);const start=performance.now();const duration=animate?4200:0;
  const assetPoints=artifact.design.routeThread?.points;
  const exactThread=artifact.mediaOrigin==='LOCAL_RENDER'&&artifact.design.routeThread?.renderedOnSurface!==false&&assetPoints?.length===artifact.route.points.length;
  const paint=document.createElement('canvas');paint.width=img.naturalWidth;paint.height=img.naturalHeight;
  const paintCtx=paint.getContext('2d');
  const frame=now=>{if(document.hidden||!state.nativeAllowed)return;const t=duration?clamp((now-start)/duration):1;const {ctx,width:w,height:h}=canvasSize($('birth-canvas'));const size=Math.min(w*.82,h*1.02),cx=w/2,cy=h*.46;
    const raw=fitPoints(artifact.route.points,size*.85,size*.75,10).map(p=>[p[0]+cx-size*.425,p[1]+cy-size*.375]);
    const destination=exactThread?assetPoints.map(p=>[cx+(p[0]-.5)*size,cy+(p[1]-.5)*size]):fitPoints(artifact.route.points,size*.28,size*.25,4).map(p=>[p[0]+cx-size*.14,p[1]+cy]);
    const fold=ease(clamp((t-.2)/.34));const points=raw.map((p,i)=>[p[0]*(1-fold)+destination[i][0]*fold,p[1]*(1-fold)+destination[i][1]*fold]);
    const spread=ease(clamp((t-.5)/.43));
    if(t<.98){ctx.save();ctx.shadowColor='#d8a354';ctx.shadowBlur=14;ctx.globalAlpha=(1-spread)*.85;strokeRoute(ctx,points,'#edc579',3+spread*size*.72,ease(clamp(t/.25)));ctx.restore();}
    if(t>.44){const reveal=ease(clamp((t-.44)/.5)),float=t>=1&&!reduced?Math.sin((now-start)/1600)*3:0;
      paintCtx.globalCompositeOperation='source-over';paintCtx.clearRect(0,0,paint.width,paint.height);paintCtx.drawImage(img,0,0);
      if(exactThread&&t<.96){paintCtx.globalCompositeOperation='destination-in';strokeRoute(paintCtx,assetPoints.map(p=>[p[0]*paint.width,p[1]*paint.height]),'#fff',3+spread*paint.width*1.65);paintCtx.globalCompositeOperation='source-over';}
      ctx.save();ctx.globalAlpha=exactThread?clamp(reveal*3):reveal;ctx.drawImage(paint,cx-size/2,cy-size/2+float,size,size);ctx.restore();
      if(t<.94){ctx.save();ctx.globalAlpha=(1-spread)*.85;ctx.shadowColor='#f9c55d';ctx.shadowBlur=20;strokeRoute(ctx,points,'#fff0bc',3);ctx.restore();}
    }
    if(t<1){for(let i=0;i<11;i++){const a=i*2.4+now/2400,r=size*(.28+.04*Math.sin(i+now/800));ctx.beginPath();ctx.arc(cx+Math.cos(a)*r,cy+Math.sin(a)*r*.8,1+i%2,0,Math.PI*2);ctx.fillStyle=`rgba(203,157,81,${.2+.3*Math.sin(t*Math.PI)})`;ctx.fill();}}
    $('birth-status').textContent=t<.22?'이번 길의 선을 따라가요':t<.6?'길의 곡선에 작은 생명을 담아요':t<1?'작은 눈티가 모습을 드러내요':'이 길에서 태어난 눈티예요';
    $('birth-progress').hidden=t>=1;$('birth-progress').firstElementChild.style.width=(t*100)+'%';
    if(t<1||!reduced)state.animation=requestAnimationFrame(frame);else state.animation=0;
  };state.animation=requestAnimationFrame(frame);
}
async function loadCollection(){const epoch=++collectionEpoch,r=await api('/v3/avatars');if(epoch!==collectionEpoch)return;state.avatars=Array.isArray(r)?r:(r.avatars||r.items||[]);$('collection-count').textContent=state.avatars.length;}
async function showCollection(){if(state.busy)return;message('');screen('collection');const epoch=viewEpoch;await loadCollection();if(epoch!==viewEpoch||!state.nativeAllowed)return;$('collection').replaceChildren();if(!state.avatars.length){$('collection').textContent='아직 눈티가 없어요. 첫 여정을 담아보세요.';return;}
  for(const a of state.avatars){const b=document.createElement('button');b.className='collection-item card';const img=document.createElement('img');img.src=a.visual.path;img.alt=a.displayName;const title=document.createElement('h3'),desc=document.createElement('p');title.textContent=a.displayName;desc.textContent=a.destination.name;b.append(img,title,desc);b.onclick=async()=>{const selection=++viewEpoch;message('');try{const artifact=await api('/v3/avatars/'+encodeURIComponent(a.characterId));if(selection!==viewEpoch||!state.nativeAllowed)return;await showArtifact(artifact,false);}catch(e){if(selection===viewEpoch)message(errorText(e));}};$('collection').append(b);}}
$('collection-button').onclick=()=>showCollection().catch(e=>message(errorText(e)));
$('collection-back').onclick=()=>screen(state.artifact?'result':'input');
$('new-button').onclick=()=>{screen('input');message('새 여정을 생성하면 새 눈티가 태어나요. 보관한 눈티는 그대로 남아 있어요.');};
$('journey-button').onclick=()=>{stopVoice();$('step-3').classList.add('active');message('눈티가 여정에 함께할 준비를 마쳤어요. 주행 이벤트·감정 피드백은 해당 모듈 연결 후 제공됩니다.');$('save-status').textContent='캐릭터 ID와 외형·목소리 설정을 저장했어요.';};
let speaking=false, voiceEpoch=0, voiceAudio=null;
const voicePageId=crypto.randomUUID();
const nativeVoiceRequestId=()=>voicePageId+':'+voiceEpoch;
function stopVoice(){voiceEpoch++;if(voiceAudio){voiceAudio.onended=null;voiceAudio.onerror=null;voiceAudio.pause();voiceAudio.src='';voiceAudio=null;}if(window.NuntiNative){window.NuntiNative.stopSpeaking();}else if('speechSynthesis'in window)speechSynthesis.cancel();speaking=false;$('listen-button').textContent='▷';}
$('listen-button').onclick=async()=>{
  if(!state.artifact||!state.nativeAllowed)return;if(speaking){stopVoice();return;}const a=state.artifact,v=a.voice;
  if(v.provider!=='DEVICE_SPEECH'){
    const epoch=++voiceEpoch;speaking=true;$('listen-button').textContent='□';
    try{
      if(!v.audio)$('voice-notice').textContent='이 눈티에게 어울리는 목소리를 만들고 있어요… 잠시만 기다려 주세요.';
      const generated=v.audio?v:await api('/v3/avatars/'+a.characterId+'/voice',{});
      a.voice=generated;
      if(state.artifact===a)$('voice-notice').textContent='이 눈티만의 목소리가 보관됐어요. 다시 열어도 같은 목소리예요.';
      if(epoch!==voiceEpoch||state.artifact!==a||!state.nativeAllowed||document.hidden)return;
      $('voice-notice').textContent='이 눈티만의 목소리가 보관됐어요. 다시 열어도 같은 목소리예요.';
      if(window.NuntiNative?.playVoice){window.NuntiNative.playVoice(generated.audio.path,nativeVoiceRequestId());}
      else{
        const player=new Audio(generated.audio.path);voiceAudio=player;
        player.onended=()=>{if(epoch===voiceEpoch&&voiceAudio===player)window.nuntiSpeechFinished();};
        player.onerror=()=>{if(epoch===voiceEpoch&&voiceAudio===player)window.nuntiSpeechFailed();};
        await player.play();
      }
    }catch(e){if(epoch!==voiceEpoch)return;stopVoice();$('voice-notice').textContent=a.voice.audio?'목소리는 준비됐어요. 재생 버튼을 한 번 더 눌러 주세요.':({LOCAL_VOICE_NOT_CONFIGURED:'로컬 음성 모델이 준비되지 않았어요. 실행 안내에서 TTS 환경을 확인해 주세요.',VOICE_IN_PROGRESS:'목소리를 준비 중이에요. 잠시 후 다시 눌러 주세요.',LOCAL_VOICE_TIMEOUT:'다른 생성이 끝난 뒤 다시 눌러 주세요. 캐릭터와 목소리 설계는 보관됐어요.'}[e.message]||'목소리를 준비하지 못했어요. 다시 눌러 재시도할 수 있어요.');}
    return;
  }
  const legacyEpoch=++voiceEpoch;const text=`안녕, 나는 ${a.displayName}. ${a.destination.name}까지 함께 갈게. 우리, 여유 있게 출발해 볼까?`;
  if(window.NuntiNative){if(!window.NuntiNative.isSpeechAvailable()){message('이 기기에 한국어 음성이 준비되지 않았어요. 기기의 TTS 설정에서 한국어 음성을 설치해 주세요. 이미지와 목소리 설정은 보관됐어요.');return;}window.NuntiNative.speak(text,Number(v.rate||1),Number(v.pitch||1.08),nativeVoiceRequestId());speaking=true;$('listen-button').textContent='□';}
  else if('speechSynthesis'in window){const voice=speechSynthesis.getVoices().find(x=>x.lang.startsWith('ko'));if(!voice){message('이 브라우저에 한국어 음성이 없어요. Android 앱에서 기기 음성을 확인하거나 한국어 음성을 설치해 주세요.');return;}
    speechSynthesis.cancel();const u=new SpeechSynthesisUtterance(text);u.lang='ko-KR';u.voice=voice;u.rate=Number(v.rate||1);u.pitch=Number(v.pitch||1.08);u.onend=u.onerror=()=>{if(legacyEpoch===voiceEpoch)window.nuntiSpeechFinished();};speechSynthesis.speak(u);speaking=true;$('listen-button').textContent='□';}
  else message('이 기기에서 음성 재생을 지원하지 않아요. 이미지와 목소리 설정은 보관됐어요.');
};
window.nuntiSpeechFinished=requestId=>{if(requestId!==undefined&&requestId!==nativeVoiceRequestId())return;speaking=false;$('listen-button').textContent='▷';};
window.nuntiSpeechFailed=requestId=>{if(requestId!==undefined&&requestId!==nativeVoiceRequestId())return;stopVoice();$('voice-notice').textContent='음성을 재생하지 못했어요. 연결을 확인한 뒤 다시 눌러 주세요.';};
window.nuntiVehicleAllowed=allowed=>{const was=state.nativeAllowed;state.nativeAllowed=allowed;if(!allowed){viewEpoch++;stopVoice();cancelAnimationFrame(state.animation);}else if(!was&&state.artifact&&!$('result-view').hidden){showArtifact(state.artifact,false).catch(e=>message(errorText(e)));}enableCreate();};
document.addEventListener('visibilitychange',()=>{if(document.hidden){viewEpoch++;stopVoice();cancelAnimationFrame(state.animation);}else if(state.artifact&&!$('result-view').hidden&&state.nativeAllowed){showArtifact(state.artifact,false).catch(()=>{});}});
window.addEventListener('resize',drawRoute);
async function init(){try{const caps=await api('/v3/capabilities');window.nuntiCapabilities=caps;window.NuntiNavigation?.setCapabilities(caps);$('session-dialog').close();$('engine-choice').hidden=!(caps.imageApiAvailable||caps.localImageModelAvailable);
  for(const [mode,available] of [['LOCAL_MODEL',caps.localImageModelAvailable===true],['IMAGE_API',caps.imageApiAvailable===true]]){const option=$('render-mode').querySelector(`option[value="${mode}"]`);option.hidden=!available;option.disabled=!available;}
  if($('render-mode').selectedOptions[0]?.disabled)$('render-mode').value='LOCAL_RENDER';if(caps.localImageModelAvailable)$('render-mode').value='LOCAL_MODEL';$('render-mode').onchange();await examples();await loadCollection();}
catch(e){if(e.status===401||e.status===403){$('session-dialog').showModal();}else message(errorText(e));}}
$('session-form').onsubmit=async event=>{event.preventDefault();try{await api('/session',{token:$('session-token').value});$('session-token').value='';$('session-error').textContent='';await init();}catch(e){$('session-error').textContent=errorText(e);}};
window.nuntiTest={getArtifact:()=>state.artifact,getRoute:()=>state.route,showCollection,viewExample:i=>viewExample(state.examples[i]),showArtifact,
  getFormation:()=>formationDisplay?{version:'route-volume-2',source:formationDisplay.plan.source,mapping:formationDisplay.plan.mapping,faceProtected:formationDisplay.plan.faceProtected,raw:formationDisplay.plan.raw,contour:formationDisplay.plan.contour,spine:formationDisplay.plan.spine,faceCenter:formationDisplay.plan.faceCenter}:null,
  captureFormation:progress=>{if(!formationDisplay||!state.nativeAllowed)return null;cancelAnimationFrame(state.animation);state.animation=0;return formationDisplay.drawAt(progress);}};
init();
