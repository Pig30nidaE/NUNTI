#!/usr/bin/env node
// Audit real Pleos form submissions. Capture wardrobe requests at the WebView
// boundary before they reach the image provider.
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import {adb, connectWebView, root, save, sha, vehicleSession} from './nunti_integration_runtime_lib.mjs';

const cases=JSON.parse(await fs.readFile(new URL('nunti_skin_scenarios.json',import.meta.url),'utf8'));
const out=path.resolve(process.argv[2]||'.local/skin-scenario-audit-'+Date.now());
const appAssets=path.join(root,'prototypes/avatar_generator');
const origin='http://127.0.0.1:8768';
const route={points:[[.12,.8],[.25,.52],[.66,.62],[.88,.22]],inputOrigin:'ROUTE_FILE',sourceLabel:'QA 합성 경로'};
const skinForScenery={coast:'sea',city:'city',mountain:'mountain',unknown:'default'};
const requestBodies=[],blocked=[],failures=[],rows=[];
const report={surface:'Pleos Android WebView',caseCount:cases.length,rows,failures};
let web,vehicle,storage;

async function enter(scenario){
  if(await web.evaluate("!$('result-view').hidden"))await web.click('#new-button');
  await web.wait("!$('input-view').hidden && !state.busy");
  await web.evaluate(`(() => {
    const values=${JSON.stringify(scenario)};
    for(const [id,value] of [['destination',values.destination],['purpose',values.purpose],['traits',values.traits],
      ['layer-destination',values.scenery],['layer-road',values.road],['layer-mood',values.mood]]){
      const node=$(id);
      node.value=value;
      node.dispatchEvent(new Event('input',{bubbles:true}));
      node.dispatchEvent(new Event('change',{bubbles:true}));
    }
    $('wardrobe-enabled').checked=false;
    setRoute(${JSON.stringify(scenario.route?route:null)},null,${scenario.route});
  })()`);
}

async function bundledResult(scenario){
  const expected=skinForScenery[scenario.scenery];
  await web.click('#create-button');
  const record=await web.wait(`(() => {
    const item=state.artifact, d=window.NuntiSkinMotion.diagnostics();
    if($('result-view').hidden||state.busy||d.running||d.phase!=='FINAL_IDLE'||d.reason!=='REDUCED'||
      item?.destination.name!==${JSON.stringify(scenario.destination)}||item?.purpose!==${JSON.stringify(scenario.purpose)})return null;
    return item;
  })()`);
  const spec=record.design.skinSpec;
  assert.equal(spec.skinId,expected);
  assert.equal(spec.mood,scenario.mood);
  assert.equal(spec.road,scenario.road);
  assert.equal(!!record.route,scenario.route);
  const pixel=await web.evaluate(`(async () => {
    const live=$('birth-canvas'), asset=await window.NuntiSkinRenderer.image(${JSON.stringify(spec.skinId)},'final',${JSON.stringify(spec.version)});
    const expected=document.createElement('canvas');
    expected.width=live.width;expected.height=live.height;
    const side=Math.min(live.width,live.height), x=(live.width-side)/2, y=(live.height-side)/2;
    const ctx=expected.getContext('2d');
    ctx.setTransform(side/768,0,0,side/768,x,y);
    ctx.drawImage(asset,0,0,768,768);
    const thumb=document.createElement('canvas');thumb.width=thumb.height=240;
    thumb.getContext('2d').drawImage(live,x,y,side,side,0,0,240,240);
    return {matches:live.toDataURL()===expected.toDataURL(),png:thumb.toDataURL(),width:live.width,height:live.height};
  })()`);
  assert(pixel.matches,'Rendered pixels diverged from the bundled final asset');
  const thumb=Buffer.from(pixel.png.split(',')[1],'base64');
  await save(out,scenario.id+'.png',thumb);
  const visual=record.visual.path;
  return {id:scenario.id,destination:scenario.destination,purpose:scenario.purpose,criterion:scenario.criterion,
    skin:spec.skinId,version:spec.version,visual,assetSha256:sha(await fs.readFile(path.join(appAssets,visual.slice(1)))),
    canvasSha256:sha(thumb),canvas:[pixel.width,pixel.height],expectedBundle:expected,
    visualFit:scenario.acceptable.includes(spec.skinId),characterId:record.characterId};
}

