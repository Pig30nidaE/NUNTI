// Requires `const foundation = <saved foundation JSON>` prefix.
const page = await figma.getNodeByIdAsync(foundation.pageId);
await figma.setCurrentPageAsync(page);
await Promise.all([...['Regular','Medium','Bold'].map(style=>figma.loadFontAsync({family:'Noto Sans KR',style})),...['Regular','Bold'].map(style=>figma.loadFontAsync({family:'Asta Sans',style}))]);
const V={}; await Promise.all(Object.entries(foundation.variables).map(async([k,id])=>V[k]=await figma.variables.getVariableByIdAsync(id)));
const createdNodeIds=[],components={},sets={},properties={};
function add(n){createdNodeIds.push(n.id);return n;}
function paint(role){return figma.variables.setBoundVariableForPaint({type:'SOLID',color:{r:0,g:0,b:0}},'color',V['color/'+role]);}
function fill(n,role){n.fills=[paint(role)];}
function radius(n,key='20'){for(const k of ['topLeftRadius','topRightRadius','bottomLeftRadius','bottomRightRadius'])n.setBoundVariable(k,V['radius/'+key]);}
function padding(n,size){for(const k of ['paddingTop','paddingBottom','paddingLeft','paddingRight'])n.setBoundVariable(k,V['space/'+size]);}
function gap(n,size){n.setBoundVariable('itemSpacing',V['space/'+size]);}
function text(value,style='Body',role='ink'){const t=add(figma.createText());t.name=value;t.fontName={family:'Noto Sans KR',style:'Regular'};t.textStyleId=foundation.styles[style];t.characters=value;fill(t,role);return t;}
function frame(name,dir='VERTICAL'){const n=add(figma.createAutoLayout(dir));n.name=name;n.fills=[];return n;}
function comp(name,w,h,dir='VERTICAL'){const n=add(figma.createComponent());n.name=name;n.layoutMode=dir;n.resize(w,h);n.fills=[];components[name]=n.id;return n;}
function prop(c,t,key,value){const id=c.addComponentProperty(key,'TEXT',value);t.componentPropertyReferences={characters:id};return id;}
function combine(name,items,cols=2){const s=add(figma.combineAsVariants(items,page));s.name='Nunti / '+name;s.description='Nunti vehicle UI proposal. Token-bound and editable. Day/Night inherited from parent; 80px primary touch height.';items.forEach((n,i)=>{n.x=32+(i%cols)*(n.width+32);n.y=32+Math.floor(i/cols)*(n.height+32);});s.resize(Math.max(...items.map(n=>n.x+n.width))+32,Math.max(...items.map(n=>n.y+n.height))+32);s.x=8000;s.y=160+Object.keys(sets).length*460;sets[name]=s.id;return s;}

// Native controls copied from Pleos Connect 2.1.5; keep these masters intact.
const officialIds={button:'18:132',field:'18:269',switch:'18:404',checkbox:'18:460',segmented:'18:587'};
const mutatedNodeIds=[];
for(const [index,[name,id]]of Object.entries(officialIds).entries()) {const n=await figma.getNodeByIdAsync(id);n.x=11200;n.y=160+index*1250;mutatedNodeIds.push(n.id);}
for(const [kind,id] of Object.entries({Primary:'18:145',Secondary:'18:181',Quiet:'18:181',Disabled:'18:153'})){components['Style='+kind]=id;properties['Button/'+kind]={Label:'Text#23417:0'};}

const choices=[];
for(const state of ['Selected','Default']) {
  const c=comp('State='+state,196,76,'HORIZONTAL');padding(c,16);radius(c,'20');c.primaryAxisAlignItems='CENTER';c.counterAxisAlignItems='CENTER';fill(c,state==='Selected'?'accent':'surface');c.strokes=[paint('accent')];c.strokeWeight=1;
  const t=text(state==='Selected'?'호기심 있게':'차분하게','Label',state==='Selected'?'onAccent':'ink');c.appendChild(t);properties['Choice/'+state]={Label:prop(c,t,'Label',t.characters)};choices.push(c);
}
combine('Choice',choices);

