# Nunti 구현 및 작업 상태

사용자 지속 선호: 사용자가 명시적으로 종료를 요청할 때만 관련 로컬 서버·AI 모델 프로세스·에뮬레이터·VSCode를 정상 종료한다. 작업이나 검증이 끝났다는 이유로 자동 종료하지 않는다. 미저장 편집을 강제로 폐기하지 않는다. 이 규칙 자체를 실제 종료 완료의 증거로 보고하지 않는다.

2026-11-04 최신: [눈티 v6 구현·검증](../design/avatar-v6/RESULT.ko.md)을 우선한다. 목적지·방문 이유를 의상·큰 기념 가방·목적별 탄생 연출·Qwen3-TTS 새 음성으로 연결했다. 빠른 일러스트 200·실제 WAV 200, 로컬 AI 30상황(최초30+수리7=37추론), 최종 Android Canvas 920회, UI 23개 및 별도 새 AI·어린 독서 캐릭터 음성의 앱 통합 32개 검사를 완료했다. AI의 핵심 의상·장소 기준은 선택본30/30이지만 활동 부소품은 명확16·부분9·누락5, 동물형4개 불확실로 남긴다. TTS 전사상 청취 검토28개, 사람의 소장 의향·Anna 동등 품질·운전습관 효과는 미검증이다. 원본 실패와 모든 시도는 보존했다. [실행 안내](../design/avatar-v6/TESTING.ko.md)를 따른다. 유료 API·녹화0, 주행 이벤트·점수 연결은 별도다. 아래 상태는 각 시점의 이력이다.

2026-11-04 최신: [사진 없는 내비 API 연결](../design/navigation-integration/RESULT.ko.md)을 구현했다. 실제 NaviHelper 3.0.5의 목적지·현재 위치·상태 콜백, 별도 OSRM 전체 도로 경로, 확인 후 생성, 저장 계획·눈티 복원을 연결했다. Android 3여정 23개 검사·UI 상태 회귀 8개·백엔드 260개와 10 subtests·debug/release/lint 통과. 내비 화면에서 정상 런처 복귀 시 SDK 세션·표시 눈티·이미지·음성 설정 보존도 통과했다. 실제 API 해변 경로로 무료 로컬 AI 새 그림을 44.2초에 만들고 Android 복원까지 검증했다. GPS 3점 주입·읽기·전체 상태 복원·기존 눈티 보존은 완료했지만 SDK의 동적 위치 반영과 재탐색 완료 콜백은 미검증이다. 현대 원경로 polyline 획득·OSRM과의 일치·새 TTS 음색·실차·소장 품질·습관 개선 효과도 미검증 또는 미구현이다. [직접 시험](../design/navigation-integration/TESTING.ko.md): `python3 scripts/run_avatar_generator.py --local-ai --navigation-api --restart-server`. 외부 키·유료 호출·사진 추출·영상/음성 녹화 0. 아래 내비 어댑터 미구현 설명은 이전 조사 시점의 기록이다.

2026-11-04 내비 검토: 전체는 운전습관 개선을 돕는 눈티이며 사용자 담당은 목적지·경로 기반 생성, [제품 기준](../product/2026-hmg-app-challenge.md)을 유지한다. [실제 내비·SDK 조사](../research/2026-11-04-navigation-review/README.md)에서 더현대서울27km/30분 탐색을 확인했다. SDK routePoints는 경유·목적지 요약점이고 전체도로polyline이 아니다. SDK callback/adapter는 미구현·미검증. 실제사진15점은부분·대안경로를오선택해확인도구보강필요. 다음은NaviHelper메타데이터연결→선택전체경로·시작끝확인→생성시험이며GPS재생은별도다. production앱변경·새아바타·유료호출·녹화0.

