# AVATAR 담당 직접 보고

수신일: 2026-11-02, Asia/Seoul. 기존 채팅: 경로 기반 아바타 시스템 개발 (`01a196f9-9015-7aa2-81b7-a0e111fcc209`). PM의 요청에 대한 담당 세션 최종 답변이다. 아래 보고의 문구는 보존하고 로컬 파일 링크만 저장소 상대경로로 바꿨다. Git 미포함 APK 링크는 경로 표기로 바꿨다.

보고 시점의 “remote 없음”은 이후 사용자가 `https://github.com/Pig30nidaE/NUNTI.git`를 지정하면서 해소됐다. PM이 origin을 연결했으며, 최종 이관 상태는 [전체 현황](../STATUS.md)과 [복원 절차](../RELOCATION.md)를 따른다. 이 보고의 `/private/tmp` 경로와 과거 로컬 절대경로는 새 로컬 설정값이 아니다.

2026-11-02 기준 아바타 담당 현황입니다. **MVP 구현과 Pleos 화면 검증은 통합 브랜치에 반영됐습니다.** 실제 내비게이션 입력, 운영용 저장·복원 연결, 실제 주행 상태 전환 검증은 남아 있습니다. 이번 점검에서는 파일이나 Git 상태를 변경하지 않았고, 기존 테스트를 재실행하지 않았습니다.

1. 확정된 요구사항·설계 결정과 후속 변경

   눈티는 경로마다 다른 캐릭터가 아니라, 같은 캐릭터의 의상·소품·장식이 바뀌는 구조입니다. 얼굴, 몸체, 눈·입 앵커, 핵심 색, 표식, 성격과 음성 프로필은 유지합니다.

   구현 방식은 Kotlin 규칙 엔진, 2D 파츠 조립, Compose Canvas, 순수 감정 reducer입니다. 생성형 이미지 모델과 3D는 도입하지 않았습니다. 생성 타당성과 재현성을 시각적 완성도보다 우선한다는 요구를 따랐습니다.

   목적지 이름이나 `routeOption`으로 도로 비율·해안·산악 여부를 추정하지 않습니다. 검증되지 않은 특징은 `UNKNOWN`으로 처리하며, 근거가 부족하면 기본 눈티를 생성합니다. 근거는 경로 ID, revision, 특징값에 묶입니다.

   후보를 모두 평가하고 선택·탈락 이유를 보존합니다. 현재 후보는 `BASE`, `CITY`, `JOURNEY`, `COASTAL`, `MOUNTAIN`입니다. 점수 가중치는 관련성 5, 신뢰도 2, 시각 일관성 1, 충돌 감점 100이며, 여정 이력 없이 다양성을 만들지 않도록 다양성 가산점은 0입니다. seed는 정확히 동점인 후보 사이에서만 사용합니다.

   거리·시간·도로 비율 기준과 감정 유지시간은 합성 테스트용 초기 설정입니다. 실도로 자료로 보정된 기준이 아닙니다.

   내부 감정과 화면 표현은 분리했습니다. 플랫폼 상태가 없거나 차단됐거나 5초보다 오래되면 화면과 접근성 설명을 숨깁니다. 명시적으로 허용된 주행 중 정적 화면에서는 중립 표정과 고정 외형만 표시합니다. 기본 앱은 Automotive에서 실제 호스트 연결 전 빈 화면을 유지합니다.

   후속 협의로 SERVER가 debug 전용 `RuntimeProbeActivity`를 추가했습니다. 실제 Pleos 넓은 창에서 발견된 Canvas 겹침은 외부 `aspectRatio`를 제거하고 높이를 320dp로 지정해 수정했습니다. 좁은 창 검증은 `wm size` 대신 실제 `am task resize` 결과로 정정했습니다.

   사용자는 SERVER 및 TTS 채팅에 협업 메시지를 보내는 것을 각각 명시적으로 허용했습니다. 이번 PM 보고에는 다른 채팅으로 메시지를 보내지 않았습니다.