async function captureWardrobe(scenario){
  await web.click('#new-button');
  await web.wait("!$('input-view').hidden");
  const before=requestBodies.length;
  await web.evaluate("$('wardrobe-enabled').checked=true");
  await web.click('#create-button');
  await web.wait("!state.busy && !$('notice').hidden && $('notice').textContent.includes('새 옷을 완성하지 못했어요')");
  assert.equal(requestBodies.length,before+1,'Expected a single intercepted wardrobe request');
  const payload=requestBodies[before];
  assert.deepEqual(payload.destination,{name:scenario.destination,traits:scenario.traits});
  assert.equal(payload.purpose,scenario.purpose);
  assert.equal(payload.scenery,scenario.scenery);
  assert.equal(payload.road,scenario.road);
  assert.equal(payload.mood,scenario.mood);
  assert.deepEqual(payload.route,scenario.route?{...route,confirmed:true}:null);
  return payload;
}

try{
  assert.equal(cases.length,30);
  assert.equal(new Set(cases.map(scenario=>scenario.id)).size,30);
  vehicle=await vehicleSession(out);
  await vehicle.parked();
  web=await connectWebView();
  await web.wait("state.nativeAllowed && NuntiSkins.MOCK_SKIN_MODE && window.nuntiCapabilities?.wardrobeAvailable");
  storage=await web.evaluate(`Object.fromEntries([NuntiSkins.storageKey,'nunti.skin-v2.reduced'].map(key=>[key,localStorage.getItem(key)]))`);
  report.beforeBudget=await web.evaluate("api('/v3/wardrobe/budget')");
  report.window=await web.evaluate("({width:innerWidth,height:innerHeight,dpr:devicePixelRatio})");
  await web.evaluate("window.NuntiSkinMotion.setReduced(true)");
  web.on('Fetch.requestPaused',event=>{
    const {requestId,request}=event;
    const url=new URL(request.url);
    if(url.origin===origin&&url.pathname==='/v3/wardrobe'&&request.method==='POST'){
      requestBodies.push(JSON.parse(request.postData));
      const body=Buffer.from(JSON.stringify({error:{code:'QA_CAPTURE_ONLY'}})).toString('base64');
      return web.command('Fetch.fulfillRequest',{requestId,responseCode:503,
        responseHeaders:[{name:'Content-Type',value:'application/json'}],body}).catch(error=>failures.push(String(error)));
    }
    if(url.origin===origin&&request.method==='GET')
      return web.command('Fetch.continueRequest',{requestId}).catch(error=>failures.push(String(error)));
    blocked.push({origin:url.origin,path:url.pathname,method:request.method});
    return web.command('Fetch.failRequest',{requestId,errorReason:'BlockedByClient'}).catch(error=>failures.push(String(error)));
  });
  await web.command('Fetch.enable',{patterns:[{urlPattern:'*',requestStage:'Request'}]});
  for(const scenario of cases){
    await enter(scenario);
    const result=await bundledResult(scenario);
    if(['02-ferry','07-hike','18-interview','19-patient','20-clinician','24-pottery','28-no-context'].includes(scenario.id))
      await save(out,scenario.id+'-device.png',await adb(['exec-out','screencap','-p'],true));
    result.wardrobeRequest=await captureWardrobe(scenario);
    rows.push(result);
    await save(out,'pleos-results.json',report);
    console.log(scenario.id,result.skin,result.visualFit?'FIT':'GAP');
  }
  report.afterBudget=await web.evaluate("api('/v3/wardrobe/budget')");
  assert.deepEqual(report.afterBudget,report.beforeBudget);
  assert.deepEqual(blocked,[]);
  assert.deepEqual(failures,[]);
  report.summary={rendered:rows.length,fit:rows.filter(row=>row.visualFit).length,
    gaps:rows.filter(row=>!row.visualFit).length,distinctAssets:new Set(rows.map(row=>row.assetSha256)).size,
    interceptedWardrobeRequests:requestBodies.length,providerReservations:report.afterBudget.calls-report.beforeBudget.calls};
}catch(error){
  failures.push(String(error));
  throw error;
}finally{
  try{
    if(web){
      await web.command('Fetch.disable').catch(()=>{});
      if(storage)await web.evaluate(`for(const [key,value] of Object.entries(${JSON.stringify(storage)})){
        if(value===null)localStorage.removeItem(key);else localStorage.setItem(key,value);
      }`);
      await web.command('Page.reload',{ignoreCache:true}).catch(()=>{});
    }
  }finally{
    web?.close();
    await save(out,'pleos-results.json',report);
    if(vehicle)await vehicle.restore();
  }
}