2026-11-04 최신: 운전습관 개선을 돕는 눈티 안의 사용자 담당은 목적지·경로 기반 생성이며 [제품 기준](../product/2026-hmg-app-challenge.md)을 유지한다. 결과 표시와 보관함 갱신 사이에서 사진 업로드가 유실되는 버그를 [재현·수정](../design/avatar-quality-v5/PHOTO-UPLOAD-FIX.md)했다. 전체 7단계 직접 실행 완료: 경계15·Chrome15·Android15·저장AI14·실제Canvas7개35자세 통과. 추가AI추론·유료호출·녹화0. 이전 승인 검토 장애는 화면 검사에 대해 해소됐으며 아래 미실행 설명은 당시 기록이다. 정원 추가AI와 미적 최종승인은 별도다.

2026-11-03 최신은 [v5 깨끗한 표면·풍성한 효과](../design/avatar-quality-v5/README.md)다. 전체 목표는 운전습관 개선을 돕는 눈티이고 사용자 담당은 목적지·경로 기반 생성이며 [제품 기준](../product/2026-hmg-app-challenge.md)을 유지한다. 몸 표면의 경로·색띠와 AI 구조 참조의 축선을 제거하고, 오로라·별가루 탄생과 새 스타일을 적용했다. 실제 새 해변 AI1건44.56초·backend246+하위10·빠른PNG6개30자세 Canvas 통과. 추가 정원과 최신 화면 회귀는 승인 검토 시간 초과·용량 오류로 실행 전 차단돼 사용자가 수동 승인했지만 이후 두 차례도 검토 서비스 용량 오류로 실행 전 차단됐다. 유료 API0·녹화0, 최종 미적 승인·습관 효과는 미검증이다. 아래 v4는 이전 기록이다.

2026-11-03 v4 후속: 전체 목표는 운전습관 개선을 돕는 눈티이며 사용자 담당은 목적지·경로 기반 생성이다. [제품 기준](../product/2026-hmg-app-challenge.md), [v4 결과](../design/avatar-quality-v4/README.md)를 우선한다. 사용자는 A2/B2/C2의 불투명 파스텔·얕은 매트 2.5D 표현을 적절하다고 평가했다. 로컬 코드 렌더·AI 결과·모션 전체의 소장 품질 승인은 남았다. 유료 API는 원화 선택 후 결정으로 보류, 실제 호출 0회다. 무료 로컬 모델의 실제 결과와 실패는 v4 보고에 남긴다. 아래 조사는 당시 기록이며 앱 변경이 없었다는 설명을 후속 구현에 적용하지 않는다.

2026-11-03 최신 디자인 판단: 사용자는 현재 일러스트·탄생 효과의 소장 매력과 경로·목적지 연관성이 부족하다고 평가했다. 아래 v3 기능 검사 통과를 디자인 승인으로 읽지 않는다. [인터넷 조사·스킬·다음 비교 기준](../research/avatar-art-direction-2026-11-03/README.md)을 우선하며, 같은 여정의 정지원화 세 안을 비교한 뒤 선정 외형의 모션을 설계한다. 이번 조사는 앱 변경·새 생성·설치를 하지 않았다.

사용자 작업 규칙: 동영상 녹화와 스피커 음성 녹음은 사용자가 명시적으로 요청한 경우에만 실행한다. 일반 구현·회귀 검증에는 녹화를 추가하지 않는다.

2026-11-03 제품 목표는 **운전습관 개선을 도와주는 아바타 눈티**다. 사용자 담당은 그 안의 **목적지·내비게이션 경로 기반 아바타 생성 기능**이다. 생성한 정체성·외형·음색을 주행 이벤트에 따른 감정·음성 피드백 모듈에서 사용한다. [제품 목표·담당 범위·공모전 기준](../product/2026-hmg-app-challenge.md)을 우선한다.