2. 구현 완료·미구현 기능과 주요 파일

   | 상태 | 기능 | 주요 파일 |
   |---|---|---|
   | 완료 | 근거 검증, 거리·시간 분류, 우세 도로·지형 추출, 감사 기록 | [RouteFeatures.kt](../../../android/feature/navigation/src/main/kotlin/ai/nunti/navigation/RouteFeatures.kt) |
   | 완료 | 후보 생성·평가·제약 검사, 결정적 ID와 결과, 생성 설명 | [AvatarEngine.kt](../../../android/feature/avatar/src/main/kotlin/ai/nunti/avatar/AvatarEngine.kt) |
   | 완료 | Identity/Journey 파츠, 슬롯·배타·대비·얼굴 가림·앵커 제약 | [Assets.kt](../../../android/feature/avatar/src/main/kotlin/ai/nunti/avatar/Assets.kt), [리소스 설정](../../../android/feature/avatar/src/main/resources) |
   | 완료 | 공통 scene, Canvas 렌더링, 자산 교체 인터페이스, 표시 정책 | [Rendering.kt](../../../android/feature/avatar/src/main/kotlin/ai/nunti/avatar/Rendering.kt), [NuntiAvatar.kt](../../../android/feature/avatar/src/compose/kotlin/ai/nunti/avatar/NuntiAvatar.kt) |
   | 완료 | 6개 감정, 우선순위·중복·역순·만료·회복·debounce·cooldown·hysteresis | [EmotionMachine.kt](../../../android/feature/emotion/src/main/kotlin/ai/nunti/emotion/EmotionMachine.kt) |
   | 완료 | v1 계약 변환, producer 신뢰 등록, 아바타 재현 기록 | [WireAdapter.kt](../../../android/feature/avatar/src/main/kotlin/ai/nunti/avatar/WireAdapter.kt) |
   | 완료 | 이벤트·tick·수신 시각을 이용한 감정 상태 복원 | [EmotionReplay.kt](../../../android/feature/avatar/src/main/kotlin/ai/nunti/avatar/EmotionReplay.kt) |
   | 완료 | 일반 Android Mock 앱, 감정 이벤트 재생, TTS DTO 변환 | [MainActivity.kt](../../../android/app/src/main/kotlin/ai/nunti/app/MainActivity.kt), [AvatarVoiceBridge.kt](../../../android/app/src/voiceIntegration/kotlin/ai/nunti/app/AvatarVoiceBridge.kt) |
   | SERVER 통합 완료 | 실제 Car 상태와 Pleos TTS를 사용하는 debug 진단 화면 | [RuntimeProbeActivity.kt](../../../android/app/src/debug/kotlin/ai/nunti/app/RuntimeProbeActivity.kt) |

   현재 아바타 담당의 미커밋 구현 작업은 없습니다. 남은 기능은 다음과 같습니다.

   - 실제 NaviHelper 응답을 `RouteSnapshot`으로 변환하는 어댑터와 실제 GIS 검증 공급자.
   - 실제 주행 이벤트 생산자 연결 및 정식 이벤트 의미 합의.
   - 운영 앱의 실제 trip·차량·정책·서버 동기화 연결.
   - `AvatarReplay`와 `EmotionJournal`을 운영 저장소에 원자적으로 기록하고 복원하는 호스트 구현. 현재 라이브러리의 인코딩·복원과 파일 왕복 테스트는 완료됐지만, 기본 앱은 경로 선택과 seed를 저장하는 Mock 수준입니다.
   - 실제 경로 복잡도 산출. 현재 `routeComplexity`는 `UNKNOWN`입니다. 검증 지역 태그는 추출하지만 지역별 디자인 규칙은 없습니다.
   - 최종 캐릭터 디자인 자산, 다양한 포즈, 사용자 평가. 기본 포즈는 `standing`이며 자동 애니메이션은 없습니다.

   점수 계산, 최종 코멘트 생성, TTS SDK 내부 구현은 아바타 담당 범위가 아닙니다.

