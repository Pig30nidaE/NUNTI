// Read-only Figma MCP reader. Inject `const auditSpec = ...` with the verifier.
const page = await figma.getNodeByIdAsync(auditSpec.pageId);
await figma.setCurrentPageAsync(page);
const results = [];
const imageSizes = {};
const masterRefs = {};
let motionAvailable = true;
let motionApiError = null;
const box = n => n.absoluteBoundingBox;
const outside = (a,b) => a && b && (a.x < b.x-1 || a.y < b.y-1 || a.x+a.width > b.x+b.width+1 || a.y+a.height > b.y+b.height+1);
for (const entry of auditSpec.screens) {
  const root = await figma.getNodeByIdAsync(entry.id);
  if (!root) { results.push({id:entry.id,name:entry.name,missing:true}); continue; }
  const nodes = [root,...root.findAll(()=>true)];
  const record = {id:root.id,name:entry.name,actualName:root.name,type:root.type,width:root.width,height:root.height,layoutMode:root.layoutMode,clipsContent:root.clipsContent,nodeCount:nodes.length,types:{},autoLayoutCount:0,instanceCount:0,textCount:0,visibleTextCount:0,fontCounts:{},fontErrors:[],images:[],actionables:[],touchErrors:[],overflow:[],intentionalScrollOverflowCount:0,scrollViewports:[],reactions:[],motionNodes:[],motionCheckedNodes:0};
  const rootBox = box(root);
  for (const n of nodes) {
    record.types[n.type]=(record.types[n.type]||0)+1;
    if ('layoutMode' in n && n.layoutMode !== 'NONE') record.autoLayoutCount++;
    let visible=n.visible!==false && n.opacity!==0, nestedInstance=false, manualScroll=null;
    const ancestry=[];
    for (let p=n.parent; p && p.id!==page.id; p=p.parent) {
      ancestry.push({id:p.id,name:p.name});
      if (p.visible===false || p.opacity===0) visible=false;
      if (p.type==='INSTANCE') nestedInstance=true;
      if (p.clipsContent && p.overflowDirection==='VERTICAL' && /Parked manual scroll viewport/.test(p.name)) manualScroll=p;
      if (p.id===root.id) break;
    }
    if ('overflowDirection' in n && n.overflowDirection && n.overflowDirection!=='NONE') record.scrollViewports.push({id:n.id,name:n.name,direction:n.overflowDirection,clipsContent:n.clipsContent});
    if (visible && n.id!==root.id && outside(box(n),rootBox)) {
      if (manualScroll) record.intentionalScrollOverflowCount++;
      else record.overflow.push({id:n.id,name:n.name,type:n.type,bounds:box(n)});
    }
    if (n.type==='TEXT') {
      record.textCount++;
      if (visible && n.characters.trim()) {
        record.visibleTextCount++;
        const segments=n.getStyledTextSegments(['fontName','fontSize']);
        for (const s of segments) {
          const family=s.fontName.family;
          record.fontCounts[family]=(record.fontCounts[family]||0)+1;
          if (family!=='Noto Sans KR') record.fontErrors.push({id:n.id,font:s.fontName,size:s.fontSize});
        }
      }
    }
    if ('fills' in n && Array.isArray(n.fills)) {
      for (const p of n.fills) if (p.type==='IMAGE') {
        if (!(p.imageHash in imageSizes)) {
          const im=figma.getImageByHash(p.imageHash);
          imageSizes[p.imageHash]=im ? await im.getSizeAsync() : null;
        }
        record.images.push({id:n.id,name:n.name,hash:p.imageHash,width:n.width,height:n.height,visible,approved:auditSpec.allowedImages.includes(p.imageHash),characterAncestor:ancestry.some(a=>/Nunti|Character|눈티/i.test(a.name)),ancestorIds:ancestry.slice(0,3).map(a=>a.id)});
      }
    }
    if (n.type==='INSTANCE') {
      record.instanceCount++;
      const main=await n.getMainComponentAsync();
      const key=main ? main.id : 'MISSING';
      if (!masterRefs[key]) masterRefs[key]={id:key,name:main?.name,count:0,minWidth:n.width,minHeight:n.height,exampleIds:[]};
      const stat=masterRefs[key];stat.count++;stat.minWidth=Math.min(stat.minWidth,n.width);stat.minHeight=Math.min(stat.minHeight,n.height);
      if (stat.exampleIds.length<3) stat.exampleIds.push(n.id);
      const explicit=Object.prototype.hasOwnProperty.call(auditSpec.actions,n.id);
      const semantic=/^(Action|Choice|Field)\s*\/|^Route confirmation$|^Motion toggle$/.test(n.name);
      if (visible && !nestedInstance && (explicit||semantic)) {
        const a={id:n.id,name:n.name,width:n.width,height:n.height,mainId:key,explicit};
        record.actionables.push(a);
        if (n.height<76-0.01 || n.width<76-0.01) record.touchErrors.push(a);
      }
    }
    if ('reactions' in n) for(const r of n.reactions||[]) record.reactions.push({id:n.id,trigger:r.trigger?.type,actions:(r.actions||(r.action?[r.action]:[])).map(a=>({type:a.type,destinationId:a.destinationId,transition:a.transition}))});
    if (motionAvailable) {
      try {
        const manual=n.manualKeyframeTracks||{};
        const styles=n.animationStyles||[];
        const resolved=n.animations||{};
        const fields=Object.keys(manual).filter(k=>manual[k] && ((manual[k].keyframes?.length||0)>0 || (manual[k].tracks?.length||0)>0));
        const resolvedFields=Object.keys(resolved).filter(k=>resolved[k] && (resolved[k].tracks?.length||0)>0);
        record.motionCheckedNodes++;
        if(fields.length || styles.length || resolvedFields.length) record.motionNodes.push({id:n.id,fields,styleCount:styles.length,resolvedFields});
      } catch(e) {motionAvailable=false;motionApiError=String(e);}
    }
  }
  record.actionableCount=record.actionables.length;
  record.minActionWidth=record.actionables.length ? Math.min(...record.actionables.map(a=>a.width)) : null;
  record.minActionHeight=record.actionables.length ? Math.min(...record.actionables.map(a=>a.height)) : null;
  delete record.actionables;
  results.push(record);
}
const out={schema:'nunti-figma-ui-readback-v1',fileKey:auditSpec.fileKey,pageId:page.id,readAt:new Date().toISOString(),motionAvailable,motionApiError,imageSizes,masterRefs:Object.values(masterRefs),screens:results};
const size=JSON.stringify(out).length;
if(size>47500) throw new Error('Audit return exceeds 47.5KB; narrow screen batch. Bytes='+size);
return out;
