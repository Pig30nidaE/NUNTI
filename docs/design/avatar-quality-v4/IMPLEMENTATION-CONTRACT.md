# 눈티 v4 품질 개선 공통 작업 계약

2026-11-03. 사용자 승인 범위는 조사 기반 외형·연관성·탄생효과 개선과 실제 테스트. **과금되는 외부 API는 사용자 승인 전 호출하지 않는다.** 별도 키 없이 제공된 내장 image_gen 도구로 개념 원화를 만든다. 녹화·음성녹음 금지. 기존 v2/v3 소장품·캐릭터 identity 보존. 기능 검사와 인간 미적 승인을 구분한다.

## 디자인 기준

최신 사용자 피드백은 **A/B/C의 형태는 모두 괜찮지만 너무 입체적이고 반투명하다**는 것이다. 이전 C 반투명 표현보다 이 교정을 우선한다. 형태는 유지하며 **불투명 파스텔 색면·매트 표면·얕은 2.5D 깊이의 일러스트**로 바꾼다. alpha는 캐릭터 바깥 배경에 쓰고 몸은 주로 불투명하다. 유리 반사·굴절·강한 광택과 사실적인 3D 토이 느낌을 줄인다.

첫 비교는 동일한 해변/휴식 여정의 구조적으로 다른 세 원화. 목표지·경로에서 큰 구조가 바뀌며 색/배의 선/작은모자만 바꾸는 것으로 끝내지 않는다. 새여정 variation은 세부 표현에 사용하고 route/destination 의미와 분리한다. 경로의 사실적 원본과 창작된 외형은 별도로 보관.

## 담당과 파일 소유

- root: 내장 image_gen 원화/참조 이미지, docs/design/avatar-quality-v4, 최종 QA/앱 실행/문서/실행 도구.
- image/renderer 담당: backend/nunti/avatar_studio/illustration.py 및 새 design_intent.py, backend/tests/test_avatar_illustration.py 및 test_avatar_design_intent.py. route geometry→semantic shape plan→새 로컬 RGBA와모션기하. 고정 AI PNG를 매여정 새AI생성이라 재사용 금지.
- server/API 담당: backend/nunti/avatar_studio/image_api.py 및 필요한 api.py/models.py, backend/tests/test_avatar_studio.py 및 test_avatar_image_prompt.py. 새 구조참조·목적지 근거·스타일참조분리, 상세prompt로 실제API어댑터향상. 유료호출0. 비용승인환경없으면API모드기본꺼짐.
- motion/UI 담당: prototypes/avatar_generator/studio.js, studio.css, 선택 추가 formation.js 및 index.html script태그. 경로가움직여 실제실루엣/부피로부푸는기하변형. 완성PNG단순공개로대체하지않기. 이전소장품은그대로표시.

## 안정된 호환 경계

render_avatar(points, destination, traits, purpose, journey_id) -> (png_bytes, design_dict) 공개함수는 유지. displayName/personality/palette/motifs/voice/routeThread 기존필드도 유지한다.

추가 design 필드:
- designVersion: 'journey-form-2'
- visualIntent: {destinationTheme, purposeMood, evidence:[{source,detail,target}], routeFeatures:{...}, variationRole:'FINE_DETAILS_ONLY'}; 모든추정과명시입력분리.
- formation: {version:'route-volume-2', contour:[[x,y],...], spine:[[x,y],...], faceCenter:[x,y], palette:[hex,...]}. 좌표는완성768PNG의0..1공간, contour는실제몸체닫힌외곽 128~256점, spine은몸의흐름이된경로64~128표본(원본routeThread와별개). 그래픽표면/얼굴/장식이포함된최종image로안착.

renderer 담당은 빠르게 formation 개략시그니처를 motion담당에게 알려준다. motion담당은없는metadata를꾸미지않고oldartifact전용표시흐름유지.

## 유료 실행과 원화 승인

사용자 응답은 **원화 선택 후 결정**이다. 유료 API는 보류이며 승인으로 간주하지 않는다. 세 초안의 형태가 괜찮다는 평가도 최종 재질·모션·전체 디자인 승인과 구분한다. 내장 image_gen 도구의 v2 편집은 위 재질 피드백을 적용한다.

## 검증

동일입력/요청재시도stable. 같은variationseed로 route만 바꾼쌍·destinationtraits만바꾼쌍에서 geometry/semantic evidence가달라짐. 새journey의미세변화도실제입력의semantic구조를깨지않음. PNGalpha와SHA유지. 실제route→volume 기하중간프레임0/.25/.5/.75/1을정지화면으로검토. 차량gate·사진확인·collection/idempotency회귀유지. 외부API테스트는대역만; 유료생성은승인후에만.

## 무료 로컬 AI 선택 모드 추가 계약

M4 16GiB에서 공개 MLX Community FLUX.2-Klein-4B 4bit 모델의 offline multi-reference 추론을 실제 실행했다. 모델4.62GB/512RGB/4step/약42~49초/Peak MLX3.49GB. 첫 inset문제는inset입력을제거해개선했고 garden얼굴가림은실패로기록한다. 품질문제를숨기지않고독립실험과production모드를구분.

- 추가 renderMode/mediaOrigin `LOCAL_MODEL`. 유료승인과독립된선택모드. runner `--local-ai`가설치된공개모델만offline으로연결. 기존빠른 `LOCAL_RENDER`와 `IMAGE_API` 보존.
- API/로컬모델 담당: `local_model.py` 추가와 api.py/models.py/tests 연결. modelbinary/weights경로는허용된workspace내설정만, HF_OFFLINE/implicit_token_disabled, credentials 미복사, shell=False, 동시추론1개, timeout/출력검사. 승인styleA2+no-inset구조참조, face앞면·두눈명시. 원본RGB·실행정보·참조SHA 보관.
- renderer 담당: `matte_cutout.py`와test만추가. 외곽배경만제거→진짜RGBA, 원본RGB바이트별도유지. 다수큰객체·잘못된배경은거절하고조용히인셋제거로오류숨기지않는다. 실제PNG alpha에서닫힌contour128~256를추출하고route를bbox에기하투영한spine64~128·faceCenter heuristic 여부·palette반환. source='MEASURED_ALPHA_BOUNDARY', mapping='GEOMETRIC_PROJECTION_NOT_SEMANTIC'. 가정된얼굴은face보호사실로표시하지않음.
- motion담당: LOCAL_MODEL의실제alpha에서준비한formation을소비할수있게변경. 버전 route-volume-2는호환사용하되source를명시. 얼굴위치미확정이면중간얼굴patch를건너뛰고마지막원본을표시. 모델PNG를로컬원형기하로가정하지않는다. UI 선택에'로컬AI · 약1분'과origins/모티브검증상태를구분. 유료API가보이지않아도이모드선택가능. old14UI회귀는빠른LOCAL_RENDER를명시하여성능테스트와분리.

서버capabilities.localImageModelAvailable bool과 localImageModelInfo {engine,model,offline:true,observedSeconds,paidApiCalls:0}. 로컬AI는artifact.visual의실제512PNG/SHA사용. provider메타는로컬모델커밋/seed/steps/원본SHA/후처리버전을기록. localmodel생성에정확경로·귀여움·소장효과검증완료를주장하지않음.
