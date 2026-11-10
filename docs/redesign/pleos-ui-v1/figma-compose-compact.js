// Concatenate after figma-layout-helpers.js.
function compact(name,state,x,y,theme){
 const s=shell(name,x,y,830,theme),w=766;header(s,state==='PRE_TRIP'?'출발 전':state==='REVEAL_PARKED'?'변형 · 정차 중':state==='POST_TRIP'?'여정 완료':'주행 중',w,state==='PRE_TRIP'||state==='REVEAL_PARKED');
 const title=frame('Compact title','VERTICAL',w,108);gap(title,8);s.appendChild(title);label(title,{PRE_TRIP:'이번 길에, 눈티를 더해요',REVEAL_PARKED:'같은 눈티, 이번 길의 모습',DRIVING_RESTRICTED:'이번 길도, 눈티와 함께',POST_TRIP:'함께한 길을 돌아봐요'}[state],'Title');label(title,state==='PRE_TRIP'?'목적지와 직접 고른 기분을 담아요.':'안목해변 · 호기심 있게','Caption','muted');
 const viewport=frame(state==='DRIVING_RESTRICTED'?'Static driving viewport':'Parked manual scroll viewport','VERTICAL',w,786);s.appendChild(viewport);viewport.layoutSizingVertical='FILL';viewport.clipsContent=true;if(state!=='DRIVING_RESTRICTED')viewport.overflowDirection='VERTICAL';
 const body=card(viewport,'Compact content',w,786,state==='DRIVING_RESTRICTED'?'soft':'surface',24);body.layoutSizingVertical='HUG';gap(body,16);
 if(state==='PRE_TRIP'){
  const hero=row(body,'Companion and route',718,220,24);hero.counterAxisAlignItems='CENTER';character(hero,'Base',220);const info=frame('Route summary','VERTICAL',474,220);gap(info,16);hero.appendChild(info);label(info,'안목해변','Heading');label(info,'경로를 확인해 주세요','Caption','muted');instance('Route preview / synthetic confirmed',info,270,110);
  const nav=row(body,'Navigation actions',718,80,16);button(nav,'내비 목적지 불러오기','Secondary',410,name+'/import');button(nav,'현대 내비 열기','Quiet',292,name+'/navigation');
  choice(body,'이번에 갈 경로가 맞아요',true,718);
  field(body,'목적지','안목해변',718);
  const types=row(body,'Explicit destination and road',718,122,16);field(types,'목적지 유형','바다  ▾',351);field(types,'도로 유형','고속도로  ▾',351);
  label(body,'어떤 기분으로 떠날까요?','Caption','muted');const moods=row(body,'Mood options',718,76,16);choice(moods,'차분하게',false,228);choice(moods,'호기심 있게',true,230);choice(moods,'씩씩하게',false,228);
  const fields=row(body,'Trip context',718,122,16);field(fields,'그곳의 느낌','바다와 커피 향',351);field(fields,'가는 이유','잠깐 쉬러 가요',351);
  button(body,'다른 방법으로 경로 가져오기','Quiet',718,name+'/route-tools');button(body,'기본 눈티 A · 생성 방식','Quiet',718,name+'/engine');
 }else if(state==='REVEAL_PARKED'){
  const art=frame('Character stage','VERTICAL',718,320);art.counterAxisAlignItems='CENTER';body.appendChild(art);character(art,'CoastCurious',320);
  label(body,'바다를 담은 눈티','Heading');status(body,'내 눈티에 자동으로 저장됐어요',718);
  const controls=row(body,'Reveal controls',718,80,16);button(controls,'바로 보기','Secondary',351,name+'/skip');button(controls,'목소리 듣기','Secondary',351,name+'/voice');
  const motion=row(body,'Motion controls',718,80,16);button(motion,'변신 다시 보기','Quiet',334,name+'/replay');button(motion,'움직임 줄이기 · 끔','Quiet',368,name+'/reduced');
  button(body,'모습 이야기','Quiet',718,name+'/story');
 }else if(state==='DRIVING_RESTRICTED'){
  body.layoutSizingVertical='FILL';body.counterAxisAlignItems='CENTER';character(body,'CoastCurious',360);label(body,'함께 살피는 중','Caption','accent');label(body,'평가 대기','Display');label(body,'함께한 시간  00:38','Heading');label(body,'주행 신호가 쌓이면 알려드려요.','Body','muted');
 }else{
  const art=frame('Collected character','HORIZONTAL',718,220);art.counterAxisAlignItems='CENTER';gap(art,24);body.appendChild(art);character(art,'CoastCurious',220);const about=frame('Saved appearance','VERTICAL',474,150);gap(about,16);art.appendChild(about);label(about,'같은 모습으로 남아요','Heading');label(about,'내 눈티에서 다시 만나요.','Caption','muted');
  const stats=row(body,'Summary metrics',718,204,16);metric(stats,'이번 여정의 점수','평가 대기','신호가 더 필요해요',351);metric(stats,'함께한 시간','38초','여정 완료',351);
  label(body,'평가할 신호가 아직 부족해요','Heading');label(body,'받지 못한 항목은 점수에서 제외해요.','Body','muted');status(body,'평가 가능한 범위  0%',718);button(body,'세부 기록 보기','Quiet',718,name+'/details');
 }
 const footer=row(s,'Persistent primary controls',w,80,24);
 if(state==='PRE_TRIP')button(footer,'이 길에서 눈티 만나기  ↗','Primary',w,name+'/create');
 else if(state==='REVEAL_PARKED'){button(footer,'새 여정 만들기','Secondary',304,name+'/new');button(footer,'눈티와 함께하기','Primary',438,name+'/start');}
 else if(state==='DRIVING_RESTRICTED'){button(footer,'음성 끄기','Secondary',310,name+'/mute');button(footer,'현대 내비 열기','Secondary',432,name+'/navigation');}
 else button(footer,'눈티로 돌아가기','Primary',w,name+'/back');
 return s;
}
note('04  /  좁은 창 · 낮과 밤','830 × 1210 px · 출발 전/변형/도착 후에만 수동 스크롤 · 주요 동작은 하단에 고정',80,4460,7040);
for(const[theme,y]of [['Day',4600],['Night',6000]])for(const[i,state]of ['PRE_TRIP','REVEAL_PARKED','DRIVING_RESTRICTED','POST_TRIP'].entries())compact(state+' / Compact / '+theme,state,80+i*930,y,theme);
return {createdNodeIds,screens,actions};
