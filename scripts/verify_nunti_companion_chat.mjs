#!/usr/bin/env node
import assert from 'node:assert/strict';
import path from 'node:path';
import {adb, capture, connectWebView, packageName, pause, save, vehicleSession} from './nunti_integration_runtime_lib.mjs';

const out=path.resolve(process.argv[2]||'.local/companion-chat-'+Date.now());
const checks=[];
let web,vehicle,task,bounds,savedRoute,savedSkins;
const routeId='f'.repeat(64);
const route={origin:{name:'출발지',latitude:37.4,longitude:127.1},
  destination:{name:'버드나무 공방',latitude:37.5,longitude:127.2},
  planId:routeId,geometry:{distanceMeters:15600,durationSeconds:1200,coordinates:[[127.1,37.4],[127.2,37.5]]},
  route:{inputOrigin:'API_ROUTE',sourceLabel:'fixture',apiPlanId:routeId,points:[[.12,.78],[.35,.56],[.85,.23]]}};
const value=(id,text)=>web.evaluate(`$(${JSON.stringify(id)}).value=${JSON.stringify(text)}; $(${JSON.stringify(id)}).dispatchEvent(new Event('input',{bubbles:true})); true`);
const fit=()=>web.evaluate(`(() => {
  const r=$('chat-form').getBoundingClientRect(), log=$('chat-log').getBoundingClientRect(), v=visualViewport;
  return {viewport:v.height,top:r.top,bottom:r.bottom,right:r.right,logBottom:log.bottom,
    fits:r.height>0&&r.bottom<=v.offsetTop+v.height+1&&r.right<=v.offsetLeft+v.width+1&&log.bottom<=r.top};
})()`);
const mark=(name,detail=true)=>{checks.push({name,detail});console.log(name);};
const contrast=()=>web.evaluate(`(() => {
  function luminance(color) {
    const rgb=color.match(/\\d+/g).slice(0,3).map(Number);
    return rgb.reduce((sum,channel,index)=>{
      const v=channel/255;
      return sum+[.2126,.7152,.0722][index]*(v<=.04045?v/12.92:((v+.055)/1.055)**2.4);
    },0);
  }
  const styles=['chat-title','chat-privacy'].map(id=>getComputedStyle($(id)));
  const bg=luminance(getComputedStyle($('chat-view')).backgroundColor);
  return styles.map(style=>{
    const fg=luminance(style.color);
    return (Math.max(fg,bg)+.05)/(Math.min(fg,bg)+.05);
  });
})()`);

