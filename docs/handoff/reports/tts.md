# TTS 담당 직접 보고

수신일: 2026-11-02, Asia/Seoul. 기존 채팅: 구현 Pleos TTS 음성 시스템 (`01a196fb-2587-77e0-adf0-f4e439247e0e`). PM의 요청에 대한 담당 세션 최종 답변이다. 아래 보고의 문구는 보존하고 로컬 파일 링크만 저장소 상대경로로 바꿨다. Git 미포함 APK 링크는 경로 표기로 바꿨다.

보고 시점의 “remote 없음”은 이후 사용자가 `https://github.com/Pig30nidaE/NUNTI.git`를 지정하면서 해소됐다. PM이 origin을 연결했으며, 최종 이관 상태는 [전체 현황](../STATUS.md)과 [복원 절차](../RELOCATION.md)를 따른다. 이 보고의 `/private/tmp` 경로와 과거 로컬 절대경로는 새 로컬 설정값이 아니다.

2026-11-02 KST 기준으로 읽기 전용 점검을 마쳤습니다. 코드·문서·Git 상태를 변경하거나 다른 세션에 메시지를 보내지 않았습니다.

**TTS 구현과 에뮬레이터 검증 결과는 루트 저장소에 통합되어 있습니다.** 다만 이전 `/private/tmp`의 worktree, SDK, 컴파일러 캐시, Pleos AVD는 현재 모두 없어졌습니다. 새 로컬은 루트 저장소와 커밋된 증거를 기준으로 환경을 다시 구성해야 합니다.

1. **TTS의 책임과 설계는 다음으로 확정되어 있습니다.**

   TTS는 승인된 텍스트를 읽습니다. 운전 점수 계산, 위험 판정, 최종 코멘트 생성, 아바타 감정 변경은 담당하지 않습니다. 종료 코멘트는 공백·줄바꿈까지 원문을 유지합니다.

   순수 Kotlin 정책·큐·모델을 Android/Pleos 코드와 분리했습니다. 기본 설정은 `nunti-default-v1`, `ko-KR`, `ON_DEVICE`, 플랫폼 기본 화자입니다. 경로와 감정이 달라져도 검증되지 않은 화자로 바꾸지 않습니다.

   여섯 감정은 논리적 스타일로 매핑합니다. 속도·음높이·감정 음향 제어는 구현하지 않았습니다. 실제 SDK에 `setSpeakerType(String)`은 있지만 허용 화자 값이 확인되지 않아 호출하지 않습니다.

   주행 중 TTS를 일괄 금지하지는 않습니다. 실제 차량 상태와 검토된 기능 허가가 모두 확인된 짧은 요청만 허용합니다. `STOPPED`, `PRE_TRIP`, UX 제한 비트만으로 주차나 발화 허가를 추정하지 않습니다. 통화·내비·중요 오디오 상태가 불명확해도 차단합니다.

   현재 제품 정책의 기본값은 다음과 같습니다. OEM이 정한 수치로 표현하면 안 됩니다.

   | 항목 | 기본값 |
   |---|---:|
   | 대기 요청 | 최대 8개 |
   | trip별 중복 확인용 ID | 최대 4,096개 |
   | 요청 TTL | 최대 120초 |
   | 전체 텍스트 | 최대 2,000 codepoint |
   | 주행 중 텍스트 | 최대 80 codepoint |
   | 주행 중 발화 간격 | 최소 15초 |
   | 동일 문구 제한 | 60초 |
   | 플랫폼 상태 유효기간 | 5초 |
   | 초기화 / 시작 / 재생 timeout | 5초 / 3초 / 30초 |

   SDK 콜백에는 요청 ID가 없습니다. 이전 요청의 늦은 콜백을 다음 요청에 연결하지 않도록 종료마다 연결을 해제하고 새 연결과 내부 세대 번호를 사용합니다. 이 선택의 반복 초기화 비용은 후속 측정 대상입니다.

   기존 계획에서 수정·확정된 사항도 보존해야 합니다. wire의 `contentSource`는 텍스트 출처로 유지하고 `speechPurpose`를 별도로 추가했습니다. 기본 프로필 ID는 AVATAR와 맞춰 `nunti-default-v1`로 통일했습니다. 알 수 없는 감정은 임의로 NEUTRAL로 바꾸지 않고 거부합니다. 외부 감정형 TTS는 MVP 필수 의존성이 아닙니다.