2026-11-03 후속 구현은 [아바타 생성기 v3](../design/avatar-generator/README.md), [직접 시험 안내](../design/avatar-generator/TESTING.ko.md), [통합 검증](../design/avatar-generator/test-report.md)을 따른다. 경로 사진·좌표 입력과 명시 확인, 새 로컬 768² RGBA 생성, 실제 금빛 실 좌표에 연결된 탄생 모션, 입력과 외형의 대응, 이미지와 독립된 기기 음성 미리 듣기, 소장·복원을 구현했다. Android main 호스트는 Debug·release 공통이며 실제 Car service의 주차·화면 사용 허가를 적용한다. 선택 이미지 API는 별도 한 키 어댑터다. 실제 API·새 음색·NaviHelper·Gleo·실차·배포·개선 효과는 미검증 또는 미구현이다. 아래 v2와 연출 보고는 이전 기록이다.

2026-11-03 후속 연출은 [경로가 몸체가 되는 탄생 연출](../design/generative-mvp/route-formation.md)을 따른다. 로컬 세 안을 비교해 A 리본 방식을 적용했다. 같은 경로 점→실제 이미지 알파 폭의 리본→같은 붓으로 표면 공개를 연결하고, 준비 전 진행값 0과 원본 알파 단일 합성을 보장한다. 최종 앱 회귀는 녹화·녹음·스크린샷 저장 없이 통과했다.

2026-11-03 최신 기준은 [생성 동반자 v2](../design/generative-mvp/README.md)와 [시험 안내](../design/generative-mvp/TESTING.ko.md)다. SERVER는 v2 작업·별도 소장품 저장·공급자 어댑터·인증 미디어·예산·동일 본문 재사용을, AVATAR는 완성 RGBA의 경로 공개·전체 움직임을, TTS는 DesignedVoice/manifest3·설치 전 전체 WAV 검증·queue를 보존한 대사 추가를 구현했다. PM은 Android 입력·다운로드·듣기·도착·보관·복원과 실행/검증 도구를 연결했다. 실제 Pleos API34에서 샘플의 입력·경로 터치·재생·후속 대사·중지·foreground·cold restore를 검증했다. API 계정·새 이미지/음색의 한국어 품질·실제 단가·사람의 소장 의향은 미검증이다. 초기20개는 비교 표본이며 고정 캐릭터 카탈로그가 아니다.

이전 절차적 생성 흐름은 [목적지·경로 시험본](../design/route-birth/test-report.md)에 보존한다. 새72점 외형·로컬 Sohee·5여정/15WAV는 당시 완료 범위다. 아래 현황은 각 시점의 과거 기록이며 최신 v2의 완료·미검증 구분을 덮지 않는다.

2026-11-02 TTS 후속 완료. [최신 PM 결과·시험 가이드](../design/journey-characters/tts-result.md)와 [TTS 구현 보고](../design/journey-characters/tts-implementation.md)를 먼저 읽는다. F3/F4/F5 기반 v2 실제 합성·6개 WAV·Android Debug catalog/player·단일 큐 연결을 구현했다. 기존 62+연동8, 새 로컬26+실제WAV6, Android 컴파일·debug/release/lint와 실제 emulator 재생·정지·background·중복·D 취소/P 복귀 이벤트를 확인했다. 인증 PCM3개와 원본 대조도 보존했다. 취소 후 추가 신호의 출처·정확한 무음 지연, 사람의 한국어 품질·귀여움은 미검증이다. 아래 전역 기본 음성·오디오 OFF·환경 부재·D 미검증은 각 시점의 과거 기록이며 현재 판정을 덮지 않는다.

2026-11-02 사용자 요구 변경: 목적지·주행경로·목적지 특성·방문 목적에서 매 여행 새 2.5D 캐릭터를 만들고 캐릭터별 음성을 보존한다. 아트 방향은 사용자가 선택한 C · 반투명 기념 오브젝트다. [최신 설계·완료 구분](../design/journey-characters/README.md)과 [레시피 실험](../../prototypes/journey_characters/README.md)을 먼저 읽는다. 시안·프로토타입·세 담당 제안은 완료했지만 실제 이미지 생성·다형 renderer·캐릭터별 TTS·컬렉션 제품 연결은 미구현이다. 아래 고정 identity·전역 기본 화자는 현재 구현 사실을 설명하며 후속 제품 요구를 제한하지 않는다. 외부 payload·담당 조율은 보류한다.

