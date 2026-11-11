# 공모전 규정 · Pleos UX 고려사항 정리

확인일: 2026-11-10 (KST). 공모전 공식 사이트와 Pleos Playground 개발 문서를 ego lite 브라우저로 직접 열어 읽고 정리했다. "우리 앱에 대한 의미"는 그 내용을 현재 코드와 대조한 판단이다.

출처
- 공모전: [소개](https://appdevchallenge.auto-hmg.io/) · [개요](https://appdevchallenge.auto-hmg.io/guide/overview) · [참가 규정](https://appdevchallenge.auto-hmg.io/guide/rules) · [심사·시상](https://appdevchallenge.auto-hmg.io/guide/judging-awards) · [지원·제출](https://appdevchallenge.auto-hmg.io/guide/submission) · [개발 환경](https://appdevchallenge.auto-hmg.io/guide/development) · [FAQ](https://appdevchallenge.auto-hmg.io/faq) · [유의사항 공지](https://appdevchallenge.auto-hmg.io/notice/c0a1a000-2026-4923-8000-000000000006) · [모집 공고](https://appdevchallenge.auto-hmg.io/notice/c0a1a000-2026-4923-8000-000000000001)
- Pleos: [앱 설계 가이드](https://document.pleos.ai/docs/pleos-only/vehicle-app-planning-guide/intro) · [주행 안전을 고려한 설계](https://document.pleos.ai/docs/pleos-only/vehicle-app-planning-guide/driver-distraction-guideline) · [지역별 주행 규제 정책](https://document.pleos.ai/docs/pleos-only/vehicle-app-planning-guide/driving-restiction-policy) · [앱 카테고리](https://document.pleos.ai/docs/pleos-only/vehicle-app-planning-guide/app-category) · [앱 구조 및 동작 모델](https://document.pleos.ai/docs/pleos-only/vehicle-app-planning-guide/app-structure-screen-model) · [보안·개인정보](https://document.pleos.ai/docs/pleos-only/vehicle-app-planning-guide/security-privacy) · [성능·리소스](https://document.pleos.ai/docs/pleos-only/vehicle-app-planning-guide/performance-resource-mgmt) · [주행 규제 개발 가이드](https://document.pleos.ai/docs/pleos-only/vehicle-app-developer-guide/driving-restriction-development-guide) · [오디오 포커스](https://document.pleos.ai/docs/pleos-only/vehicle-app-developer-guide/audio-focus-development-guide/audio-focus-development) · [Suspend 오디오 포커스](https://document.pleos.ai/docs/pleos-only/vehicle-app-developer-guide/audio-focus-development-guide/suspend-mode-audio-focus) · [TTS 선행 묵음](https://document.pleos.ai/docs/pleos-only/vehicle-app-developer-guide/voice-guidance-preroll-silence-guide) · [앱 보안 가이드](https://document.pleos.ai/docs/pleos-only/app-registration-guide/app-security-guide) · [앱 실행 환경 FAQ](https://document.pleos.ai/docs/pleos-only/vehicle-app-developer-guide/vehicle-app-faq) · [프로젝트 생성 및 SDK 신청](https://document.pleos.ai/docs/pleos-only/create-my-project)

## 1. 공모전 규정

### 일정
| 날짜 | 내용 |
|---|---|
| 2026-10-21 ~ 11-15 | 접수 (이메일) |
| 11-23 | 1차 서류심사 결과 (20팀) |
| 12-03 ~ 12-04 | 2차 최종 PT 심사, 오프라인 (현대차 강남대로사옥 1층 UX스튜디오 서울) |
| 12-18 | 최종 선정 10팀 발표 |
| 12-19 ~ 2027-01 | 전시 준비 기간 (새 기능 개발 기간이 아님) |
| 2027-02 | 현대차그룹 행사 전시·시연, 시상식, 최종 순위 발표 |

### 심사 기준 (1차, 세부 배점 비공개)
- **차량특화성**: 모바일 대비 차량 환경만의 가치가 있는가. 주행·정차 맥락, 차량 기능과 유기적으로 결합됐는가.
- **창의성**: 독창적인가. 운전자·동승자의 페인포인트와 해결 방식이 명확한가.
- **기술 활용성**: Pleos Playground SDK·API를 앱의 **핵심 기능과 사용 경험**에 적절히 활용했는가.
- **사업성**: 타깃 고객, 예상 MAU, 리텐션, 확대 계획.
- **가산점**: 시연 영상(화면 녹화 포함), GitHub 저장소(소스 + APK). 제출 수준에 따라 단계별로 가산.
- 2차 PT 심사 기준은 아직 미공개다 (확정되면 공지).
- 최종 순위는 2차 PT에서 제출·시연한 결과물로 확정된다. PT 이후의 추가 개발은 순위에 반영되지 않는다.

### 쓸 수 있는 SDK
- FAQ 기준: Vehicle, NaviHelper, TextToSpeech, SpeechToText, FusedLocation.
- **특정 SDK를 반드시 써야 한다는 규정은 없다.** 외부 API나 외부 TTS를 금지하는 문구도 없다.
- 개발 환경 페이지의 예시 시나리오에 **"안전운전 점수 앱 (Vehicle SDK 차량 상태로 주행 습관 점수화)"**이 그대로 나온다. 예시라서 주제를 제한하지는 않지만, 그만큼 흔한 아이디어라는 뜻이기도 하다.
- Playground 프로젝트 기준으로 TTS·STT·FusedLocation·Vehicle Control은 "준비 중(Coming Soon)", Vehicle State·NaviHelper는 "신청 없이 사용 가능"이다. TTS/STT는 서버 모드를 쓸 때 클라이언트 ID와 시크릿이 필요하다.

### 제출물
- **필수**: 접수양식(기획서) DOCX와 참가자 전원의 개인정보 동의서·서명.
- 메일 주소는 appdevchallenge@hyundai-partners.com, 제목은 `[차량용 앱 개발 공모전] 팀명(개인은 성명)_대표자명`. 팀원 전원을 CC에 넣는다.
- 수정 제출: 마감 전, 처음 보낸 주소에서 `[수정제출] ...` 제목으로 보낸다. **전체 자료와 서명한 동의서를 다시 첨부**해야 한다. 마지막으로 제출한 것이 최종본이다.
- 접수양식 5번(개발 계획)에는 Pleos Connect에서 어떻게 구현할지, 개발 범위, **SDK/API 사용 계획**을 구체적으로 적는다.
- **선택 (가산점)**: 시연 영상(목업·프로토타입·화면 녹화 인정), GitHub 저장소.
  - APK는 저장소의 `apk/` 폴더에 `팀명_앱이름_release.apk`로 넣는다. 실행 가능한 **release** 빌드여야 한다. 용량이 넘치면 GitHub Releases 링크를 낸다.
  - 비공개 저장소도 된다. 공지된 심사용 계정을 Collaborator로 초대하고, 마감 전에 접근되는지 확인해야 한다. 개인 계정 비공개 저장소의 Collaborator에게는 쓰기 권한까지 생긴다.
  - README.md에 넣을 내용: 앱 이름과 한 줄 소개, 실행 방법, 테스트 환경과 필요한 설정, APK 위치 또는 Release 링크.
- 숏폼(선택, 가산점 없음, 별도 50만원 상): 30초~1분 세로 영상을 릴스나 쇼츠로 올리고 `#HMG차량용앱개발공모전`을 포함해 해시태그 2~3개를 단다.

### 2차·전시 의무
- 2차 PT 대상 20팀은 **실제 동작하는 앱 시연(에뮬레이터 화면 또는 기기)이 필수**다.
- 최종 10팀은 전시 구동용 최종 APK를 내야 하고, 2027-02 행사에 직접 참석해 시연할 의무가 있다. 주최 측은 결과물이 정상 구동되는지 확인하고 보완을 요청할 수 있다.

### 권리·유의사항
- 순수 창작물이어야 한다. 표절이나 기존 공모전 수상작은 심사에서 제외된다. 제출 서류 내용이 사실과 다르면 선정이 취소될 수 있다.
- **제3자 권리(초상권, 저작권, 디자인권 등)를 침해하면 안 되고, 분쟁 책임은 응모자에게 있다.** 수상 후에 밝혀져도 수상 취소와 상금 환수 대상이다.
- 출품작의 지식재산권은 응모자에게 있다. 수상작에 대해서는 주최 측이 통상실시권과 4개월 우선협상권을 가질 수 있다.
- 현대차그룹 임직원은 참가는 가능하지만 수상 대상에서 제외된다.

## 2. Pleos UX · 플랫폼 고려사항

### 주행 중 사용 (주행 규제)
- **DO(distractionOptimized)를 선언하지 않은 앱은 주행 중 사용할 수 없다** (Parking에서만 가능).
- DO를 선언한 앱도 `CarUxRestrictionsManager.registerListener()`로 받은 `ActiveRestrictions`에 따라 기능을 직접 줄이거나 막아야 한다. 지역별 사양은 플랫폼이 내려 준다.
- 주행 중 제한 항목: 키보드(NO_KEYBOARD), 설정(NO_SETUP), 동영상(NO_VIDEO), 대용량 텍스트(LIMIT_CONTENT, LIMIT_STRING_LENGTH) 등. 북미가 가장 엄격하고(검색도 음성만 허용), 유럽과 그 외 지역은 일부 허용한다.
- 지역 코드는 `product.sw.target_region`으로 구분한다: KOR, EUR, USA/CAN. 지역별 UX 정책을 적용하라고 되어 있다.

### 주의 분산 방지 원칙 ([주행 안전을 고려한 설계](https://document.pleos.ai/docs/pleos-only/vehicle-app-planning-guide/driver-distraction-guideline))
- 정보는 짧은 시간 안에 이해되도록 간결하게 표시한다.
- **주행 중에는 동영상, 애니메이션, 움직이는 이미지를 최소화하거나 제한한다. 장식적이거나 반복해서 움직이는 시각 요소는 지양한다.**
- 자동 애니메이션과 반복적인 화면 전환을 최소화한다.
- 자주 쓰는 기능은 첫 화면 상단에 두고, 드롭다운이나 다단 메뉴는 남용하지 않는다.
- 큰 터치 영역, 높은 대비, 텍스트 최소화를 적용한다. 버튼 크기와 간격은 Pleos Connect UI Design Guide를 따른다.
- 터치를 최소화하고 음성·물리 버튼과 연계한다. 키보드보다 프리셋, 최근 항목, 음성을 우선한다.
- 게임처럼 주의를 분산시키는 활동을 유도하지 않는다.

### 화면 구조
- 화면은 Driving view(고정, 앱이 가리면 안 됨)와 앱 영역(window 1~2개)으로 나뉜다.
- 화면 방향을 지정하지 않으면 portrait로 window 1개를 쓰고, landscape로 지정하면 2개를 쓴다. 두 형태를 각각 설계하고 반응형으로 만든다.
- 포그라운드·백그라운드 전환이 잦다. 백그라운드로 가면 화면 갱신, 애니메이션, 불필요한 센서 수집을 멈추고, 포그라운드로 오면 상태를 복원한다. 프로세스가 재생성돼도 진행 상태를 복원할 수 있게 저장 전략을 둔다.

### 오디오 (음성 대사에 바로 해당)
- 재생 전에 `AudioAttributes` + `AudioFocusRequest`로 포커스를 요청한다. 다른 소리와 함께 재생하려면 `AUDIOFOCUS_GAIN_TRANSIENT_MAY_DUCK`을 쓴다.
- 포커스 변경 이벤트 처리는 필수다: LOSS면 즉시 중단, LOSS_TRANSIENT면 일시정지, CAN_DUCK이면 볼륨을 줄인다.
- **Gleo 음성 명령(VOICE_COMMAND)이 호출되어 LOSS_TRANSIENT를 받으면 즉시 재생을 멈추고 필요하면 포커스를 반납한다.**
- **Suspend(시동 OFF 후 저전력)에 들어가면 재생을 중단하고 포커스를 반드시 반납한다. Resume 때 자동으로 복원하지 않는다.**
- **선행 묵음: 모든 음성 안내 앞에 150~200ms 묵음을 넣는다.** 오디오 데이터(WAV) 앞에 직접 넣는 방식을 가장 권장한다. 재생을 지연시키는 방식은 권장하지 않는다. 하나로 이어지는 연속 발화 중간에는 넣지 않는다.

### 성능
- CPU: 내비가 아닌 앱은 주행 중 **5% 미만**, 정차 중 25% 이하. RAM은 400MB 이하.
- 백그라운드의 긴 작업, 타이머, 폴링을 최소화한다. 콜드 스타트를 빠르게 하고 나머지는 지연 로딩한다.

### 보안 · 개인정보
- 텔레메트리에서 **차량 ID와 사용자 ID를 어떻게 익명화·가명화할지 정책을 세운다.** 운전 행동 데이터를 마케팅에 쓰지 않도록 구분한다.
- 위치·음성 등을 받을 때는 왜 필요한지 설명하고, 동의 흐름을 단순하게 만든다. 로그의 PII는 마스킹한다.
- 토큰은 Keystore 등 안전한 저장소에 둔다. 비밀 키와 토큰을 소스·리소스·설정 파일에 하드코딩하지 않는다.
- HTTPS(TLS 1.2 이상, 1.3 권장)를 쓰고, 서버 주소는 IP보다 도메인으로 관리한다.
- 배포 APK는 정식 서명 인증서를 쓰고, 디버깅을 비활성화한다. 필요한 권한과 API만 쓰고, 외부에서 호출할 필요 없는 컴포넌트는 노출하지 않는다.

### 기타
- 클러스터와 같은 속도를 쓰려면 `PERF_VEHICLE_SPEED`(CarPropertyManager)를 읽는다. GPS 속도와는 다를 수 있다.
- `Build.DEVICE`(CONNECT_S/L/W)는 실차에서만 유효하고 에뮬레이터에서는 구분되지 않는다.
- 에뮬레이터의 미디어 코덱은 실차와 다르다. WAV(PCM)는 모든 플랫폼에서 지원된다.

## 3. 우리 앱(점수·음성)에 대한 의미

| 항목 | 현재 상태 | 해야 할 것 |
|---|---|---|
| 외부 TTS 캐릭터 음성 | 규정상 금지 없음 | 진행해도 된다. 다만 **실존 성우나 연예인 목소리를 복제하지 않는다** (제3자 권리 조항). 사용하는 TTS 서비스의 출력물 이용 조건이 "출품·전시"를 허용하는지 요금제 선택 때 함께 본다. |
| 기술 활용성 | Vehicle SDK가 점수의 핵심 입력이다. NaviHelper 일부와 Pleos TTS를 쓴다 | 음성을 외부 TTS로 바꿔도 Vehicle·NaviHelper 활용이 핵심이므로 문제없다. 기획서 5번에 SDK별 용도를 적는다. |
| 아이디어 차별성 | "안전운전 점수 앱"이 공식 예시에 있다 | 기획서와 PT에서 점수 자체보다 **캐릭터가 감정으로 반응하는 동승자 경험**을 앞세운다. |
| 주행 중 동작 | ScoreActivity에 `distractionOptimized` 선언됨 | `CarUxRestrictions`에 따라 화면 요소를 줄이는 처리는 점수 화면에 없다 (UI 담당 영역). |
| 아바타 애니메이션 | — | 주행 중 반복·장식 애니메이션은 지양 대상이다. 주행 중에는 표정 전환 정도로 제한하는 게 맞다 (UI 담당에 전달). |
| 오디오 포커스 | `:feature:voice`가 USAGE_NOTIFICATION + GAIN_TRANSIENT_MAY_DUCK을 쓰고, GAIN이 아닌 모든 변경에서 중단·반납한다 | 지금 정책과 맞다. 로컬 WAV 재생 경로도 같은 포커스 컨트롤러를 거치는지 교체할 때 확인한다. |
| 선행 묵음 | 참고 음원에만 180ms를 넣었다 | **미리 합성하는 캐릭터 WAV 앞에 150~200ms 묵음을 넣는다** (합성 스크립트의 후처리 단계에서). |
| 통화·내비 중 대사 | `PleosSpeechSink`가 통화·내비 상태를 QUIET로 가정한다 | 오디오 포커스가 실제 충돌을 막아 주지만, 통화 중에는 대사를 아예 만들지 않는 편이 낫다. |
| Suspend | — | 시동 OFF 때 재생 중단과 포커스 반납을 실차에서 확인한다. |
| 텔레메트리 | 서버에 주행 샘플·이벤트·보고서를 보낸다 | 차량 ID와 사용자 ID의 가명화 정책을 문서로 남기고, 마케팅에 쓰지 않는다는 원칙을 기획서에 적는다. 배포 빌드의 동기화 토큰은 하드코딩하지 않는다. |
| 성능 | 1초 샘플링과 2초 경고등 폴링 | 주행 중 CPU 5% 미만을 에뮬레이터 `top`으로 한 번 측정해 둔다. |
| GitHub 제출 | — | `apk/팀명_앱이름_release.apk` (release 서명), README 4개 항목, 비공개 저장소라면 심사 계정 초대. |
| 2차 PT | — | 에뮬레이터 시연이 인정되므로, 지금의 가상 콘솔 주행 시연 흐름을 PT용으로 다듬는다. |