2. **구현은 완료되어 있으며, 남은 작업은 운영 연결과 검증입니다.**

   | 구현 범위 | 주요 파일 |
   |---|---|
   | 로컬 모델, wire 매핑, 신뢰 근거 | [Models.kt](../../../android/feature/tts/src/main/kotlin/ai/nunti/tts/Models.kt), [ContractBridge.kt](../../../android/feature/tts/src/main/kotlin/ai/nunti/tts/ContractBridge.kt) |
   | 프로필·감정 매핑, 요청 검증 | [VoiceProfiles.kt](../../../android/feature/tts/src/main/kotlin/ai/nunti/tts/VoiceProfiles.kt) |
   | 차량 출력 정책 | [SpeechPlaybackPolicy.kt](../../../android/feature/tts/src/main/kotlin/ai/nunti/tts/SpeechPlaybackPolicy.kt) |
   | 큐, 중복·만료·취소, lifecycle | [SpeechQueueManager.kt](../../../android/feature/tts/src/main/kotlin/ai/nunti/tts/SpeechQueueManager.kt) |
   | Provider 인터페이스와 Mock | [TtsProvider.kt](../../../android/feature/tts/src/main/kotlin/ai/nunti/tts/TtsProvider.kt) |
   | Pleos 연결·등록·콜백·해제 | [PleosTtsProvider.kt](../../../android/feature/tts/src/main/kotlin/ai/nunti/tts/PleosTtsProvider.kt), [AndroidPleosConnection.kt](../../../android/feature/voice/src/main/kotlin/ai/nunti/voice/AndroidPleosConnection.kt) |
   | Android 진입점·포커스·UX 입력 | [AndroidVoiceSession.kt](../../../android/feature/voice/src/main/kotlin/ai/nunti/voice/AndroidVoiceSession.kt), [AndroidAudioFocusController.kt](../../../android/feature/voice/src/main/kotlin/ai/nunti/voice/AndroidAudioFocusController.kt), [CarUxRestrictionFeed.kt](../../../android/feature/voice/src/main/kotlin/ai/nunti/voice/CarUxRestrictionFeed.kt) |
   | 테스트·시연·재현 도구 | [verify.py](../../../android/feature/tts/scripts/verify.py), [SpeechSystemTest.kt](../../../android/feature/tts/src/test/kotlin/ai/nunti/tts/SpeechSystemTest.kt), [IntegrationFixtureTest.kt](../../../android/feature/tts/src/test/kotlin/ai/nunti/tts/IntegrationFixtureTest.kt), [SpeechDemo.kt](../../../android/feature/tts/src/main/kotlin/ai/nunti/tts/SpeechDemo.kt) |

   A~D Mock 시연은 구현되어 있습니다. Mock Provider 자체는 소리를 생성하지 않습니다.

   실제 음성 실행 경로는 debug 전용 [RuntimeProbeActivity.kt](../../../android/app/src/debug/kotlin/ai/nunti/app/RuntimeProbeActivity.kt)에 연결되어 있습니다. 일반 앱 화면에서 실제 주행 데이터와 운영 리포트를 자동 발화하는 제품 흐름까지 완료한 상태는 아닙니다.

   외부 TTS Provider, 감정 음성 클립 재생기, 실제 음향 감정 제어, Pleos PCM 선행 묵음 삽입, 재생 상태 서버 업로드는 구현하지 않았습니다. 추가 작업이 진행 중인 미커밋 TTS 코드는 없습니다.