새 로컬 후속 결과는 [2026-11-02 PM 복원 보고](restoration/2026-11-02/PM.md)를 따른다. 원격 main `ebde902`에서 세 독립 worktree와 도구를 복원했고 기존 자동 검사·APK·lint·release를 재현했다. 공식 Console 브라우저 세션 유지로 DDS·gear 준비를 활성화해 실제 에뮬레이터 P→D·속도→P, 표시 차단·복귀, D 전환 TTS 취소를 새로 확인했다. 새 PCM·청취·실차·운영 E2E는 미검증이다. 아래 본문은 인수인계 당시 구현·과거 검증 범위를 보존한 기록이며, 당시 D 전환 차단은 후속 보고와 구분한다.

2026-11-02, Asia/Seoul 기준. 구현 스냅샷은 `bc0a9483d4baaefee397635dd3dc01fe2b7f4b3e`, 기존 통합 브랜치는 `server/integration-v1`이다. 기능 변경 없이 담당 보고, 코드, 저장된 검사 결과를 대조한 인수인계 기록이다.

## 프로젝트와 현재 도달점

눈티는 경로 특징에 따라 외형이 달라지고 검증된 주행 이벤트에 반응하는 가상 동승자다. 앱이 아바타·감정·발화 허가를 로컬에서 결정하고, 서버는 사용자가 동의한 기록을 비동기로 저장한다. 서버 연결과 동의 여부가 로컬 반응을 차단해서는 안 된다.

| 영역 | 구현된 범위 | 남은 범위 |
| --- | --- | --- |
| 아바타 | 경로 근거 검증, 특징 추출, 후보 평가·제약, 결정적 생성, 복원, Compose 렌더링 | 실제 NaviHelper 입력·GIS 근거, 최종 디자인 자산·rig, 사용자 평가 |
| 감정 | 6종 reducer, 검증·신뢰도·시간·중복·incident·역순 처리, 유지·회복·만료, journal | 실제 운전 이벤트 공급, 앱의 영속 inbox 및 production host |
| TTS | 계약 변환, 원문 보존, 음성 프로필, 허가 정책, 큐·TTL·중복·취소, lifecycle·포커스, 실제 Pleos 어댑터 | 한국어 청취·첫 음절·선행 묵음·가청 지연, 감정 음향 제어, 실차·장기 시험 |
| 서버 | FastAPI·SQLite, 인증·동의·보존기간, 저장·조회·삭제, 멱등성·충돌·배치 원자성 | Android HTTP client/outbox, 운영 인증·배포·백업 복원·부하 시험 |
| Android 앱 | 일반 Android Mock 뷰어, Debug 전용 Pleos 진단 화면, DTO bridge | 실제 차량용 production host와 차량·통화·내비 정책 feed |
| 점수·최종 코멘트 | 외부 입력 `TripReport` 저장·전달 계약 | 실제 점수 산정·최종 코멘트 생성 및 이벤트 규격 합의 |

현재 JVM·API 연결 검증은 모듈 경계의 호환성 검증이다. 실제 Android 앱에서 서버까지 기록을 보내는 전체 제품 경로는 아직 없다. `backend/nunti/demo_outbox.py`는 Python 실행 참조 예제이며 Android outbox 구현이 아니다.

## 담당 세션과 작업 인계 시점

