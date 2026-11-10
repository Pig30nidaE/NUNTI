'use strict';
// Figma 4:13, seven tracks, 4000ms. Existing server AvatarSpec owns all mapping.
// Canvas is the Studio's established renderer. No model calls or sample-ID mapping.
(function () {
  const duration = 4000, manifest = window.NuntiMotionManifest;
  const cached = new Map();
  const clamp = x => Math.max(0, Math.min(1, x));
  function easing(x) {
    if (x <= 0 || x >= 1) return x;
    let lo = 0, hi = 1;
    for (let i = 0; i < 24; i++) {
      const t = (lo + hi) / 2;
      const curve = 3 * (1-t) * (1-t) * t * .4 + 3 * (1-t) * t * t * .2 + t*t*t;
      if (curve < x) lo = t; else hi = t;
    }
    const t = (lo + hi) / 2;
    return 3 * (1-t) * t * t + t*t*t;
  }
  function timeline(ms) {
    const p = (start, end) => easing(clamp((ms - start) / (end - start)));
    return { road:p(450,1300), scarf:p(1300,1900), pocket:p(1700,2500), expression:p(2850,3050),
      glow:p(450,550)*(1-p(1200,1300)) };
  }
  function pathsFor(artifact) {
    const spec = artifact?.design?.avatarSpec;
    if (artifact?.mediaOrigin !== 'LOCAL_LAYERS' || artifact.design?.renderStatus !== 'COMPOSITED' ||
        spec?.assetVersion !== manifest?.sourceAssetVersion || spec?.mappingVersion !== 'nunti-layers-v1' ||
        spec?.schemaVersion !== 'nunti.avatar.layers/1' || !Array.isArray(spec.layers)) return null;
    const {destinationMotif:d, roadMotif:r, routeVariant:v, expression:e} = spec;
    if (!['none','coast','mountain','city'].includes(d) || !['none','urban','highway','rural','mixed'].includes(r) ||
        !['base','calm','curious','adventurous'].includes(e) || !Number.isInteger(v) || v<0 || v>2) return null;
    const expected = ['body','head','sprout','scarf','bag','badge'].map(name=>'core/'+name+'.png');
    expected.push('expressions/'+e+'.png');
    if (d !== 'none') expected.push('destinations/'+d+'.png');
    if (r !== 'none') expected.push('roads/'+r+'-'+v+'.png');
    // Refuse a future or modified renderer rather than showing an approximate transformation.
    if (spec.layers.length !== expected.length || expected.some((path,i) =>
      spec.layers[i]?.path !== path || artifact.design.layerAssets?.[path] !== manifest.sourceHashes[path])) return null;
    return { core:'core.png', baseExpression:'expression-base.png', expression:'expression-'+e+'.png',
      scarf:d==='none'?null:'destinations/'+d+'-scarf.png', pocket:d==='none'?null:'destinations/'+d+'-pocket.png',
      road:r==='none'?null:'roads/'+r+'-'+v+'.png', expressionIsBase:e==='base',
      hasChanges:d!=='none'||r!=='none'||e!=='base' };
  }
  async function load(path) {
    if (!path) return null;
    if (!manifest?.files[path]) throw new Error('UNKNOWN_MOTION_ASSET');
    if (!cached.has(path)) cached.set(path, (async () => {
      const response = await fetch('/nunti-motion/'+path, {credentials:'same-origin'});
      if (!response.ok) throw new Error('MOTION_ASSET_UNAVAILABLE');
      const raw = await response.arrayBuffer();
      if (raw.byteLength !== manifest.files[path].bytes) throw new Error('MOTION_ASSET_SIZE');
      const hash = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',raw)),b=>b.toString(16).padStart(2,'0')).join('');
      if (hash !== manifest.files[path].sha256) throw new Error('MOTION_ASSET_HASH');
      const url = URL.createObjectURL(new Blob([raw],{type:'image/png'}));
      try { const image = new Image(); image.src = url; await image.decode();
        if (image.naturalWidth !== 768 || image.naturalHeight !== 768) throw new Error('MOTION_ASSET_DIMENSIONS');
        return image;
      } finally { URL.revokeObjectURL(url); }
    })().catch(error=>{cached.delete(path);throw error;}));
    return cached.get(path);
  }
  function create({canvas, allowed, visible, onFrame}) {
    let epoch=0, raf=0, elapsed=0, status='BASE', reason='NONE', images=null, finalImage=null, label='기본 친근한 눈티', active=false;
    let base=null, frameCount=0, lastFrame=0, intervals=[], startedAt=0, nextDraw=0, lastAria='';
    let userReduced=false, systemReduced=false;
    try { userReduced=localStorage.getItem('nunti-reduced-motion')==='true'; } catch {}
    const media=matchMedia('(prefers-reduced-motion: reduce)');
    const reduced=()=>userReduced||systemReduced||media.matches;
    load('base.png').then(value=>{base=value;if(!images&&elapsed<duration)redraw();}).catch(()=>{});
    function publish() { onFrame?.({active,status,reason,elapsedMs:elapsed,running:status==='RUNNING',finalReady:!!finalImage,reducedMotion:reduced(),userReducedMotion:userReduced,systemReducedMotion:systemReduced||media.matches}); }
    function drawImage(ctx, image, alpha=1) { if (!image || alpha<=0) return; ctx.globalAlpha=alpha;ctx.drawImage(image,0,0,768,768);ctx.globalAlpha=1; }
    function reveal(ctx,image,path,p) {
      if (!image || p<=0) return;
      if (p>=1) { drawImage(ctx,image);return; }
      const [x,y,right,bottom]=manifest.files[path].bounds;
      ctx.save();ctx.beginPath();ctx.rect(x-1,y-1,(right-x)*p+1,bottom-y+2);ctx.clip();drawImage(ctx,image);ctx.restore();
    }
    function artwork(ctx, ms=elapsed) {
      if (ms>=duration && finalImage) { drawImage(ctx,finalImage);return; }
      if (!images) { drawImage(ctx,base);return; }
      const f=timeline(ms);
      drawImage(ctx,images.core);
      if(images.expressionIsBase)drawImage(ctx,images.baseExpression);
      else {drawImage(ctx,images.baseExpression,1-f.expression);drawImage(ctx,images.expression,f.expression);}
      drawImage(ctx,images.scarf,f.scarf);
      reveal(ctx,images.pocket,images.paths.pocket,f.pocket);
      reveal(ctx,images.road,images.paths.road,f.road);
      if (images.road && f.glow>0) {
        const [left,top,right,bottom]=manifest.files[images.paths.road].bounds;
        const x=left+(right-left)*f.road,y=(top+bottom)/2;
        for(const [radius,alpha] of [[8,.16],[3,.7]]) {ctx.beginPath();ctx.arc(x,y,radius,0,Math.PI*2);ctx.fillStyle='rgba(249,216,146,'+(f.glow*alpha)+')';ctx.fill();}
      }
    }
    function redraw() {
      if (!active || !visible()) return;
      // The host calibrates CSS coordinates to display pixels using viewport scale.
      // Avoid rasterizing an extra 1.375² pixels on Pleos before downsampling them.
      const rect=canvas.getBoundingClientRect(),dpr=Math.min((devicePixelRatio||1)*(window.visualViewport?.scale||1),2);
      if (!rect.width || !rect.height) return;
      const w=Math.round(rect.width*dpr),h=Math.round(rect.height*dpr);
      if(canvas.width!==w||canvas.height!==h){canvas.width=w;canvas.height=h;}
      const ctx=canvas.getContext('2d');ctx.setTransform(dpr,0,0,dpr,0,0);ctx.clearRect(0,0,rect.width,rect.height);
      const size=Math.min(rect.width,rect.height);
      ctx.save();ctx.translate((rect.width-size)/2,(rect.height-size)/2);ctx.scale(size/768,size/768);artwork(ctx);ctx.restore();
      const aria=status==='RUNNING'?'같은 눈티에 여행의 장식과 표정이 더해지고 있어요':label;
      if(aria!==lastAria){canvas.setAttribute('aria-label',aria);lastAria=aria;}
    }
    function stop(why='SKIPPED') {
      cancelAnimationFrame(raf);raf=0;epoch++;elapsed=finalImage?duration:0;status='SETTLED';reason=why;redraw();publish();
    }
    function clear() {
      cancelAnimationFrame(raf);raf=0;epoch++;active=false;images=null;finalImage=null;elapsed=0;lastAria='';status='BASE';reason='SCREEN_CHANGED';publish();
    }
    function animate(now) {
      if(!allowed()){stop('RESTRICTED');return;}
      if(!visible()){stop('BACKGROUNDED');return;}
      if(reduced()){stop('REDUCED_MOTION');return;}
      elapsed=Math.max(0,Math.min(duration,now-startedAt));
      if(now>=nextDraw || elapsed>=duration) {
        if(lastFrame)intervals.push(now-lastFrame);lastFrame=now;frameCount++;
        redraw();publish();nextDraw+=1000/30;
      }
      if(elapsed>=duration){status='SETTLED';reason='COMPLETED';raf=0;publish();}
      else raf=requestAnimationFrame(animate);
    }
    async function loading() {
      stop('LOADING'); const ticket=++epoch;active=true;finalImage=null;images=null;elapsed=0;status='LOADING';reason='NONE';label='기본 친근한 눈티';
      publish();try {const value=await load('base.png');if(ticket!==epoch)return;base=value;redraw();}catch{if(ticket!==epoch)return;status='FAILED';reason='BASE_ASSET_FAILURE';publish();}
    }
    async function show(artifact,image,play) {
      stop('CHANGED');const ticket=++epoch;
      active=true;finalImage=image;images=null;label=artifact.design?.avatarSpec?.accessibilityLabel||artifact.displayName;
      const paths=pathsFor(artifact);
      const canPlay=paths?.hasChanges&&play&&allowed()&&visible()&&!reduced();
      elapsed=canPlay?0:duration;status=canPlay?'LOADING':'SETTLED';reason='STATIC';redraw();publish();
      if(!paths || !paths.hasChanges || !play || !allowed() || !visible() || reduced()) {
        reason=reduced()?'REDUCED_MOTION':!allowed()?'RESTRICTED':!paths?'UNSUPPORTED_SPEC':!paths.hasChanges?'BASE_ONLY':'STATIC';publish();return;
      }
      try {
        const keys=['core','baseExpression','expression','scarf','pocket','road'];
        const values=await Promise.all(keys.map(key=>load(paths[key])));
        if(ticket!==epoch)return;
        images={...Object.fromEntries(keys.map((key,i)=>[key,values[i]])),paths,expressionIsBase:paths.expressionIsBase};
        if(!allowed()||!visible()||reduced()){stop(reduced()?'REDUCED_MOTION':!allowed()?'RESTRICTED':'BACKGROUNDED');return;}
        elapsed=0;status='RUNNING';reason='NONE';frameCount=0;lastFrame=0;intervals=[];startedAt=performance.now();nextDraw=startedAt;
        redraw();publish();raf=requestAnimationFrame(animate);
      } catch {if(ticket===epoch)stop('LAYER_ASSET_FAILURE');}
    }
    function setReduced(value){userReduced=!!value;try{localStorage.setItem('nunti-reduced-motion',String(userReduced));}catch{}if(reduced())stop('REDUCED_MOTION');publish();}
    function appearance(value){systemReduced=!!value.systemReducedMotion;if(reduced()&&active&&(status==='RUNNING'||status==='LOADING'))stop('REDUCED_MOTION');publish();}
    media.addEventListener('change',()=>{if(reduced())stop('REDUCED_MOTION');publish();});
    // Diagnostic capture uses this same renderer and never grants vehicle permission.
    function capture(ms) {
      if(!allowed()||!visible()||!finalImage)return null;
      stop('CAPTURE');elapsed=Math.max(0,Math.min(duration,ms));redraw();publish();
      const out=document.createElement('canvas');out.width=out.height=768;artwork(out.getContext('2d'));
      return out.toDataURL('image/png');
    }
    return {show,loading,stop,clear,redraw,setReduced,appearance,capture,
      diagnostics:()=>({active,status,reason,elapsedMs:elapsed,frameCount,intervalsMs:intervals.slice(),reducedMotion:reduced(),userReducedMotion:userReduced,layerReady:!!images,finalReady:!!finalImage})};
  }
  window.NuntiTransformation={create,timeline,pathsFor,duration};
})();
