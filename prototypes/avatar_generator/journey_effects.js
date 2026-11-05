/* Purpose-led birth choreography. Every particle starts on the actual input path.
 * One anticipation, one arrival bloom; reduced-motion callers render p=1 directly.
 */
(function (scope) {
  'use strict';
  const clamp = x => Math.max(0, Math.min(1, x));
  const ease = x => { x = clamp(x); return x * x * (3 - 2 * x); };
  const themes = {
    BUSINESS: { name: '티켓이 열어 주는 출발', motif: 'ticket', colors: ['#e0ad53','#86a9b8','#fff0c6'], words: ['길 위에 출발의 빛이 켜져요', '티켓과 약속이 모여요', '오늘의 멋진 동료가 준비됐어요'] },
    SWIM: { name: '파도에서 솟아나는 인사', motif: 'bubble', colors: ['#55c9c1','#78b9eb','#fff2cf'], words: ['길을 따라 물빛이 번져요', '물방울이 파도가 되어 모여요', '첨벙! 바다 친구가 인사해요'] },
    HIKING: { name: '숲바람이 깨우는 친구', motif: 'leaf', colors: ['#7daf85','#b8d281','#f7c76b'], words: ['길 위로 숲의 빛이 스며요', '잎사귀가 바람을 따라 모여요', '든든한 산책 친구가 태어났어요'] },
    DATE: { name: '꽃잎 속 작은 설렘', motif: 'petal', colors: ['#e9a0b3','#bea0dd','#f7d8aa'], words: ['길 끝에 설렘이 피어요', '꽃잎이 마음을 모아줘요', '오늘의 설렘을 닮은 눈티예요'] },
    PLAY: { name: '장난꾸러기의 깜짝 등장', motif: 'star', colors: ['#f6c057','#e896b2','#81c7d9'], words: ['길 위에 장난스런 빛이 뛰어요', '작은 별들이 폴짝 모여요', '짜잔! 같이 놀 준비가 됐어요'] },
    ART: { name: '색이 피어나는 아틀리에', motif: 'paint', colors: ['#b59bdf','#f2a387','#79bdb4'], words: ['길이 한 줄의 붓질이 돼요', '색들이 이야기를 그려요', '너만의 작은 작품이 태어났어요'] },
    CAFE: { name: '따뜻한 향의 마법', motif: 'steam', colors: ['#cfa37f','#d6b7cf','#f1d599'], words: ['길 위로 따뜻한 향이 올라요', '포근한 순간이 모여요', '잠깐의 쉼을 함께할 눈티예요'] },
    NIGHT: { name: '밤하늘의 작은 별자리', motif: 'star', colors: ['#929fe4','#bc9fd8','#edce86'], words: ['길이 작은 별자리가 돼요', '별빛이 밤의 친구를 깨워요', '조용한 밤을 함께할 눈티예요'] },
    CELEBRATE: { name: '축하를 담은 선물', motif: 'ribbon', colors: ['#f0af66','#dd92b8','#9ebadf'], words: ['길 위에 축하의 빛이 켜져요', '리본이 선물을 감싸요', '오늘을 기억할 눈티예요'] },
    REST: { name: '구름처럼 포근한 탄생', motif: 'steam', colors: ['#a8c9c3','#c7b7db','#eedbb6'], words: ['길 위에 포근한 숨이 내려요', '편안한 순간을 모으고 있어요', '천천히 쉬어도 괜찮아요'] },
    STUDY: { name: '호기심이 여는 책장', motif: 'ticket', colors: ['#8fafbf','#b9b9e0','#eccb88'], words: ['길 위에 호기심이 반짝여요', '작은 배움이 한 장씩 모여요', '함께 알아갈 친구가 태어났어요'] },
    FOOD: { name: '맛있는 순간의 반짝임', motif: 'steam', colors: ['#edae77','#dcb7a4','#c0c88e'], words: ['길 끝의 맛있는 순간을 담아요', '따뜻한 향이 모여요', '오늘의 한 끼를 기억할 눈티예요'] },
    EXPLORE: { name: '여행 가방 속 작은 발견', motif: 'ticket', colors: ['#81b9b3','#dfb467','#e6a39c'], words: ['길 위에 발견의 빛이 켜져요', '여정의 조각들이 모여요', '새로운 곳을 함께 만날 눈티예요'] },
  };
  function theme(plan) { return themes[plan.character?.purpose?.role] || themes.EXPLORE; }
  function sample(plan, progress) {
    const t = clamp(progress), spec = theme(plan);
    const opacity = ease(t/.08) * (1-ease((t-.83)/.17));
    const gather = ease((t-.16)/.48), burst = ease((t-.65)/.23);
    const particles = plan.effectSeeds.map((seed, i) => {
      const phase = seed.phase, around = phase + t * (i%2 ? .85 : -.65);
      const end = [plan.center[0]+Math.cos(around)*(.30+.06*burst), plan.center[1]+Math.sin(around)*(.28+.07*burst)];
      const arch = Math.sin(Math.PI*gather);
      return { x: seed.route[0]*(1-gather)+end[0]*gather + Math.sin(phase)*.055*arch,
        y: seed.route[1]*(1-gather)+end[1]*gather-.10*arch,
        rotation: phase+t*(i%2?1.8:-1.8), size:(i%7===0?.016:.007+(i%3)*.003)*(1+.25*burst),
        alpha: opacity*(.3+(i%5)*.12), color:spec.colors[i%3], hero:i%7===0, phase };
    });
    return { progress:t, spec, opacity, gather, burst, particles,
      bloom: Math.sin(Math.PI*clamp((t-.64)/.30)) };
  }
  function glyph(ctx, kind, size, hero) {
    ctx.beginPath();
    if (kind==='bubble') {
      ctx.arc(0,0,size,0,Math.PI*2); ctx.stroke();
      ctx.beginPath();ctx.arc(-size*.30,-size*.34,size*.20,0,Math.PI*2);ctx.fill();return;
    }
    if (kind==='ticket' || kind==='ribbon') {
      ctx.roundRect(-size*1.1,-size*.64,size*2.2,size*1.28,size*.15);ctx.fill();
      ctx.strokeStyle='rgba(255,255,255,.8)';ctx.beginPath();ctx.moveTo(-size*.5,-size*.45);ctx.lineTo(-size*.5,size*.45);ctx.stroke();return;
    }
    if (kind==='leaf' || kind==='petal' || kind==='paint') {
      ctx.moveTo(0,-size);ctx.bezierCurveTo(size*1.4,-size*.7,size*.9,size*.8,0,size);
      ctx.bezierCurveTo(-size*.8,size*.6,-size*.9,-size*.7,0,-size);ctx.fill();return;
    }
    if (kind==='steam') {
      ctx.moveTo(-size*.3,size);ctx.bezierCurveTo(size,-size*.1,-size,-size*.1,size*.3,-size);ctx.stroke();return;
    }
    const rays=hero?4:5;for(let i=0;i<rays*2;i++){const a=i*Math.PI/rays-Math.PI/2,r=i%2?size*.30:size;const x=Math.cos(a)*r,y=Math.sin(a)*r;if(i)ctx.lineTo(x,y);else ctx.moveTo(x,y);}ctx.closePath();ctx.fill();
  }
  function draw(ctx, plan, progress, layer) {
    const frame=sample(plan,progress);if(!frame.opacity)return;
    const {spec,opacity,gather,bloom}=frame;
    ctx.save();ctx.lineCap='round';ctx.lineJoin='round';
    if(layer==='behind') {
      // A soft atmospheric field supports the silhouette without covering its face.
      const glow=ctx.createRadialGradient(...plan.center,.01,...plan.center,.52);
      glow.addColorStop(0,spec.colors[0]+'48');glow.addColorStop(.58,spec.colors[1]+'20');glow.addColorStop(1,spec.colors[1]+'00');
      ctx.globalAlpha=opacity*gather;ctx.fillStyle=glow;ctx.fillRect(0,0,1,1);ctx.globalAlpha=1;
      for(let j=0;j<3;j++) {
        const radius=.20+.12*gather+j*.035;
        ctx.save();ctx.translate(...plan.center);ctx.rotate(-.32+j*.25);
        ctx.beginPath();ctx.ellipse(0,0,radius,radius*.71,0,-Math.PI+progress*(1.1+j*.15),Math.PI*.55+progress);
        ctx.globalAlpha=opacity*gather*(.38-j*.08);ctx.strokeStyle=spec.colors[j];ctx.lineWidth=.006-j*.001;ctx.stroke();ctx.restore();
      }
      if(bloom>0){ctx.globalAlpha=bloom*.35;ctx.strokeStyle=spec.colors[0];ctx.lineWidth=.002;ctx.beginPath();ctx.ellipse(...plan.center,.20+frame.burst*.20,.16+frame.burst*.19,0,0,Math.PI*2);ctx.stroke();}
    }
    for(const p of frame.particles) {
      if((layer==='front')!==p.hero)continue;
      ctx.save();ctx.translate(p.x,p.y);ctx.rotate(p.rotation);ctx.globalAlpha=p.alpha;ctx.fillStyle=p.color;ctx.strokeStyle=p.color;ctx.lineWidth=.0018;
      glyph(ctx,spec.motif,p.size,p.hero);ctx.restore();
    }
    ctx.restore();
  }
  const api={themes,theme,sample,draw};scope.NuntiJourneyEffects=api;
  if(typeof module!=='undefined')module.exports=api;
})(globalThis);