| 역할 | 기존 채팅 제목 | 채팅 ID | 보고 요청 시 상태 |
| --- | --- | --- | --- |
| PM | 세션별 진행 상황 인수인계 정리 | `01a19b65-2f17-7843-8196-9c50b1ef5469` | 현황 취합·이관 문서 작성 |
| TTS | 구현 Pleos TTS 음성 시스템 | `01a196fb-2587-77e0-adf0-f4e439247e0e` | 기존 구현 완료 후 idle, PM 요청으로 읽기 전용 보고 |
| AVATAR | 경로 기반 아바타 시스템 개발 | `01a196f9-9015-7aa2-81b7-a0e111fcc209` | 기존 구현 완료 후 idle, PM 요청으로 읽기 전용 보고 |
| SERVER | Nunti 서버 시스템 통합 구현 | `01a196f8-81b9-7ac1-85ad-15b5ed127fcd` | 통합·런타임 검증 후 idle, PM 요청으로 읽기 전용 보고 |

기존 채팅은 새 로컬 작업의 필수 의존성이 아니다. 직접 보고는 [reports](README.md)에 보존하고, 새 세션은 문서와 실제 파일을 기준으로 재개한다.

## AVATAR 구현과 결정

소유 파일은 `android/feature/avatar`, `android/feature/navigation`, `android/feature/emotion`이다. 공통 Android host·Gradle 파일은 최초 AVATAR가 협의 후 작성했고, 이후 공통 변경은 PM 조율 대상으로 둔다.

- `RouteFeatureExtractor`는 검증된 거리·시간·도로 비율·지형 근거를 사용한다. 목적지 이름이나 routeOption에서 해안·산악·고속도로를 추정하지 않는다. 모르는 값은 UNKNOWN으로 유지한다.
- `AvatarEngine`은 Identity Layer를 고정하고 Journey Layer의 의상·소품·장식을 고른다. 기본 후보도 항상 포함하며, seed는 동점 순위만 정한다. 반복 여정 이력이 없어 다양성 가산점은 0이다.
- `generation.properties`의 단거리 20km·장거리 150km·우세 도로 0.60 같은 수치는 합성 시험용 초깃값이다. 실제 도로로 검증한 제품 분류 기준이 아니다.
- `avatarId`는 baseCharacterId와 routeId에 따라 결정되고 revision 변경에도 유지된다. 원래 route·seed·평가 시각·rule/asset digest가 같아야 복원이 가능하다.
- `EmotionMachine`은 검증된 이벤트로만 반응한다. 신뢰도 0.80 미만, 미래·만료·미확인 데이터로 부정 감정을 만들지 않는다. 회복에는 현재 cause와 연결되는 새 이벤트가 필요하다.
- 6종 감정은 NEUTRAL, RELAXED, JOYFUL, STARTLED, CONCERNED, RELIEVED다. 감정 intensity는 표현 강도이며 위험도·운전 점수가 아니다. CALM은 음성 스타일 hint와 구분한다.
- 플랫폼 정책 누락·차단·5초 초과 노후 상태에서는 화면과 접근성 텍스트를 숨긴다. 승인된 주행 중 정적 표시에서도 중립·고정 외형만 허용한다.
- `CharacterAssetProvider` 교체 지점은 있지만 현재 시각 자산은 placeholder다. 생성 알고리즘의 후보 점수는 운전 점수가 아니다.

주요 파일은 `AvatarEngine.kt`, `Assets.kt`, `Rendering.kt`, `WireAdapter.kt`, `RouteFeatures.kt`, `EmotionMachine.kt`, `NuntiAvatar.kt`, `CarUxPolicyBinding.kt`다. [AVATAR 가이드](../../android/feature/avatar/README.md)에 상세 구조가 있다.

## TTS 구현과 결정

소유 파일은 `android/feature/tts`, `android/feature/voice`다. `android/app/src/voiceIntegration`은 DTO 변환 경계이며, 발화 허가·큐·포커스·SDK 호출은 TTS가 소유한다.