3. **검증 결과는 자동 검사, 빌드, 에뮬레이터 실행을 구분해서 전달해야 합니다.**

   이번 점검에서는 테스트·빌드·에뮬레이터를 재실행하지 않았습니다. 저장된 결과, 소스, APK와 증거 파일을 직접 확인했습니다.

   | 검증 | 기록된 결과 |
   |---|---|
   | JVM 자동 테스트 | 62개 통과 |
   | 실제 SERVER/AVATAR JSON fixture 연동 | 8개 통과 |
   | Mock A~D 시연 | 통과 |
   | Android 35 + android.car + 실제 Pleos 3.3.1 바이너리 컴파일 | 통과 |
   | 통합 debug APK 및 Lint | 성공, 최종 기록 오류 0개·경고 3개 |
   | release APK | 빌드 성공, 진단 Activity 제외 확인. unsigned 산출물 |
   | Pleos ON_DEVICE | 초기화, 한국어 설정, 재생 시작·완료, 출력 PCM 확인 |
   | 사용자 중지·백그라운드 | `USER_CANCELLED`, `BACKGROUND` 확인 |
   | 복귀 후 동일 문장 | `REPEATED_TEXT` 거부 확인 |

   현재 재현 명령은 다음과 같습니다. 첫 명령은 저장소 루트에서, Gradle 명령은 Android SDK 경로를 설정한 뒤 실행합니다.

   ```sh
   python3 android/feature/tts/scripts/verify.py --bootstrap --android

   cd android
   ./gradlew :feature:tts:verifySpeech :app:assembleDebug :app:lintDebug
   ./gradlew :app:assembleRelease
   ```

   `:feature:tts:verifySpeech`는 62개 테스트를 실행합니다. 실제 JSON fixture 8개까지 포함하려면 `verify.py`를 사용해야 합니다. 캐시가 없는 첫 빌드에 `--offline`을 붙이면 안 됩니다.

   런타임 재현은 [verify_runtime_probe.py](../../../android/scripts/verify_runtime_probe.py)와 [Pleos 런타임 보고서](../../../docs/architecture/pleos-runtime.md)를 사용합니다.

   ```sh
   python3 android/scripts/verify_runtime_probe.py \
     --adb "$ANDROID_HOME/platform-tools/adb" \
     --serial emulator-5554 \
     --output /tmp/nunti-runtime-lifecycle.json
   ```

   이 스크립트는 설치된 debug 앱을 대상으로 실행하며, Android 사용자 `10`을 사용합니다. 새 AVD의 사용자 구성이 다르면 확인이 필요합니다. 실행 중 앱을 재시작하고 음성을 재생하므로 읽기 전용 검사가 아닙니다.

   핵심 증거는 [검증 증거 디렉터리](../../../docs/architecture/validation-evidence)와 [런타임 manifest](../../../docs/architecture/validation-evidence/pleos-runtime/manifest.json)에 있습니다. 이번 점검에서 런타임 증거 28개, TTS provenance 4개, 루트 통합 증거 5개의 해시를 대조했고 모두 일치했습니다.

   에뮬레이터 검증 범위는 제한적입니다. 공식 Pleos Connect 2.1.0 ARM/API34에서 실제 기어 P, 속도 0, UX 제한 0을 관찰했습니다. 경로·감정·발화 텍스트는 Mock 입력입니다. 경쟁 오디오가 없다는 조건도 운영자가 통제한 테스트 조건입니다. 서버 HTTP, 실제 내비게이션 경로, 점수 담당자의 실제 코멘트까지 이어지는 운영 E2E 검증은 아닙니다.

   최종 발화는 `QUEUED → STARTED → COMPLETED`를 기록했습니다. 41ms와 최초 발화의 73ms는 각각 submit부터 SDK `onStart`까지의 단일 관찰입니다. 최초 가청 샘플 지연이나 p50/p95 성능 수치로 사용할 수 없습니다.

   [최종 WAV](../../../docs/architecture/validation-evidence/pleos-runtime/tts-final.wav)는 48kHz·16bit·stereo, 7.166875초이며 nonzero sample 293,067개입니다. 인간 청취에 의한 발음·첫 음절·음질 평가는 아직 하지 않았습니다.

