// Shared authoring helpers. Prefix foundation and library ledgers before use.
const page=await figma.getNodeByIdAsync(foundation.pageId);await figma.setCurrentPageAsync(page);
await Promise.all([...['Regular','Medium','Bold'].map(style=>figma.loadFontAsync({family:'Noto Sans KR',style})),...['Regular','Bold'].map(style=>figma.loadFontAsync({family:'Asta Sans',style}))]);
const V={};await Promise.all(Object.entries(foundation.variables).map(async([k,id])=>V[k]=await figma.variables.getVariableByIdAsync(id)));
const colorCollection=await figma.variables.getVariableCollectionByIdAsync(foundation.collections.color.id);
const M={};await Promise.all(Object.entries(library.components).map(async([k,id])=>M[k]=await figma.getNodeByIdAsync(id)));
const createdNodeIds=[],screens={},actions={};
function add(n){createdNodeIds.push(n.id);return n;}
function track(n){createdNodeIds.push(n.id);if('findAll'in n)for(const d of n.findAll(()=>true))createdNodeIds.push(d.id);return n;}
function paint(role){return figma.variables.setBoundVariableForPaint({type:'SOLID',color:{r:0,g:0,b:0}},'color',V['color/'+role]);}
function fill(n,role){n.fills=[paint(role)];}
function radius(n,key='20'){for(const k of ['topLeftRadius','topRightRadius','bottomLeftRadius','bottomRightRadius'])n.setBoundVariable(k,V['radius/'+key]);}
function padding(n,size){for(const k of ['paddingTop','paddingBottom','paddingLeft','paddingRight'])n.setBoundVariable(k,V['space/'+size]);}
function gap(n,size){n.setBoundVariable('itemSpacing',V['space/'+size]);}
function text(value,style='Body',role='ink',width){const t=add(figma.createText());t.name=value;t.fontName={family:'Noto Sans KR',style:'Regular'};t.textStyleId=foundation.styles[style];t.characters=value;fill(t,role);if(width){t.textAutoResize='HEIGHT';t.resize(width,t.height);}return t;}
function frame(name,dir='VERTICAL',w,h){const n=add(figma.createAutoLayout(dir));n.name=name;n.fills=[];if(w&&h)n.resize(w,h);return n;}
function row(parent,name,w,h,g=16){const n=frame(name,'HORIZONTAL',w,h);gap(n,g);parent.appendChild(n);return n;}
function fillWidth(n){n.layoutSizingHorizontal='FILL';return n;}
function label(parent,value,style='Body',role='ink',width){const t=text(value,style,role,width);parent.appendChild(t);return t;}
function instance(key,parent,w,h){const n=track(M[key].createInstance());parent.appendChild(n);if(w&&h)n.resize(w,h);return n;}
function props(n,mapping,values){const p={},available=n.componentProperties;for(const [k,v]of Object.entries(values)){const key=mapping[k]in available?mapping[k]:Object.keys(available).find(x=>x.startsWith(k+'#'));if(!key)throw new Error('Missing property '+k+' on '+n.name);p[key]=v;}n.setProperties(p);}
function button(parent,value,kind='Secondary',w=280,action){const isToggle=value.startsWith('움직임 줄이기');const n=instance(isToggle?'Motion toggle':'Style='+kind,parent,w,80);if(!isToggle){props(n,library.properties['Button/'+kind],{Label:value});fill(n,kind==='Primary'?'accent':kind==='Disabled'||kind==='Quiet'?'soft':'surface');if(kind==='Secondary'){n.strokes=[paint('accent')];n.strokeWeight=1;n.strokeAlign='INSIDE';for(const p of ['strokeTopWeight','strokeRightWeight','strokeBottomWeight','strokeLeftWeight'])n[p]=1;}if(kind==='Quiet')n.strokes=[];for(const t of n.findAllWithCriteria({types:['TEXT']})){t.fontName={family:'Noto Sans KR',style:'Medium'};t.textStyleId=foundation.styles.Label;fill(t,kind==='Primary'?'onAccent':kind==='Disabled'?'muted':'accent');}}n.name='Action / '+value;if(action)actions[action]=n.id;return n;}
function choice(parent,value,selected,w){if(value.includes('경로가 맞아요'))return instance('Route confirmation',parent,w,80);const kind=selected?'Selected':'Default';const n=instance('State='+kind,parent,w,76);props(n,library.properties['Choice/'+kind],{Label:value});n.name='Choice / '+value;return n;}
function field(parent,heading,value,w){const n=instance('Field',parent,w,122);props(n,library.properties.Field,{Label:heading});const native=n.findAllWithCriteria({types:['INSTANCE']}).find(x=>x.name==='Official Pleos input');native.setProperties({'Label#28158:0':value,'Place holder#34129:2':value});n.name='Field / '+heading;return n;}
function status(parent,value,w){const n=instance('Status',parent,w,72);props(n,library.properties.Status,{Message:value});n.name='Status / '+value;return n;}
function metric(parent,heading,value,context,w){const n=instance('Metric',parent,w,204);props(n,library.properties.Metric,{Label:heading,Value:value,Context:context});return n;}
function character(parent,variant,size){const n=instance('Character / '+variant,parent,size,size);n.name='Approved Nunti A / '+variant;return n;}
function card(parent,name,w,h,role='surface',pad=32){const n=frame(name,'VERTICAL',w,h);padding(n,pad);gap(n,16);radius(n,'28');fill(n,role);parent.appendChild(n);return n;}
function spacer(parent){const n=frame('Flexible space','VERTICAL',1,1);parent.appendChild(n);n.layoutSizingVertical='FILL';return n;}
function shell(name,x,y,w=1682,theme='Day'){const n=frame(name,'VERTICAL',w,1210);page.appendChild(n);n.x=x;n.y=y;padding(n,w===1682?40:32);gap(n,24);fill(n,'background');n.setExplicitVariableModeForCollection(colorCollection,foundation.collections.color.modes[theme]);n.clipsContent=true;screens[name]=n.id;return n;}
function header(parent,state,w,collection=true){const h=row(parent,'App header',w,80,24);h.counterAxisAlignItems='CENTER';label(h,'눈티','Title');label(h,state,'Caption','muted');const space=frame('Header space','HORIZONTAL',1,1);h.appendChild(space);fillWidth(space);if(collection)button(h,'내 눈티','Quiet',180,parent.name+'/collection');return h;}
function intro(parent,title,subtitle,w){const n=frame('Screen title','VERTICAL',w,108);gap(n,8);parent.appendChild(n);label(n,title,'Display','ink',w);label(n,subtitle,'Body','muted',w);return n;}
function note(title,body,x,y,w=1682){const n=frame(title,'VERTICAL',w,118);page.appendChild(n);n.x=x;n.y=y;gap(n,8);label(n,title,'Title','ink',w);label(n,body,'Caption','muted',w);n.layoutSizingVertical='HUG';return n;}