- `SpeechContractBridge`와 `SpeechRequestBuilder`가 서버·아바타 입력을 검증한다. `contentSource`와 `speechPurpose`는 별개이며 외부 JSON의 verified 표시만으로 로컬 근거를 신뢰하지 않는다.
- 최종 코멘트는 외부 모듈의 원문을 보존한다. TTS가 운전 점수나 코멘트를 생성하지 않는다.
- `voiceProfileId=nunti-default-v1`, persona COMPANION, 기본 CALM을 사용한다. 여행마다 화자 ID를 바꾸지 않는다. 감정 스타일은 논리 메타데이터이며 실제 emotion/rate/pitch API 지원을 뜻하지 않는다.
- `SpeechQueueManager`는 단일 실행 스레드, pending 최대 8, trip당 ID 최대 4,096, TTL 최대 120초, 시작 timeout 3초, 초기화 5초, 재생 최대 30초다.
- 주행 중 최대 80 codepoint, 최소 발화 간격 15초, 동일 문구 60초 제한이다. 제품 초깃값이며 법규 수치가 아니다.
- 앱 재시작은 빈 큐다. 거부·취소·만료 요청은 자동 재생하지 않는다. suspend 이후에는 새 `AndroidVoiceSession`을 만든다.
- NOTIFICATION / SPEECH / TRANSIENT_MAY_DUCK을 사용하며 포커스 상실·통화·내비·안전음·백그라운드에서 정책에 따라 중단한다. 실제 신호가 없으면 UNKNOWN을 유지한다.
- 기본 provider는 Pleos ON_DEVICE다. HYBRID/SERVER는 자격 증명·등록·네트워크 시험이 남아 있다. 별도 외부 감정 TTS 도입은 결정하지 않았다.
- `reference-ko.wav`는 macOS Yuna 참고 오디오다. 실제 Pleos 출력 증거는 `tts-first.wav`와 `tts-final.wav`다.

주요 파일은 `ContractBridge.kt`, `VoiceProfiles.kt`의 `SpeechRequestBuilder`, `SpeechPlaybackPolicy.kt`, `SpeechQueueManager.kt`, `PleosTtsProvider.kt`, `AndroidVoiceSession.kt`, `AndroidPleosConnection.kt`다. [TTS](../../android/feature/tts/README.md)와 [voice 가이드](../../android/feature/voice/README.md)를 함께 읽는다.

## SERVER 구현과 결정

소유 파일은 `backend`, `contracts/v1`, `docs/architecture`, 서버 협업 문서다. `api.py`, `models.py`, `store.py`, `config.py`가 핵심이다.

- FastAPI/Pydantic v2/SQLite로 trip, route, avatar, event, emotion, report를 저장한다. 서버가 아바타·감정·운전 점수·코멘트를 계산하거나 음성을 재생하지 않는다.
- 인증 token→principal 분리, 명시적 syncConsent, HTTPS 기본 요구, 동기화·Mock 기본 비활성화, 30일 보존, 소유자별 삭제를 구현했다.
- 동일 ID·동일 내용은 duplicate로 처리하고 원래 receivedAt을 보존한다. 내용 충돌·경로 revision 충돌은 409다. 이벤트·감정 배치는 최대 100개이며 원자적이다.
- 단절·응답 유실·서버 재시작·재전송을 Python outbox 예제로 검증했다. Android 구현은 별도 작업이다.
- `TripReport.finalText`는 원문 보존, overallScore는 null을 허용한다. 점수의 미확인 상태를 임의 계산으로 채우지 않는다.
- 실제 사용자 로그인, 토큰 발급·회전, 공개 배포, 운영 TLS 프록시, 백업 복원과 부하 시험은 미구현·미검증이다.

[서버 실행 가이드](../../backend/README.md), [설계](../architecture/server.md), [연결 예제](../architecture/integration.md)를 참고한다.

## 공통 계약과 협업 경계

`contracts/v1`은 SERVER 소유의 schemaVersion `1.0`, camelCase, JSON Schema Draft 2020-12 계약 초안이다. 7개 공유 모델과 TripCreate·EventBatch·EmotionBatch를 포함한다. 기존 모듈 간 호환 검증은 끝났지만 점수 담당 이벤트 종류·verification/confidence 의미·correlation/recovery 규약의 최종 합의는 남아 있다.