4. **새 로컬의 기준은 TTS 단독 브랜치보다 현재 통합 브랜치입니다.**

   | 구분 | 현재 상태 |
   |---|---|
   | 루트 경로 | `/Users/pig30nidae/Pig30nidaE/Project/Nunti` |
   | 루트 브랜치 | `server/integration-v1` |
   | 루트 HEAD | `bc0a9483d4baaefee397635dd3dc01fe2b7f4b3e` |
   | TTS 담당 브랜치 | `codex/tts-system` |
   | TTS 브랜치 HEAD | `e640908963eba85571e7fa553c506d0f72f28ecf` |
   | 루트 미커밋·미추적 파일 | 없음 |
   | Git remote | 설정 없음 |

   TTS 소유 경로 34개 파일은 담당 브랜치와 루트 사이에 diff가 없습니다. 최종 TTS 문서는 루트의 `98a1ec5`에 통합됐고, 에뮬레이터 실행 증거는 `bc0a948`에 포함됩니다. 이미 통합된 TTS 커밋을 다시 cherry-pick할 필요가 없습니다.

   `/private/tmp/nunti-tts-worktree`와 `/private/tmp/nunti-avatar`는 사라졌습니다. `git worktree list`에는 `prunable` 등록 정보만 남아 있습니다. 옛 임시 경로를 인수인계 프롬프트의 작업 위치로 사용하면 안 됩니다.

   소스, fixture, Gradle wrapper JAR, 참고 WAV, 실제 Pleos 캡처 WAV, 로그·스크린샷은 Git에 들어 있습니다. 반면 다음 APK는 ignored 산출물이므로 일반 Git 이관에 포함되지 않습니다. **검증 당시의 바이너리 자체를 보존하려면 별도로 복사해야 합니다.**

   | ignored 산출물 | 현재 SHA-256 |
   |---|---|
   | `android/build/app/outputs/apk/debug/app-debug.apk` | `87f207f35418d1979133c903117327eb46cc4fc0a3aa6a40847a5a24ff74cc58` |
   | `android/build/app/outputs/apk/release/app-release-unsigned.apk` | `e09c1735d9ca0e204965dfabdcbd9a5bd7dba89e50d49615e4fb16dbee21a7a3` |

   `android/feature/tts/build/verification/`의 JAR·로그·properties는 재생성 가능합니다. 주요 결과 사본은 커밋된 증거 디렉터리에 있습니다. `.gradle`, `build`, `__pycache__` 등 캐시도 소스 복원을 위한 필수 파일은 아닙니다.

   remote가 없으므로 PM은 루트 Git 이력의 별도 이관 방법을 마련해야 합니다. 이번 점검에서는 bundle 생성, push, worktree 정리를 수행하지 않았습니다.

