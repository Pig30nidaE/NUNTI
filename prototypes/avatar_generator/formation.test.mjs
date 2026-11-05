import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import crypto from 'node:crypto';
const require=createRequire(import.meta.url);
const F=require('./formation.js');
const routes=[[[.1,.8],[.3,.45],[.7,.55],[.9,.1]],[[.1,.2],[.1,.8],[.8,.8],[.8,.2]],[[.9,.9],[.6,.7],[.5,.2],[.1,.1]]];
function artifact(route){
  const contour=Array.from({length:192},(_,i)=>{const a=i/191*Math.PI*2;return [.5+Math.cos(a)*.26,.48+Math.sin(a)*.33];});
  const spine=F.resample([[.32,.66],[.45,.48],[.6,.3]],96);
  return {mediaOrigin:'LOCAL_RENDER',route:{points:route},design:{formation:{version:'route-volume-2',contour,spine,faceCenter:[.5,.4],palette:['#9fd4d8','#72afba']}}};
}
let frames=0;
for(const route of routes){
  const a=artifact(route),plan=F.prepare(a);assert(plan);
  assert.equal(plan.contour.length,192);assert.equal(plan.spine.length,96);
  const original=JSON.stringify(a);
  const start=F.pose(plan,0),growing=F.pose(plan,.5),grown=F.pose(plan,.82),last=F.pose(plan,1);
  assert(start.area<plan.finalArea*.08,'starts as a thin material, not a complete bitmap silhouette');
  assert(growing.area>start.area*5,'closed body gains real geometric area');
  assert.equal(growing.imageWeight,0,'body growth occurs before any complete source image is drawn');
  assert.deepEqual(grown.contour,plan.contour);assert.deepEqual(last.contour,plan.contour);
  assert.equal(grown.imageWeight,0);assert.equal(last.imageWeight,1);
  assert.equal(last.scaleX,1);assert.equal(last.scaleY,1);assert.equal(last.floatY,0);
  assert.deepEqual(F.pose(plan,.74).faceCenter,plan.faceCenter);
  let previous=null;
  for(let i=0;i<=1000;i++){
    const p=F.pose(plan,i/1000);frames++;
    assert(p.contour.every(v=>v.every(Number.isFinite)));
    assert(p.area>=0&&p.imageWeight>=0&&p.imageWeight<=1);
    assert(Math.abs(p.scaleX*p.scaleY-1)<1e-12,'landing preserves planar volume');
    if(previous){const jump=Math.max(...p.contour.map((v,j)=>Math.hypot(v[0]-previous.contour[j][0],v[1]-previous.contour[j][1])));assert(jump<.025,'continuous contour motion');}
    previous=p;
  }
  assert.equal(JSON.stringify(a),original,'source artifact remains immutable');
}
const unequal=[[0,0],[.01,0],[1,0]];
assert.deepEqual(F.trace(unequal,0),[[0,0]]);
assert(Math.abs(F.trace(unequal,.5).at(-1)[0]-.5)<1e-12,'pen follows distance, not point count');
assert.deepEqual(F.trace(unequal,1),unequal);
const good=artifact(routes[0]);
assert.equal(F.prepare({...good,mediaOrigin:'PROVIDER_GENERATED'}),null,'unverified API geometry is not borrowed');
assert.equal(F.prepare({route:good.route,design:{}}),null,'old artifacts use their own display');
const malformed=structuredClone(good);malformed.design.formation.contour[0]=[NaN,.5];assert.equal(F.prepare(malformed),null);
const open=structuredClone(good);open.design.formation.contour.pop();assert.equal(F.prepare(open),null);
const injection=structuredClone(good);injection.design.formation.palette[0]='url(javascript:bad)';assert.equal(F.prepare(injection),null);
assert.throws(()=>F.pose(F.prepare(good),NaN),RangeError);
const effectPlan=F.prepare(good);
for(const style of F.effectStyles){
  for(let i=0;i<=200;i++){
    const p=i/200,effect=F.effectPose(effectPlan,p,style);
    assert(effect.opacity>=0&&effect.opacity<=1);
    assert(effect.particles.length<=54&&effect.rings.length<=3,'bounded celebration particles');
    assert(effect.particles.every(v=>v.position.every(Number.isFinite)&&Number.isFinite(v.size)&&v.alpha>=0&&v.alpha<=1));
    if(p>=.98)assert.equal(effect.opacity,0,'celebration settles completely before the final frame');
    if(p>=.46)assert.equal(F.pose(effectPlan,p).strokeOpacity,0,'route ink disappears before the grown body is shown');
  }
  assert.equal(F.effectPose(effectPlan,0,style).particles.length,0,'no flash on entry');
  assert.equal(F.effectPose(effectPlan,1,style).particles.length,0,'no permanent overlay on final artwork');
}
assert.throws(()=>F.effectPose(effectPlan,.5,'INVALID'),RangeError);
assert.throws(()=>F.effectPose(effectPlan,NaN),RangeError);
const measured=structuredClone(good);measured.mediaOrigin='LOCAL_MODEL';
Object.assign(measured.design.formation,{source:'MEASURED_ALPHA_BOUNDARY',mapping:'GEOMETRIC_PROJECTION_NOT_SEMANTIC',faceCenter:null,faceCenterVerified:false});
const measuredPlan=F.prepare(measured);assert(measuredPlan,'measured AI alpha boundary is supported');
assert.equal(measuredPlan.source,'MEASURED_ALPHA_BOUNDARY','provenance remains a string and cannot be overwritten by route samples');
assert.equal(measuredPlan.mapping,'GEOMETRIC_PROJECTION_NOT_SEMANTIC');
assert(Array.isArray(measuredPlan.sourceSamples)&&measuredPlan.sourceSamples.length===96,'route samples have a separate field');
assert.equal(F.prepare(good).source,'LOCAL_RENDER_GEOMETRY');
assert.equal(measuredPlan.faceProtected,false);assert.equal(measuredPlan.faceCenter,null);
for(const p of [0,.25,.5,.75,.9,1]){const frame=F.pose(measuredPlan,p);assert.equal(frame.faceCenter,null);assert.equal(frame.faceOpacity,0,'unknown face never contributes a bitmap patch');}
assert.deepEqual(F.pose(measuredPlan,1).contour,measuredPlan.contour);assert.equal(F.pose(measuredPlan,1).imageWeight,1,'the unmodified final image still includes its original face');
const heuristicFace=structuredClone(measured);heuristicFace.design.formation.faceCenter=[.4,.4];
assert.equal(F.prepare(heuristicFace).faceCenter,null,'heuristic coordinate is not a verified face');
delete heuristicFace.design.formation.faceCenterVerified;
assert.equal(F.prepare(heuristicFace).faceCenter,null,'missing verification does not become true');
const verifiedFace=structuredClone(heuristicFace);verifiedFace.design.formation.faceCenterVerified=true;
assert.equal(F.prepare(verifiedFace).faceProtected,true,'explicitly verified face may be protected');
const borrowedGeometry=structuredClone(measured);delete borrowedGeometry.design.formation.source;
assert.equal(F.prepare(borrowedGeometry),null,'AI geometry requires measured-alpha provenance');
borrowedGeometry.design.formation.source='MEASURED_ALPHA_BOUNDARY';borrowedGeometry.design.formation.mapping='SEMANTIC_PARTS';
assert.equal(F.prepare(borrowedGeometry),null,'geometric AI projection cannot claim semantic part correspondence');
const fixtureDir=path.resolve(process.argv.find(x=>x.startsWith('--fixtures='))?.slice(11)||path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../../.local/avatar-quality-v4/motion-fixtures'));
let realFixtures=0;
if(fs.existsSync(fixtureDir))for(const name of fs.readdirSync(fixtureDir).filter(n=>n.endsWith('.json')&&n!=='index.json')){
  const value=JSON.parse(fs.readFileSync(path.join(fixtureDir,name),'utf8')),a=value.artifact||value;
  const plan=F.prepare(a);assert(plan,`${name}: actual metadata accepted`);realFixtures++;
  assert.deepEqual(F.pose(plan,0).centerline,plan.sourceSamples,'initial samples follow original route arc');
  assert(F.pose(plan,.52).centerline.every((v,i)=>Math.hypot(v[0]-plan.spine[i][0],v[1]-plan.spine[i][1])<1e-12),'original arc index reaches the matching target spine index');
  const end=F.displayTransform(plan,768,768,1);
  assert(end.bodyWidth<=768*.780001&&end.bodyHeight<=768*.760001,'full final silhouette fits the stage');
  assert(Math.abs(end.bodyWidth-768*.78)<.001||Math.abs(end.bodyHeight-768*.76)<.001,'body fills 78% width or 76% height');
  const start=F.displayTransform(plan,768,768,0);
  assert(plan.raw.every(p=>p[0]*start.scale+start.x>=0&&p[0]*start.scale+start.x<=768&&p[1]*start.scale+start.y>=0&&p[1]*start.scale+start.y<=768),'complete input route visible before inflation');
  let previous=null,previousFit=null;
  for(let i=0;i<=1000;i++){
    const p=F.pose(plan,i/1000),fit=F.displayTransform(plan,768,768,p.fold);frames++;
    if(previous){
      const jump=Math.max(...p.contour.map((v,j)=>Math.hypot(v[0]-previous.contour[j][0],v[1]-previous.contour[j][1])));
      assert(jump<.025,`${name}: real contour correspondence continuous`);
      assert(Math.abs(fit.scale-previousFit.scale)<20&&Math.abs(fit.x-previousFit.x)<20&&Math.abs(fit.y-previousFit.y)<20,`${name}: display fit continuous`);
    }
    previous=p;previousFit=fit;
  }
}
const proof={status:'PASS_FORMATION_GEOMETRY',frames,realFixtures,effectStyles:F.effectStyles,effectSamples:603,checks:['real-area-growth','zero-whole-png-before-handoff','exact-final-contour','fixed-face-center','source-arc-index-correspondence','continuous-body-fit','initial-full-route','arc-length-trace','source-immutability','bounded-metadata','old-and-api-fallback','measured-local-ai-provenance','unknown-ai-face-patch-omitted','route-ink-clears-before-grown-body','bounded-celebration-particles','celebration-clear-before-rest','no-entry-flash'],sourceSha256:crypto.createHash('sha256').update(fs.readFileSync(new URL('./formation.js',import.meta.url))).digest('hex')};
const out=path.resolve(process.argv.find(x=>x.startsWith('--out='))?.slice(6)||path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../../.local/avatar-quality-v4/motion-qa'));fs.mkdirSync(out,{recursive:true});fs.writeFileSync(path.join(out,'geometry-verification.json'),JSON.stringify(proof,null,2)+'\n');
console.log(JSON.stringify(proof));
