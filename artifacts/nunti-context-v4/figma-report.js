const button=await figma.getNodeByIdAsync('18:145');
const page=figma.createPage();page.name='Context v4 · 옷장과 주행 리포트';await figma.setCurrentPageAsync(page);
await Promise.all(['Regular','Medium','Bold'].map(style=>figma.loadFontAsync({family:'Noto Sans KR',style})));
const names={ink:'VariableID:55:9',muted:'VariableID:55:10',surface:'VariableID:55:7',soft:'VariableID:55:8',accent:'VariableID:55:12'};
const vars={};await Promise.all(Object.entries(names).map(async([k,id])=>vars[k]=await figma.variables.getVariableByIdAsync(id)));
function rgb(h){return{r:parseInt(h.slice(0,2),16)/255,g:parseInt(h.slice(2,4),16)/255,b:parseInt(h.slice(4,6),16)/255}}
function fill(n,k,dark){const c={ink:'F3F2E9',muted:'B4C8C3',surface:'1A2B2E',soft:'22393B',accent:'B5DDD2'};n.fills=[dark?{type:'SOLID',color:rgb(c[k])}:figma.variables.setBoundVariableForPaint({type:'SOLID',color:rgb('FFFFFF')},'color',vars[k])]}
function box(parent,name,w,h,dark=false,color='surface',dir='VERTICAL'){const n=figma.createAutoLayout();n.name=name;n.layoutMode=dir;n.resize(w,h);n.primaryAxisSizingMode='FIXED';n.counterAxisSizingMode='FIXED';n.itemSpacing=16;n.paddingLeft=n.paddingRight=n.paddingTop=n.paddingBottom=24;n.cornerRadius=28;fill(n,color,dark);parent.appendChild(n);return n}
function txt(p,s,size=28,weight='Regular',dark=false,color='ink'){const t=figma.createText();t.fontName={family:'Noto Sans KR',style:weight};t.characters=s;t.fontSize=size;t.lineHeight={unit:'PIXELS',value:Math.ceil(size*1.45)};fill(t,color,dark);p.appendChild(t);return t}
function art(p,w,h){const n=figma.createRectangle();n.name='눈티 원화';n.resize(w,h);n.fills=[{type:'IMAGE',imageHash:'b3f8a223e2a892d99506d56edb569098dbd1a7e4',scaleMode:'FIT'}];p.appendChild(n);return n}
const roots=[];
for(const dark of [false,true]){
 const root=box(page,dark?'B · 경로 중심의 야간 리포트':'A · 눈티와 돌아보는 주행',1683,1210,dark,'surface');
 root.x=200+(dark?1803:0);root.y=160;root.paddingLeft=root.paddingRight=40;root.paddingTop=root.paddingBottom=32;root.itemSpacing=24;root.cornerRadius=0;
 const header=box(root,'머리말',1603,66,dark,'surface','HORIZONTAL');header.paddingLeft=header.paddingTop=header.paddingBottom=0;txt(header,'눈티',32,'Bold',dark);txt(header,'주행 리포트 · 예시 데이터',24,'Regular',dark,'muted');
 txt(root,'이번 길을 돌아봐요',44,'Bold',dark);
 const content=box(root,'리포트 본문',1603,816,dark,'surface','HORIZONTAL');content.paddingLeft=content.paddingRight=content.paddingTop=content.paddingBottom=0;content.itemSpacing=24;
 const summary=box(content,'점수와 눈티',dark?430:500,816,dark,'soft');
 txt(summary,'한눈에 보는 운전',26,'Medium',dark,'muted');txt(summary,'82점',76,'Bold',dark);txt(summary,'가속·제동을 조금 더 부드럽게',24,'Medium',dark);
 art(summary,dark?350:414,320);
 txt(summary,'함께 달린 시간  12분 40초',24,'Regular',dark);txt(summary,'평가 가능한 범위  90%',22,'Regular',dark,'muted');
 const details=box(content,'경로와 습관',dark?1149:1079,816,dark,'surface');details.paddingLeft=details.paddingRight=details.paddingTop=details.paddingBottom=0;
 const map=box(details,'이벤트가 발생한 구간',dark?1149:1079,360,dark,'soft');
 txt(map,'어느 구간에서 달라졌나요?',28,'Bold',dark);
 const svg='<svg width="920" height="185" viewBox="0 0 920 185" xmlns="http://www.w3.org/2000/svg"><path d="M40 150 L165 150 Q200 150 200 108 L200 80 Q200 48 240 48 L450 48 Q485 48 485 90 L485 120 Q485 150 530 150 L710 150 Q760 150 760 100 L760 50 L880 50" fill="none" stroke="'+(dark?'#B5DDD2':'#195057')+'" stroke-width="9" stroke-linecap="round"/><circle cx="200" cy="108" r="20" fill="#955434"/><circle cx="485" cy="90" r="20" fill="#955434"/><circle cx="760" cy="100" r="20" fill="#955434"/></svg>';
 map.appendChild(figma.createNodeFromSvg(svg));txt(map,'급가속 1회     급제동 1회     회전 전 감속 부족 1회',22,'Regular',dark);
 const improve=box(details,'다음 주행에서 바꿀 습관',dark?1149:1079,150,dark,'soft');txt(improve,'다음에는 이렇게',24,'Bold',dark);txt(improve,'앞차와 거리를 두고, 정지 전에 일찍 속도를 줄여 보세요.',24,'Regular',dark);
 const good=box(details,'잘한 습관',dark?1149:1079,150,dark,'soft');txt(good,'잘한 습관',24,'Bold',dark,'accent');txt(good,'안전벨트를 잘 착용했어요. 계속 유지해 주세요.',26,'Medium',dark);
 const more=box(details,'평가 근거',dark?1149:1079,90,dark,'surface','HORIZONTAL');txt(more,'가속·제동  72     차간 거리  84     안전 상태  100',24,'Medium',dark);
 const footer=box(root,'하단 동작',1603,80,dark,'surface','HORIZONTAL');footer.paddingLeft=footer.paddingTop=footer.paddingBottom=0;
 txt(footer,'주차 후 자세히 확인할 수 있어요',24,'Regular',dark,'muted');
 if(button?.type==='COMPONENT'){
  const instance=button.createInstance();footer.appendChild(instance);instance.resize(420,80);
  for(const t of instance.findAllWithCriteria({types:['TEXT']})){await figma.loadFontAsync(t.fontName);t.characters='눈티로 돌아가기';}
 }
 roots.push(root);
}
return {pageId:page.id,createdNodeIds:[page.id,...roots.flatMap(r=>[r.id,...r.findAll(()=>true).map(n=>n.id)])],frames:roots.map(r=>({id:r.id,name:r.name,width:r.width,height:r.height})),font:'Noto Sans KR'};
