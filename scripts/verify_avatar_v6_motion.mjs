#!/usr/bin/env node
// Actual Android avatar / generated voice / purpose motion integration. No recording.
import fs from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
import {execFileSync} from 'node:child_process';
import {createHash} from 'node:crypto';
import {fileURLToPath} from 'node:url';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const aiArg=process.argv.find(arg=>arg.startsWith('--ai-dir='));
const aiDir=aiArg?path.resolve(root,aiArg.slice('--ai-dir='.length)):null;
const out=path.join(root,aiDir?'.local/avatar-v6/motion-ai':'.local/avatar-v6/motion');await fs.mkdir(out,{recursive:true});
const adb=path.join(root,'.local/pm-tools/sdk/platform-tools/adb');
const pid=execFileSync(adb,['-s','emulator-5554','shell','pidof','ai.nunti.avatar.demo'],{encoding:'utf8'}).trim();assert(/^\d+$/.test(pid));
execFileSync(adb,['-s','emulator-5554','forward','tcp:9224',`localabstract:webview_devtools_remote_${pid}`]);
const target=(await(await fetch('http://127.0.0.1:9224/json/list')).json()).find(v=>v.type==='page'&&v.url.startsWith('http://127.0.0.1:8768'));assert(target);
const socket=new WebSocket(target.webSocketDebuggerUrl);await new Promise((resolve,reject)=>{socket.onopen=resolve;socket.onerror=reject;});
let id=0;const pending=new Map(),exceptions=[];
socket.onmessage=e=>{const m=JSON.parse(e.data);if(m.id){const p=pending.get(m.id);pending.delete(m.id);m.error?p?.reject(new Error(JSON.stringify(m.error))):p?.resolve(m.result);}else if(m.method==='Runtime.exceptionThrown')exceptions.push(m.params.exceptionDetails);};
const call=(method,params={})=>new Promise((resolve,reject)=>{const n=++id;pending.set(n,{resolve,reject});socket.send(JSON.stringify({id:n,method,params}));});
async function evaluate(expression){const r=await call('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(r.exceptionDetails)throw new Error(JSON.stringify(r.exceptionDetails));return r.result?.value;}
const pause=ms=>new Promise(resolve=>setTimeout(resolve,ms));
async function wait(expression,timeout=30000){const end=Date.now()+timeout;while(Date.now()<end){const v=await evaluate(expression);if(v)return v;await pause(150);}throw new Error('Timed out: '+expression+'; '+await evaluate('document.getElementById("notice").textContent'));}
const matrix=JSON.parse(await fs.readFile(path.join(root,'.local/avatar-v6/matrix/voice-input.json')));
let cases=matrix.cases;
if(aiDir){
  const jobs=JSON.parse(await fs.readFile(path.join(aiDir,'jobs.json'))).jobs;
  cases=await Promise.all(jobs.map(async job=>{
    const c=matrix.cases.find(c=>c.id===job.id);assert(c,'AI case must match a prepared character');
    const folder=path.join(aiDir,'cases',job.id),record=JSON.parse(await fs.readFile(path.join(folder,'result.json')));
    assert.equal(record.status,'READY',job.id+' AI image must be ready');
    const input=JSON.parse(await fs.readFile(path.join(folder,'input.json')));
    const design=JSON.parse(await fs.readFile(path.join(folder,'design.json')));
    design.formation=JSON.parse(await fs.readFile(path.join(folder,'formation.json')));
    return {id:job.id,input,design,pngPath:path.join(folder,'avatar.png'),sha256:record.rgbaSha256};
  }));
}
const report={status:'FAIL',surface:'ACTUAL_ANDROID_WEBVIEW_OFFSCREEN_CANVAS',imageMode:aiDir?'LOCAL_MODEL':'LOCAL_RENDER',expected:cases.length,cases:[],videoRecorded:false,audioRecorded:false};
let initialArtifact=null;
try{
  await call('Runtime.enable');initialArtifact=await evaluate('window.nuntiTest?.getArtifact()||null');await call('Page.reload',{ignoreCache:true});await wait('window.NuntiFormation&&window.NuntiJourneyEffects');
  for(const c of cases){
    const png=await fs.readFile(c.pngPath||path.join(root,'.local/avatar-v6/matrix/images',c.id+'.png'));
    const imageSha256=createHash('sha256').update(png).digest('hex');
    if(c.sha256)assert.equal(imageSha256,c.sha256,c.id+' file hash');
    const a={design:c.design,route:c.input.route,mediaOrigin:report.imageMode};
    const result=await evaluate(`(async()=>{
      const a=${JSON.stringify(a)},plan=NuntiFormation.prepare(a);if(!plan)throw new Error('missing formation');
      const image=new Image();image.src=${JSON.stringify('data:image/png;base64,'+png.toString('base64'))};await image.decode();
      const canvas=document.createElement('canvas');canvas.width=canvas.height=256;const ctx=canvas.getContext('2d',{willReadFrequently:true});
      const sheet=document.createElement('canvas');sheet.width=1024;sheet.height=256;const sheetCtx=sheet.getContext('2d');sheetCtx.fillStyle='#f8f5ed';sheetCtx.fillRect(0,0,1024,256);
      const renderer=NuntiFormation.createRenderer(image,plan),frames=[];let finalPixels;
      const hash=async bytes=>[...new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))].map(n=>n.toString(16).padStart(2,'0')).join('');
      for(const [i,p] of [.14,.4,.7,1].entries()){
        ctx.clearRect(0,0,256,256);const frame=renderer.draw(ctx,256,256,p,0);
        const pixels=ctx.getImageData(0,0,256,256).data;let visible=0;for(let k=3;k<pixels.length;k+=4)if(pixels[k])visible++;
        if(p===1)finalPixels=new Uint8ClampedArray(pixels);
        frames.push({p,visible,hash:await hash(pixels),finite:frame.contour.flat().every(Number.isFinite)});
        sheetCtx.drawImage(canvas,i*256,0);
      }
      const fit=NuntiFormation.displayTransform(plan,256,256,1);ctx.clearRect(0,0,256,256);ctx.drawImage(image,fit.x,fit.y,fit.scale,fit.scale);
      const direct=ctx.getImageData(0,0,256,256).data;let maxPremultipliedDelta=0,totalDelta=0;
      for(let k=0;k<direct.length;k+=4){for(let j=0;j<4;j++){
        const delta=Math.abs(j===3?direct[k+3]-finalPixels[k+3]:direct[k+j]*direct[k+3]/255-finalPixels[k+j]*finalPixels[k+3]/255);
        maxPremultipliedDelta=Math.max(maxPremultipliedDelta,delta);totalDelta+=delta;
      }}
      // Compare composited color, not meaningless RGB under near-zero alpha.
      const meanPremultipliedDelta=totalDelta/direct.length;
      const finalUnmodified=maxPremultipliedDelta===0&&meanPremultipliedDelta===0;
      const start=NuntiJourneyEffects.sample(plan,0),end=NuntiJourneyEffects.sample(plan,1);
      return {frames,finalUnmodified,maxPremultipliedDelta,meanPremultipliedDelta,theme:NuntiJourneyEffects.theme(plan).name,
        sourceRouteParticles:start.particles.every((p,i)=>p.x===plan.effectSeeds[i].route[0]&&p.y===plan.effectSeeds[i].route[1]),
        noFinishedOverlay:end.opacity===0,sheet:sheet.toDataURL('image/png')};
    })()`);
    if(!(result.finalUnmodified&&result.sourceRouteParticles&&result.noFinishedOverlay&&result.frames.every(f=>f.visible>0&&f.finite))){const {sheet,...failure}=result;report.failure={id:c.id,...failure};}
    assert(result.finalUnmodified&&result.sourceRouteParticles&&result.noFinishedOverlay&&result.frames.every(f=>f.visible>0&&f.finite),c.id);
    if(['01-business','02-date','03-swim'].includes(c.id))await fs.writeFile(path.join(out,c.id+'-keyposes.png'),Buffer.from(result.sheet.split(',')[1],'base64'));
    delete result.sheet;report.cases.push({id:c.id,imageSha256,...result});
    if(report.cases.length%25===0)console.log(JSON.stringify({completed:report.cases.length,total:cases.length}));
  }
  assert.equal(report.cases.length,cases.length);assert.equal(exceptions.length,0);
  report.status='PASS';report.actualCanvasRenders=report.cases.length*4;
  report.distinctPurposeThemes=new Set(report.cases.map(c=>c.theme)).size;
}catch(e){report.error=e.stack;throw e;}finally{
  report.exceptions=exceptions;await fs.writeFile(path.join(out,'verification.json'),JSON.stringify(report,null,2));
  if(initialArtifact)await evaluate(`state.nativeAllowed&&window.nuntiTest.showArtifact(${JSON.stringify(initialArtifact)},false)`).catch(()=>{});
  socket.close();
  console.log(JSON.stringify({status:report.status,cases:report.cases.length,actualCanvasRenders:report.actualCanvasRenders,report:path.join(out,'verification.json')}));
}