- 원본 GPS·주소·목적지는 서버 계약에서 제외한다. 자유 텍스트에도 위치 원문을 넣지 않는다.
- evidence는 소속 routeId/revision/특징값에 귀속된다. 값이나 revision이 바뀌면 producer가 다시 검증한다.
- EmotionSnapshot.emotionId와 eventId는 동일 재전송에 그대로 사용한다. 조회한 감정을 로컬 엔진에 다시 입력하지 않는다.
- SpeechRequest는 원격 재생 명령이 아니다. 재연결 시 서버 기록을 자동 재생하지 않는다.
- CarUxRestrictionsManager listener는 실제 host의 한 개 연결을 공유한다. AVATAR/TTS가 각각 중복 등록하지 않는다.
- 공통 schema·SDK·Gradle·host 경계를 바꾸기 전 영향과 수신자를 PM과 조율한다. 다른 담당 소유 파일을 임의로 함께 수정하지 않는다.

## 실제 검증 범위

아래 자동 검사·에뮬레이터 실행은 2026-11-01에 수행한 기록이다. 이번 PM 문서화에서 전부 다시 빌드한 결과가 아니다. 새 로컬 재검사는 별도로 수행한다.

| 검사 | 보존된 결과 | 해석 범위 |
| --- | --- | --- |
| 서버 pytest | 91 passed | API·계약·인증·동의·멱등성·저장·Mock 시나리오 |
| 서버 Ruff·wheel/sdist·실제 HTTP smoke | 통과 | 패키징·loopback·재전송·프로세스 재시작 영속성 |
| AVATAR JVM | 58개 + 합성 경로 1,000개 | 생성·감정·복원·정책 및 합성 반복 |
| 실제 Kotlin 출력→서버 | JSON 10개, API round trip 4쌍 통과 | 스키마/Pydantic/저장·조회 호환성 |
| TTS JVM·실제 fixture | 62개 + 연동 8개 | 정책·큐·타입 변환·원문·근거 연결 |
| Android/Pleos 실제 바이너리 컴파일 | 통과 | SDK API 대상 컴파일, 런타임 보증과 별개 |
| 통합 debug assemble/lint | 오류 0, 경고 3 | 이전 온라인 실행 경고 7과 실행 조건이 다름 |
| release 및 진단 화면 제외 검사 | 통과 | Debug 진단 Activity가 release에 포함되지 않음 |
| Pleos 2.1.0 ARM/API34 | P·speed 0·UX 0, 4종 경로 외형·일부 표정 표시 | 경로·감정은 Mock, 차량 상태 조회는 실제 |
| ON_DEVICE TTS | QUEUED→STARTED→COMPLETED, 출력 PCM 확인 | 통제된 에뮬레이터 오디오 조건 |
| lifecycle | USER_CANCELLED, BACKGROUND, 복귀 후 REPEATED_TEXT | 이벤트 관찰, 취소 후 실제 무음 지연은 미측정 |

최종 WAV는 48kHz/16bit/stereo, 7.166875초다. 41ms와 초기 73ms는 개별 submit→SDK callback 지연이며 가청 지연이나 통계 benchmark가 아니다. 인간 청취에 의한 발음·첫 음절·음질 평가는 하지 않았다.

최종 런타임 APK의 SHA-256은 `87f207f35418d1979133c903117327eb46cc4fc0a3aa6a40847a5a24ff74cc58`다. 이전 통합 빌드 해시 `49a66460…`와 혼동하지 않는다. APK 자체는 ignored이고, 해시·화면·WAV·로그는 Git에 있다. 새 환경의 debug 서명과 빌드 조건이 달라지면 새 APK 해시도 달라질 수 있다.