3. 실제 검증 명령·결과·증거와 한계

   마지막 기능 검증은 2026-11-01 기록입니다.

   | 검증 | 결과 |
   |---|---|
   | AVATAR JVM 시나리오 | 58개 통과 |
   | 합성 경로 1,000개 | 동일 결과 1,000, 파츠 충돌 0, 근거 있는 출력 1,000, 근거 제거 후 fallback 1,000 |
   | SERVER 계약 연동 | 실제 Kotlin JSON 10개 검증, 경로·아바타 4쌍 API 저장·조회 |
   | TTS 계약 연동 | 실제 fixture 8개 통과 |
   | 최종 runtime debug 빌드·Lint | 42초 빌드 성공, Lint 오류 0·경고 3 |
   | release 빌드 | 38초 성공, 진단 Activity 제외 확인 |

   핵심 테스트는 [test.sh](../../../android/feature/avatar/scripts/test.sh)로 실행했습니다. 당시 `KOTLINC`, `JSON_JAR`, `CONTRACT_ROOT`를 지정했습니다. 재현 명령은 새 로컬 경로에 맞춰 아래처럼 사용할 수 있습니다.

   ```sh
   NUNTI_ROOT=/absolute/path/to/Nunti
   export JAVA_HOME=/absolute/path/to/jdk-21
   export PATH="$JAVA_HOME/bin:$PATH"

   KOTLINC=/absolute/path/to/kotlinc \
   JSON_JAR=/absolute/path/to/json-20250517.jar \
   CONTRACT_ROOT="$NUNTI_ROOT/contracts/v1" \
   bash "$NUNTI_ROOT/android/feature/avatar/scripts/test.sh"

   "$NUNTI_ROOT/backend/.venv/bin/python" \
     "$NUNTI_ROOT/backend/scripts/verify_android_outputs.py"

   export ANDROID_HOME=/absolute/path/to/android-sdk
   "$NUNTI_ROOT/android/gradlew" -p "$NUNTI_ROOT/android" \
     --no-daemon --console=plain :app:assembleDebug :app:lintDebug
   ```

   `JSON_JAR`를 생략하면 테스트 스크립트가 고정 버전을 다운로드합니다. 첫 Gradle 빌드에는 네트워크가 필요합니다.

   증거는 [루트 AVATAR 테스트 로그](../../../docs/architecture/validation-evidence/root-avatar-tests.txt), [아바타 검증 보고서](../../../android/feature/avatar/reports/validation.md), [최종 Pleos 검증 보고서](../../../docs/architecture/pleos-runtime.md)에 있습니다.

   Pleos Connect 2.1.0 ARM, API 34, Emulator 37.2.13에서 실제 P 기어·속도 0·UX 0을 읽었습니다. 도심·장거리·해안·산악 외형과 놀람·기쁨 표정을 확인했습니다. 1682×1210 앱 창과 847×910으로 줄인 CITY 화면에서 겹침이 없었습니다. 경로와 감정 입력은 Mock입니다. 실제 서버 HTTP와 NaviHelper 입력은 이 시연 경로에 포함되지 않습니다.

   SERVER의 최종 기록에는 실제 Pleos ON_DEVICE TTS 출력, 사용자 중지, 백그라운드 중지, 반복 발화 차단도 포함됩니다. 사람의 청취를 통한 발음·첫 음절·음질 평가는 수행하지 않았습니다.

   실제 D 전환·주행 UX 제한·재주차 복귀는 미검증입니다. Virtual Console이 `emulator_inactive`로 HTTP 503을 반환했고, DDS가 준비되지 않았습니다. `hmg_car_service`는 없었고 일반 `car_service` 명령은 user build 제한으로 거부됐습니다. 회전·접근성 instrumentation과 모든 창 크기 조합도 검증하지 않았습니다.

   이번 점검에서는 runtime manifest의 **28개 증거 파일 해시가 모두 일치**하고, 현재 debug·release APK가 [APK provenance](../../../docs/architecture/validation-evidence/pleos-runtime/apk-provenance.json)와 일치함을 확인했습니다.

   기존 `root-integration.json`의 `vehicleRuntimeTested=false`, 초기 APK 해시, 아바타 보고서의 Lint 경고 7개는 이전 빌드 기록입니다. 최종 runtime 결과와 구분해야 합니다. 생성 시간도 초기 측정과 루트 재실행 값이 다르며, 어느 쪽도 실차 성능 보장값이 아닙니다.

