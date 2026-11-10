// Concatenate after helpers; existing screen ledgers are provided separately.
const links=[],mutatedNodeIds=[];
async function overlay(fromId,toId){const n=await figma.getNodeByIdAsync(fromId);await n.setReactionsAsync([{trigger:{type:'ON_CLICK'},actions:[{type:'NODE',destinationId:toId,navigation:'OVERLAY',transition:null}]}]);mutatedNodeIds.push(n.id);links.push({from:fromId,to:toId,kind:'OVERLAY'});}
async function close(id){const n=await figma.getNodeByIdAsync(id);await n.setReactionsAsync([{trigger:{type:'ON_CLICK'},actions:[{type:'CLOSE'}]}]);mutatedNodeIds.push(n.id);}
function options(name,x,y,theme,engine){
 const s=shell(name,x,y,830,theme),w=766;header(s,'정차 중',w,false);
 const title=frame('Options title','VERTICAL',w,108);gap(title,8);s.appendChild(title);label(title,engine?'눈티의 모습을 만드는 방식':'여정 옵션과 작은 이야기','Title');label(title,engine?'선택한 방식으로 같은 입력을 이어가요.':'준비된 그림과 목소리로 함께 출발해요.','Caption','muted');
 const body=card(s,'Existing options',w,786,'surface',24);body.layoutSizingVertical='FILL';
 if(engine){
  label(body,'현재 선택','Caption','muted');choice(body,'기본 눈티 A · 모습 조합',true,718);label(body,'경로·목적지 유형·직접 고른 기분을 반영해요.','Caption','muted',718);
  button(body,'빠른 일러스트','Secondary',718,name+'/local-render');button(body,'로컬 AI · 현재 사용할 수 없음','Disabled',718);button(body,'AI 이미지 · 현재 사용할 수 없음','Disabled',718);
  label(body,'사용할 수 있는 방식만 선택할 수 있어요.','Body','muted',718);spacer(body);status(body,'입력한 목적지와 경로는 그대로 유지돼요',718);
 }else{
  label(body,'여정에 사용할 신호','Caption','muted');const source=row(body,'LIVE and DEMO selector',718,76,16);choice(source,'실시간 차량 신호',true,351);choice(source,'시험 시나리오',false,351);
  label(body,'시험 시나리오는 실제 운전 기록과 구분해요.','Caption','muted',718);
  button(body,'이 눈티의 주행 음성 준비','Secondary',718,name+'/prepare-voice');status(body,'음성이 준비되지 않아도 출발할 수 있어요',718);
  button(body,'진행 중인 여정 · 마지막 리포트','Secondary',718,name+'/previous-journey');
  label(body,'이 눈티가 담은 이야기','Heading');label(body,'길게 이어진 고속도로의 패턴,\n바다의 물결과 직접 고른 호기심을 담았어요.','Body','muted',718);
 }
 const footer=row(s,'Close options',w,80,24);button(footer,'닫기','Primary',w,name+'/close');return s;
}
note('07  /  기존 옵션 보존','기본 생성 방식 변경·유료 호출을 실행하지 않습니다. 이 페이지는 현재 API와 bridge에 연결할 편집 가능한 옵션 UI입니다.',80,11540,7040);
for(const[theme,index]of [['Day',0],['Night',1]]){
 const journey=options('JOURNEY_OPTIONS / '+theme,80+index*930,11700,theme,false),engine=options('GENERATION_OPTIONS / '+theme,2080+index*930,11700,theme,true);
 await close(actions[journey.name+'/close']);await close(actions[engine.name+'/close']);
 for(const small of [false,true]){
  const ledger=small?compactLedger:mainLedger,suffix=(small?'Compact / ':'')+theme;
  const story=await figma.getNodeByIdAsync(ledger.actions['REVEAL_PARKED / '+suffix+'/story']);story.setProperties({'Text#23417:0':'여정 옵션 · 이야기'});story.name='Action / 여정 옵션 · 이야기';mutatedNodeIds.push(story.id);
  await overlay(story.id,journey.id);await overlay(ledger.actions['PRE_TRIP / '+suffix+'/engine'],engine.id);
 }
 // The existing previous-journey action chooses ACTIVE or latest report at runtime.
 const previous=await figma.getNodeByIdAsync(actions[journey.name+'/previous-journey']);await previous.setReactionsAsync([{trigger:{type:'ON_CLICK'},actions:[{type:'NODE',destinationId:mainLedger.screens['POST_TRIP / '+theme],navigation:'NAVIGATE',transition:null}]}]);mutatedNodeIds.push(previous.id);
}
return {createdNodeIds,mutatedNodeIds,screens,actions,links};
