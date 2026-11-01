# Nunti 경로 기반 아바타 MVP

같은 눈티의 정체성은 유지하고, 검증된 경로 특징으로 Journey Layer만 결정한다.
모든 시연 경로는 **합성 Mock**이다. 목적지 이름·경로 옵션에서 도로/지형을 추측하지 않는다.

## 실행

저장소 루트에서 JDK 21 및 Kotlin 2.2.21 컴파일러로 실행한다. 생성물은 `android/feature/avatar/build/reports/`에 생긴다.

```sh
KOTLINC=/path/to/kotlinc bash android/feature/avatar/scripts/test.sh
```

`JSON_JAR`가 없으면 테스트 스크립트가 Maven Central에서 고정 버전 `org.json:json:20250517`을 받는다.
Android에서는 플랫폼의 `org.json`을 사용한다. `CONTRACT_ROOT`를 지정하면 SERVER 예제도 읽는다.

이 개발 환경에서 사용한 명령:

```sh
KOTLINC=/private/tmp/nunti-kotlin/kotlinc/bin/kotlinc \
JSON_JAR=/private/tmp/nunti-kotlin/json.jar \
CONTRACT_ROOT=/Users/pig30nidae/Pig30nidaE/Project/Nunti/contracts/v1 \
bash android/feature/avatar/scripts/test.sh
```

실제 Compose/AAOS 소스 컴파일만 별도로 확인할 수 있다. 공식 Android SDK의 `android.jar`, `optional/android.car.jar`를 지정한다.

```sh
python3 android/feature/avatar/scripts/check-compose.py \
  --kotlinc /path/to/kotlinc \
  --android-jar /path/to/android-35/android.jar \
  --car-jar /path/to/android-35/optional/android.car.jar \
  --cache /tmp/nunti-compose-check
```

앱은 `android/`에서 Gradle Wrapper 8.11.1, AGP 8.10.1, Kotlin 2.2.21, compileSdk 35, minSdk 28로 구성된다.
서버 동의와 TTS 협의로 만든 공통 설정이다. `./gradlew :app:assembleDebug`로 빌드한다.
TTS의 별도 checkout은 `-PnuntiTtsCheckout=/path/to/checkout/android`로 연결 가능하다.
외부 모듈 소스는 변경하지 않으며 빌드 출력은 현재 checkout의 `android/build/`에 저장한다.

`MainActivity`는 **일반 Android 기기용 Mock 검증 뷰어**다. AAOS에서는 실제 호스트 정책 연결 전 표시를 중지한다.
`distractionOptimized` 메타데이터나 실제 주행 허가는 선언하지 않는다.
차량용 화면은 `NuntiAppShell`에 실제 플랫폼 정책, 주차 상태, trip 단계, `AvatarSpec`, `EmotionSnapshot`을 공급해야 한다.
음성 SDK 호출/점수 계산/최종 후기 생성은 이 모듈에서 하지 않는다.

## 구성

- `feature/navigation`: RouteSnapshot 내부 모델, 근거 검증, 특징 추출. SDK에 직접 의존하지 않는다.
- `feature/avatar`: 후보 생성·평가·조합 검증, manifest, 설명, wire projection, 재생 기록, 공통 scene.
- `feature/emotion`: 순수 reducer, 이벤트 중복/역순 처리, 유지·회복·만료, 타임라인·요약.
- `src/compose`: 실제 Compose Canvas 렌더러, 앱 화면, 선택적 AAOS 제한 feed.
- `android/app`: Mock 실행 앱 및 선택적 TTS DTO 연결. host가 발화 허가를 결정한다.
- `src/test`: 58개 시나리오 검사 및 1,000개 합성 경로 반복, 공통 scene의 SVG/PNG 검증 생성.
- `demo/`: 검증 때 생성한 정적 HTML/PNG 시연. JavaScript는 단계만 전환하며 알고리즘을 재구현하지 않는다.
- `reports/`: 실제 측정값, 테스트 결과, 검증 및 기술 비교 보고서.

## 데이터에서 외형까지

`RouteSnapshot → 근거/값 검증 → RouteFeatures → 후보 전체 생성 → 가중 점수 → 제약 검사 → AvatarSpec → CharacterScene → Compose`

Identity Layer는 manifest의 기본 얼굴, 몸체, 눈·입 앵커를 쓰는 고정 rig, 핵심 색, 고유 표식, persona, voiceProfileId다.
Journey Layer는 의상·가방/티켓/물병·물결/능선 장식·팔레트다. 기본 포즈는 현재 standing이며 임의 포즈 생성은 하지 않는다.
`CharacterAssetProvider.renderIdentity/renderPart`를 교체하면 실디자인 자산을 넣을 수 있다. 생성 엔진을 바꿀 필요는 없다.
placeholder 좌표는 320×320 viewBox 기준, Compose는 종횡비를 보존하여 중앙에 그린다.

기본 후보는 항상 포함된다. 도심 도로, 장거리, 검증 해안, 검증 산악 후보를 함께 평가한다.
근거 신뢰도, 관련성, 제약을 통과한 시각 일관성으로 선택하고 탈락 후보 점수·이유도 기록한다.
다양성 가산점은 **0**이다. 실제 반복 여정 이력 입력 없이 임의 차별화를 만들지 않는다.
seed는 점수가 정확히 같은 경우에만 SHA-256 순위를 결정한다. 임의 선택이 근거 없는 테마를 만들 수 없다.

