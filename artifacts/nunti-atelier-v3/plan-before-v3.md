# 눈티 11월 10일 마감 구현 계획

오늘의 납품 단위는 Pleos 에뮬레이터에서 **경로 선택 → 정차 중 변신 → 출발 → 주행 점수 기록 → 정차 후 결과와 음성**을 한 캐릭터로 끝까지 시연할 수 있는 APK다. 바다를 대표 변신으로 잡고, 도시·산악도 같은 경로를 통과하는지 확인한다. 아래 시간은 방향을 정한 시점부터의 작업 상한이다. 자정 전 마지막 30분은 빌드와 검증에 배정한다.

## 지금 합쳐진 코드

- 현재 작업 트리의 `JourneyService`는 1초 간격으로 차량 신호를 수집한다. `JourneySession`이 선택한 눈티의 ID와 경로 ID를 소유하고, 팀원의 `ScoreEngine`이 속도 변화로 급가속·급감속을 평가한다. 감속 때 브레이크가 눌렸으면 급제동으로 구분한다. 벨트·문·후진 등도 받은 신호에 한해 평가하고, 결과에 데이터 커버리지를 남긴다. 여정 서비스는 내비가 앞에 있어도 수집하도록 설계되어 있고, 종료 시 로컬 보고서를 저장한다. [여정 서비스](../../android/app/src/main/kotlin/ai/nunti/app/journey/JourneyService.kt) · [점수 계산](../../android/feature/score/src/main/kotlin/ai/nunti/score/ScoreEngine.kt) · [신호 검증 기록](../architecture/score-signals-api.md)
- 로컬에 보이는 팀원 최신 브랜치 `origin/feat/telemetry-sync`의 `9f413d3`은 현재 작업 트리와 갈라져 있다. 여기에 추가된 것은 Pleos 화자 선택·테스트, 이벤트별 멘트와 종료 멘트, 미연동·해당 상황 없음 분리, 점수 기준 변경, 동의 기반 파일 저장 큐와 서버 업로드다. 팀원 기록상 서버 검증은 DEMO 481샘플·점수 7건·사건 1건·리포트 1건이다. 오늘은 현 통합 점수와 여정 계약을 기준으로 삼고, 화자 매핑과 테스트를 작은 단위로 가져온다. 서버 동기화와 새 점수 산식은 각각 통합 검증 후 별도 반영한다. [팀원 브랜치](https://github.com/Pig30nidaE/NUNTI/tree/9f413d393d8f1b7c6c95322de5b03d111481c682)
- LIVE는 Pleos 서비스 콜백이고 DEMO는 정해진 샘플의 재생이다. 현재 차속 입력에는 비공개 차량 서비스 구독 경로가 있다. LIVE 점수, 내비를 앞에 둔 상태의 기록, 기본 내비 지도 이동을 따로 판정한다. 이전 통합 검증은 D·30km/h 유지에서 시간 초과했고 지도 이동까지 도달하지 못했다. 해당 구간을 통과하기 전에는 **시연 모드**라고 표시한다. [기존 통합 결과](../architecture/integrated-journey.md) · [NaviHelper 공식 문서](https://document.pleos.ai/en/api-reference/connect-sdk-pleos/NaviHelper/intro)
- 로컬 스킨의 음성은 여정 입력을 만들 때 비어 있다. 기존 서버 보관 캐릭터는 저장된 음원 경로를 넘기고, Studio의 Android 기기 TTS는 한국어 음성이 설치됐을 때 쓸 수 있는 별도 경로다. 로컬 스킨을 생성해 출발하는 경로에서 같은 화자의 인사와 도착 음성을 복구한다. [로컬 스킨의 여정 입력](../../android/app/src/main/kotlin/ai/nunti/app/journey/JourneyRuntime.kt#L125) · [Studio의 기기 TTS](../../android/app/src/main/kotlin/ai/nunti/app/studio/AvatarStudioActivity.kt#L176)
- 기존 출발 전 화면은 목적지 불러오기, 내비 열기, 폼, 생성 방식, 만들기를 한 화면에 같은 비중으로 펼친다. 정차 중 여정 화면에는 “감정 음성 0/4 준비” 같은 내부 상태가 보인다. 목적지와 기분을 먼저 두고, 생성 방식과 보조 입력은 기존 옵션으로 옮긴다. “이 길에서 눈티 만나기”는 “눈티 만들기”로 바꾼다. 음성 준비 상태는 목소리 버튼을 눌렀을 때 짧게 설명한다. [출발 전 캡처](../../artifacts/nunti-visual-polish/runtime/01-pre-trip-sea-ready.png) · [여정 캡처](../../artifacts/nunti-visual-polish/runtime/09-skin-journey-active.png)

## A/B 디자인

두 시안은 같은 바다 눈티와 목적지로 비교한다. **오늘 구현 추천은 A**다. 기존 네이티브 스킨 무대에서 출발해 변신을 가장 크게 개선할 수 있고, 목적지와 출발 버튼도 같은 화면에 남는다. Figma는 기존 Pleos 버튼 컴포넌트, 승인 눈티와 현재 스킨 원화를 사용한 정차 화면과 정적 키프레임이다. [편집 가능한 Figma 비교판](https://www.figma.com/design/LHLHBra8ON3OdVW0qhBnbm?node-id=47-5)

| 방향 | 화면 | 변신 |
| --- | --- | --- |
| A 해안의 빛 | 어두운 무대에 눈티를 크게 두고, 옆에 목적지·출발·음성·다시 보기를 모은다. | 기본 눈티가 몸을 낮춘다. 파도가 발밑에 닿는 순간 신발·재킷이 바뀌고, 물보라가 앞뒤로 지나갈 때 모자와 가방이 자리 잡는다. 그림자와 빛이 가라앉으며 최종 스킨이 남는다. |
| B 길을 담은 엽서 | 밝은 화면에서 목적지와 경로를 먼저 읽고, 옆의 해안 일러스트에서 눈티를 본다. | 경로 획을 따라 해안 풍경이 채워지고, 풍경의 색과 무늬가 기본 눈티의 의상에 옮겨간다. 끝나면 눈티와 목적지가 한 장면에 남는다. |

A에서도 실제 경로가 장면을 바꾼다. 확인된 경로의 굽이와 진행 방향으로 파도가 들어오는 곡선을 정한다. 목적지 유형은 의상과 효과 재질을, 사용자가 고른 기분은 자세와 표정을 고른다. 좌표가 없으면 목적지 유형별 기본 궤적을 쓴다.

## 구현 순서와 완료 기준

### 0~20분 · 빌드 기준과 팀원 연동

기존 APK의 출발 전·변신·여정·결과 화면을 캡처한다. 작업 트리와 팀원 브랜치의 차이를 기준으로 가져올 화자 매핑·테스트를 확정한다. DEMO를 한 바퀴 돌리고 Virtual Console에서 LIVE의 P·D 전환과 속도 콜백을 각각 기록한다. 실패 지점이 SDK 신호인지, 서비스 수명인지, 내비 위치인지 먼저 나눈다.

### 20~85분 · 아트·변신, UI, 음성

- **아트·변신.** 승인 기본형의 얼굴과 새싹, 몸 비율을 고정한다. 바다는 세일러 재킷·조개, 도시는 보머·헤드폰, 산악은 바람막이·니트와 배낭으로 작은 화면에서도 구분한다. 기존 원화와 새 후보를 실루엣, 얼굴 일치, 재질, 작은 크기 기준으로 비교한다. 원화 보완이 필요한 부위는 참조 기반 ImageGen 편집이나 직접 보정으로 만들고, 768×768 공통 좌표에서 정적 PNG와 의상 레이어를 정렬한다. 새 후보는 검토 자산으로 분리한다. 실제 앱의 `MOCK_SKIN_MODE=true`에서 생성과 재열기를 검증한다. [Skin V2 기준](SKIN_SYSTEM_V2.md) · [POP MART HIRONO 수집 피겨](https://www.popmart.com/us/products/13/HIRONO-Little-Mischief-Series) · [GPT Image 편집](https://developers.openai.com/api/docs/guides/image-generation)
- **효과.** 현재 `StudioCharacterMotion`과 `StudioAtlasVfx`에서 앞·뒤 효과와 의상 마스크를 같은 타임라인에 맞춘다. 바다는 수면과 물보라, 도시는 아래에서 위로 조립되는 빛 조각, 산악은 발밑 등고선에서 자라나는 잎으로 움직임을 구분한다. 바다부터 약 4초 안에 자세 변화, 접점, 의상 변화, 최종 포즈가 보이게 만든다. 모티프가 몸에 닿는 프레임에 의상 변화를 맞추고, 새 얼굴을 그리거나 화면 전체를 번쩍이게 하지 않는다. 기존 허용 자산과 Effekseer의 투명 프레임을 활용하고 출처·라이선스를 기록한다. [현재 렌더러](../../android/app/src/main/kotlin/ai/nunti/app/studio/StudioCharacterMotion.kt) · [현행 효과와 라이선스](../NUNTI_VFX_ASSET_CREDITS.md) · [포켓몬 공식 테라스탈 참고](https://press.pokemon.com/en/NEW-DETAILS-REVEALED-FOR-POKEMON-SCARLET-AND-POKEMON-VIOLET-INCLUDING-) · [Niagara의 동작 시점에 맞춘 효과](https://dev.epicgames.com/documentation/unreal-engine/quick-start-for-niagara-effects-in-unreal-engine?lang=en-US)
- **차량 UI.** 전체 화면 2560×1440과 기존 Studio 영역 1682×1210, 좁은 실제 앱 창 847×910을 구분한다. 기기에서 앱 창 크기와 WebView 배율을 다시 잰다. 넓은 창은 두 열, 좁은 창은 한 열과 고정 주요 버튼으로 구성한다. 출발 전에는 목적지와 **눈티 만들기**, 결과에서는 **눈티와 출발**, 도착 후에는 점수·급가속·급제동·측정 범위와 **여정 마치기** 흐름을 정리한다. 제목 36–48sp, 주요 본문 24sp 안팎, 행간 1.4배 전후, 기본 자간을 초기 목표로 잡고 한국어 줄바꿈을 확인한다. 주요 버튼은 64dp 이상을 목표로 하고 일반 텍스트 대비 4.5:1, 포커스 및 필수 컨트롤 대비 3:1을 측정한다. 제한 상태에는 플랫폼이 허용하는 최소 정적 화면만 표시한다. [Pleos 화면 구성](https://document.pleos.ai/en/docs/connect/guide/docs-design/getting-started/layout) · [Pleos 창 정책](https://document.pleos.ai/en/docs/connect/guide/docs-design/getting-started/window) · [Pleos 글꼴 가이드](https://document.pleos.ai/en/docs/connect/guide/docs-design/foundations/typography) · [Polestar 4 지도와 위젯](https://www.polestar.com/uk/manual/polestar-4/2025/article/7c9fa435bf2aa212c0a8b0c15c74d87d-a72b54a9bf2afb7dc0a8b0c10b874b59-8664b2fa77a7e089c0a8296870d1a409) · [기기 치수 검증 기록](../architecture/pleos-runtime.md)
- **한국어 음성.** 기존 `AndroidVoiceSession`의 큐·중복 방지·포커스를 재사용한다. Pleos `ON_DEVICE`와 기존 로컬 Sohee 후보를 같은 문장, 같은 출력 크기로 들어보고, 과거 선호 음색 Anna를 톤 기준으로 참고한다. 한국어 발음, 문장 끝 억양, 한 화자로 들리는지를 듣고 고른다. 후보 문장은 “안녕, 눈티야. 같이 가자.”와 “도착했어. 같이 와서 좋았어.”다. Pleos가 품질을 통과하면 주차 중 인사와 도착 안내에 연결한다. 로컬 후보가 더 좋으면 검수한 음원을 앱에 넣어 같은 목소리를 유지한다. Pleos 서버 모드 비교는 프로젝트 등록이 가능할 때만 추가한다. 내비·통화·차량 제한을 확인할 수 없는 경우 주행 중 캐릭터 발화를 억제한다. [기존 음성 선호 기록](../../prototypes/voice_audition/selected-voice.json) · [Pleos TTS 모드](https://document.pleos.ai/en/docs/pleos-only/connect-sdk-pleos/TextToSpeech/intro) · [Pleos 주행 안전 지침](https://document.pleos.ai/docs/pleos-only/vehicle-app-planning-guide/driver-distraction-guideline)

### 85~130분 · 실제 앱에 연결

Figma에서 선택한 방향을 출발 전 입력, 정차 중 변신, 주행 제한, 도착 리포트까지 확장한다. 출발 전에는 목적지 선택과 만들기, 변신 중에는 건너뛰기, 주행 제한 화면에는 허용된 정적 상태, 도착 화면에는 결과와 다음 행동이 먼저 보이게 한다. 마이페이지는 기존 보관함에서 눈티와 경로를 열 수 있는지 회귀 검증한다.

음성은 정차 중 **목소리 듣기**, 출발 인사, 주차 후 도착으로 나눠 확인한다. 이전의 상황별 반응 음성은 Pleos 정책과 실제 내비·통화 상태 확인이 가능한 조건에서만 재생한다. 해당 조건을 충족하지 못하면 정차 후 요약에 반응을 담는다.

Studio WebView와 네이티브 여정 화면의 버튼 순서, 문구, 간격을 맞춘다. 점수·여정 서비스에는 표시 데이터만 요청한다. 기분은 직접 선택한 값, 주행 반응은 점수의 `Emotion`에서 읽는다. 경로를 그릴 때는 앱에서 확인한 좌표를 로컬에서 단순화한다. 사용할 좌표가 없으면 목적지 일러스트를 보여주고, 목적지 분류도 없으면 기본 눈티를 쓴다. 같은 입력과 버전은 같은 스킨을 생성한다. 정차 상태에서 같은 캐릭터로 출발하고, 주차 후 **여정 마치기**를 누르면 보고서가 저장된 뒤 음성이 재생되는지 확인한다. 기존 보관함의 그림과 경로를 다시 연다.

### 130~170분 · 출시 후보 판정

| 확인 | 통과 조건 |
| --- | --- |
| UI | Figma와 같은 상태의 실제 캡처를 넓은 창·좁은 창·주간·야간에서 대조한다. 긴 목적지, 글자 확대, 접근성 이름, 대비와 터치 영역을 확인한다. |
| 변신 | 세 테마를 실제 녹화해 기본 얼굴 유지, 앞뒤 깊이, 의상 변화의 접점을 확인한다. 30fps 안정 재생을 목표로 한 빌드에서 연속 재생하며 프레임 시간·끊김·PSS·CPU를 기존 빌드와 비교한다. 이전 캡처에는 p95 32ms와 gfxinfo jank 69.23%가 함께 기록됐다. [성능 원본](../../artifacts/nunti-visual-polish/runtime/verification.json) |
| 차량 제한 | 재생 중 P→D, 앱 이탈, 모션 축소, 건너뛰기, 파일 누락을 시험한다. 제한이 걸리면 모션이 즉시 중단되고, 다시 주차해도 자동 재생하지 않는다. 정적 결과 또는 기본 눈티로 돌아간다. |
| 음성 | 기기에서 시작·종료를 듣고 음소거, 중복 재생, 포커스 상실, 네트워크 없음, 정차 해제와 음원 누락을 확인한다. 실패하면 짧은 자막을 표시한다. |
| 점수·저장 | DEMO와 LIVE를 각각 기록한다. 신호 누락은 평가 불가로 표시하고, 급가속·급제동과 최종 저장을 검증한다. 기존 눈티를 다시 열어 그림과 경로가 같은지 본다. |

마지막 30분에 복잡한 도시·산악 효과가 기준을 넘지 못하면 해당 테마의 검수된 짧은 연출 또는 정적 스킨을 사용한다. 바다 변신이 기준을 넘지 못하면 APK에는 정적 결과를 넣고 변신을 미완료로 표시한다. Pleos 음성이 청취 기준을 넘지 못하면 승인된 로컬 음원을 사용하고, 승인된 음원이 없으면 음성을 미완료로 표시한다. LIVE 검증을 통과하지 못하면 시연 화면과 인수 기록에 DEMO 범위를 명시한다.

현재 환경에는 Pleos SDK·AVD와 Effekseer가 있다. 이번 계획 검토 중에는 샌드박스가 ADB 소켓을 막아 새 기기 측정 대신 기존 캡처와 로그를 사용했다. 실행 단계의 첫 확인은 Pleos 에뮬레이터 연결이다. 새 도구 설치는 이 계획의 선행 조건이 아니다.
