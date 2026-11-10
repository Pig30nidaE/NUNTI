'use strict';
(() => {
  function create({preview, result, inputView, resultView, allowed}) {
    const bridge=window.NuntiNative;
    if(!bridge?.startCharacterCompanion||!bridge.stopCharacterCompanion||!bridge.reactCharacterCompanion)return null;
    const baseReactions=['curious','happy','wink','proud'];
    const skinReactions=[...baseReactions,'signature'];
    const fullyVisible=new Set();
    let nextId=0, current=null, resultSkin=null, failedKey=null, timer=0;

    function stop() {
      if(!current)return;
      const request=current;
      current=null;
      delete request.portrait.dataset.nuntiCompanionReady;
      request.portrait.disabled=true;
      bridge.stopCharacterCompanion(request.id);
    }

    function candidate() {
      if(!allowed()||document.hidden||document.querySelector('dialog[open]'))return null;
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
      current={...scene,id:++nextId,index:0,nextTap:0,ready:false};
      bridge.startCharacterCompanion(current.id,scene.skin,...scene.bounds);
    }

    window.nuntiCharacterCompanionReady=(id, ready)=>{
      const request=current;
      if(request?.id!==id)return;
      if(ready!==true||candidate()?.key!==request.key){
        failedKey=ready===true?null:request.key;
        stop();
        return;
      }
      request.ready=true;
      request.portrait.dataset.nuntiCompanionReady='';
      request.portrait.disabled=false;
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
      portrait.addEventListener('click',()=>{
        const request=current, now=performance.now();
        if(!request?.ready||request.portrait!==portrait||now<request.nextTap||candidate()?.key!==request.key)return;
        const choices=request.skin==='default'?baseReactions:skinReactions;
        bridge.reactCharacterCompanion(request.id,choices[request.index++%choices.length]);
        request.nextTap=now+1200;
      });
    }
    const changes=new MutationObserver(sync);
    for(const view of [inputView,resultView])changes.observe(view,{attributes:true,attributeFilter:['hidden']});
    for(const dialog of document.querySelectorAll('dialog'))changes.observe(dialog,{attributes:true,attributeFilter:['open']});
    const move=()=>{
      stop();
      clearTimeout(timer);
      timer=setTimeout(sync,140);
    };
    document.addEventListener('visibilitychange',sync);
    matchMedia('(prefers-reduced-motion: reduce)').addEventListener('change',sync);
    window.addEventListener('scroll',move,true);
    window.addEventListener('resize',move);
    window.visualViewport?.addEventListener('scroll',move);
    window.visualViewport?.addEventListener('resize',move);
    return {sync, setResult(skin){if(resultSkin!==skin){resultSkin=skin;sync();}}};
  }
  window.NuntiCompanion={create};
})();