## 알려진 차단사항과 오래된 기록

1. 실제 D/30km/h 전환·실제 주행 UX 차단·P 복귀는 미검증이다. 당시 Virtual Console은 `emulator_inactive`, bridge/DDS 미준비, gear PUT 503이었다. hmg_car_service 부재와 user build 제한도 확인했다. 보호를 우회하거나 합성 상태를 실제 성공으로 기록하지 않는다.
2. production `MainActivity`는 AAOS에서 화면을 차단한다. `RuntimeProbeActivity`는 Debug 에뮬레이터 전용이며 제품 host가 아니다. 실제 서버 HTTP와 내비 입력도 포함하지 않는다.
3. 점수 담당 이은룡의 실제 이벤트·점수·최종 코멘트 모듈은 이 저장소에 없다. PM이 입력 계약과 제공 일정을 확인해야 한다.
4. 임시 SDK·AVD·도구 캐시 및 기존 AVATAR/TTS worktree는 현재 사라졌다. 새 환경 설치가 필요하다.
5. 기존 README·server 협업 기록·validation.md 일부의 “에뮬레이터/음성 미검증” 문장은 초기 빌드 단계 기록이다. 2026-11-01 후속 [Pleos 런타임 보고서](../architecture/pleos-runtime.md)와 해당 증거를 현재 판정 기준으로 사용한다. 실제 주행·음질 미검증은 여전히 유효하다.
6. 실제 WAV를 수집했던 임시 gRPC 오디오 캡처 클라이언트는 저장소와 현재 임시 경로에 없다. WAV·형식·수치·해시는 보존돼 있지만, 새 녹음 자동화는 인증 처리를 포함해 복원해야 한다. lifecycle 재현 스크립트는 Git에 있다.

최신 사용자 요구는 허용된 상황의 짧은 TTS다. 원본 기획 HTML의 STT-only 문구를 현재 요구로 되돌리지 않는다. 현재 `routeComplexity`는 UNKNOWN이며 운영 AvatarReplay·EmotionJournal 저장 연결도 별도 작업이다.

## 새 로컬에서의 우선순위와 인계 완료 조건

| 순서 | 작업 | 주 담당 | 완료를 판단할 증거 |
| --- | --- | --- | --- |
| 1 | clone·도구 설치·과거 증거 무결성·기본 검사 재현 | PM 및 각 담당 | HEAD, 실행 명령, 결과 로그, 환경 차이 |
| 2 | Pleos 차량 상태 제어 환경 복구 | PM 조율, SERVER 통합, AVATAR/TTS 검증 | 실제 P→D/속도→P 및 화면·발화 정책 로그 |
| 3 | 점수 담당·내비 SDK·차량 host 입력 계약 확정 | PM | 실제 payload·신호 출처·소유자·승인 기준 |
| 4 | production host와 Android 영속 inbox/HTTP outbox 범위 확정·구현 | PM 배정, SERVER 계약 협업 | 앱 재시작·단절·동의 철회·중복 포함 E2E |
| 5 | 실제 경로·이벤트→아바타·감정·발화·저장 연결 | 각 담당 | Mock과 실제 입력을 구분한 전체 시나리오 |
| 6 | 한국어 청취·가청 지연·포커스 경합·실차 장기 검증 | TTS, PM 수용 | 청취 평가와 실제 측정 기록 |
| 7 | 최종 시각 자산·사용자 평가, 운영 배포 준비 | AVATAR, SERVER, PM | 사용자 평가 및 운영 시험 결과 |

다음 구현 항목은 사용자 우선순위에 맞춰 PM이 배정한다. 환경 복원과 사실 확인은 바로 시작할 수 있다. 새 네 세션이 동일 기준에서 자신의 검사와 첫 작업을 보고하고, 모듈 간 계약·소유권·차단사항을 재확인하면 작업 인계가 성립한다. 실차 제품 완성을 인계 완료 조건으로 주장하지 않는다.
