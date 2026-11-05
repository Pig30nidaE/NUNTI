# 캐릭터 로컬 음성 구현 및 검증 보고

2026-11-02. TTS worktree `codex/tts-next`, 기준 `ebde9027f97f56f80bf8262c1200dbbb92827483`.

PM이 승인한 debug 비교 범위의 구현과 정적·JVM·APK 검증을 완료했다. PM이 실행한 실제 Pleos 앱 이벤트·인증 PCM·취소 증거도 대조했다. 인간 청취와 제품 음성 선정은 미완료다. 기존 환경 복원 기록은 [복원 보고](../../handoff/restoration/2026-11-02/tts.md)에 보존했다. 이번 변경은 미커밋 상태다.

## 착수 전 경계

기존 `SpeechQueueManager` 한 개가 정책·TTL·중복·포커스·취소를 계속 소유한다. `AndroidVoiceSession`에 provider factory 주입 지점을 추가한다. 진단 session은 기본 Pleos와 로컬 WAV를 요청별로 고르는 provider를 사용하되, 큐·포커스는 공유한다. 로컬 파일은 `MediaPlayer`로 재생하며 콜백 세대 번호로 취소된 요청의 늦은 이벤트를 차단한다. 실제 파일 출력의 mode는 새 로컬 enum `LOCAL_FILE`로 구분하고 provider 식별도 기록한다. wire 1.0은 수정하지 않는다.

로컬 catalog는 캐릭터 ID·profile ID·speaker ID·원문 UTF-8 SHA-256·WAV SHA-256·파일명·locale을 소유한다. 파일은 app-private `files/journey-voice/`에 주입한다. 파일명은 단일 WAV basename만 허용한다. 최초 binding을 별도 app-private 파일에 원자적으로 저장하고 같은 캐릭터에 다른 binding이 들어오면 거부한다. 재시도·reroute·프로세스 재시작은 기존 binding을 사용한다. 자산 공급과 재생 요청은 분리하며 manifest 로드·앱 시작은 자동 발화하지 않는다.

PM 확정 입력 `providerId`와 `clips` 형식을 사용한다. clip은 `characterId`, `profileId`, `speakerId`, `text`, `textSha256`, `audioPath`, `audioSha256`, `sampleRateHz`, `channels`, `sampleWidthBytes`, `durationMs`, `sourceModelRevision`, `bindingId`, `preset`, nested `binding`을 가진다. 외부 JSON은 Android 경계에서 타입과 outer/nested 정합성을 검사한다. 원본 manifest를 debug assets에 보존했다.

음성 정체성 fingerprint는 provider·캐릭터·profile·speaker·locale·model revision·bindingId·speed/steps·catalog hash다. 문장 목록과 WAV hash는 정체성 fingerprint에 넣지 않는다. 같은 binding의 새 문장은 허용하고 화자·preset 변경은 `VOICE_BINDING_CHANGED`로 거부한다. 별도로 캐릭터+원문 SHA마다 음원 SHA·PCM 포맷·duration을 고정하여, 이미 등록한 같은 문장의 음원을 새 manifest로 바꿔도 `VOICE_ASSET_CHANGED`로 거부한다. 두 종류의 고정값은 한 ledger에 원자적으로 저장한다. 각 파일은 원문 SHA·파일 SHA·실제 RIFF PCM16·채널·rate·duration을 검사한 뒤에만 저장한다. 같은 profile을 여러 캐릭터가 공유할 수 있으나 자산 선택에는 character도 반드시 일치해야 한다.

`PreparedSpeech`의 avatar/profile/speaker/locale 및 원문 hash와 catalog가 모두 일치해야 재생한다. 누락·불일치·파일 손상·binding 변경은 명시 사유로 거부하며 Pleos fallback은 하지 않는다. 기존 기본 음성 액션은 유지한다. 새 debug 액션은 `local_speak`와 `character` extra로 명시 실행한다. 같은 문장을 캐릭터만 바꿔 연속 요청해도 기존 중복 억제를 우회하지 않는다.

공통 Gradle·production host·backend·wire 변경은 계획하지 않는다. Supertonic3는 미리 만든 실험 WAV의 출처이며 Android에 모델 runtime을 넣지 않는다. 실제 sample 생성은 PM 소유다.

## v2 음원과 적용 범위

사용자의 “전체적으로 더 작고 귀여운 느낌” 요청에 맞춰 PM이 제공한 `samples-v2`를 import했다. 공통 비교 문장은 `안녕하세요. 오늘의 여행도 함께할게요.`이며 캐릭터별 인사까지 총 6개다. v1 원본은 PM 소유 경로에 보존했다.

