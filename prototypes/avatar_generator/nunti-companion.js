'use strict';
(() => {
  function create({preview, result, inputView, resultView, allowed, onUnavailable}) {
    const bridge=window.NuntiNative;
    if(!bridge?.startCharacterCompanion||!bridge.stopCharacterCompanion||!bridge.reactCharacterCompanion)return null;
    const skinReactions=['wink','happy','curious','proud','signature','surprised','nod','sleepy'];
    const fullyVisible=new Set();
    let nextId=0, current=null, resultSkin=null, failedKey=null, timer=0, focusTimer=0;

    function stop() {
      if(!current)return;
      const request=current;
      current=null;
      clearTimeout(focusTimer);
      delete request.portrait.dataset.nuntiCompanionReady;
      request.portrait.disabled=true;
      bridge.stopCharacterCompanion(request.id);
    }

    function candidate() {
      if(!allowed()||document.hidden||document.body.dataset.chatOpen==='true'||
        document.activeElement?.matches('input:not([type=checkbox]), textarea, [contenteditable=true]')||
        document.querySelector('dialog[open]'))return null;
      const portrait=!inputView.hidden?preview:!resultView.hidden&&resultSkin?result:null;
      if(!portrait||!fullyVisible.has(portrait))return null;
      const skin=portrait===preview?'default':resultSkin;
      const rect=portrait.getBoundingClientRect(), viewport=window.visualViewport;
      const scale=(window.devicePixelRatio||1)*(viewport?.scale||1);
      const bounds=[(rect.left-(viewport?.offsetLeft||0))*scale,(rect.top-(viewport?.offsetTop||0))*scale,
        rect.width*scale,rect.height*scale];
      if(!bounds.every(Number.isFinite)||bounds[0]<0||bounds[1]<0||bounds[2]<1||bounds[3]<1)return null;
      const key=[portrait.id,skin,...bounds.map(value=>Math.round(value*4))].join(':');
      return {portrait,skin,bounds,key};
    }

    function sync() {
      const scene=candidate();
      if(!scene){stop();failedKey=null;return;}
      if(current?.key===scene.key)return;
      stop();
      if(failedKey===scene.key)return;
      current={...scene,id:++nextId,index:0,nextTap:0,lastPoint:-Infinity,ready:false};
      bridge.startCharacterCompanion(current.id,scene.skin,...scene.bounds);
    }

    window.nuntiCharacterCompanionReady=(id, ready)=>{
      const request=current;
      if(request?.id!==id)return;
      if(ready!==true||candidate()?.key!==request.key){
        const unavailable=ready!==true&&candidate()?.key===request.key;
        failedKey=ready===true?null:request.key;
        stop();
        if(unavailable)onUnavailable?.(request.skin);
        return;
      }
      request.ready=true;
      request.portrait.dataset.nuntiCompanionReady='';
      request.portrait.disabled=false;
      request.portrait.setAttribute('aria-label','눈티. 머리를 쓰다듬거나 손을 눌러 인사하기');
    };

    const visibility=new IntersectionObserver(entries=>{
      for(const entry of entries){
        if(entry.isIntersecting&&entry.intersectionRatio>=.995)fullyVisible.add(entry.target);
        else fullyVisible.delete(entry.target);
      }
      sync();
    },{threshold:[0,.995,1]});
    const layout=new ResizeObserver(sync);
    for(const portrait of [preview,result]){
      visibility.observe(portrait);
      layout.observe(portrait);
      const point=event=>{
        const rect=portrait.getBoundingClientRect(), side=Math.min(rect.width,rect.height);
        if(!side||!Number.isFinite(event.clientX)||!Number.isFinite(event.clientY))return null;
        const p=[(event.clientX-rect.left-(rect.width-side)/2)/side,(event.clientY-rect.top-(rect.height-side)/2)/side];
        return p.every(value=>value>=0&&value<=1)?p:null;
      };
      const resetFocus=()=>{
        clearTimeout(focusTimer);
        if(current?.ready&&current.portrait===portrait)bridge.focusCharacterCompanion?.(current.id,0,0);
      };
      portrait.addEventListener('pointermove',event=>{
        const request=current, p=point(event), now=performance.now();
        if(!request?.ready||request.portrait!==portrait||!p||now-request.lastPoint<33||candidate()?.key!==request.key)return;
        request.lastPoint=now;
        bridge.focusCharacterCompanion?.(request.id,Math.max(-1,Math.min(1,(p[0]-.5)*2)),Math.max(-1,Math.min(1,(p[1]-.4)*2)));
        clearTimeout(focusTimer);focusTimer=setTimeout(resetFocus,1400);
      });
      portrait.addEventListener('pointerleave',resetFocus);
      portrait.addEventListener('pointercancel',resetFocus);
      portrait.addEventListener('click',event=>{
        const request=current, now=performance.now();
        if(!request?.ready||request.portrait!==portrait||now<request.nextTap||candidate()?.key!==request.key)return;
        const shared=!!bridge.focusCharacterCompanion&&(request.skin==='default'||request.skin.startsWith('wardrobe-shared1-'));
        const p=event.detail===0?null:point(event);
        if(event.detail!==0&&!p)return;
        const reaction=shared?(!p?'wave-right':p[1]<.51?'pat':p[0]<.38?'wave-left':p[0]>.62?'wave-right':p[1]>.72?'stretch':'curious')
          :skinReactions[request.index++%skinReactions.length];
        bridge.reactCharacterCompanion(request.id,reaction);
        request.nextTap=now+(shared?450:4400);
      });
    }
    const changes=new MutationObserver(sync);
    for(const view of [inputView,resultView,document.getElementById('notice'),document.getElementById('connection-retry')]){
      if(view)changes.observe(view,{attributes:true,attributeFilter:['hidden']});
    }
    for(const dialog of document.querySelectorAll('dialog'))changes.observe(dialog,{attributes:true,attributeFilter:['open']});
    changes.observe(document.body,{attributes:true,attributeFilter:['data-chat-open']});
    const move=()=>{
      stop();
      clearTimeout(timer);
      timer=setTimeout(sync,140);
    };
    document.addEventListener('visibilitychange',sync);
    document.addEventListener('focusin',sync);
    document.addEventListener('focusout',()=>queueMicrotask(sync));
    matchMedia('(prefers-reduced-motion: reduce)').addEventListener('change',sync);
    window.addEventListener('scroll',move,true);
    window.addEventListener('resize',move);
    window.visualViewport?.addEventListener('scroll',move);
    window.visualViewport?.addEventListener('resize',move);
    return {sync, setResult(skin){if(resultSkin!==skin){resultSkin=skin;sync();}}};
  }
  window.NuntiCompanion={create};
})();