분류/가중치: `src/main/resources/generation.properties`.
초기값은 단거리 ≤20km, 장거리 ≥150km, 짧은 시간 ≤30분, 긴 시간 ≥2시간, 우세 도로 비율 ≥0.60이다.
이는 합성 테스트용 제안이며 실도로/사용자 조사로 검증된 분류가 아니다.
거리 >2,000km, 시간 >48시간 등 모듈의 유효 범위 밖 값은 UNKNOWN으로 내려간다.
confidence는 확인 가능한 5개 특징군을 고정 분모로 계산하므로 하나의 확실한 필드만 있어도 전체를 100%로 표시하지 않는다.

## 재현·복원

동일 입력, rule/asset 버전과 내용 digest, seed는 동일 결과를 만든다. Map/Set 입력 순서에 영향받지 않는다.
`avatarId=SHA256(baseCharacterId|routeId)`의 접두 식별자는 routeRevision 변경에도 유지한다.
다른 경로의 같은 revision 저장 충돌을 피하면서 `baseCharacterId`로 동일 눈티임을 표현한다.

`AvatarReplay`는 원래 wire route와 seed, 원래 평가 시각 및 rule/asset digest를 저장한다.
재현은 **원래 평가 시각**을 사용하고, 새 생성에서는 현재 시각에 근거 만료를 다시 확인한다.
버전 내용이 달라지면 묵시적 재생성 대신 복원을 거절한다. 엔진은 외부 Properties를 복사하여 런타임 설정 변경이 기존 digest의 의미를 바꾸지 못하게 한다.
`EmotionJournal`은 원래 수신 시각·이벤트·tick을 저장하여 pending, cooldown, hysteresis, dedup까지 복원한다.
재부팅 뒤 monotonic 원점은 그대로 재사용하지 않는다. 세션 epoch/지속 시간을 복원하고 새 시계를 연결해야 한다.
저널은 app-private 저장소에 원자적으로 기록한다. 현재 decoder 한도는 20,000 entry/10MB이며 대규모 여정은 호스트가 보존·압축 정책을 정한다.

## 감정 및 화면 정책

- 신뢰도 0.80 미만/미확인/미래/만료 이벤트는 부정 감정을 만들지 않는다.
- eventId를 trip별 dedup하며 위험 사건 correlationId도 중복을 막는다. 회복은 새 eventId로 처리한다.
- 과거 발생 시각의 이벤트는 타임라인을 소급 변경하지 않고 `OUT_OF_ORDER`로 반환한다. 서버 원본 이력은 별도로 보존한다.
- 최소 유지 2초, debounce 0.7초, 같은 부정 감정 cooldown 8초, 안정 확인 3초(관측 간격 ≤2초).
- 놀람은 최대 6초 뒤 중립으로 가라앉는다. 회복 근거 없이 안도/안전을 주장하지 않는다.
- 명시적 회복은 현재 cause event와 일치해야 한다. 안도 3초 뒤 평온, 데이터 30초 미수신 시 중립.
- 모든 초기 감정 설정은 `emotion.properties`에 있다. score 입력으로 감정을 직접 계산하지 않는다.
- 플랫폼 상태 누락/차단/5초 초과 노후 상태에서는 전체 화면과 접근성 텍스트를 숨긴다.
- 주행 중 명시적으로 승인된 정적 화면만 중립 표정으로 유지한다. 설명/상호작용/감정 애니메이션을 내보내지 않는다.
- Compose는 정적 표시 동안 AvatarSpec도 고정한다. 기본 MVP는 출발 전/종료 후에도 자동 애니메이션을 쓰지 않는다.

## 계약/신뢰 경계

공유 wire schema는 SERVER의 `contracts/v1`이 소유한다. 내부 모델은 wire 계약 자체가 아니다.
`V1WireAdapter` 앞단은 JSON Schema(추가 키, 길이, enum, 날짜 포함)와 계약 관계 규칙을 검증해야 한다.
adapter는 revision 정수/범위, 숫자 문자열 거부, timestamp 파싱, evidence 만료, provider 신뢰도 등 생성에 중요한 경계를 추가로 검사한다.
잘못된 전체 envelope는 adapter에서 예외로 거부하고 호스트가 기본 상태로 전환한다. 순수 extractor는 잘못된 특징값을 UNKNOWN으로 대체한다.

`SourceRegistry`는 호스트가 승인한 (kind, provider)만 NAVI_HELPER/VERIFIED_GIS로 매핑한다. 기본은 아무 producer도 신뢰하지 않는다.
MOCK는 `allowMock=true`인 개발 경계에서만 채택한다. USER_INPUT은 지형 검증 근거가 아니다.
scenic/region 전체 근거 또는 `scenicTags.COASTAL`/`regionTags.<tag>`별 근거를 처리한다.
태그별 근거는 해당 태그만 승인한다. 도로 비율 누락분은 UNKNOWN으로 채우며 과다/음수 비율을 근거로 정규화하지 않는다.
근거는 snapshot의 routeId/revision/값에 묶인다. producer가 오래된 근거를 새 revision에 붙여 보내는 거짓 주장은 이 모듈만으로 탐지할 수 없으므로 adapter 작성자가 재검증해야 한다.

compact wire AvatarSpec에는 의상 없는 경우 `outfit-none`, 장식은 accessoryIds에 포함한다.
후보 점수·감사 데이터·digest는 로컬 sidecar로 보존한다. VoiceProfile은 고정 `nunti-default-v1`, persona `COMPANION`, style `CALM`, 지원 제어 목록은 빈 배열이다.
SDK 지원 가능 여부와 실제 화자는 TTS 모듈이 결정한다.