| 캐릭터 | 고정 profile | 화자 | 생성 speed/steps | 공통/인사 길이 |
| --- | --- | --- | --- | --- |
| 파도빛 · coast | `nunti-keepsake-calm-v2` | F3 | 1.04 / 16 | 4029 / 6848ms |
| 이끼별 · mountain | `nunti-keepsake-curious-v2` | F4 | 1.08 / 16 | 3269 / 5485ms |
| 조각빛 · city | `nunti-keepsake-clear-v2` | F5 | 1.06 / 16 | 3702 / 6422ms |

실제 파일은 44100Hz·mono·PCM16이다. 생성 후 개발 머신에서 길이를 유지하는 +3 semitone DSP를 적용한 후보이며 Android/Pleos의 runtime pitch 지원을 뜻하지 않는다. 원본 manifest의 DSP·출처·binding 기록을 그대로 보존했다. manifest SHA-256은 `abb1baa0bb4e9caa3506ef735231980e2de342b4466483f425c681ed2b35be7b`다.

기존 `nunti-default-v1`/Pleos 액션은 그대로다. 새 캐릭터 profile은 debug catalog의 명시 요청에만 사용한다. `TripReport.finalText` 변형, 점수·최종 코멘트 생성, production host 연결, 공통 Gradle·backend·wire 변경은 없다.

변경 위치는 TTS의 catalog·binding ledger·파일 provider·큐의 provider 선택 단계, voice의 manifest parser·MediaPlayer adapter·provider factory 주입 지점, 승인된 debug `RuntimeProbeActivity`와 debug assets다. 원문 검증과 단일 큐·포커스·차량 정책·TTL·중복·취소·자동 재생 금지 규칙을 공유한다.

## 새 검증 결과

| 검사 | 결과 | 증거 |
| --- | --- | --- |
| 기존 JVM 정책·큐·provider | 62 통과, 0 실패 | [tests.txt](tts-evidence-v2/tests.txt) |
| 로컬 음성 JVM | 26 통과 | [tests.txt](tts-evidence-v2/tests.txt) |
| 실제 SERVER/AVATAR fixture | 8 통과 | [integration.txt](tts-evidence-v2/integration.txt) |
| 실제 v2 WAV를 Kotlin loader로 검증 | 6 통과, F3/F4/F5·원문·파일 hash·PCM 포맷·길이 일치 | [local-voice-samples.txt](tts-evidence-v2/local-voice-samples.txt) |
| Android35/android.car/Pleos3.3.1 실제 바이너리 컴파일 | 통과 | [android-compile.txt](tts-evidence-v2/android-compile.txt) |
| Gradle verifySpeech·assembleDebug·lintDebug·assembleRelease | 종료 코드 0 | [gradle.log](tts-evidence-v2/gradle.log) |
| lint | Fatal 0 · Error 0 · Warning 7 | [lint XML](tts-evidence-v2/lint-results-debug.xml) |
| APK 자산 경계 | debug의 manifest·WAV6·license7·출처1이 원본 파일과 byte 단위 일치, release의 journey-voice 자산 0개 | [결과·해시](tts-evidence-v2/result.json) |
| 인수인계 원시 증거 보존 | 165 통과, 실패 0 | [handoff.json](tts-evidence-v2/handoff.json) |

새 JVM 검사는 세 화자 선택, profile·speaker·원문·파일 hash 불일치, 누락·손상·경로 탈출, 재시작 후 binding 유지, 같은 정체성의 새 문장 추가, 기존 문장의 음원 교체 거부, 차량 UNKNOWN/주행 전환, 포커스 거부·상실, background·suspend·TTL·중복·취소, 취소 뒤 늦은 콜백, 재생 중 파일 변경, pending 파일 삭제, legacy provider 경로와 cold 초기화 시한을 포함한다. 검증한 bytes를 MediaPlayer에 직접 전달하므로 해시 검사 뒤 경로를 다시 열지 않는다.

이 결과는 가청 출력·음질·음성 인식 정확도·인간이 느끼는 귀여움을 증명하지 않는다. 실제 가청 시작·취소 후 무음 지연은 SDK/MediaPlayer callback과 별도로 측정해야 한다.

## PM 런타임 검사 준비

최종 debug APK SHA-256: `695d70b56b80a8b1be3f14bc681ba3012b78d361ed4c50d846f9e86d50a07668`.

PM이 앞서 확인한 `74879b9b1488999172da0a387c3841b3fb6c56825634b6caaea503565e98b013`와 다른 빌드다. 최종 빌드에는 기존 문장별 음원 고정과 26번째 회귀 검사가 추가됐다. v2 manifest와 WAV는 동일하다. PM은 위 최종 SHA를 기존 시험 키로 재서명한 APK로 검증했다.