5. **새 로컬에서는 도구와 런타임 환경을 다시 설치해야 합니다.**

   | 용도 | 검증에 사용한 구성 |
   |---|---|
   | 통합 Gradle 빌드 | JDK 21, Gradle 8.11.1, AGP 8.10.1, Kotlin 2.2.21 |
   | 생성 bytecode | Java/Kotlin target 17 |
   | Android 앱·voice | compileSdk 35, minSdk 28, android.car |
   | Pleos SDK | `ai.pleos.playground:TextToSpeech:3.3.1` |
   | 독립 TTS 검증 스크립트 | Python 3.9 이상, JDK 17 이상, Kotlin compiler 2.2.20 |
   | 실제 검증 호스트 | macOS ARM, Temurin 21.0.8 |
   | 에뮬레이터 | Android Emulator 37.2.13, Pleos Connect 2.1.0 ARM/API34, RAM 4GB, cold boot |

   Gradle 설정은 toolchain 21을 요구하므로 새 로컬에서는 JDK 21을 준비하는 편이 맞습니다. Java와 Kotlin target을 모두 17로 유지해야 합니다. 첫 통합 빌드에서 Java 21/Kotlin 17 불일치가 발생했고 이를 수정했습니다.

   SDK 저장소는 `https://nexus-playground.pleos.ai/repository/maven-releases/`입니다. 독립 검증 스크립트는 [toolchain-lock.json](../../../android/feature/tts/scripts/toolchain-lock.json)의 공식 다운로드 URL과 SHA-256으로 컴파일러·Pleos AAR·Android JAR을 복원합니다. 이것만으로 에뮬레이터나 전체 Android SDK가 설치되지는 않습니다.

   다음 외부 경로는 이번 점검에서 모두 존재하지 않았습니다.

   - `/private/tmp/nunti-tts-tools`
   - `/private/tmp/nunti-android-build`
   - `/private/tmp/nunti-pleos-runtime`
   - `/Users/pig30nidae/Library/Android/sdk`

   Pleos 시스템 이미지와 emulator 설치 기록은 [tool-provenance.json](../../../docs/architecture/validation-evidence/pleos-runtime/tool-provenance.json)에 있습니다. 기록은 macOS ARM 기준이므로 다른 OS·CPU에서는 호환 배포물을 확인해야 합니다. 이미지 ZIP은 약 4.67GB였고 해제 공간도 별도로 필요했습니다.

   설정에 사용하는 이름은 `JAVA_HOME`, 선택적 `NUNTI_JAVA`, `ANDROID_HOME`, `ANDROID_USER_HOME`, `ANDROID_AVD_HOME`, `GRADLE_USER_HOME`입니다. 현재 이 환경변수들은 설정되어 있지 않고 `android/local.properties`도 없습니다.

   `ON_DEVICE`에는 앱 등록 자격 증명이 필요하지 않습니다. `HYBRID`와 `SERVER`에는 `PleosCredentials.clientId`, `clientSecret`이 필요합니다. Pleos 프로젝트에서 발급받아 호스트의 credential callback으로 공급해야 하며 소스·로그에 넣지 않습니다. TTS 구현에는 고정된 비밀정보 환경변수 이름이 없습니다.

   추가 복원 공백이 하나 있습니다. lifecycle 재현 스크립트는 커밋되어 있지만, 실제 WAV를 수집했던 gRPC 오디오 캡처 클라이언트는 현재 저장소에서 찾지 못했습니다. WAV·포맷·수치·해시는 보존되어 있습니다. 새 캡처를 자동화하려면 클라이언트와 새 에뮬레이터 세션의 인증 처리를 별도로 복원해야 합니다.

6. **남은 우선순위는 검증 범위를 넓히는 것입니다.**

   가장 큰 차단사항은 실제 D 전환입니다. Virtual Console이 `emulator_inactive`, `dds_ready=false` 및 HTTP 503을 반환했습니다. `hmg_car_service`는 없었고 `car_service` 명령은 user build 제한으로 거부됐습니다. P에서 D·주행 속도로 전환했을 때의 차단과 재주차 복귀는 통과한 것으로 보고하면 안 됩니다.

   다음 우선순위는 새 로컬에서 환경을 복원하고 62개 테스트·8개 연동 검사를 재현한 뒤, 저장된 실제 WAV의 인간 청취 평가를 수행하는 것입니다. 이후 정상 동작하는 차량 시뮬레이터 또는 검증 장치로 주행 상태 변경 중 재생 차단을 확인해야 합니다.

   그다음에는 실제 통화·내비·안전음과의 포커스 충돌, Suspend/Resume, 네트워크 단절과 HYBRID 전환, SERVER 실패, 장시간 연결·리스너·메모리 누수를 검사해야 합니다.

   선행 묵음은 아직 해결되지 않았습니다. 공식 가이드의 150~200ms 권장값은 조사했지만 확인한 Pleos API에는 PCM 결과나 padding 제어가 없습니다. 참고 Yuna WAV에 넣은 180ms 묵음을 Pleos 구현 증거로 사용하면 안 됩니다.

   화자 목록, 감정별 실제 음색·속도·피치, 최초 가청 샘플 지연, 취소부터 실제 무음까지의 시간도 미검증입니다. 외부 감정형 TTS 도입은 이런 측정에서 필요한 개선점이 확인된 뒤 판단합니다.

   문서를 읽을 때도 시점을 구분해야 합니다. 초기 빌드 provenance의 `runtimeAudioTested: false`와 초기 APK 해시는 당시 기록입니다. 최신 런타임 상태는 [pleos-runtime.md](../../../docs/architecture/pleos-runtime.md)와 그 manifest를 기준으로 삼아야 합니다.

