// Run with Figma MCP use_figma. Reuses the official skill helper algorithms.
// This file only creates the scoped Nunti redesign foundations.
const createdNodeIds = [];
const pageName = 'Redesign · Pleos UI';
if (figma.root.children.some(p => p.name === pageName)) throw new Error('Redesign already exists; inspect its ledger before retrying.');
const page = figma.createPage(); page.name = pageName; createdNodeIds.push(page.id);
await figma.setCurrentPageAsync(page);
await Promise.all(['Regular','Medium','Bold'].map(style => figma.loadFontAsync({family:'Noto Sans KR',style})));

// Adapted from figma-generate-library/scripts/createVariableCollection.js.
async function createVariableCollection(name, modeNames) {
  const collection = figma.variables.createVariableCollection(name);
  const modeIds = {};
  collection.renameMode(collection.modes[0].modeId, modeNames[0]);
  modeIds[modeNames[0]] = collection.modes[0].modeId;
  for (const name of modeNames.slice(1)) modeIds[name] = collection.addMode(name);
  return {collection,modeIds};
}
function rgba(hex) {const v=hex.replace('#','');return {r:parseInt(v.slice(0,2),16)/255,g:parseInt(v.slice(2,4),16)/255,b:parseInt(v.slice(4,6),16)/255,a:1};}
// Adapted from createSemanticTokens.js; creates only the requested role set.
function token(collection,modeIds,name,type,values,scopes,android,web) {
  const v=figma.variables.createVariable(name,collection,type);
  v.scopes=scopes;
  for(const [mode,value] of Object.entries(values)) v.setValueForMode(modeIds[mode],type==='COLOR'&&typeof value==='string'?rgba(value):value);
  v.setVariableCodeSyntax('ANDROID',android);
  v.setVariableCodeSyntax('WEB',`var(${web})`);
  return v;
}
const primitive=await createVariableCollection('Nunti / primitives',['Value']);
const color=await createVariableCollection('Nunti / semantic',['Day','Night']);
const layout=await createVariableCollection('Nunti / layout & type',['Value']);
const roles={
  background:['#F4F3EE','#131D1B','--bg'],
  surface:['#FFFEF9','#1D2C28','--paper'],
  soft:['#E8EDE3','#263B33','--mint'],
  tint:['#E1EAD8','#314B3F','--surface-tint'],
  ink:['#253E3E','#EAF2E6','--ink'],
  muted:['#56675E','#B2C4B9','--muted'],
  border:['#CCD6C9','#4D6357','--line'],
  accent:['#355C4B','#B6D0A0','--green'],
  onAccent:['#FFFFFF','#17271F','--on-accent'],
  warm:['#925238','#F1BC8A','--accent'],
  info:['#2E5C71','#9CC7D8','--info'],
};
const vars={},primitives={};
for(const [name,[day,night,css]] of Object.entries(roles)) {
  for(const [mode,value] of Object.entries({Day:day,Night:night})) {
    const key=name+'/'+mode;
    primitives[key]=token(primitive.collection,primitive.modeIds,key,'COLOR',{Value:value},[],`NuntiPalette.${name}${mode}`,`--nunti-raw-${name}-${mode.toLowerCase()}`);
  }
  const scopes=name==='border'?['STROKE_COLOR']:['ink','muted','onAccent'].includes(name)?['TEXT_FILL']:['FRAME_FILL','SHAPE_FILL','TEXT_FILL','STROKE_COLOR'];
  vars['color/'+name]=token(color.collection,color.modeIds,'color/'+name,'COLOR',Object.fromEntries(['Day','Night'].map(m=>[m,{type:'VARIABLE_ALIAS',id:primitives[name+'/'+m].id}])),scopes,`NuntiColors.${name}`,css);
}
const metrics={
  'space/8':8,'space/12':12,'space/16':16,'space/24':24,'space/32':32,'space/40':40,'space/48':48,'space/64':64,
  'radius/12':12,'radius/20':20,'radius/28':28,'radius/pill':999,
  'control/height':80,'control/compact':76,
};
for(const [name,value] of Object.entries(metrics)) vars[name]=token(layout.collection,layout.modeIds,name,'FLOAT',{Value:value},[name.startsWith('space')?'GAP':name.startsWith('radius')?'CORNER_RADIUS':'WIDTH_HEIGHT'],`NuntiMetrics.${name.replaceAll('/','_')}`,`--nunti-${name.replaceAll('/','-')}`);
vars['font/family']=token(layout.collection,layout.modeIds,'font/family','STRING',{Value:'Noto Sans KR'},['FONT_FAMILY'],'NuntiTypography.family','--nunti-font-family');
const typography={Display:[56,72,'Bold'],Title:[38,52,'Bold'],Heading:[30,44,'Medium'],Body:[26,40,'Regular'],Label:[26,38,'Medium'],Caption:[22,34,'Regular'],Number:[72,88,'Bold']};
const styles={};
for(const [name,[size,line,weight]] of Object.entries(typography)) {
  const sizeVar=token(layout.collection,layout.modeIds,'type/'+name+'/size','FLOAT',{Value:size},['FONT_SIZE'],`NuntiTypography.${name.toLowerCase()}.fontSize`,`--nunti-type-${name.toLowerCase()}-size`);
  const lineVar=token(layout.collection,layout.modeIds,'type/'+name+'/line','FLOAT',{Value:line},['LINE_HEIGHT'],`NuntiTypography.${name.toLowerCase()}.lineHeight`,`--nunti-type-${name.toLowerCase()}-line`);
  vars['type/'+name+'/size']=sizeVar;vars['type/'+name+'/line']=lineVar;
  const s=figma.createTextStyle();s.name='Nunti / '+name;s.fontName={family:'Noto Sans KR',style:weight};s.fontSize=size;s.lineHeight={unit:'PIXELS',value:line};
  s.setBoundVariable('fontFamily',vars['font/family']);s.setBoundVariable('fontSize',sizeVar);s.setBoundVariable('lineHeight',lineVar);styles[name]=s.id;
}
return {createdNodeIds,pageId:page.id,collections:{primitive:{id:primitive.collection.id,modes:primitive.modeIds},color:{id:color.collection.id,modes:color.modeIds},layout:{id:layout.collection.id,modes:layout.modeIds}},variables:Object.fromEntries(Object.entries(vars).map(([k,v])=>[k,v.id])),primitives:Object.fromEntries(Object.entries(primitives).map(([k,v])=>[k,v.id])),styles,roles,typography,metrics,font:'Noto Sans KR',codeSyntaxStatus:'Existing CSS names reused where applicable; Nunti Kotlin tokens proposed, not production classes.'};
