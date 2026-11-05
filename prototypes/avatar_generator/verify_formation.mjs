#!/usr/bin/env node
// Real Canvas raster checks and still key poses. No recording or audio.
import fs from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
import {spawn} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import crypto from 'node:crypto';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../..');
const base='http://127.0.0.1:8768',port=9227;
const fixtures=path.resolve(process.argv.find(x=>x.startsWith('--fixtures='))?.slice(11)||path.join(root,'.local/avatar-quality-v4/motion-fixtures'));
const out=path.resolve(process.argv.find(x=>x.startsWith('--out='))?.slice(6)||path.join(root,'.local/avatar-quality-v4/motion-qa'));await fs.mkdir(out,{recursive:true});
const formationSha=crypto.createHash('sha256').update(await fs.readFile(path.join(root,'prototypes/avatar_generator/formation.js'))).digest('hex');
const pause=ms=>new Promise(r=>setTimeout(r,ms));
const proof={status:'FAIL',surface:'ACTUAL_CHROME_CANVAS',recorded:false,speakerPlayed:false,providerApiCalls:0,fixtures:[]};
let socket,chrome,id=1;const pending=new Map();
const command=(method,params={})=>new Promise((resolve,reject)=>{const next=id++;pending.set(next,{resolve,reject});socket.send(JSON.stringify({id:next,method,params}));});
async function evaluate(expression){const r=await command('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(r.exceptionDetails)throw new Error('Canvas evaluation failed');return r.result.value;}
async function endpoint(){return (await fetch(`http://127.0.0.1:${port}/json/list`)).json();}
try{
  const files=(await fs.readdir(fixtures)).filter(name=>name.endsWith('.json')&&name!=='index.json');assert(files.length>=3,'Need at least three real renderer fixtures');
  let busy=false;try{await endpoint();busy=true;}catch{}assert(!busy,'Port 9227 is already in use');
  chrome=spawn('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',['--headless=new',`--remote-debugging-port=${port}`,'--remote-debugging-address=127.0.0.1',`--user-data-dir=${path.join(root,'.local/avatar-quality-v4/chrome-motion-qa')}`,'--no-first-run','--no-default-browser-check','about:blank'],{stdio:'ignore'});
  let target;for(let i=0;i<100;i++){try{target=(await endpoint()).find(t=>t.type==='page');if(target)break;}catch{}await pause(100);}assert(target,'Dedicated Chrome did not start');
  socket=new WebSocket(target.webSocketDebuggerUrl);await new Promise((resolve,reject)=>{socket.onopen=resolve;socket.onerror=reject;});
  socket.onmessage=e=>{const m=JSON.parse(e.data);if(m.id){const p=pending.get(m.id);pending.delete(m.id);if(m.error)p?.reject(new Error('CDP failed'));else p?.resolve(m.result);}};
  await command('Runtime.enable');await command('Page.enable');await command('Network.enable');await command('Network.setCacheDisabled',{cacheDisabled:true});
  const previousOrigin=await evaluate('performance.timeOrigin');
  await command('Page.navigate',{url:base});
  for(let i=0;i<200;i++){if(await evaluate(`performance.timeOrigin!==${previousOrigin}&&document.readyState==='complete'&&!!window.NuntiFormation`))break;await pause(50);}
  assert(await evaluate(`performance.timeOrigin!==${previousOrigin}&&!!window.NuntiFormation`),'Formation module not served after navigation');
  proof.capabilityPresentation=[];
  for(const caps of [{imageApiAvailable:false,localImageModelAvailable:true},{imageApiAvailable:true,localImageModelAvailable:false},{imageApiAvailable:false,localImageModelAvailable:false}]){
    const view=await evaluate(`(async()=>{const original=window.fetch;window.fetch=(url,options)=>new URL(typeof url==='string'?url:url.url,location.href).pathname==='/v3/capabilities'?Promise.resolve(new Response(JSON.stringify({data:${JSON.stringify(caps)}}),{status:200,headers:{'Content-Type':'application/json'}})):original(url,options);try{await init();}finally{window.fetch=original;}const select=document.getElementById('render-mode');select.value=${JSON.stringify(caps.localImageModelAvailable?'LOCAL_MODEL':'LOCAL_RENDER')};select.onchange();return {hidden:document.getElementById('engine-choice').hidden,options:Array.from(select.options).map(o=>({value:o.value,hidden:o.hidden,disabled:o.disabled})),note:document.getElementById('engine-note').textContent};})()`);
    assert.equal(view.hidden,!(caps.imageApiAvailable||caps.localImageModelAvailable));
    assert.equal(view.options.find(o=>o.value==='LOCAL_MODEL').disabled,!caps.localImageModelAvailable);
    assert.equal(view.options.find(o=>o.value==='IMAGE_API').disabled,!caps.imageApiAvailable);
    if(caps.localImageModelAvailable)assert(view.note.includes('약 1분'));
    proof.capabilityPresentation.push({caps,...view});
  }
  proof.capabilityTestTransport='Local capability response fixtures only; no generation POST';
  const comparisonName=files.find(n=>n==='coast.json')||files[0];
  for(const name of files){
    const value=JSON.parse(await fs.readFile(path.join(fixtures,name),'utf8'));
    const source=value.artifact||value;
    const pngPath=path.resolve(fixtures,value.imageFile||name.replace(/\.json$/,'.png'));
    const bytes=await fs.readFile(pngPath);
    const artifact={...source,mediaOrigin:source.mediaOrigin||'LOCAL_RENDER',route:source.route||{points:value.points}};
    if(name===comparisonName){
      const comparison=await evaluate(`(async()=>{const a=${JSON.stringify(artifact)},image=new Image();image.src='data:image/png;base64,${bytes.toString('base64')}';await image.decode();const F=window.NuntiFormation,plan=F.prepare(a);if(!plan)throw Error('metadata');const sheet=document.createElement('canvas');sheet.width=1920;sheet.height=1080;const sc=sheet.getContext('2d');sc.fillStyle='#f6f3ec';sc.fillRect(0,0,1920,1080);const checks=[];const poses=[.12,.34,.56,.72,.86,1];for(const [row,style]of F.effectStyles.entries()){const renderer=F.createRenderer(image,plan,{effectStyle:style});sc.fillStyle='#34594f';sc.font='18px sans-serif';sc.fillText(style,18,row*360+26);for(const [column,p]of poses.entries()){const c=document.createElement('canvas');c.width=c.height=768;const cx=c.getContext('2d',{willReadFrequently:true});const start=performance.now();renderer.draw(cx,768,768,p,0);const elapsed=performance.now()-start;sc.drawImage(c,column*320,row*360+38,320,300);sc.fillStyle='#657b70';sc.font='14px sans-serif';sc.fillText(String(Math.round(p*100))+'%',column*320+18,row*360+352);const effect=F.effectPose(plan,p,style);checks.push({style,progress:p,particles:effect.particles.length,opacity:effect.opacity,elapsedMs:elapsed});if(p===1){const ref=document.createElement('canvas');ref.width=ref.height=768;const rc=ref.getContext('2d',{willReadFrequently:true}),fit=F.displayTransform(plan,768,768,1);rc.drawImage(image,fit.x,fit.y,fit.scale,fit.scale);const aa=cx.getImageData(0,0,768,768).data,bb=rc.getImageData(0,0,768,768).data;let opaqueChanged=0,maxDelta=0;for(let i=0;i<aa.length;i+=4){let changed=false;for(let j=0;j<4;j++){const d=Math.abs(aa[i+j]-bb[i+j]);maxDelta=Math.max(maxDelta,d);changed ||=d>0;}if(changed&&aa[i+3]===255&&bb[i+3]===255)opaqueChanged++;}checks.push({style,finalOpaqueChanged:opaqueChanged,finalMaxDelta:maxDelta});}}}return {png:sheet.toDataURL('image/png').split(',')[1],checks};})()`);
      await fs.writeFile(path.join(out,'effect-comparison.png'),Buffer.from(comparison.png,'base64'));
      for(const check of comparison.checks.filter(v=>'finalOpaqueChanged'in v)){assert.equal(check.finalOpaqueChanged,0,`${check.style}: final pixels altered`);assert(check.finalMaxDelta<=1,`${check.style}: final alpha changed`);}
      proof.effectComparison={fixture:comparisonName,styles:['STARDUST','PETAL_BLOOM','AURORA_RIBBON'],checks:comparison.checks};
    }
    const result=await evaluate(`(async()=>{const a=${JSON.stringify(artifact)},image=new Image();image.src='data:image/png;base64,${bytes.toString('base64')}';await image.decode();const F=window.NuntiFormation,plan=F.prepare(a);if(!plan)throw Error('metadata');const r=F.createRenderer(image,plan),canvas=document.createElement('canvas');canvas.width=canvas.height=768;const ctx=canvas.getContext('2d',{willReadFrequently:true});const poses=[];let finalPixels;for(const p of [0,.25,.5,.75,1]){ctx.clearRect(0,0,768,768);const start=performance.now(),frame=r.draw(ctx,768,768,p,0),elapsed=performance.now()-start;const pixels=ctx.getImageData(0,0,768,768).data;if(p===1)finalPixels=new Uint8ClampedArray(pixels);let foreground=0;for(let i=3;i<pixels.length;i+=4)if(pixels[i]>24)foreground++;poses.push({progress:p,area:frame.area,inflate:frame.inflate,imageWeight:frame.imageWeight,faceOpacity:frame.faceOpacity,elapsedMs:elapsed,foregroundPixels:foreground,png:canvas.toDataURL('image/png').split(',')[1]});}
      const ref=document.createElement('canvas');ref.width=ref.height=768;const rc=ref.getContext('2d',{willReadFrequently:true}),fit=F.displayTransform(plan,768,768,1);rc.drawImage(image,fit.x,fit.y,fit.scale,fit.scale);const expected=rc.getImageData(0,0,768,768).data,actual=finalPixels;let changedBytes=0,maxDelta=0,opaqueChangedPixels=0,edgeMaxDelta=0;for(let i=0;i<actual.length;i+=4){let changed=false;for(let c=0;c<4;c++)if(actual[i+c]!==expected[i+c]){changed=true;changedBytes++;maxDelta=Math.max(maxDelta,Math.abs(actual[i+c]-expected[i+c]));if(actual[i+3]<255||expected[i+3]<255)edgeMaxDelta=Math.max(edgeMaxDelta,Math.abs(actual[i+c]-expected[i+c]));}if(changed&&actual[i+3]===255&&expected[i+3]===255)opaqueChangedPixels++;}const referencePng=ref.toDataURL('image/png').split(',')[1];
      const mask=document.createElement('canvas');mask.width=mask.height=768;const mc=mask.getContext('2d',{willReadFrequently:true});mc.beginPath();plan.contour.forEach((v,i)=>i?mc.lineTo(v[0]*768,v[1]*768):mc.moveTo(v[0]*768,v[1]*768));mc.closePath();mc.fill();const m=mc.getImageData(0,0,768,768).data;rc.clearRect(0,0,768,768);rc.drawImage(image,0,0,768,768);const original=rc.getImageData(0,0,768,768).data;let intersect=0,union=0,maskPixels=0;for(let i=3;i<m.length;i+=4){const inside=m[i]>127,visible=original[i]>96;if(inside)maskPixels++;if(inside||visible)union++;if(inside&&visible)intersect++;}
      return {poses,referencePng,mediaOrigin:a.mediaOrigin,geometrySource:plan.source,mapping:plan.mapping,faceProtected:plan.faceProtected,finalChangedBytes:changedBytes,finalMaxDelta:maxDelta,opaqueChangedPixels,edgeMaxDelta,displayFit:fit,contourAlphaIou:intersect/union,contourPixels:maskPixels,contourPoints:plan.contour.length,spinePoints:plan.spine.length,finalArea:plan.finalArea};})()`);
    const slug=path.basename(name,'.json');
    await fs.writeFile(path.join(out,`${slug}-reference.png`),Buffer.from(result.referencePng,'base64'));delete result.referencePng;
    for(const pose of result.poses){await fs.writeFile(path.join(out,`${slug}-${String(pose.progress).replace('.','_')}.png`),Buffer.from(pose.png,'base64'));delete pose.png;}
    const item={name:slug,imageSha256:crypto.createHash('sha256').update(bytes).digest('hex'),humanQualityStatus:source.humanQualityStatus||'NOT_EVALUATED_BY_THIS_TEST',...result};proof.fixtures.push(item);
    assert.equal(result.opaqueChangedPixels,0,`${slug}: original opaque body pixels changed`);
    assert(result.finalMaxDelta<=1,`${slug}: final PNG exceeds one-byte antialiasing quantization`);
    assert(result.displayFit.bodyWidth<=768*.780001&&result.displayFit.bodyHeight<=768*.760001,`${slug}: final body clipped`);
    assert(Math.abs(result.displayFit.bodyWidth-768*.78)<.001||Math.abs(result.displayFit.bodyHeight-768*.76)<.001,`${slug}: body does not fill the agreed stage size`);
    if(artifact.mediaOrigin==='LOCAL_MODEL'&&!result.faceProtected)assert(result.poses.every(p=>p.faceOpacity===0),`${slug}: unknown AI face patch was drawn`);
    assert(result.contourAlphaIou>.70,`${slug}: metadata does not match the source silhouette`);
    assert(result.poses[2].imageWeight===0&&result.poses[2].area>result.poses[0].area*3,`${slug}: no actual geometric inflation`);
    if(artifact.mediaOrigin==='LOCAL_MODEL'){
      const ui=await evaluate(`(async()=>{const source=${JSON.stringify(artifact)},a={...source,characterId:'qa-local-model-${slug}',displayName:'실제 로컬 AI 그림의 UI 시험',destination:{name:'시험 목적지'},purpose:'모션 경계 검사',voice:{description:'재생하지 않는 시험'},visual:{path:'data:image/png;base64,${bytes.toString('base64')}'},route:{...source.route,inputOrigin:'TEST_ROUTE',sourceLabel:'실제 AI PNG와 측정 기하 시험'},design:{...source.design,personality:'UI 연결 시험',motifs:[]}};await window.nuntiTest.showArtifact(a,false);await new Promise(requestAnimationFrame);const valid={source:window.nuntiTest.getFormation()?.source,faceProtected:window.nuntiTest.getFormation()?.faceProtected,origin:document.getElementById('origin-label').textContent,notice:document.getElementById('formation-notice').textContent,motifs:document.getElementById('motifs-notice').textContent};const invalid=structuredClone(a);invalid.design.formation.source='UNVERIFIED';await window.nuntiTest.showArtifact(invalid,false);await new Promise(requestAnimationFrame);return {valid,invalid:{hasFormation:!!window.nuntiTest.getFormation(),notice:document.getElementById('formation-notice').textContent,status:document.getElementById('birth-status').textContent}};})()`);
      assert.equal(ui.valid.source,'MEASURED_ALPHA_BOUNDARY');assert.equal(ui.valid.faceProtected,false);
      assert(ui.valid.origin.includes('외부 API 없음')&&ui.valid.notice.includes('얼굴 위치가 확인되지 않아')&&ui.valid.motifs.includes('아직 확인하지'));
      assert.equal(ui.invalid.hasFormation,false);assert(ui.invalid.notice.includes('모션을 건너뛰었어요')&&ui.invalid.status.includes('원본 그림'));
      (proof.localModelPresentation??=[]).push({name:slug,...ui});
    }
  }
  assert.equal(crypto.createHash('sha256').update(await fs.readFile(path.join(root,'prototypes/avatar_generator/formation.js'))).digest('hex'),formationSha,'Formation source changed during verification; rerun');
  proof.sourceSha256=formationSha;
  proof.status='PASS_FORMATION_PIXELS';
}catch(error){proof.error=error.message;process.exitCode=1;}
finally{await fs.writeFile(path.join(out,'verification.json'),JSON.stringify(proof,null,2)+'\n');socket?.close();chrome?.kill('SIGTERM');console.log(JSON.stringify({status:proof.status,fixtures:proof.fixtures.length,report:path.join(out,'verification.json'),error:proof.error}));}
