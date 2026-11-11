# 눈티 Context v4 구현·검증 기록

2026-11-11. 대상은 Pleos Connect Android 앱 `ai.nunti.avatar.demo`다. 기존 팀원의 `ScoreEngine` 계산식과 TTS 기능은 변경하지 않았다. 실행 순서는 [기능 확인 방법](CONTEXT_V4_TRY.md)에 있다.

## 여섯 요구사항

| 요구사항 | 구현 결과 | 확인 자료 |
| --- | --- | --- |
| 상황별 외형 | 목적지, 방문 목적, 명시적 기분, 풍경, 도로, 경로 모양을 입력으로 OpenAI 이미지 편집을 호출한다. 원본 얼굴과 실루엣을 유지하는 정장·의사복·축구복을 생성했다. 동일 입력과 버전은 저장된 결과를 재사용한다. 기본 눈티에서 새 옷으로 변하는 기존 네이티브 연출에 연결했다. | `artifacts/nunti-context-v4/wardrobe/` |
| 실제 표정 | 얼굴 영역의 메시와 별도 눈꺼풀 레이어로 눈·눈썹·입을 변화시킨다. 눈 깜빡임이 입을 찌그러뜨리던 문제를 수정했다. 주행 이벤트의 걱정·안도 상태는 사용자가 고른 기분과 별도로 처리한다. | `final-ui/02-face.mp4`, `final-ui/frames/face-contact.png` |
| 상호작용 | 주차 상태에서 호흡, 시선, 눈 깜빡임, 터치 시 웃음·윙크·고개 반응을 제공한다. 앱의 움직임 줄이기와 시스템 애니메이션 설정을 반영한다. | `final-ui/reduced-motion.json` |
| 주행 리포트 | 총점, 수신 데이터의 평가 범위, 항목별 기준, 좋은 습관, 개선할 습관, 시간·속도 근거, 경로상의 이벤트 위치를 표시한다. 실제 GPS와 시뮬레이션 좌표를 구분한다. | `runtime-demo-2/verification.json`, `runtime-live-3/verification.json` |
| UI | 출발 전 입력폼, 캐릭터 결과, 주행 리포트의 정보 순서와 간격을 정리했다. Noto Sans KR와 주야간 색상을 적용했다. 1682×1210 및 830×1210 앱 창에서 확인했다. | [Figma A안](https://www.figma.com/design/LHLHBra8ON3OdVW0qhBnbm?node-id=65-5), `figma-report-final.png`, `final-gates/` |
| Pleos 점검 | 공식 가이드와 구현을 대조하고, 실제 D/P 전환·화면 제한·위치 권한·주야간·좁은 창을 확인했다. 아래에 확인 범위와 남은 심사 항목을 구분했다. | `final-gates/`, `runtime-live-3/` |

위 표의 짧은 자료 경로는 모두 `artifacts/nunti-context-v4/` 아래다. Figma에는 크림색 A안과 짙은색 B안을 남겼으며, 현재 앱의 크림색 방향에 맞춰 A안을 구현 기준으로 사용했다. Figma의 경로 그림은 화면 구성용 예시이고 앱은 기록된 좌표를 그린다.

## 생성 비용과 자산 경계

- 모델은 `gpt-image-2.5-sunburst`, 1024×1024 medium 1장이다. 원본 참조 이미지를 함께 보내고 768×768 RGBA PNG로 저장한다.
- 세 번의 실제 API 응답에 따른 비용 추정 합계는 **$0.069086**이다. OpenAI 청구서의 확정 금액은 아니다.
- 중복을 제외한 시도마다 **$2를 먼저 예약**한다. 실패나 시간 초과에도 예약을 돌려주지 않는다. 현재 예약 $6, 남은 예약 예산 $24, 총한도 $30이다. 자동 재시도는 없다.
- 비공개 키는 `.local/credentials/openai-api-key`에 0600 권한으로 저장한다. 서버에서만 읽으며 실제 APK에 키가 없음을 검사했다. 이 파일은 Git에서 제외된다.
- 외부 이미지 요청에는 방문 목적·분위기와 정규화한 경로 모양을 보낸다. 원시 GPS와 목적지 이름은 보내지 않는다.
- `MOCK_SKIN_MODE`는 유지한다. 사용자에게 허가받은 `/v3/wardrobe`만 기존 제한에서 예외 처리한다. 생성 결과의 `humanQualityApproved`는 `false`이며, 자동으로 승인 자산으로 승격하지 않는다.
- 각 결과 JSON에는 소유자, 모델, 원본 해시, 프롬프트, 버전, 출력 규격, 이용 조건 메모와 사용량이 있다. 로딩 실패 시 기본 눈티와 안내 문구를 표시하고 저장된 원본은 보존한다.

## 주행 기록과 점수

`JourneyAnalysis`가 팀원 점수 엔진의 결과에 위치와 설명을 더한다. 급회전은 20 km/h 이상에서 핸들 변화량 100°/s 이상을 참고 이벤트로 기록하며 **총점에는 반영하지 않는다**. 기준은 실험용이며 공식 운전 등급이 아니다. 수신하지 못한 항목은 좋은 습관으로 평가하지 않는다.

Pleos FusedLocation 1.1.3의 콜백을 사용한다. 권한이 없거나 좌표가 없으면 해당 위치를 기록하지 않는다. 3초 이상 지난 위치와 유효하지 않은 값은 버린다. 경로를 수신하지 못한 구간에 가짜 이벤트 핀을 만들지 않는다.

| 실행 | 관측 결과 |
| --- | --- |
| 운전 습관 연습 | 151개 샘플, 압축 재생 약 27초, 기록상 2분 30초, 1.503 km, 79.74점. 급가속·급제동·급회전·회전 전 감속 부족 4개 이벤트와 좋은 습관·개선할 습관을 확인했다. |
| 버추얼 콘솔 + GPS 재생 | 실제 SDK의 속도·기어·핸들 값을 수신했다. 서울 경로를 따라 전달한 GPS에서 서로 다른 18개 WGS84 위치와 이벤트 위치를 확인했다. 물리적인 차량 주행 시험은 아니다. |
| 신호 방향 | 콘솔의 +160°가 SDK에서 -160°로 전달됐다. 급회전 판정은 변화량의 절댓값을 사용한다. |

실행 후 콘솔 설정, 기어, 주야간 모드, 화면 크기와 원래 GPS를 복원했다.

## Pleos 규격 대조

| 점검 항목 | 결과 |
| --- | --- |
| 주행 중 장식 애니메이션·조작 | 변신·대기 동작·터치 놀이를 주차 상태로 제한한다. `CarUxRestrictions`를 우회하지 않았다. 현재 에뮬레이터에서는 D단에 진입하면 플랫폼이 앱 화면을 차단한다. 차단 중 기록은 계속되며 P단 복귀 후 확인할 수 있다. |
| 화면 제한의 실제 효과 | 30 km/h에서 상세 화면이 닫혔다. 2초 간격의 앱 영역 이미지가 동일했다. 네이티브 코드의 정적인 주행 표정은 구현돼 있으나, 이 에뮬레이터의 플랫폼 차단 화면 위에 표시되지는 않는다. |
| 멀티윈도·플랫폼 영역 | 넓은 창과 830 px 창에서 입력폼·결과·리포트와 고정 하단 버튼을 확인했다. 좁은 입력폼의 문서 폭과 창 폭은 모두 830 px다. 플랫폼 내비게이션과 차량 정보 영역은 변경하지 않았다. |
| 색·글자 | 주야간 주요 텍스트/배경 조합 24개의 대비가 모두 4.5:1 이상이다. 최저값은 4.96:1이다. 본문·버튼 글꼴과 행간을 통일했다. |
| 접근성·처리 대기 | 기본 입력 요소와 버튼 이름, 터치 반응, 움직임 줄이기를 적용했다. 생성 중 상태와 실패 안내를 표시한다. 화면 읽기 도구로 전체 흐름을 탐색하는 시험은 수행하지 않았다. |
| 위치 권한·미수신 | 공식 `pleos.car.permission.FUSED_LOCATION`을 선언하고 주차 상태에서 권한을 요청한다. null·오류·오래된 위치를 처리한다. 차량 개인정보 설정에 의한 차단 및 공식 `showLocationAccessBlockedPopup()` 연결은 추가 확인 항목이다. 현재 일반 오류 상태와 위치 누락은 처리하지만 전용 차단 팝업은 연결하지 않았다. |
| 성능 | 녹화 없이 측정한 대기 애니메이션 460 프레임 중 jank 8개(1.74%). 이 에뮬레이터에서 측정한 수치이며 기기 성능 보장은 아니다. 앱 PSS는 약 160 MiB였다. 원본 CPU·프레임·메모리 기록을 보관했다. |
| 배포 심사 | 공식 디스플레이의 물리 글자 크기, 차량별 동작, 앱 분류와 마켓 심사는 별도다. 기존 서비스의 `mediaPlayback` 분류도 배포 심사 때 확인해야 한다. 규격 전체 준수나 심사 통과를 판정하지 않았다. |

이번 점검에서 확인한 주행 중 애니메이션, 화면 겹침, 위치 미수신 처리 문제는 위와 같이 제한하거나 수정했다. 개인정보 설정 차단 전용 팝업은 남아 있는 SDK 안내 연결 항목이다.

## 검증 자료

- Debug·Release 빌드와 `lintDebug` 성공. Lint 오류 0개, 경고 50개. 기존 경고를 포함하므로 경고 없는 빌드로 표시하지 않는다.
- 점수 모듈 단위 테스트 21개, 의상 생성 백엔드 테스트 6개 통과.
- `runtime-demo-2/verification.json`: 실제 앱 입력폼의 캐시 재사용, 네이티브 캐릭터, 시뮬레이션, 리포트 통과.
- `runtime-live-3/verification.json`: 버추얼 콘솔과 FusedLocation 연결 통과. 앞선 실행의 핸들 부호 가정과 화면 복귀 경로를 고친 뒤 얻은 결과다.
- `final-ui/05-score-basis.png`: 항목별 평가 근거. `final-ui/03-art-fallback.png`: 이미지 실패 대체 화면.
- `final-ui/02-face.mp4`: 최종 눈꺼풀 수정 후 표정 영상. `final-ui/idle-cpu.txt`, `final-ui/idle-performance.txt`, `runtime-demo-2/memory.txt`: 성능 원본.
- `final-gates/static-driving.json`, `compact-layout.json`, `restoration.json`: 화면 제한·폭·설정 복원.
- `key-boundary-check.json`: 키 파일 권한과 APK 제외 확인.

## 참고한 공식 자료

- [Pleos UI 디자인 가이드](https://document.pleos.ai/en/docs/connect/guide/docs-design/Introduction/intro): 주행 중 동작, 대비, 글자, 주야간, 멀티윈도 기준.
- [Pleos 운전자 주의 분산 심사 가이드](https://document.pleos.ai/en/docs/pleos-only/distribute/app-review-guide/review-driver-distraction-elements): 주행 중 화면 제한과 심사 범위.
- [Pleos FusedLocation 권한](https://document.pleos.ai/en/docs/pleos-only/connect-sdk-pleos/FusedLocation/declaring-permissions), [오류 처리](https://document.pleos.ai/en/docs/pleos-only/connect-sdk-pleos/FusedLocation/error-handling), [공식 샘플](https://github.com/Pleos-Playground/pleos-sample-fusedlocation-app).
- [Android 차량 인터랙션 원칙](https://developers.google.com/cars/design/design-foundations/interaction-principles): 간단한 조작과 정보 순서.
- [Strava 활동 기록](https://support.strava.com/en-us/articles/15401981-viewing-activities): 경로·수치·상세 기록의 분리.
- [OpenAI 이미지 생성](https://developers.openai.com/api/docs/guides/image-generation), [가격](https://developers.openai.com/api/docs/pricing): 이미지 편집과 사용량 기반 비용 추정.