function preTrip(name,x,y,theme='Day',direction='A'){
 const s=shell(name,x,y,1682,theme),w=1602;header(s,'출발 전',w);intro(s,'이번 길에, 눈티를 더해요','목적지와 직접 고른 기분을 같은 눈티에 담아요.',w);
 const body=row(s,'Route and journey input',w,770,32);body.layoutSizingVertical='FILL';
 const left=card(body,'Route & canonical companion',706,770,direction==='A'?'soft':'surface');left.layoutSizingVertical='FILL';
 label(left,direction==='A'?'길을 함께 기억해요':'이번 여정','Heading');
 const hero=row(left,'Route and base Nunti',642,332,8);hero.counterAxisAlignItems='CENTER';
 if(direction==='A'){character(hero,'Base',332);const mini=frame('Confirmed path','VERTICAL',302,300);gap(mini,16);hero.appendChild(mini);label(mini,'안목해변','Title');label(mini,'경로를 확인해 주세요','Caption','muted');instance('Route preview / synthetic confirmed',mini,302,123);}
 else{const mini=frame('Confirmed path','VERTICAL',390,300);gap(mini,16);hero.appendChild(mini);label(mini,'안목해변','Title');label(mini,'경로를 확인해 주세요','Caption','muted');instance('Route preview / synthetic confirmed',mini,390,158);character(hero,'Base',240);}
 const routeActions=row(left,'Navigation actions',642,80,16);button(routeActions,'내비 목적지 불러오기','Secondary',368,name+'/import');button(routeActions,'현대 내비 열기','Quiet',258,name+'/navigation');
 const confirm=choice(left,'✓  이번에 갈 경로가 맞아요',true,642);actions[name+'/confirm']=confirm.id;
 button(left,'다른 방법으로 경로 가져오기','Quiet',642,name+'/route-tools');
 const right=card(body,'Journey attributes',864,770,'surface');right.layoutSizingHorizontal='FILL';right.layoutSizingVertical='FILL';
 field(right,'목적지','안목해변',800);
 const info=row(right,'Trip context',800,122,16);field(info,'그곳의 느낌','바다와 커피 향',392);field(info,'가는 이유','잠깐 쉬러 가요',392);
 const types=row(right,'Explicit destination and road',800,122,16);field(types,'목적지 유형','바다  ▾',392);field(types,'도로 유형','고속도로  ▾',392);
 const mood=frame('Explicit mood','VERTICAL',800,118);gap(mood,8);right.appendChild(mood);label(mood,'어떤 기분으로 떠날까요?','Caption','muted');const moods=row(mood,'Mood options',800,76,16);choice(moods,'차분하게',false,256);choice(moods,'호기심 있게',true,256);choice(moods,'씩씩하게',false,256);
 spacer(right);button(right,'기본 눈티 A · 생성 방식','Quiet',800,name+'/engine');
 const footer=row(s,'Primary action',w,80,24);footer.counterAxisAlignItems='CENTER';const copy=frame('Save note','VERTICAL',1000,72);gap(copy,8);footer.appendChild(copy);fillWidth(copy);label(copy,'내 눈티에 자동으로 저장돼요','Label','accent');label(copy,'경로가 없으면 장식 없는 기본 눈티로 만나요.','Caption','muted');button(footer,'이 길에서 눈티 만나기  ↗','Primary',450,name+'/create');return s;
}
