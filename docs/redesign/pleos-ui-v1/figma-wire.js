// Concatenate after layout helpers. Also prefix main/compact/support ledgers.
const mutatedNodeIds=[],removedNodeIds=[],links=[];
function descendants(n){return [n,...n.findAll(()=>true)];}
async function link(fromId,toId){const n=await figma.getNodeByIdAsync(fromId);await n.setReactionsAsync([{trigger:{type:'ON_CLICK'},actions:[{type:'NODE',destinationId:toId,navigation:'NAVIGATE',transition:null}]}]);mutatedNodeIds.push(n.id);links.push({from:fromId,to:toId,trigger:'ON_CLICK'});}
for(const[theme,index]of [['Day',0],['Night',1]]){
 for(const small of [false,true]){
  const original=await figma.getNodeByIdAsync((small?compactLedger:mainLedger).screens['DRIVING_RESTRICTED / '+(small?'Compact / ':'')+theme]);
  const root=track(original.clone());page.appendChild(root);root.name='JOURNEY_PARKED / '+(small?'Compact / ':'')+theme;root.x=80+(small?3604:0)+index*(small?930:1802);root.y=10200;screens[root.name]=root.id;
  const headerState=root.findOne(n=>n.type==='TEXT'&&n.characters==='주행 중');headerState.characters='정차 중';
  const title=root.findOne(n=>n.type==='TEXT'&&n.characters==='이번 길도, 눈티와 함께');title.characters='눈티와 함께 출발해요';
  for(const t of root.findAllWithCriteria({types:['TEXT']})){if(t.characters.includes('00:38'))t.characters=t.characters.replace('00:38','00:00');}
  const footer=root.findOne(n=>n.type==='FRAME'&&['Optional single-step controls','Persistent primary controls'].includes(n.name));
  for(const n of [...footer.children]){removedNodeIds.push(n.id);n.remove();}
  if(small){
   const content=root.findOne(n=>n.type==='FRAME'&&n.name==='Compact content');const art=content.findOne(n=>n.type==='INSTANCE'&&n.name.startsWith('Approved Nunti'));art.resize(264,264);
   const optional=row(content,'Optional parked controls',718,80,16);button(optional,'음성 끄기','Secondary',270,root.name+'/mute');button(optional,'현대 내비 열기','Secondary',432,root.name+'/navigation');
   button(footer,'눈티로 돌아가기','Secondary',304,root.name+'/back');button(footer,'여정 마치기','Primary',438,root.name+'/finish');
  }else{
   button(footer,'눈티로 돌아가기','Secondary',320,root.name+'/back');button(footer,'음성 끄기','Secondary',240,root.name+'/mute');button(footer,'현대 내비 열기','Secondary',320,root.name+'/navigation');const sp=frame('Footer space','HORIZONTAL',1,1);footer.appendChild(sp);fillWidth(sp);button(footer,'여정 마치기','Primary',450,root.name+'/finish');
  }
  const ledger=small?compactLedger:mainLedger,suffix=(small?'Compact / ':'')+theme;
  await link(ledger.actions['PRE_TRIP / '+suffix+'/create'],ledger.screens['REVEAL_PARKED / '+suffix]);
  await link(ledger.actions['REVEAL_PARKED / '+suffix+'/new'],ledger.screens['PRE_TRIP / '+suffix]);
  await link(ledger.actions['REVEAL_PARKED / '+suffix+'/start'],root.id);
  await link(actions[root.name+'/finish'],ledger.screens['POST_TRIP / '+suffix]);
  await link(actions[root.name+'/back'],ledger.screens['REVEAL_PARKED / '+suffix]);
  await link(ledger.actions['POST_TRIP / '+suffix+'/back'],ledger.screens['REVEAL_PARKED / '+suffix]);
 }
 await link(mainLedger.actions['PRE_TRIP / '+theme+'/route-tools'],supportLedger.screens['ROUTE_TOOLS / '+theme]);
 await link(supportLedger.actions['ROUTE_TOOLS / '+theme+'/back'],mainLedger.screens['PRE_TRIP / '+theme]);
}
// Imported raster is the approved character only, never an app screenshot.
const baseUpload=await figma.getNodeByIdAsync('14:4');page.appendChild(baseUpload);baseUpload.name='Reference / Approved A canonical PNG';baseUpload.x=8900;baseUpload.y=2100;mutatedNodeIds.push(baseUpload.id);
page.flowStartingPoints=[{nodeId:mainLedger.screens['PRE_TRIP / Day'],name:'Nunti · Day · 1682px'},{nodeId:mainLedger.screens['PRE_TRIP / Night'],name:'Nunti · Night · 1682px'},{nodeId:compactLedger.screens['PRE_TRIP / Compact / Day'],name:'Nunti · Compact · 830px'},{nodeId:mainLedger.screens['DRIVING_RESTRICTED / Day'],name:'Static driving proposal · platform approval pending'}];mutatedNodeIds.push(page.id);
note('06  /  함께하기 후 · 정차 상태','함께하기는 여정을 시작합니다. 종료는 P/정차/UX 허용 상태의 여정 마치기 버튼으로만 요청합니다. 자동 도착 종료를 추가하지 않습니다.',80,10040,7040);
note('공식 원본과 Nunti 구성요소','오른쪽 원본은 Pleos Connect 2.1.5의 native component sets입니다. Nunti 화면은 이 버튼·입력·스위치·체크박스의 인스턴스에 브랜드 변수와 Noto Sans KR을 적용합니다.',8000,80,4800);
return {createdNodeIds,mutatedNodeIds,removedNodeIds,screens,actions,links,flowCount:4};