4. 브랜치·HEAD·이관할 파일

   | 항목 | 현재 상태 |
   |---|---|
   | 통합 브랜치 | `server/integration-v1` |
   | 통합 HEAD | `bc0a9483d4baaefee397635dd3dc01fe2b7f4b3e` |
   | 아바타 브랜치 | `avatar/route-emotion-v1` |
   | 아바타 HEAD | `e1183b6770c533ce159bc74d77b2e45d17b4d0bd` |
   | 루트 변경·미추적 파일 | 없음 |
   | Git remote | 등록된 remote 없음 |
   | 이전 아바타 worktree | 폴더는 없고 Git 등록만 남아 `prunable` 상태 |

   아바타 기능 최초 구현은 `f6ad9ac`, 통합 커밋은 `e9d500b`입니다. 레이아웃 수정 `01bf3be`는 `3cef188`로, runtime 문서 `802101c`는 `94dc3f6`으로, 좁은 창 문서 `e1183b6`는 `884ccf1`로 통합됐습니다. 아바타 소유 모듈 3개와 협업 문서는 현재 아바타 브랜치와 통합 HEAD 사이에 차이가 없습니다. 다시 cherry-pick할 필요가 없습니다.

   **새 로컬은 통합 HEAD에서 시작해야 합니다.** remote가 없으므로 로컬 브랜치가 다른 컴퓨터에서 자동으로 내려받아진다고 가정하면 안 됩니다. PM이 Git 이력과 통합 브랜치를 bundle 또는 승인된 저장소 전송 방식으로 보존해야 합니다. 이번에는 이관 작업을 실행하지 않았습니다.

   소스, Gradle Wrapper JAR, 파츠 설정, Mock fixture, 데모 이미지·HTML, 테스트 로그, Pleos 캡처·WAV·manifest는 Git에 들어 있습니다. 아바타 기능 재개에 필요한 미추적·ignored 소스는 발견하지 않았습니다.

   ignored 항목은 빌드 출력과 캐시, Python 가상환경입니다. 재생성할 수 있습니다. 다만 검증 당시 APK 바이너리 자체를 보존하려면 다음 두 파일은 별도로 이관해야 합니다.

   - `android/build/app/outputs/apk/debug/app-debug.apk`, SHA-256 `87f207f35418d1979133c903117327eb46cc4fc0a3aa6a40847a5a24ff74cc58`
   - `android/build/app/outputs/apk/release/app-release-unsigned.apk`, SHA-256 `e09c1735d9ca0e204965dfabdcbd9a5bd7dba89e50d49615e4fb16dbee21a7a3`

5. 새 로컬의 도구·의존성·외부 데이터

   | 의존성 | 검증한 버전·복원 방법 |
   |---|---|
   | JDK | Temurin 21. Java/Kotlin 출력 대상은 17 |
   | Kotlin CLI | 2.2.21. 순수 JVM 테스트에 필요 |
   | Gradle | 8.11.1. 저장소 Wrapper로 다운로드하며 체크섬 고정 |
   | AGP | 8.10.1 |
   | Android SDK | platform 35, build-tools 35, platform-tools, `android.car` optional library |
   | Compose | 1.8.3, Activity Compose 1.10.1 |
   | JVM JSON | `org.json:json:20250517`. Android 실행은 플랫폼 `org.json` 사용 |
   | Pleos TTS | `ai.pleos.playground:TextToSpeech:3.3.1`. 저장소에 등록된 Pleos Maven에서 복원 |
   | runtime 검증 | 공식 Pleos Connect 2.1.0 ARM 이미지, API 34, Emulator 37.2.13, RAM 4GB, cold boot |
   | SERVER 계약 검사 | Python 환경과 `backend/uv.lock` 복원. 상세는 SERVER 인수인계 기준 |

   설정 이름은 `JAVA_HOME`, `ANDROID_HOME`, `ANDROID_USER_HOME`, `ANDROID_AVD_HOME`, `GRADLE_USER_HOME`, `KOTLINC`, `JSON_JAR`, `CONTRACT_ROOT`, `AVATAR_BUILD_DIR`입니다. 새 로컬의 실제 설치 경로로 지정해야 합니다. TTS가 같은 checkout에 있으면 `nuntiTtsCheckout` 재정의는 필요 없습니다.

   이전 `/private/tmp`의 아바타 worktree, Kotlin 도구, Android 빌드 SDK·캐시, TTS 검증 도구, Pleos runtime SDK·AVD는 현재 모두 없습니다. 문서에 남은 임시 경로를 그대로 사용하면 실패합니다. JDK 21 설치만 현재 존재함을 확인했습니다.

   아바타 엔진 자체에는 API 키나 외부 모델 자격증명이 필요하지 않습니다. 향후 실제 GIS·내비·서버 연결 자격증명은 해당 담당의 보안 저장소에서 복원해야 합니다. debug 서명키와 에뮬레이터 gRPC 인증 자료는 새 환경에서 생성하며, 보고서에 비밀값을 넣지 않습니다.

