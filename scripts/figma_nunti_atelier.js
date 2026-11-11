// Run with use_figma on the NUNTI file. Editable Android app-window reference.
const created = [], mutated = [], uploads = [];
const remember = n => { created.push(n.id); return n; };
const primary = await figma.getNodeByIdAsync('18:145');
const field = await figma.getNodeByIdAsync('22:104');
for (const source of [primary, field]) {
  for (const t of source.findAllWithCriteria({types:['TEXT']})) {
    for (const s of t.getStyledTextSegments(['fontName'])) await figma.loadFontAsync(s.fontName);
  }
}
await Promise.all(['Regular','Medium','Bold'].map(style => figma.loadFontAsync({family:'Noto Sans KR',style})));
const page = remember(figma.createPage()); page.name = 'Atelier v3 · 실제 차량 UI';
await figma.setCurrentPageAsync(page);
const colors = {
  background:['f5f3ed','111d20'], surface:['fffefb','1a2b2e'], soft:['e8eeea','22393b'],
  ink:['203c3d','f3f2e9'], muted:['526965','b4c8c3'], border:['73847f','72928a'],
  accent:['195057','b5ddd2'], onAccent:['fffefb','173a3c']
};
const rgb = h => ({r:parseInt(h.slice(0,2),16)/255,g:parseInt(h.slice(2,4),16)/255,b:parseInt(h.slice(4,6),16)/255});
const collection = figma.variables.createVariableCollection('Nunti Atelier / appearance');
collection.renameMode(collection.defaultModeId,'Day'); const night = collection.addMode('Night');
const vars = {};
for (const [name, values] of Object.entries(colors)) {
  const v = figma.variables.createVariable(name,collection,'COLOR');
  v.scopes = ['FRAME_FILL','SHAPE_FILL','TEXT_FILL','STROKE_COLOR'];
  v.setValueForMode(collection.defaultModeId,rgb(values[0])); v.setValueForMode(night,rgb(values[1])); vars[name]=v;
}
const paint = name => figma.variables.setBoundVariableForPaint({type:'SOLID',color:rgb(colors[name][0])},'color',vars[name]);
function auto(parent,name,w,h,direction='VERTICAL',fill=null,gap=0,padding=0) {
  const n = remember(figma.createAutoLayout(direction)); parent.appendChild(n); n.name=name;
  n.resize(w,h); n.primaryAxisSizingMode='FIXED'; n.counterAxisSizingMode='FIXED';
  n.itemSpacing=gap; n.paddingTop=n.paddingBottom=n.paddingLeft=n.paddingRight=padding;
  n.fills=fill?[paint(fill)]:[]; n.clipsContent=false; return n;
}
function text(parent,value,size=26,width=500,weight='Regular',color='ink',line=1.5) {
  const n=remember(figma.createText()); parent.appendChild(n);
  n.fontName={family:'Noto Sans KR',style:weight}; n.fontSize=size; n.lineHeight={unit:'PIXELS',value:Math.round(size*line)};
  n.letterSpacing={unit:'PERCENT',value:-2}; n.characters=value; n.fills=[paint(color)];
  n.textAutoResize='HEIGHT'; n.resize(width,n.height); return n;
}
async function button(parent,label,w,kind='secondary',h=80) {
  const n=remember(primary.createInstance()); parent.appendChild(n); n.name=label; n.resize(w,h); n.cornerRadius=16;
  n.fills=kind==='primary'?[paint('accent')]:kind==='quiet'?[paint('soft')]:[];
  n.strokes=kind==='secondary'?[paint('border')]:[]; n.strokeWeight=1;
  for(const t of n.findAllWithCriteria({types:['TEXT']})) {
    for(const s of t.getStyledTextSegments(['fontName'])) await figma.loadFontAsync(s.fontName);
    t.fontName={family:'Noto Sans KR',style:kind==='primary'?'Bold':'Medium'}; t.fontSize=26;
    t.lineHeight={unit:'PIXELS',value:39}; t.characters=label; t.fills=[paint(kind==='primary'?'onAccent':'accent')];
  }
  created.push(...n.findAll(()=>true).map(v=>v.id)); return n;
}
async function input(parent,label,value,w) {
  const n=remember(field.createInstance()); parent.appendChild(n); n.resize(w,124); n.name=label;
  const texts=n.findAllWithCriteria({types:['TEXT']});
  for(let i=0;i<texts.length;i++) {
    const t=texts[i]; for(const s of t.getStyledTextSegments(['fontName'])) await figma.loadFontAsync(s.fontName);
    t.fontName={family:'Noto Sans KR',style:'Regular'}; t.fontSize=i===0?24:28; t.lineHeight={unit:'PIXELS',value:i===0?36:42};
    t.characters=i===0?label:value; t.fills=[paint(i===0?'muted':'ink')];
  }
  created.push(...n.findAll(()=>true).map(v=>v.id)); return n;
}
function imageSlot(parent,name,w,h,source) {
  const n=remember(figma.createRectangle()); parent.appendChild(n); n.name=name; n.resize(w,h); n.fills=[];
  uploads.push({nodeId:n.id,source}); return n;
}
function frame(name,x) {
  const n=auto(page,name,1683,1210,'VERTICAL','background',24,40); n.x=x;n.y=180;n.paddingTop=28;n.paddingBottom=32;return n;
}
async function header(root) {
  const n=auto(root,'앱 헤더',1603,68,'HORIZONTAL',null,22); n.counterAxisAlignItems='CENTER';
  text(n,'눈티',34,62,'Bold'); text(n,'출발 준비',22,1357,'Regular','muted'); await button(n,'내 눈티',140,'secondary',64);
}
function intro(root,heading,subheading) {
  const n=auto(root,'화면 제목',1603,107.43,'VERTICAL',null,10); text(n,heading,48,1603,'Bold','ink',1.28);text(n,subheading,24,1603,'Regular','muted');
}
const pre=frame('01 출발 전 · 1683 × 1210',240); await header(pre);
intro(pre,'어디로 떠날까요?','길을 고르면, 눈티도 여행을 준비해요.');
const pbody=auto(pre,'입력과 경로',1603,814.57,'HORIZONTAL',null,40);
const hero=auto(pbody,'경로와 오늘의 동행',812,814.57,'VERTICAL','soft',16,28);hero.cornerRadius=28;
text(hero,'오늘의 동행',22,756,'Medium','muted');
imageSlot(hero,'승인 기본 눈티',756,430,'prototypes/avatar_generator/nunti-motion/base.png');
const route=auto(hero,'선택한 경로',756,116,'HORIZONTAL','surface',16,20);route.cornerRadius=16;route.counterAxisAlignItems='CENTER';
const routeWords=auto(route,'목적지',500,76,'VERTICAL',null,4);text(routeWords,'안목해변',28,500,'Bold');text(routeWords,'바다를 따라 가는 길',22,500,'Regular','muted');
const vector=remember(figma.createVector());route.appendChild(vector);vector.name='경로 선';
vector.vectorPaths=[{windingRule:'NONZERO',data:'M 0 48 C 28 40 24 12 52 22 C 70 30 70 56 96 35 C 116 18 126 22 144 8'}];
vector.strokes=[paint('accent')];vector.strokeWeight=5;vector.strokeCap='ROUND';vector.fills=[];
const nav=auto(hero,'경로 선택',756,80,'HORIZONTAL',null,12);await button(nav,'내비 목적지 불러오기',372);await button(nav,'현대 내비 열기',372);
text(hero,'✓  이번에 갈 경로가 맞아요',24,756,'Medium');
const form=auto(pbody,'여행 입력',751,814.57,'VERTICAL',null,28);
await input(form,'목적지','안목해변',751);
const pair=auto(form,'여행 환경',751,124,'HORIZONTAL',null,20);await input(pair,'어떤 풍경인가요?','바다',365);await input(pair,'가는 길','고속도로',366);
const mood=auto(form,'직접 고르는 기분',751,128,'VERTICAL',null,12);text(mood,'어떤 기분으로 떠날까요?',24,751,'Regular','muted');
const choices=auto(mood,'기분 선택',751,80,'HORIZONTAL',null,12);await button(choices,'차분하게',243,'primary');await button(choices,'호기심 있게',242,'quiet');await button(choices,'씩씩하게',242,'quiet');
await button(form,'여행에 대해 더 알려주기  ·  선택',751,'quiet',76);
text(form,'눈티 설정  ›',24,751,'Medium','accent');
const pfooter=auto(pre,'주요 동작',1603,88,'HORIZONTAL',null,24);pfooter.counterAxisAlignItems='CENTER';text(pfooter,'완성된 눈티는 내 눈티에 저장돼요.',22,1199,'Regular','muted');await button(pfooter,'눈티 만들기     →',380,'primary',88);
const result=frame('02 눈티 완성 · 1683 × 1210',2083);await header(result);
intro(result,'이번 여행의 눈티','준비가 끝나면 함께 출발하세요.');
const rbody=auto(result,'완성된 눈티와 여행',1603,814,'HORIZONTAL',null,40);
const stage=auto(rbody,'캐릭터 무대',836,814,'VERTICAL','soft',0,24);stage.cornerRadius=28;stage.counterAxisAlignItems='CENTER';stage.primaryAxisAlignItems='CENTER';
imageSlot(stage,'바닷길 눈티 · local v2.2',720,666,'prototypes/avatar_generator/skin-v2/atelier/sea/final.png');
const caption=auto(stage,'캡션 54px',720,54);caption.primaryAxisAlignItems='CENTER';
text(caption,'출발 준비 완료',20,720,'Regular','muted').textAlignHorizontal='CENTER';
const detail=auto(rbody,'눈티와 목적지',727,814,'VERTICAL',null,24);detail.primaryAxisAlignItems='CENTER';
text(detail,'바닷길 눈티',42,727,'Bold');text(detail,'바다색 코트에 나침반을 챙겼어요.',24,727,'Regular','muted');
const destination=auto(detail,'이번 여행',727,86,'VERTICAL',null,4);text(destination,'안목해변',26,707,'Bold');text(destination,'바다 산책',22,707,'Regular','muted');
text(detail,'내 눈티에 저장됨',20,727,'Regular','muted');
const secondary=auto(detail,'추가 동작',727,80,'HORIZONTAL',null,12);await button(secondary,'목소리 듣기',357);await button(secondary,'여행 기록',358,'quiet');
const motion=auto(detail,'모션 제어',727,64,'HORIZONTAL',null,16);await button(motion,'변신 다시 보기',168,'quiet',64);text(motion,'움직임 줄이기  ○',22,400,'Regular','muted');
const rfooter=auto(result,'다음 동작',1603,88,'HORIZONTAL',null,24);rfooter.counterAxisAlignItems='CENTER';await button(rfooter,'다른 길 고르기',208);auto(rfooter,'여백',1051,1,'HORIZONTAL');await button(rfooter,'함께 출발     →',296,'primary',88);
return {pageId:page.id,frameIds:[pre.id,result.id],uploads,createdNodeIds:[...new Set(created)],mutatedNodeIds:mutated,
  variableCollectionId:collection.id,variableIds:Object.values(vars).map(v=>v.id),frames:[pre,result].map(n=>({id:n.id,width:n.width,height:n.height}))};
