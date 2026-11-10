'use strict';
(() => {
  const {path,phaseAt,version}=window.NuntiSkins;
  const size=768, layers=['outfit','head','eyes','accessory'];
  const cameraPivotY=size*-.12;
  const light={
    sea:{glow:'#64DFF5',ink:'#1685A2',core:'#EAFFFF'},
    city:{glow:'#D395FF',ink:'#7848B8',core:'#FFF0FF'},
    mountain:{glow:'#EABC6E',ink:'#678047',core:'#FFF4C9'}
  };
  // Static regions lock to individual costume parts, with the face kept visible.
  const headLine=[[0,395],[230,395],[287,408],[481,408],[538,395],[768,395]];
  const wardrobeRegions=[
    {at:2700,clip:[[0,0],[768,0],...headLine.slice().reverse()]},
    {at:3250,clip:[...headLine,[768,768],[0,768]]}
  ];
  const assets=new Map();
  function image(id,layer='final',assetVersion=version) {
    const url=path(id,layer,assetVersion);
    if(!assets.has(url)){
      const load=(async()=>{const img=new Image();img.src=url;await img.decode();
        if(img.naturalWidth!==size||img.naturalHeight!==size)throw new Error('INVALID_SKIN_ASSET');
        return img;
      })();
      assets.set(url,load);load.catch(()=>assets.delete(url));
    }
    return assets.get(url);
  }
  const ease=(t,a,b)=>{const x=Math.min(1,Math.max(0,(t-a)/(b-a)));return x*x*(3-2*x);};
  const mix=(a,b,t)=>a+(b-a)*t;
  function create({canvas,allowed,visible,onFrame}) {
    const ctx=canvas.getContext('2d');
    let token=0,raf=0,spec=null,final=null,base=null,wardrobe=null,direction=0,start=0,last=-Infinity;
    let running=false,phase='FINAL_IDLE',elapsedMs=0,reason='IDLE',visited=[],systemReduced=false,userReduced=false;
    let nativeRequest=null,nativePlaying=false;
    const media=matchMedia('(prefers-reduced-motion: reduce)');
    try{userReduced=localStorage.getItem('nunti.skin-v2.reduced')==='true';}catch{}
    const reduced=()=>systemReduced||userReduced||media.matches;
    function diagnostics(){return {phase,elapsedMs,reason,skinId:spec?.skinId??null,visited:[...visited],running,reducedMotion:reduced(),systemReducedMotion:systemReduced,active:!!spec,renderer:nativePlaying?'NATIVE_CANVAS':'CANVAS'};}
    const emit=()=>onFrame(diagnostics());
    function mark(next) {
      phase=next;
      if(visited.at(-1)!==next)visited.push(next);
    }
    function beginDraw(){
      const rect=canvas.getBoundingClientRect();
      const scale=Math.min((window.devicePixelRatio||1)*(window.visualViewport?.scale||1),2);
      const w=Math.max(1,Math.min(1024,Math.round(rect.width*scale))),h=Math.max(1,Math.min(1024,Math.round(rect.height*scale)));
      if(canvas.width!==w)canvas.width=w;if(canvas.height!==h)canvas.height=h;
      ctx.setTransform(1,0,0,1,0,0);ctx.clearRect(0,0,w,h);
      const fit=Math.min(w,h)/size;
      ctx.setTransform(fit,0,0,fit,(w-size*fit)/2,(h-size*fit)/2);
    }
    function paint(img){if(img)ctx.drawImage(img,0,0,size,size);}
    function routeDirection(route) {
      const points=route?.points;
      const bend=(points?.at(-1)?.[1]??.5)-(points?.[0]?.[1]??.5);
      const intent=spec.animationPreset.sweep==='uphill'?-.28:spec.animationPreset.sweep==='diagonal'?.28:0;
      return Number.isFinite(bend)?Math.max(-1,Math.min(1,bend+intent)):intent;
    }
    function glow(x,y,radius,color,alpha) {
      if(alpha<=0)return;
      const halo=ctx.createRadialGradient(x,y,0,x,y,radius);
      halo.addColorStop(0,color);halo.addColorStop(1,color+'00');
      ctx.globalAlpha=alpha;ctx.fillStyle=halo;ctx.fillRect(x-radius,y-radius,2*radius,2*radius);
    }
    function costume(t) {
      if(t<2620||!wardrobe){paint(base);return;}
      if(t>=3340){paint(wardrobe);return;}
      for(const region of wardrobeRegions){
        const progress=ease(t,region.at-80,region.at+90);
        ctx.save();ctx.beginPath();
        region.clip.forEach(([x,y],index)=>{if(index===0)ctx.moveTo(x,y);else ctx.lineTo(x,y);});
        ctx.closePath();ctx.clip();
        if(progress<1)paint(base);
        if(progress>0){ctx.globalAlpha=progress;paint(wardrobe);}
        ctx.restore();
      }
    }
    function draw(t){
      if(nativePlaying)return;
      beginDraw();
      if(t>=4000){paint(final||base);return;}
      if(t===0){paint(base);return;}
      const color=light[spec.skinId];
      const charge=ease(t,650,3100)*(1-ease(t,3290,3540));
      const impact=ease(t,3275,3340)*(1-ease(t,3340,3630));
      const attention=.008*Math.sin(Math.PI*ease(t,30,600));
      const headTurn=.021*Math.sin(Math.PI*ease(t,70,550))*(direction<0?-1:1);
      const bounce=Math.sin(Math.PI*ease(t,3380,3860));
      const scale=1+attention+impact*.055;
      ctx.save();
      glow(384,418,mix(310,205,charge),color.ink,.28*charge);
      glow(384,405,300,color.glow,.44*charge+.29*impact);
      ctx.restore();
      ctx.save();ctx.translate(384,cameraPivotY);ctx.rotate(headTurn);ctx.scale(scale,scale);
      ctx.translate(-384,-cameraPivotY-23*bounce);
      if(t>=3340&&charge>.15){
        ctx.save();ctx.shadowColor=color.glow;ctx.shadowBlur=18+30*charge;
        ctx.globalAlpha=.58*charge;paint(wardrobe);ctx.restore();
      }
      const trail=ease(t,3280,3350)*(1-ease(t,3430,3630));
      if(trail>0){
        ctx.save();ctx.translate(14*trail,-9*trail);ctx.globalAlpha=.25*trail;paint(wardrobe);ctx.restore();
      }
      costume(t);ctx.restore();
    }
    function releaseNative() {
      const request=nativeRequest;
      nativeRequest=null;nativePlaying=false;
      if(!request)return;
      request.resolve(false);
      window.NuntiNative?.stopCharacterMotion?.(request.id);
    }
    function startNative(id) {
      const bridge=window.NuntiNative;
      if(spec.version!==version||!bridge?.startCharacterMotion||!bridge.stopCharacterMotion)return Promise.resolve(false);
      const rect=canvas.getBoundingClientRect(),viewport=window.visualViewport;
      const scale=(window.devicePixelRatio||1)*(viewport?.scale||1);
      const left=(rect.left-(viewport?.offsetLeft||0))*scale,top=(rect.top-(viewport?.offsetTop||0))*scale;
      const width=rect.width*scale,height=rect.height*scale;
      if(![left,top,width,height].every(Number.isFinite)||width<=0||height<=0)return Promise.resolve(false);
      return new Promise(resolve=>{
        const timer=setTimeout(()=>{if(nativeRequest?.id===id)releaseNative();},12000);
        nativeRequest={id,resolve:ready=>{clearTimeout(timer);resolve(ready);}};
        try{bridge.startCharacterMotion(id,spec.skinId,left,top,width,height,direction);}
        catch{releaseNative();}
      });
    }
    window.nuntiCharacterMotionReady=(id,ready)=>{
      if(nativeRequest?.id!==id)return;
      if(ready===true)nativeRequest.resolve(true);
      else releaseNative();
    };
    window.nuntiCharacterMotionFinished=id=>{
      if(nativeRequest?.id!==id||!nativePlaying||!running)return;
      // Ask the parked portrait to adopt the finished actor before its old
      // transformation request is released. The native stage checks both owners.
      window.NuntiCompanionPlayer?.setResult(spec.skinId);
      stop('COMPLETE');
    };
    function redraw() {
      releaseNative();
      if(spec)draw(elapsedMs);
    }
    const reflow=()=>{if(nativeRequest)redraw();};
    window.addEventListener?.('scroll',reflow,true);
    window.visualViewport?.addEventListener?.('scroll',reflow);
    function halt(){++token;cancelAnimationFrame(raf);raf=0;running=false;releaseNative();}
    function stop(why){
      if(!spec)return;
      halt();elapsedMs=4000;reason=why;mark('FINAL_IDLE');draw(4000);emit();
    }
    function clear(){halt();spec=null;wardrobe=null;final=null;direction=0;visited=[];reason='IDLE';elapsedMs=0;phase='FINAL_IDLE';}
    function frame(now){
      if(!running)return;
      if(!allowed()||!visible()||reduced()){stop(!allowed()?'RESTRICTED':!visible()?'BACKGROUNDED':'REDUCED');return;}
      const time=Math.max(0,now-start);
      if((!nativePlaying&&time>=4000)||time>=5500){stop('COMPLETE');return;}
      // Only the native stage completion ends native playback. The cap is a fail-safe for a lost event.
      const elapsed=Math.min(time,3999);
      const next=phaseAt(elapsed);
      if(elapsed-last>=32||next!==phase){
        last=elapsed;elapsedMs=elapsed;mark(next);draw(elapsed);emit();
      }
      raf=requestAnimationFrame(frame);
    }
    async function show(skinSpec,finalImage,route,animate) {
      halt();const epoch=token;spec=skinSpec;final=finalImage;visited=[];wardrobe=null;direction=0;
      reason='LOADING';elapsedMs=0;mark('DEFAULT_IDLE');
      if(!animate||spec.skinId==='default'||!allowed()||!visible()||reduced()){
        stop(reduced()?'REDUCED':!allowed()?'RESTRICTED':!visible()?'BACKGROUNDED':'STATIC');return;
      }
      try{
        direction=routeDirection(route);
        base=await image('default');
        if(epoch!==token)return;
        draw(0);emit();
        const target=await Promise.all(layers.map(layer=>image(spec.skinId,layer,spec.version)));
        if(epoch!==token)return;
        // Compose at native size so the shared layer edges are resampled only once.
        wardrobe=document.createElement('canvas');
        wardrobe.width=size;wardrobe.height=size;
        const wardrobeContext=wardrobe.getContext('2d');
        for(const layer of target)wardrobeContext.drawImage(layer,0,0);
      }catch{if(epoch===token)stop('LAYER_ASSET_FAILURE');return;}
      if(!allowed()||!visible()||reduced()){stop(!allowed()?'RESTRICTED':!visible()?'BACKGROUNDED':'REDUCED');return;}
      const nativeReady=await startNative(epoch);
      if(epoch!==token)return;
      if(!allowed()||!visible()||reduced()){stop(!allowed()?'RESTRICTED':!visible()?'BACKGROUNDED':'REDUCED');return;}
      nativePlaying=nativeReady&&nativeRequest?.id===epoch;
      if(nativePlaying)beginDraw();
      start=performance.now();last=-Infinity;reason='PLAYING';running=true;emit();raf=requestAnimationFrame(frame);
    }
    function appearance(payload){systemReduced=!!payload.systemReducedMotion;if(spec&&reduced()&&(running||reason==='LOADING'))stop('REDUCED');else emit();}
    media.addEventListener?.('change',()=>appearance({systemReducedMotion:systemReduced}));
    return {show,stop,clear,diagnostics,appearance,redraw,
      setReduced:value=>{userReduced=!!value;try{localStorage.setItem('nunti.skin-v2.reduced',String(userReduced));}catch{}appearance({systemReducedMotion:systemReduced});}};
  }
  window.NuntiSkinRenderer=Object.freeze({create,image});
})();