try {
  vehicle=await vehicleSession(out);
  await vehicle.parked();
  web=await connectWebView();
  await web.wait('state.nativeAllowed && !!window.NuntiChat && window.nuntiCapabilities?.conversationAvailable');
  savedRoute=await web.evaluate("localStorage.getItem('nunti.lastRoutePlan')");
  savedSkins=await web.evaluate("localStorage.getItem(NuntiSkins.storageKey)");
  assert(await web.evaluate("!$('destination').value && !$('wardrobe-enabled').checked && !$('nav-case').value"));
  mark('empty form and wardrobe opt-in');
  const activities=await adb(['shell','dumpsys','activity','activities']);
  task=activities.match(/topResumedActivity=ActivityRecord\{[^\n]*ai\.nunti\.avatar\.demo\/[^\n]* t(\d+)\}/)?.[1];
  const start=activities.indexOf('ai.nunti.app.studio.AvatarStudioActivity');
  bounds=activities.slice(start).match(/mOverrideConfig=.*?mAppBounds=Rect\((\d+), (\d+) - (\d+), (\d+)\)/)?.slice(1).map(Number);
  assert(task&&bounds,'Cannot locate Studio window');

  await web.wait("$('canonical-portrait').hasAttribute('data-nunti-companion-ready')");
  await web.click('#chat-open');
  assert(await web.evaluate("!$('chat-view').hidden && !$('canonical-portrait').hasAttribute('data-nunti-companion-ready')"));
  assert(await web.evaluate("document.activeElement.id==='chat-title' && $('chat-input').labels.length===1 && getComputedStyle($('input-view')).display==='none'"));
  assert((await fit()).fits);
  await capture(out,'01-wide',{xml:false});

  const point=await web.evaluate(`(() => {
    const r=$('chat-input').getBoundingClientRect(), v=visualViewport, scale=devicePixelRatio*v.scale;
    return [(r.left+r.width/2-v.offsetLeft)*scale,(r.top+r.height/2-v.offsetTop)*scale];
  })()`);
  const before=await fit();
  await adb(['shell','input','tap',Math.round(bounds[0]+point[0]),Math.round(bounds[1]+point[1])]);
  await web.wait("document.activeElement === $('chat-input')");
  await web.wait(`visualViewport.height<${before.viewport-50}`);
  const keyboard=await fit();
  assert(keyboard.fits,JSON.stringify(keyboard));
  await capture(out,'02-keyboard',{xml:false});
  mark('native IME keeps composer visible and separate from avatar',keyboard);
  await adb(['shell','input','keyevent','4']);
  await web.wait(`visualViewport.height>=${before.viewport-5}`);
  assert(await web.evaluate("!$('chat-view').hidden"));

  const stage=`(() => {
    const original=window.NuntiChat.speechAmplitude;
    window.nuntiTestAmplitudeCount=0;
    window.NuntiChat.speechAmplitude=(id,value)=>{window.nuntiTestAmplitudeCount++;original(id,value);};
  })()`;
  await web.evaluate(stage);
  let failChat=true;
  web.on('Fetch.requestPaused',async ({requestId,request})=>{
    if(!new URL(request.url).pathname.endsWith('/conversation'))return;
    if(!failChat){await web.command('Fetch.continueRequest',{requestId});return;}
    const body=Buffer.from(JSON.stringify({error:{code:'CONVERSATION_UNAVAILABLE'}})).toString('base64');
    await web.command('Fetch.fulfillRequest',{requestId,responseCode:503,responseHeaders:[{name:'Content-Type',value:'application/json'}],body});
  });
  await web.command('Fetch.enable',{patterns:[{urlPattern:'*/v3/conversation'}]});
  await web.click('#chat-voice');
  await value('chat-input','안녕 눈티');
  await web.click('#chat-send');
  await web.wait("!$('chat-retry').hidden && $('chat-log').children.length===1");
  failChat=false;
  await web.click('#chat-retry');
  await web.wait("!!document.querySelector('.chat-avatar[data-speaking=true]')");
  await web.wait("!document.querySelector('.chat-avatar[data-speaking=true]')");
  assert(await web.evaluate("$('chat-status').hidden"));
  assert((await adb(['logcat','-d','-s','NuntiStudio:I'])).includes('STUDIO_CONVERSATION_SPEECH_STARTED'));
  await web.command('Fetch.disable');
  mark('cloud failure keeps retry available without duplicating a message');
  mark('Pleos speech starts and ends the avatar mouth motion',{
    amplitudeSamples:await web.evaluate("window.nuntiTestAmplitudeCount"),
  });

  await adb(['shell','am','task','resize',task,bounds[0],bounds[1],bounds[0]+830,bounds[3]]);
  await web.wait('innerWidth<900');
  const compact=await fit();
  assert(compact.fits,JSON.stringify(compact));
  await capture(out,'03-split',{xml:false});
  mark('830px split window keeps conversation and composer in bounds',compact);
  const day=await contrast();
  const theme=await web.evaluate("window.NuntiAppearance.config.theme");
  await web.evaluate("window.NuntiAppearance.apply({theme:'night'},false)");
  const night=await contrast();
  assert([...day,...night].every(ratio=>ratio>=4.5));
  await capture(out,'03-split-night',{xml:false});
  await web.evaluate(`window.NuntiAppearance.apply({theme:${JSON.stringify(theme)}},false)`);
  mark('day and night conversation title and disclosure meet 4.5:1 contrast',{day,night});
  await web.click('#chat-close');
  await web.click('#route-tools-open');
  await web.evaluate("window.NuntiNavigation.setCapabilities({...window.nuntiCapabilities,routeApiAvailable:true}); document.querySelector('.api-coordinates').open=true");
  await value('route-destination-input',route.destination.name);
  for(const [id,number] of [['nav-origin-lat',37.4],['nav-origin-lon',127.1],['nav-destination-lat',37.5],['nav-destination-lon',127.2]])await value(id,String(number));
  let fail=true,requests=0;
  web.on('Fetch.requestPaused',async ({requestId})=>{
    requests++;
    const responseCode=fail?503:200;
    const body=fail?{error:{message:'경로에 연결하지 못했어요.'}}:{data:route};
    await web.command('Fetch.fulfillRequest',{requestId,responseCode,responseHeaders:[{name:'Content-Type',value:'application/json'}],body:Buffer.from(JSON.stringify(body)).toString('base64')});
  });
  await web.command('Fetch.enable',{patterns:[{urlPattern:'*/v3/route-plans*'}]});
  await web.click('#nav-calculate');
  await web.wait("!state.planning && $('route-tool-feedback').textContent.includes('연결하지 못했어요')");
  assert(await web.evaluate("$('notice').hidden && $('route-tools-dialog').open"));
  fail=false;
  await web.click('#nav-calculate');
  await web.wait("state.route?.inputOrigin==='API_ROUTE' && !state.planning");
  assert(await web.evaluate("!$('route-tools-dialog').open && $('route-feedback').hidden && $('route-tool-feedback').hidden && $('notice').hidden"));
  await web.click("label[for='route-confirmed']");
  assert(await web.evaluate("!$('create-button').disabled"));
  await web.click('#route-tools-open');
  await web.click('#nav-replay');
  await web.wait("!state.planning && !$('route-tools-dialog').open && $('route-feedback').hidden");
  assert.equal(requests,3);
  mark('route failure, successful retry and replay clear scoped feedback',requests);
  await web.click("label[for='route-confirmed']");
  await web.click('#chat-open');
  await web.click('#chat-voice');
  await value('chat-input','이 길은 얼마나 걸려?');
  await web.click('#chat-send');
  await web.wait("!!$('chat-log').lastElementChild?.querySelector('.chat-avatar') && !document.querySelector('#chat-feedback:not([hidden])')");
  const routeReply=await web.evaluate("$('chat-log').lastElementChild.textContent");
  assert.match(routeReply,/20\s*분/);
  mark('cloud route reply uses the selected trip',routeReply);

  await value('chat-input','내가 만든 도자기에 달빛무늬를 넣고 싶어. 조용한 이름 하나 붙여 줄래?');
  await web.click('#chat-send');
  await web.wait("!!$('chat-log').lastElementChild?.querySelector('.chat-avatar') && !document.querySelector('#chat-feedback:not([hidden])')");
  const creativeReply=await web.evaluate("$('chat-log').lastElementChild.textContent");
  assert.match(creativeReply,/달|빛|밤|도자/);
  assert.notEqual(creativeReply,routeReply);
  mark('cloud reply addresses an unseen free-text request',creativeReply);

  await value('chat-input','방금 만든 이름을 넣어 소개 문장 하나로 바꿔 줄래?');
  await web.click('#chat-send');
  await web.wait("!!$('chat-log').lastElementChild?.querySelector('.chat-avatar') && !document.querySelector('#chat-feedback:not([hidden])')");
  const followupReply=await web.evaluate("$('chat-log').lastElementChild.textContent");
  assert.match(followupReply,/달|빛|밤|도자/);
  assert.notEqual(followupReply,creativeReply);
  mark('cloud reply follows the prior message',followupReply);

  const reduced=await web.evaluate(`(() => {
    const root=document.documentElement;
    const original=root.dataset.systemReducedMotion;
    root.dataset.systemReducedMotion='true';
    const image=$('chat-log').lastElementChild.querySelector('.chat-avatar img');
    const result=getComputedStyle(image).animationName;
    root.dataset.systemReducedMotion=original;
    return result;
  })()`);
  assert.equal(reduced,'none');
  mark('reduced motion suppresses the companion gesture');

  await vehicle.drive(30);
  await web.wait("!state.nativeAllowed && $('chat-view').hidden && !document.querySelector('[data-speaking=true]')");
  await capture(out,'04-restricted',{xml:false});
  await vehicle.parked();
  await web.wait("state.nativeAllowed && $('chat-view').hidden");
  mark('platform restriction closes conversation without auto reopening');
  await adb(['shell','am','task','resize',task,...bounds]);
  await web.wait('innerWidth>1400');
  await value('layer-destination','city');
  await value('purpose','도자기 전시를 둘러보고 작은 접시를 만들러');
  await web.click('#create-button');
  await web.wait("state.artifact?.design?.skinSpec?.skinId==='city' && $('result-portrait').hasAttribute('data-nunti-companion-ready')");
  await adb(['shell','dumpsys','gfxinfo',packageName,'reset']);
  await web.click('#result-portrait');
  await pause(950);
  const characterLog=await adb(['logcat','-d','-s','NuntiCharacter:I']);
  assert(characterLog.includes('CANVAS_REACTION skin=city reaction=wink'));
  await capture(out,'05-skin-gesture',{xml:false});
  const activeGraphics=await adb(['shell','dumpsys','gfxinfo',packageName]);
  const activeFrames=Number(activeGraphics.match(/Total frames rendered: (\d+)/)?.[1]);
  assert(activeFrames>0);
  await save(out,'active-gesture-gfxinfo.txt',activeGraphics);
  mark('rendered frames sampled while a skin gesture was active',activeFrames);
  assert(await web.evaluate("!state.busy && !state.planning"));
  await web.click('#chat-open');
  await web.wait("!$('chat-view').hidden && $('chat-log').querySelector('.chat-avatar img')?.src.endsWith('/skin-v2/atelier/city/final.png')");
  await capture(out,'06-selected-skin-chat',{xml:false});
  mark('free-form trip selects a bundled skin that reacts and carries into chat');
  await adb(['shell','dumpsys','gfxinfo',packageName,'reset']);
  await pause(2500);
  await save(out,'gfxinfo.txt',await adb(['shell','dumpsys','gfxinfo',packageName]));
  await save(out,'memory.txt',await adb(['shell','dumpsys','meminfo',packageName]));
  await save(out,'cpu.txt',await adb(['shell','top','-b','-n','2','-d','1','-p',web.pid]));
  await save(out,'verification.json',{checks});
} finally {
  if(web){
    await web.command('Fetch.disable').catch(()=>{});
    if(savedRoute!==undefined)await web.evaluate(`window.NuntiChat?.close(false);
      for(const [key,value] of Object.entries(${JSON.stringify({'nunti.lastRoutePlan':savedRoute,'nunti.skin-v2.records':savedSkins})}))
        value===null?localStorage.removeItem(key):localStorage.setItem(key,value);`).catch(()=>{});
    await web.command('Page.reload',{ignoreCache:true}).catch(()=>{});
    web.close();
  }
  if(task&&bounds)await adb(['shell','am','task','resize',task,...bounds]);
  if(vehicle)await vehicle.restore();
}