APK: `/Users/pig30nidae/NUNTI/.worktrees/tts/android/build/app/outputs/apk/debug/app-debug.apk`.
빌드 로그: [gradle.log](tts-evidence-v2/gradle.log). 독립 검증 로그: [verify.log](tts-evidence-v2/verify.log).

Debug assets는 `android/app/src/debug/assets/journey-voice/`에 manifest·WAV6개·Supertonic 코드/모델 및 DSP 의존성 license7개·source-references.json을 포함한다. unsigned release SHA-256은 `eb61897dc492edbc157ce5d9a45a7fe7f834fa58cbca43e1961d17fa08dae7c5`이며 이 debug 자산을 포함하지 않는다. 한국어 음질·귀여움·화자 구별은 인간 청취 전 후보 상태다.

최종 ledger는 `voice.<hash>`/`asset.<hash>` 형식이다. 앞선 실험 ledger는 `BINDING_STORE_CORRUPT`로 거부하며 자동 초기화하지 않는다. PM이 허용한 새 debug 시험 데이터에서 v2를 시작한다. 수집된 캐릭터의 기존 binding을 몰래 바꾸는 migration은 제공하지 않는다.

### Debug 서명 차이와 해결

제가 이번 Gradle 직접 실행에서 `ANDROID_USER_HOME`과 역할별 `JAVA_TOOL_OPTIONS`를 빠뜨렸다. 따라서 `/Users/pig30nidae/.android/debug.keystore`의 인증서 `9a4a176f8995adaed9cb9bf67ef1f6821ca0a8b8508f693dd14cecfcc7dfbd1d`로 서명됐다. 초기 복원 빌드는 worktree의 `.local/android-user/debug.keystore`, 인증서 `e38674e93ae953186a2b22f67e75022975ecbb41f39b36ee7caed483ef9ec993`를 사용했다. 두 키의 공개 인증서 SHA-256을 keytool로 대조했다.

이 차이로 PM 설치에서 `INSTALL_FAILED_UPDATE_INCOMPATIBLE`이 발생했다. PM은 앱을 삭제하지 않고 기존 시험 키로 `/Users/pig30nidae/NUNTI/.local/pm-tools/journey-voice-debug.apk`를 재서명해 user10에 `install -r`했다. 런타임 APK SHA-256은 `b25907f9c753d3cbf9cc4a3727032ffeb03bb1a7599ba4f737434551f9af30ca`다. TTS에서도 원본·재서명본의 SHA와 META-INF 밖 모든 ZIP 파일 내용이 같은지 재확인했다. 원본 APK·키·기존 앱 데이터는 보존했다. [PM 서명 기록](tts-evidence-v2/pm-runtime-review.json)에 근거를 함께 담았다.

아래 재현 명령은 원래의 `run_gradle.py`를 사용한다. 이 스크립트가 Android 설정·서명 home·Gradle cache·tmp를 역할별 디렉터리로 고정한다. 현재 PM 검증 산출물을 덮어쓰는 추가 빌드는 하지 않았다.

APK 설치 후 실제 P·속도0 및 오디오 시험 조건에서 아래 액션을 실행한다. `local_install`은 명시 요청에서만 app-private WAV를 복사하며 발화하지 않는다. 앱 재시작 시 파일을 자동 재설치하지 않아 missing-file 검사가 가능하다.

```sh
adb -s emulator-5554 shell am start --user 10 -W -f 0x14000000 -n ai.nunti.avatar.demo/ai.nunti.app.RuntimeProbeActivity --ez confirm_quiet_test true
adb -s emulator-5554 shell am start --user 10 -f 0x14000000 -n ai.nunti.avatar.demo/ai.nunti.app.RuntimeProbeActivity --es probe_action local_install
adb -s emulator-5554 shell am start --user 10 -f 0x14000000 -n ai.nunti.avatar.demo/ai.nunti.app.RuntimeProbeActivity --es probe_action local_speak --es character coast --ez confirm_quiet_test true
```

`character`는 coast·mountain·city다. `local_speak`는 세 캐릭터 동일 문장, `local_greeting`은 캐릭터별 승인 인사다. 같은 비교 문장을 60초 이내 다시 요청하면 캐릭터가 달라도 `REPEATED_TEXT`로 거부한다. 비교 사이 정상 대기 또는 별도 cold launch를 사용하고 정책을 끄지 않는다. 기존 `speak`·`stop` 액션과 route/emotion 동작은 유지한다.

