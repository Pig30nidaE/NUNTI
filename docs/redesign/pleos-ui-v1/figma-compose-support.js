// Concatenate after helpers and the main functions, without the main invocation.
function routeTools(name,x,y,theme){
 const s=shell(name,x,y,1682,theme),w=1602;header(s,'경로 도구 · 정차 중',w,false);intro(s,'경로를 가져오는 다른 방법','사진과 좌표, 현대 내비에서 이번 길을 확인해요.',w);
 const body=row(s,'Existing route capabilities',w,770,32);body.layoutSizingVertical='FILL';
 const left=card(body,'Images and navigation',770,770);left.layoutSizingVertical='FILL';label(left,'사진 · 파일 · 현대 내비','Heading');
 const upload=row(left,'Legacy input methods',706,80,16);button(upload,'경로 사진 불러오기','Secondary',345,name+'/image');button(upload,'좌표 파일','Secondary',345,name+'/json');
 const detection=row(left,'Extraction correction',706,122,16);field(detection,'경로선 색상','자동으로 찾기  ▾',410);button(detection,'다시 찾기','Quiet',280,name+'/extract');
 button(left,'이 목적지를 현대 내비에 설정','Secondary',706,name+'/send');button(left,'현대 경로 전체 보기','Secondary',706,name+'/overview');
 label(left,'사진이나 좌표로 불러온 선을 확인한 뒤\n이번에 갈 경로로 선택해 주세요.','Body','muted',706);
 const right=card(body,'Existing API route tools',800,770);right.layoutSizingHorizontal='FILL';right.layoutSizingVertical='FILL';label(right,'공개 장소로 경로 확인','Heading');field(right,'시험 여정','강릉역 → 안목해변  ▾',736);
 const origin=row(right,'Origin coordinates',736,122,16);field(origin,'출발 위도','입력한 위도',360);field(origin,'출발 경도','입력한 경도',360);
 const dest=row(right,'Destination coordinates',736,122,16);field(dest,'목적지 위도','입력한 위도',360);field(dest,'목적지 경도','입력한 경도',360);
 const api=row(right,'API controls',736,80,16);button(api,'경로 API로 길 불러오기','Secondary',430,name+'/calculate');button(api,'저장 경로 다시 보기','Quiet',290,name+'/replay');label(right,'현대 내비의 선택 경로와 별도로 계산합니다.','Caption','muted',736);
 spacer(right);label(right,'경로: OSRM · FOSSGIS / 지도 데이터 © OpenStreetMap','Caption','muted',736);
 const footer=row(s,'Return to preserved inputs',w,80,24);label(footer,'입력한 여정은 그대로 유지돼요.','Body','muted');const space=frame('Flexible footer','HORIZONTAL',1,1);footer.appendChild(space);fillWidth(space);button(footer,'여정 담기로 돌아가기','Primary',450,name+'/back');return s;
}
function fallback(name,x,y,theme,kind){
 const s=shell(name,x,y,830,theme),w=766;header(s,'정차 중',w,false);
 const copy={Loading:['이번 길의 모습을 준비해요','기본 눈티와 잠깐 기다려 주세요.','모습을 준비하는 중','Disabled'],Offline:['연결을 확인해 주세요','기본 눈티와 잠깐 기다려요.','다시 연결','Primary'],MissingRoute:['경로가 아직 없어요','길을 가져오거나 기본 모습으로 만나요.','기본 눈티 만나기','Primary'],AssetFailure:['모습을 불러오지 못했어요','기본 눈티와 함께해요.','눈티로 돌아가기','Primary']}[kind];
 const title=frame('Fallback title','VERTICAL',w,108);gap(title,8);s.appendChild(title);label(title,copy[0],'Title');label(title,copy[1],'Caption','muted');
 const body=card(s,'Canonical fallback',w,786,'soft');body.layoutSizingVertical='FILL';body.counterAxisAlignItems='CENTER';spacer(body);character(body,'Base',530);label(body,'눈티는 같은 자리에 있어요','Body','accent');spacer(body);
 const footer=row(s,'Fallback action',w,80,24);if(kind==='MissingRoute')button(footer,'경로 가져오기','Secondary',304,name+'/import');button(footer,copy[2],copy[3],kind==='MissingRoute'?438:w,name+'/action');return s;
}
note('05  /  정차 상태와 실패 대응','실제 API·차량 gate에 연결할 상태 설계. 아래 화면은 Figma 제안이며 production 변경이 아닙니다.',80,7260,7040);
for(const [i,kind]of ['Loading','Offline','MissingRoute','AssetFailure'].entries())fallback(kind+' / Day',80+i*930,7400,'Day',kind);
for(const [i,kind]of ['Loading','Offline','MissingRoute','AssetFailure'].entries())fallback(kind+' / Night',80+i*930,8800,'Night',kind);
routeTools('ROUTE_TOOLS / Day',4000,7400,'Day');routeTools('ROUTE_TOOLS / Night',5800,7400,'Night');
note('구현 경계와 차량 제한','주행 화면은 정적 제안입니다. 현재 에뮬레이터는 ACTIVE/D 상태에서도 플랫폼 차단을 표시합니다. 이 차단을 해제하거나 우회하지 않습니다.',4000,8800,3482);
note('상태 전환','생성 완료 → 자동 저장 → 함께하기 → ACTIVE/P → 차량 이벤트 D → 정적 주행 / 플랫폼 차단 → P → 여정 마치기 → 마지막 리포트',4000,9000,3482);
note('원본 재사용','승인 A PNG는 이미지 레이어로만 가져왔고 UI는 텍스트·Auto Layout·컴포넌트·변수로 구성했습니다. 화면 전체 이미지를 디자인 배경으로 사용하지 않았습니다.',4000,9200,3482);
note('정확한 데이터 범위','안목해변과 경로선은 검토용 입력입니다. 목적지·도로·기분은 명시 선택값입니다. 주행 피드백은 차량 데이터에서 오며 선택한 기분을 추론하거나 바꾸지 않습니다.',4000,9400,3482);
note('다음 구현 단계','WebView의 입력/결과, JourneyActivity의 주행/리포트에 각각 토큰을 적용합니다. 4초 모션은 기존 debug Canvas를 어댑터로 연결하며 서버 API는 재작성하지 않습니다.',4000,9600,3482);
return {createdNodeIds,screens,actions};