6. 알려진 문제·차단사항·다음 우선순위

   가장 먼저 통합 Git 이력을 이관하고 SDK·컴파일러를 재설치해야 합니다. 기존 임시 작업 폴더는 재사용할 수 없습니다.

   그다음 동일한 58개 테스트와 계약 round trip, 통합 APK 빌드를 재실행해 새 환경을 확인해야 합니다. 이후 아바타 기능의 우선순위는 실제 `RouteSnapshot`·`DrivingEvent` 공급자 연결입니다. 전체 경로 거리와 잔여 거리의 의미, 도로 비율 제공 여부, GIS 교차 근거, 이벤트 confidence·correlation·recovery 의미를 먼저 확정해야 합니다.

   운영 호스트에서는 실제 정책 갱신, lifecycle, trip 단계, 저장·복원, 서버 동기화를 연결해야 합니다. `EmotionJournal` 복원 시 재부팅 전 monotonic 시계를 그대로 쓰면 안 됩니다. 현재 decoder 제한은 20,000 entry와 문자열 길이 10,000,000이며, 보존·압축 정책은 호스트 책임입니다.

   실제 주행 차단 검증은 정상 동작하는 차량 시뮬레이터나 검증 장치에서 재개해야 합니다. D 전환 실패를 정책 코드의 성공 또는 실패로 판정할 근거는 없습니다.

   최종 디자인 교체와 사용자 평가는 그 이후입니다. 현재 자산은 교체 가능한 Canvas 임시 디자인입니다. Lint 경고 3개는 임시 앱 아이콘, 백업 설정, KTX 권고이며 출시 준비 작업으로 남아 있습니다.

7. 타 담당과의 계약·소유권·통합 주의사항

   AVATAR 소유는 `android/feature/avatar`, `android/feature/emotion`, `android/feature/navigation`, 전용 렌더링·App Shell, [협업 문서](../../../docs/coordination/avatar.md)입니다. 공통 Gradle과 기본 앱은 SERVER·TTS 합의 후 작성했습니다. debug 진단 Activity와 runtime 검증 스크립트는 SERVER가 협의 후 추가했습니다. 공통 파일을 바꿀 때는 현재 담당 간 소유권을 다시 맞춰야 합니다.

   SERVER는 `contracts/v1`, API, 저장, 시스템 통합을 소유합니다. wire `schemaVersion`은 `1.0`입니다. 내부 Kotlin 모델은 wire 계약 자체가 아니며, 호스트는 `V1WireAdapter` 앞에서 전체 JSON Schema와 관계 규칙을 검증해야 합니다. adapter만으로 모든 계약 검증이 끝났다고 보면 안 됩니다.

   `avatarId`는 `baseCharacterId|routeId`에서 결정하며 revision 변경에도 유지합니다. wire AvatarSpec은 compact projection이므로 후보 점수·감사 기록·rule/asset digest와 복원 자료는 별도 보존해야 합니다. 의상 없음은 `outfit-none`, 지형 장식은 wire `accessoryIds`에 포함합니다.

   `SourceRegistry`는 호스트가 승인한 producer만 신뢰합니다. production에서 `allowMock=true`를 사용하면 안 됩니다. producer는 경로 revision이나 값이 바뀔 때 근거를 재검증해야 합니다. 거짓 producer가 오래된 근거를 새 snapshot에 붙이는 행위까지 아바타 모듈이 판별할 수는 없습니다.

   이벤트 `correlationId`는 사건 중복 방지용 `incidentId`로 전달합니다. 회복은 새로운 event ID를 사용하며 현재 원인 사건과 일치해야 합니다. `EmotionSnapshot.emotionId`는 결정적으로 생성합니다. 점수 담당 이은룡의 모듈이 점수와 최종 코멘트를 소유합니다.

   TTS에는 고정 `voiceProfileId=nunti-default-v1`, persona `COMPANION`, style hint `CALM`, 현재 감정을 전달합니다. 실제 화자·지원 제어·발화 허가·SDK·큐·오디오 포커스는 TTS 책임입니다. `AvatarVoiceBridge`는 DTO 변환만 합니다.

   `CarUxRestrictionsManager` listener는 호스트에서 하나만 등록하고 AVATAR와 TTS에 공유해야 합니다. 두 모듈이 같은 manager에 각각 등록하지 않도록 주의해야 합니다. 다음 아바타 세션은 통합 HEAD를 기준으로 독립 작업 폴더를 만들고, 실제 입력 어댑터와 운영 호스트 연결 범위를 SERVER와 먼저 확정하는 것이 적절합니다.