const field=comp('Field',640,122);gap(field,8);
const fl=text('목적지','Caption','muted');field.appendChild(fl);
const fb=add((await figma.getNodeByIdAsync('18:318')).createInstance());for(const n of fb.findAll(()=>true))createdNodeIds.push(n.id);fb.name='Official Pleos input';field.appendChild(fb);fb.resize(640,80);fb.layoutSizingHorizontal='FILL';fb.setProperties({'Label#28158:0':'안목해변','Place holder#34129:2':'안목해변'});fill(fb,'surface');fb.strokes=[paint('accent')];fb.strokeWeight=1;
for(const t of fb.findAllWithCriteria({types:['TEXT']})){t.fontName={family:'Noto Sans KR',style:'Medium'};t.textStyleId=foundation.styles.Label;fill(t,'ink');}
fb.fills=[];fb.strokes=[];const fieldSurface=fb.findOne(n=>n.type==='FRAME'&&n.name==='Text Fields');fill(fieldSurface,'surface');fieldSurface.strokes=[paint('accent')];fieldSurface.strokeWeight=1;radius(fieldSurface,'20');
properties.Field={Label:prop(field,fl,'Label','목적지')};field.x=8000;field.y=1580;
const toggle=comp('Motion toggle',368,80,'HORIZONTAL');padding(toggle,16);gap(toggle,16);toggle.counterAxisAlignItems='CENTER';radius(toggle,'20');fill(toggle,'surface');
const tl=text('움직임 줄이기','Label','accent');toggle.appendChild(tl);const sw=add((await figma.getNodeByIdAsync('18:411')).createInstance());for(const n of sw.findAll(()=>true))createdNodeIds.push(n.id);toggle.appendChild(sw);toggle.x=8000;toggle.y=2250;
fill(sw,'soft');sw.strokes=[paint('accent')];sw.strokeWeight=1;for(const n of sw.findAllWithCriteria({types:['RECTANGLE']}))fill(n,'accent');
const confirmation=comp('Route confirmation',642,80,'HORIZONTAL');padding(confirmation,8);gap(confirmation,16);confirmation.counterAxisAlignItems='CENTER';radius(confirmation,'20');fill(confirmation,'surface');
const cb=add((await figma.getNodeByIdAsync('18:467')).createInstance());for(const n of cb.findAll(()=>true))createdNodeIds.push(n.id);confirmation.appendChild(cb);const ct=text('이번에 갈 경로가 맞아요','Label','accent');confirmation.appendChild(ct);confirmation.x=8000;confirmation.y=2390;
fill(cb.findOne(n=>n.name==='Box'),'accent');fill(cb.findOne(n=>n.type==='VECTOR'),'onAccent');

const status=comp('Status',640,72,'HORIZONTAL');padding(status,16);gap(status,12);radius(status,'12');fill(status,'soft');status.counterAxisAlignItems='CENTER';
const st=text('내 눈티에 자동으로 저장됐어요','Caption','accent');status.appendChild(st);properties.Status={Message:prop(status,st,'Message',st.characters)};status.x=8000;status.y=1760;

const metric=comp('Metric',290,204);padding(metric,24);gap(metric,8);radius(metric,'20');fill(metric,'surface');
const ml=text('함께한 시간','Caption','muted'),mv=text('38분','Title'),mc=text('이번 여정','Caption','muted');[ml,mv,mc].forEach(n=>metric.appendChild(n));properties.Metric={Label:prop(metric,ml,'Label',ml.characters),Value:prop(metric,mv,'Value',mv.characters),Context:prop(metric,mc,'Context',mc.characters)};metric.x=8000;metric.y=1930;

for(const [kind,hash] of [['Base','2893d38594281749383c75afa1b9636d2b84398c'],['CoastCurious','9267bd06cd286b3e692443fe30d026123d5581df']]) {
  const c=comp('Character / '+kind,768,768,'NONE');c.description='Approved Nunti A. Fixed source pixels; use FIT and scale proportionally. Do not regenerate or change silhouette.';
  const im=add(figma.createRectangle());im.name='Approved A PNG';im.resize(768,768);im.fills=[{type:'IMAGE',imageHash:hash,scaleMode:'FIT'}];c.appendChild(im);im.constraints={horizontal:'SCALE',vertical:'SCALE'};
  c.x=8900+(kind==='Base'?0:820);c.y=160;
}

const route=comp('Route preview / synthetic confirmed',640,260,'NONE');radius(route,'20');fill(route,'soft');route.description='Editable normalized five-point route from coast-curious/request.json. Synthetic, not GPS, ETA or a navigation map.';
const svg=add(figma.createNodeFromSvg('<svg width="640" height="260" viewBox="0 0 640 260" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M64 213.2 L160 176.8 L256 140.4 L390.4 104 L537.6 46.8" stroke="#355C4B" stroke-width="7" stroke-linecap="round" stroke-linejoin="round"/><circle cx="64" cy="213.2" r="11" fill="#FFFEF9" stroke="#355C4B" stroke-width="5"/><circle cx="537.6" cy="46.8" r="12" fill="#9B593C"/></svg>'));svg.name='Normalized route · editable paths';route.appendChild(svg);
svg.constraints={horizontal:'SCALE',vertical:'SCALE'};
for(const n of svg.findAll(()=>true)){createdNodeIds.push(n.id);if('strokes'in n&&Array.isArray(n.strokes)&&n.strokes.length)n.strokes=[paint('accent')];if('fills'in n&&Array.isArray(n.fills)&&n.fills.length){n.fills=n.name.includes('Ellipse')?[paint('warm')]:n.fills;}}
const rt=text('예시 경로','Caption','muted');route.appendChild(rt);rt.x=24;rt.y=16;route.x=8900;route.y=1100;

return {createdNodeIds,mutatedNodeIds,pageId:page.id,components,sets,properties,officialMasters:officialIds,counts:{components:page.findAllWithCriteria({types:['COMPONENT']}).length,sets:Object.keys(sets).length},sourceImages:[{node:'14:4',hash:'2893d38594281749383c75afa1b9636d2b84398c',source:'android/app/src/debug/assets/nunti_motion_v1/base.png'},{node:'3:8',hash:'9267bd06cd286b3e692443fe30d026123d5581df',source:'docs/redesign/route-variants-v1/samples/coast-curious/character.png'}]};