7. **소유권과 계약 경계는 다음 세션에서도 유지해야 합니다.**

   TTS 소유 영역은 `android/feature/tts/`, `android/feature/voice/`, `docs/coordination/tts.md`입니다. 앱 shell·루트 Gradle·아바타·감정 로직은 AVATAR 담당과, 공통 wire 계약·서버 API는 SERVER 담당과 협의합니다. debug 진단 Activity와 런타임 검사 스크립트는 SERVER의 통합 작업이므로 TTS가 임의 수정하지 않습니다.

   wire `contentSource`는 `MOCK`, `TEMPLATE`, `EXTERNAL_REPORT`입니다. 발화 목적은 별도 `speechPurpose`의 `PRE_DRIVE_GREETING`, `VERIFIED_EVENT_RESPONSE`, `USER_INITIATED`, `POST_DRIVE_REPORT`입니다. TTS 로컬 모델의 `contentSource`는 목적 enum이므로 이름만 보고 wire와 직접 연결하면 안 됩니다. `SpeechContractBridge`를 사용해야 합니다.

   `SpeechEvidence`는 신뢰된 호스트가 공급합니다. wire의 출처 문자열 자체를 승인 근거로 삼지 않습니다. Mock은 기본 거부이며 진단 경로에서만 명시적으로 허용합니다. 감정·trip·avatar·emotion ID가 맞지 않는 요청은 거부합니다.

   [AvatarVoiceBridge.kt](../../../android/app/src/voiceIntegration/kotlin/ai/nunti/app/AvatarVoiceBridge.kt)는 읽기 전용 DTO 변환입니다. AVATAR의 상대 감정 시각을 `sessionEpochMillis + since`로 변환하므로 같은 세션 기준 시각을 전달해야 합니다. AVATAR의 `PRE_DRIVE`, `POST_DRIVE`는 TTS의 `PRE_TRIP`, `POST_TRIP`으로 매핑합니다.

   Android 진입 순서는 main thread에서 `AndroidVoiceSession` 생성, `beginTrip`, 최신 context를 사용한 `onForeground`, `submit` 또는 `submitWire`입니다. 세션 생성보다 오래된 `requestedAt`은 `BEFORE_SESSION`으로 거부됩니다. 과거 fixture를 그대로 재생하려 하지 말고 승인된 텍스트로 새 요청을 만들어야 합니다.

   `onBackground`는 재생·큐를 취소합니다. `onSuspend`는 세션을 폐기하므로 Resume에서는 새 객체가 필요합니다. 자동 재생은 하지 않습니다. Car UX listener는 호스트에서 공유하고 `CarUxRestrictionFeed`를 중복 등록하지 않습니다.

   새 TTS 담당은 **통합 HEAD `bc0a948`을 기준으로 새 worktree를 만들고, 기존 정책을 유지한 채 환경 복원과 검증부터 시작**하면 됩니다. 현재 기능 구현을 다시 만들거나 이미 통합된 커밋을 재적용할 필요는 없습니다.