`LOCAL_REQUEST` 로그에는 원래 manifest characterId·clipId·profileId·speakerId·textSha256·audioSha256가 기록된다. `SPEECH`에는 providerId=`supertonic3-local-catalog`, mode=`LOCAL_FILE`, 실제 profile/speaker를 기록한다. UI와 로그에 기존 Mock 시각과 새 캐릭터 음성이 별도 비교임을 표시했다.

router는 발화 대상 선택 뒤 SDK 초기화를 기존 5초 watchdog에서 처리하고, focus와 3초 시작 watchdog은 초기화 완료 뒤 시작한다. 요청별 초기화는 발화 전 준비 단계다. 이 debug mixed provider의 실제 cold/warm 지연은 PM 실행에서 별도 기록해야 한다.

## PM 실제 런타임 증거 대조

PM의 `docs/design/journey-characters/tts-evidence/runtime-v2/verification.json`과 raw 이벤트·PCM summary를 읽고, manifest의 character/profile/speaker/text/audio hash와 대조했다. [대조 결과](tts-evidence-v2/pm-runtime-review.json)에 원본 경로·해시·관찰 한계를 보존했다. 환경은 Pleos2.1.0/API34, emulator-5554, user10, 실제 P(gear4)·속도0·DO=false, 운영자가 오디오 경합을 통제한 debug 조건이다. route/emotion은 MOCK이다.

- 파도빛 F3, 이끼별 F4, 조각빛 F5 각각 `QUEUED → STARTED → COMPLETED`, provider=`supertonic3-local-catalog`, mode=`LOCAL_FILE`를 확인했다. 설치된 WAV hash도 manifest와 일치한다.
- 각 완료 뒤 재요청은 `REPEATED_TEXT`였다. 사용자 중지는 `USER_CANCELLED`, background는 `BACKGROUND`였고 복귀 뒤 재요청도 `REPEATED_TEXT`였다.
- 취소·복귀·최종 idle에서 기록된 각 1.25초 이상 관찰 구간 동안 자동 발화 이벤트가 없었다. 장시간 보장은 아니다.
- 공식 인증 speaker stream의 48000Hz·stereo·PCM16 파일 3개를 수집했다. TTS가 파일 SHA와 실제 PCM의 nonzero 수·peak를 재계산해 summary와 일치함을 확인했다. peak는 coast402·mountain437·city323이다. 출력 신호의 존재를 확인한 것이며 음성 귀속·발음·인간 청취 합격을 의미하지 않는다.

세 정상 요청의 STARTED callback은 47/40/49ms다. 이 값은 가청 지연이 아니다. PCM은 패킷 간 간격을 채우지 않은 연결 파일이며 다른 guest 오디오도 포함될 수 있어 실제 타이밍은 packet timestamp와 별도로 분석해야 한다. 이번 로컬 음성 런타임에는 D/주행 전환이 포함되지 않았다.

## 재현과 다음 작업

TTS worktree 루트에서 실행한다. importer는 PM이 제공한 음원 원본을 검증하고 debug 자산으로 복사한다. 기존 v2 자산만 재검증할 때 importer 재실행은 필요 없다.

```sh
python3 android/feature/tts/scripts/import_voice_samples.py --samples /Users/pig30nidae/NUNTI/prototypes/journey_voice/samples-v2
NUNTI_JAVA=/Users/pig30nidae/NUNTI/.local/tts-tools/jdk/jdk-21.0.8+9/Contents/Home/bin/java \
python3 android/feature/tts/scripts/verify.py --android --tools-dir /Users/pig30nidae/NUNTI/.local/tts-tools/artifacts
```

전체 Android 검증은 worktree 루트에서 기존 격리 helper로 실행한다. sandbox의 Gradle 로컬 소켓 제한 때문에 허용된 escalated 실행이 필요했다. 이번 직접 실행의 검증은 네트워크 없이 기존 도구 cache로 통과했으며, 아래 helper는 초기 복원 때 검증된 서명 환경을 유지한다.

```sh
python3 docs/handoff/restoration/2026-11-02/tts-evidence/run_gradle.py \
  :feature:tts:verifySpeech :app:assembleDebug :app:lintDebug :app:assembleRelease --offline
```

빌드·컴파일·시험 설치의 현재 차단사항은 없다. 다음은 인간 청취로 한국어 명료도·화자 구별·작고 귀여운 인상·첫 음절·DSP 잡음을 평가하고 제품 음성을 선정하는 일이다. 로컬 파일 재생 중 실제 D 전환, 취소→실제 무음 지연, production host 연결, 실차·통화/내비 경합·장시간 검증은 별도 미완료 항목이다.

