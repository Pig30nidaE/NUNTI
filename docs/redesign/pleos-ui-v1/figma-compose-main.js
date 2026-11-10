// Concatenate after figma-layout-helpers.js.
function reveal(name,x,y,theme='Day'){
 const s=shell(name,x,y,1682,theme),w=1602;header(s,'변형 · 정차 중',w);intro(s,'같은 눈티, 이번 길의 모습','길의 패턴과 바다의 색, 호기심을 차례로 담아요.',w);
 const body=row(s,'Companion and trip story',w,770,32);body.layoutSizingVertical='FILL';
 const stage=card(body,'Parked transformation stage',770,770,'soft');stage.layoutSizingVertical='FILL';stage.counterAxisAlignItems='CENTER';character(stage,'CoastCurious',650);label(stage,'고속도로 · 바다 · 호기심','Caption','accent');
 const detail=card(body,'Result and actions',800,770,'surface');detail.layoutSizingHorizontal='FILL';detail.layoutSizingVertical='FILL';
 label(detail,'바다를 담은 눈티','Title');label(detail,'안목해변 · 잠깐 쉬러 가요','Body','muted');status(detail,'내 눈티에 자동으로 저장됐어요',736);
 label(detail,'이번 여정의 작은 이야기','Heading');
 for(const [k,v]of [['길의 패턴','길게 이어진 고속도로'],['목적지 장식','바다의 물결'],['직접 고른 기분','호기심 있게']]){const r=row(detail,k,736,40,24);label(r,k,'Caption','muted');label(r,v,'Body');}
 spacer(detail);
 const voice=row(detail,'Manual voice action',736,80,16);button(voice,'목소리 듣기','Secondary',352,name+'/voice');button(voice,'모습 이야기','Quiet',368,name+'/story');
 const motion=row(detail,'Motion controls',736,80,16);button(motion,'변신 다시 보기','Quiet',352,name+'/replay');button(motion,'움직임 줄이기 · 끔','Quiet',368,name+'/reduced');
 const footer=row(s,'Result primary actions',w,80,24);button(footer,'새 여정 만들기','Secondary',340,name+'/new');const space=frame('Result footer space','HORIZONTAL',1,1);footer.appendChild(space);fillWidth(space);button(footer,'바로 보기','Quiet',200,name+'/skip');button(footer,'눈티와 함께하기  ↗','Primary',450,name+'/start');return s;
}
function driving(name,x,y,theme='Day'){
 const s=shell(name,x,y,1682,theme),w=1602;header(s,'주행 중',w,false);intro(s,'이번 길도, 눈티와 함께','안목해변으로 가는 길',w);
 const body=row(s,'Static companion and driving information',w,770,48);body.layoutSizingVertical='FILL';
 const companion=card(body,'Static only · no timeline',770,770,'soft');companion.layoutSizingVertical='FILL';companion.counterAxisAlignItems='CENTER';character(companion,'CoastCurious',650);label(companion,'함께 살피는 중','Caption','accent');
 const info=frame('Glanceable driving status','VERTICAL',784,770);padding(info,32);gap(info,24);body.appendChild(info);info.layoutSizingVertical='FILL';info.layoutSizingHorizontal='FILL';
 spacer(info);label(info,'현재까지 주행 점수','Body','muted');label(info,'평가 대기','Display');label(info,'주행 신호가 쌓이면 알려드려요.','Body','muted',720);label(info,'함께한 시간  00:38','Heading','ink');label(info,'실시간 차량 신호','Caption','muted');spacer(info);
 const footer=row(s,'Optional single-step controls',w,80,24);label(footer,'자세한 내용은 정차 후 확인해요.','Body','muted');const space=frame('Driving footer space','HORIZONTAL',1,1);footer.appendChild(space);fillWidth(space);button(footer,'음성 끄기','Secondary',240,name+'/mute');button(footer,'현대 내비 열기','Secondary',320,name+'/navigation');return s;
}
function postTrip(name,x,y,theme='Day'){
 const s=shell(name,x,y,1682,theme),w=1602;header(s,'여정 완료',w,false);intro(s,'함께한 길을 돌아봐요','여정을 마친 뒤, 이번 운전을 차분히 살펴봐요.',w);
 const body=row(s,'Final companion and report',w,770,32);body.layoutSizingVertical='FILL';
 const left=card(body,'Collected companion',650,770,'soft');left.layoutSizingVertical='FILL';left.counterAxisAlignItems='CENTER';character(left,'CoastCurious',566);label(left,'안목해변 · 호기심 있게','Heading');label(left,'같은 모습으로 내 눈티에 남아요.','Caption','muted');
 const report=frame('Latest on-device report','VERTICAL',920,770);gap(report,24);body.appendChild(report);report.layoutSizingHorizontal='FILL';report.layoutSizingVertical='FILL';
 const stats=row(report,'Summary metrics',920,204,24);metric(stats,'이번 여정의 점수','평가 대기','신호가 더 필요해요',448);metric(stats,'함께한 시간','38초','여정 완료',448);
 const summary=card(report,'Report explanation',920,270,'surface');label(summary,'평가할 신호가 아직 부족해요','Heading');label(summary,'받지 못한 항목은 점수에서 제외해요.','Body','muted',856);status(summary,'평가 가능한 범위  0%',856);
 const detail=card(report,'Parked details',920,248,'surface');label(detail,'이번 여정의 세부 기록','Heading');button(detail,'세부 기록 보기','Quiet',856,name+'/details');
 const footer=row(s,'Return action',w,80,24);label(footer,'마지막 여정 리포트는 기기에 보관돼요.','Body','muted');const space=frame('Report footer space','HORIZONTAL',1,1);footer.appendChild(space);fillWidth(space);button(footer,'눈티로 돌아가기','Primary',450,name+'/back');return s;
}
note('02  /  실제 앱 영역 · 낮','1682 × 1210 px · 네 상태 · 원화와 기능 흐름 유지',80,1660,7040);
note('03  /  실제 앱 영역 · 밤','같은 의미의 색상 변수에 Night 모드를 적용한 제안',80,3060,7040);
for(const [theme,y]of [['Day',1800],['Night',3200]]){
 preTrip('PRE_TRIP / '+theme,80,y,theme);
 reveal('REVEAL_PARKED / '+theme,1882,y,theme);
 driving('DRIVING_RESTRICTED / '+theme,3684,y,theme);
 postTrip('POST_TRIP / '+theme,5486,y,theme);
}
return {createdNodeIds,screens,actions,screenCount:Object.keys(screens).length};
