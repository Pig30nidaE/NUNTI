'use strict';
(() => {
  const view=$('chat-view'), log=$('chat-log'), input=$('chat-input');
  const voice=$('chat-voice'), openButton=$('chat-open'), status=$('chat-status');
  const send=$('chat-send'), retryButton=$('chat-retry');
  const base='/nunti-motion/base.png';
  const motion=matchMedia('(prefers-reduced-motion: reduce)');
  const gestures=['listen','wave','nod','bounce','tilt','smile'];
  let context, avatar, speech, draft='', sequence=0, pending=null, failed=null;
  const history=[];
  const pageId=crypto.randomUUID();

  function setStatus(text='',retry=false){
    status.textContent=text;
    status.hidden=!text;
    $('chat-feedback').hidden=!text;
    retryButton.hidden=!retry;
  }
  function currentContext(){
    const artifact=$('result-view').hidden?null:state.artifact;
    const destination=artifact?.destination.name||$('destination').value.trim();
    const purpose=(artifact?.purpose??$('purpose').value).trim();
    const route=artifact?.route||($('route-confirmed').checked?state.route:null);
    const skin=artifact?.design?.skinSpec?.skinId;
    const path=artifact?.visual?.path;
    const src=/^\/(?:skin-v2\/[a-z0-9/-]+\/final\.png|v3\/assets\/[a-f0-9]{64})$/.test(path||'')?path:base;
    const mouth=src===base?[.508,.43,.094,.070]
      :skinRecord(artifact)&&artifact.design.skinSpec.version===skins.version&&skin!=='default'?[skin==='sea'?.494:.512,.385,.10,.065]
      :null;
    return {key:JSON.stringify([artifact?.characterId,destination,purpose,route?.apiPlanId,route&&!artifact?state.routeVersion:null]),
      destination,purpose,route,src,mouth};
  }

  function actor(){
    const wrapper=document.createElement('span');
    wrapper.className='chat-avatar';
    wrapper.setAttribute('aria-hidden','true');
    const picture=new Image();
    const canvas=document.createElement('canvas');
    canvas.width=canvas.height=192;
    canvas.hidden=true;
    const ctx=canvas.getContext('2d');
    const side=canvas.width;
    const mouth=context.mouth?.map(value=>value*side);
    picture.alt='';
    picture.src=context.src;
    picture.onerror=()=>{if(picture.getAttribute('src')!==base)picture.src=base;};
    wrapper.append(picture,canvas);
    let frame=0, last=0, accent=0, peak=0, level=0, sampleTime=-Infinity, openness=1;
    const reduce=()=>motion.matches||document.documentElement.dataset.systemReducedMotion==='true'||
      !!window.NuntiSkinMotion?.diagnostics().reducedMotion;
    function draw(time){
      if(!wrapper.isConnected||view.hidden||document.hidden||!state.nativeAllowed||reduce()){stop();return;}
      frame=requestAnimationFrame(draw);
      if(!ctx||!mouth||!picture.complete||!picture.naturalWidth||time-last<32)return;
      last=time;
      const [cx,cy,w,h]=mouth;
      const x=cx-w/2,y=cy-h/2,strip=h*.24;
      const fallback=.47+.40*Math.abs(Math.sin((time-accent)/69))+.13*Math.abs(Math.sin((time-accent)/119));
      const target=time-sampleTime<180?.35+.65*Math.sqrt(level):fallback;
      openness+=(target-openness)*.65;
      const middle=(h-2*strip)*openness, padding=(h-middle)/2;
      const sx=picture.naturalWidth/side,sy=picture.naturalHeight/side;
      ctx.clearRect(0,0,side,side);
      ctx.drawImage(picture,0,0,side,side);
      ctx.drawImage(picture,x*sx,y*sy,w*sx,strip*sy,x,y,w,padding);
      ctx.drawImage(picture,x*sx,(y+strip)*sy,w*sx,(h-2*strip)*sy,x,y+padding,w,middle);
      ctx.drawImage(picture,x*sx,(y+h-strip)*sy,w*sx,strip*sy,x,y+padding+middle,w,padding);
      canvas.hidden=false;
      picture.hidden=true;
    }
    function stop(){
      cancelAnimationFrame(frame);frame=0;
      delete wrapper.dataset.speaking;
      canvas.hidden=true;picture.hidden=false;
    }
    return {wrapper,stop,gesture(name){if(!reduce())wrapper.dataset.gesture=name;},
      speak(){if(reduce())return;wrapper.dataset.speaking='true';accent=performance.now();if(mouth&&!frame)frame=requestAnimationFrame(draw);},
      syllable(){accent=performance.now();},
      amplitude(value){
        if(!frame||!Number.isFinite(value))return;
        const magnitude=Math.abs(value);
        peak=Math.max(peak*.985,magnitude);
        level=peak>0?Math.min(1,magnitude/peak):0;
        sampleTime=performance.now();
      }};
  }

  function append(text, fromNunti, gesture){
    const row=document.createElement('div');
    row.className=fromNunti?'chat-turn':'chat-turn chat-turn-user';
    if(fromNunti){
      avatar?.stop();
      avatar=actor();
      row.append(avatar.wrapper);
      avatar.gesture(gesture);
    }
    const bubble=document.createElement('p');
    bubble.className='chat-bubble';
    const speaker=document.createElement('span');
    speaker.className='visually-hidden';
    speaker.textContent=fromNunti?'눈티: ':'나: ';
    bubble.append(speaker,document.createTextNode(text));
    row.append(bubble);
    log.append(row);
    while(log.children.length>31)log.firstElementChild.remove();
    log.scrollTop=log.scrollHeight;
    return row;
  }
  function tripBrief(){
    const plan=window.NuntiNavigation?.getPlan();
    const geometry=plan&&context.route?.apiPlanId===plan.planId?plan.geometry:null;
    return {
      destination:context.destination,purpose:context.purpose,
      ...(Number.isFinite(geometry?.distanceMeters)?{routeKm:Math.round(geometry.distanceMeters/100)/10}:{}),
      ...(Number.isFinite(geometry?.durationSeconds)?{routeMinutes:Math.ceil(geometry.durationSeconds/60)}:{}),
    };
  }

  function updateSend(){send.disabled=!!pending||!input.value.trim();}
  function cancelPending(){
    const request=pending;
    pending=null;
    if(!request)return;
    clearTimeout(request.timeout);
    request.controller.abort();
    request.row.remove();
  }
  async function requestReply(message){
    if(!message||pending||view.hidden||!state.nativeAllowed||document.hidden)return;
    stopSpeech();
    failed=null;
    const controller=new AbortController();
    const row=append(message,false);
    const request={message,controller,row,timeout:setTimeout(()=>controller.abort(),16000)};
    pending=request;
    updateSend();
    avatar?.gesture('listen');
    setStatus('눈티가 답변을 준비하고 있어요…');
    try{
      const result=await api('/v3/conversation',{message,history:history.slice(-6),trip:tripBrief()},'POST',controller.signal);
      if(pending!==request||view.hidden||!state.nativeAllowed||document.hidden)return;
      if(typeof result?.reply!=='string'||!result.reply.trim()||result.reply.length>180||!gestures.includes(result.gesture))
        throw new Error('CONVERSATION_INVALID_RESPONSE');
      history.push({role:'user',content:message},{role:'assistant',content:result.reply});
      if(history.length>6)history.splice(0,history.length-6);
      setStatus();
      append(result.reply,true,result.gesture);
      say(result.reply);
    }catch(error){
      if(pending!==request||view.hidden||!state.nativeAllowed||document.hidden)return;
      row.remove();
      const retry=error.message!=='CONVERSATION_REFUSED';
      failed=retry?message:null;
      const feedback={
        CONVERSATION_NOT_CONFIGURED:'눈티 대화 연결이 준비되지 않았어요.',
        CONVERSATION_AUTH:'눈티 대화 연결 설정을 확인해 주세요.',
        CONVERSATION_RATE_LIMIT:'대화 요청이 많아요. 잠시 뒤 다시 보내 주세요.',
        CONVERSATION_REFUSED:'이 메시지에는 답변하기 어려워요. 다른 이야기를 들려주세요.',
      };
      setStatus(feedback[error.message]||'눈티의 답변을 받지 못했어요. 다시 보내 주세요.',retry);
    }finally{
      clearTimeout(request.timeout);
      if(pending===request){pending=null;updateSend();}
    }
  }

  function speechEnded(id,failed=false){
    if(!speech||speech.id!==id)return false;
    clearTimeout(speech.timeout);
    speech=null;
    avatar?.stop();
    if(failed)setStatus('음성을 재생할 수 없어요. 답변은 화면에서 읽을 수 있어요.');
    return true;
  }
  function stopSpeech(){
    if(!speech)return;
    speechEnded(speech.id);
    if(window.NuntiNative)window.NuntiNative.stopSpeaking();
    else window.speechSynthesis?.cancel();
  }
  function say(text){
    if(voice.getAttribute('aria-pressed')!=='true')return;
    stopSpeech();
    const id=`chat-${pageId}:${++sequence}`;
    speech={id,timeout:setTimeout(()=>{if(speech?.id===id){stopSpeech();setStatus('음성을 재생할 수 없어요.');}},20000)};
    const bridge=window.NuntiNative;
    if(bridge){
      if(bridge.speakConversation)bridge.speakConversation(text,id);
      else if(bridge.isSpeechAvailable())bridge.speak(text,1,1.08,id);
      else speechEnded(id,true);
      return;
    }
    const engine=window.speechSynthesis;
    const korean=engine?.getVoices().find(item=>item.lang.startsWith('ko')&&item.localService);
    if(!korean){speechEnded(id,true);return;}
    const utterance=new SpeechSynthesisUtterance(text);
    utterance.lang='ko-KR';utterance.voice=korean;utterance.pitch=1.08;
    utterance.onstart=()=>speechStarted(id);
    utterance.onboundary=()=>speechRange(id);
    utterance.onend=()=>speechEnded(id);
    utterance.onerror=()=>speechEnded(id,true);
    engine.speak(utterance);
  }
  function speechStarted(id){if(speech?.id===id)avatar?.speak();}
  function speechRange(id){if(speech?.id===id)avatar?.syllable();}
  function speechAmplitude(id,value){if(speech?.id===id)avatar?.amplitude(value);}

  function open(){
    if(!view.hidden||!state.nativeAllowed||state.busy||state.planning)return;
    const next=currentContext();
    const fresh=context?.key!==next.key;
    context=next;
    stopVoice();
    document.body.dataset.chatOpen='true';
    resize();
    window.NuntiCompanionPlayer?.sync();
    interruptSkin('SKIPPED');
    window.NuntiBirth?.stop('SKIPPED');
    view.hidden=false;
    $('chat-context').textContent=context.destination?`${context.destination} 가는 길`:'주차 중 대화';
    if(fresh){
      history.length=0;draft='';log.replaceChildren();
      append(context.destination?`안녕! ${context.destination} 가기 전에 무슨 이야기 할까?`:'안녕! 오늘 어떤 일이 있었어?','wave');
    }
    input.value=draft;
    updateSend();
    $('chat-title').focus({preventScroll:true});
  }
  function close(restoreFocus=true){
    if(view.hidden)return false;
    draft=input.value||pending?.message||failed||'';
    cancelPending();
    failed=null;
    stopSpeech();
    avatar?.stop();
    input.blur();
    view.hidden=true;
    delete document.body.dataset.chatOpen;
    setStatus();
    if(restoreFocus)openButton.focus({preventScroll:true});
    window.dispatchEvent(new Event('resize'));
    window.NuntiCompanionPlayer?.sync();
    return true;
  }
  openButton.onclick=open;
  $('chat-close').onclick=()=>close();
  voice.onclick=()=>{
    const on=voice.getAttribute('aria-pressed')!=='true';
    voice.setAttribute('aria-pressed',String(on));
    voice.textContent=on?'음성 답변 켜짐':'음성 답변';
    if(!on)stopSpeech();
    if(!pending&&!failed)setStatus();
  };
  input.addEventListener('input',updateSend);
  retryButton.onclick=()=>{if(failed)requestReply(failed);};
  $('chat-form').onsubmit=event=>{
    event.preventDefault();
    const text=input.value.trim();
    if(!text||pending||view.hidden||!state.nativeAllowed||document.hidden)return;
    input.value='';
    requestReply(text);
  };
  document.addEventListener('visibilitychange',()=>{if(document.hidden)close(false);});
  document.addEventListener('keydown',event=>{if(event.key==='Escape'&&close())event.preventDefault();});
  function resize(){
    if(document.body.dataset.chatOpen!=='true')return;
    const height=window.visualViewport?.height||window.innerHeight;
    document.body.style.setProperty('--chat-height',height+'px');
    document.body.classList.toggle('chat-short',height<640);
  }
  window.addEventListener('resize',resize);
  window.visualViewport?.addEventListener('resize',resize);
  window.NuntiChat={close,speechStarted,speechRange,speechAmplitude,speechEnded};
})();
