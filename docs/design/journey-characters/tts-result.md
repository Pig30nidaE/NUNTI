# 여정 캐릭터 TTS 구현과 시험

이 문서는 이전 v2 시험 기록이다. 현재 사용자 선호와 Sohee 생성 연동·새 Android Debug 검증은 [최신 연결 결과](tts-dynamic-generation.md)를 따른다. 아래 과거 APK·음원을 최신 결과로 사용하지 않는다.

2026-11-02 PM 취합. 사용자의 "TTS까지는 이어서 진행해주세요"와 "전체적으로 더 작고 귀여운 느낌"을 반영했다. 실제 합성 WAV와 Android Debug 재생까지 구현했다. 새 2.5D 외형은 기존 MOCK 화면과 분리된 시안이며 제품의 매 여행 자동 생성 화면은 아직 없다.

## 지금 시험하기

개발 도구 없이 [v2 청취 페이지](../../../prototypes/journey_voice/listen-v2.html)를 로컬 브라우저에서 연다. 세 캐릭터의 동일 문장과 개별 인사를 들을 수 있다. "높이를 올리기 전 목소리와 비교"를 열면 같은 원본 A안과 후처리 B안을 비교할 수 있다. 기본 후보는 B안이다. 이 페이지는 파일을 직접 읽으며 서버·계정·업로드가 필요 없다.

```sh
cd /Users/pig30nidae/NUNTI
open prototypes/journey_voice/listen-v2.html
```

| 캐릭터 | 방문 목적 | 실제 화자·profile | 공통 문장 / 인사 |
| --- | --- | --- | --- |
| 파도빛 | 바다에서 휴식 | F3 · `nunti-keepsake-calm-v2` | [4.029초](../../../prototypes/journey_voice/samples-v2/coast-common.wav) / [6.848초](../../../prototypes/journey_voice/samples-v2/coast-greeting.wav) |
| 이끼별 | 숲에서 캠핑 | F4 · `nunti-keepsake-curious-v2` | [3.269초](../../../prototypes/journey_voice/samples-v2/mountain-common.wav) / [5.485초](../../../prototypes/journey_voice/samples-v2/mountain-greeting.wav) |
| 조각빛 | 도시 전시 관람 | F5 · `nunti-keepsake-clear-v2` | [3.702초](../../../prototypes/journey_voice/samples-v2/city-common.wav) / [6.422초](../../../prototypes/journey_voice/samples-v2/city-greeting.wav) |

공통 문장은 "안녕하세요. 오늘의 여행도 함께할게요."다. v1의 F1/M3/F2는 보존하고 별도 v2에서 F3/F4/F5를 선택했다. 합성 speed는 1.04/1.08/1.06이며, 같은 파형의 길이를 유지하면서 +3반음 후처리했다. 이는 작고 귀여운 인상을 위한 청취 후보다. 새 음성의 한국어 명료도·귀여움·DSP 잡음은 아직 사람 평가를 통과하지 않았다.

에이전트의 내장 브라우저에서는 로컬 `file://` 미리보기가 제한되어 실제 청취 페이지 UI 조작을 검증하지 않았다. HTML·참조 파일을 검사했고 Android는 아래 별도 절차로 실제 실행했다. 페이지를 HTTP로 우회 제공하거나 음원을 외부에 올리지 않았다.

## 실제 구현

여정 레시피의 `voiceIntent`를 고정 카탈로그의 화자·속도·단계·후처리에 매핑한다. 새 여정은 새 캐릭터를 만들고, 같은 캐릭터의 reroute·재시도·프로세스 재시작에는 저장 binding을 사용한다. voice binding과 원문 UTF-8 hash를 함께 써서 합성한 WAV를 캐시한다. 원문과 실제 모델 내부 정규화 문자열은 별도로 기록한다.

PC의 실제 Supertonic3 ONNX 추론으로 파일을 만든다. [v2 실행 가이드](../../../prototypes/journey_voice/README-v2.md)에 모델·dependency lock, 별도 환경, 캐시, 원본과 후처리, 라이선스가 있다. 지원이 종료된 공개 아카이브 모델을 사용한 로컬 시제품이며 운영 공급자를 선정한 결과가 아니다. 모델이나 음성 복제 기능을 Android에 넣지 않았다.

Android에는 `LocalVoiceCatalog`, `LocalFileTtsProvider`, `AndroidLocalAudioPlayer`, manifest parser를 추가했다. 기존 `SpeechQueueManager` 한 개가 정책·큐·포커스·TTL·중복·취소를 계속 소유한다. 파일은 character/profile/speaker/locale/정확한 원문과 SHA·실제 PCM 형식까지 맞아야 재생한다. 화자 변경·변조·없는 자산·미등록 profile은 명시적으로 거부한다. 같은 binding에 새 문장은 추가할 수 있지만 이미 등록한 문장의 WAV는 바꿀 수 없다.

재생기는 검증한 바이트를 직접 `MediaPlayer`에 전달한다. 취소·종료 뒤 늦은 콜백은 세대 번호로 무효화한다. 앱 시작·설치·복원·동기화·주행 후 P 복귀는 발화 트리거가 아니다. `TripReport.finalText`를 캐릭터 말투로 재작성하거나 점수·최종 코멘트를 생성하지 않는다.

기존 TTS 채팅이 독립 worktree에서 구현한 41개 파일을 PM이 검토해 루트로 바이트 동일하게 복사했다. [복사 파일·SHA](tts-evidence/imported-files.json)와 [담당 구현 보고](tts-implementation.md)를 보존했다. backend·wire v1·공통 Gradle·production host·AVATAR 엔진은 이번에 변경하지 않았다. 새 catalog 음원과 진단 화면은 Debug 전용이다.

## 검증한 결과

| 층 | 실제 결과 | 증거 |
| --- | --- | --- |
| 로컬 합성 | 기존 19개 + v2 7개 검사, v2 실제 WAV12개 검사. B안6개와 원본의 프레임 길이 일치·full-scale clipping0. 재실행6개 캐시 적중·동일 hash | [v2 가이드](../../../prototypes/journey_voice/README-v2.md), [실측 JSON](../../../prototypes/journey_voice/sample-verification-v2.json) |
| 새 문장 | 샘플에 없던 줄바꿈·연속 공백 포함 원문을 실제 v1/v2로 합성. v2 4518ms, UTF-8 digest 보존 | [원문](tts-evidence/pm-new-text.txt), [v2 WAV](tts-evidence/pm-new-text-v2.wav), [metadata](tts-evidence/pm-new-text-v2.json) |
| 루트 취합 코드 | 기존 JVM62 + 새 로컬26 + SERVER/AVATAR fixture8 + 실제 WAV6 + Android35/android.car/Pleos3.3.1 컴파일 재실행 통과 | [루트 실행 로그](tts-evidence/root-verify.log) |
| APK | TTS worktree의 verifySpeech·assembleDebug·lintDebug·assembleRelease 통과. lint Fatal0/Error0/Warning7. Debug 음원·manifest·license는 원본과 동일, release의 journey-voice 자산0 | [빌드 결과·해시](tts-evidence-v2/result.json), [Gradle 로그](tts-evidence-v2/gradle.log) |
| 실제 Pleos 앱 | 공식 Pleos2.1.0 ARM/API34·user10에서 세 캐릭터 QUEUED→STARTED→COMPLETED. 설치한 WAV6개 hash 동일. 각 중복 REPEATED_TEXT, 중지 USER_CANCELLED, background BACKGROUND. 복귀·idle의 각 1.25초 이상 구간에 자동 발화 없음 | [8개 case 결과](tts-evidence/runtime-v2/verification.json), [원시 이벤트](tts-evidence/runtime-v2/runtime-events.jsonl) |
| 실제 D 전환 | Console 조작으로 gear8/D·UX차단·화면숨김. 재생 중 CANCELLED/SPEECH_NOT_ALLOWED, D에서 새 요청 REJECTED/SPEECH_NOT_ALLOWED. gear4/P 복귀 뒤 2초간 자동 발화 없음 | [후속 D 시험](tts-evidence/runtime-drive-v2/verification.json), [원시 이벤트](tts-evidence/runtime-drive-v2/runtime-events.jsonl), [최종 Console](tts-evidence/console-final-parked.png) |
| 실제 guest 출력 | 기존 인증을 사용한 emulator speaker stream에서 세 PCM 수집. 실제 source와 다른 source까지 9쌍 대조. 신호·요청·자산 대응을 보존 | [음원 대조와 한계](tts-evidence/runtime-v2/audio-comparison-analysis.md), [9쌍 실측](tts-evidence/runtime-v2/source-cross-comparison-v2.json) |
| 취합 무결성 | 파일·binding·원시 이벤트·PCM 재검증90/90, 기존 인수인계275/275 통과 | [TTS 취합 검증](tts-verification.json), [과거 증거 보존 검사](tts-evidence/handoff-final.json) |

정상 발화 세 건의 STARTED callback은 47/40/49ms였다. 가청 지연이 아니다. PCM의 단일 파형 NCC는 .271/.226/.288로 낮고, 고정 RMS envelope NCC는 .965/.975/.980이었다. 각 capture에서 자신의 source가 다른 두 source보다 높았다. 국소 정렬 위치가 달라지는 관측이 있으나 발생 계층은 미확정이다. 파형이 완전히 동일하거나 음질이 합격했다고 판단하지 않는다.

D 취소 이벤트 후에도 PCM에 큰 신호가 다시 관찰됐다. 남은 TTS인지 차량·시스템음인지, guest/host clock 차이인지 확인하지 못했다. 따라서 **취소 후 완전 무음이나 정확한 mute 지연은 미검증**이다. 앱 이벤트 취소와 실제 출력의 무음은 별개다. [D 출력 분석](tts-evidence/runtime-drive-v2/cancel-pcm-observations.md)과 raw packet·WAV는 [D 시험 폴더](tts-evidence/runtime-drive-v2)에 보존한다.

실행한 원본 APK SHA는 `695d70b56b80a8b1be3f14bc681ba3012b78d361ed4c50d846f9e86d50a07668`, 기존 시험 키로 재서명해 설치한 APK는 `b25907f9c753d3cbf9cc4a3727032ffeb03bb1a7599ba4f737434551f9af30ca`다. META-INF 밖 ZIP 내용은 같다. 서명 차이에 따른 업데이트 실패를 앱 삭제 없이 해결했다. 재현 시 격리된 기존 Gradle helper를 사용한다. [서명 기록](tts-evidence/apk-signing.json)에 원인과 비교 결과가 있다. 커밋·푸시는 하지 않았다.

## 개발자가 재현하기

이 로컬에 준비한 환경으로 새 원문을 합성한다. 기존 파일을 덮지 않는 출력 이름을 사용한다.

```sh
cd /Users/pig30nidae/NUNTI
.local/journey-voice/venv-v2/bin/python prototypes/journey_voice/voice_v2.py \
  --recipe prototypes/journey_characters/sample-output.json \
  --text '오늘의 작은 여행도 함께할게.' \
  --output .local/journey-voice/my-next-voice.wav
```

현재 CLI는 짧은 한국어 원문 최대100 codepoint·음원30초 제한의 실험이다. 임의 길이의 모든 finalText 처리나 앱의 자동 합성을 구현한 것은 아니다. 다른 새 여정의 레시피를 만들면 그 레시피로 다시 호출한다. 외형·음성 생성과 제품의 journey 시작 연결은 다음 작업이다.

코드·파일·보존된 실행 증거는 아래로 재검사한다. 마지막 명령은 기기 실행 없이 보존 증거의 정합성을 검사한다.

```sh
NUNTI_JAVA=/Users/pig30nidae/NUNTI/.local/tts-tools/jdk/jdk-21.0.8+9/Contents/Home/bin/java \
python3 android/feature/tts/scripts/verify.py --android \
  --tools-dir /Users/pig30nidae/NUNTI/.local/tts-tools/artifacts
python3 scripts/verify_journey_tts_delivery.py \
  --output /tmp/nunti-tts-delivery.json
```

Android 직접 재생은 [담당 보고의 Debug 액션](tts-implementation.md)과 [인증 PCM·앱 검사 절차](tts-runtime-notes.md)를 따른다. 이번 시험 뒤 임시 에뮬레이터·ADB·Console은 종료한다. 다시 시험할 때 [복원 보고](../../handoff/restoration/2026-11-02/PM.md)의 공식 SDK/AVD·Console 절차로 시작하고 오디오를 켠다. Console 브라우저가 연결을 유지해야 한다. 실제 P·속도0·알려진 UX와 통제한 오디오 조건을 확인한다. 보호·중복 제한을 끄지 않는다.

최신 시험 APK는 `.local/pm-tools/journey-voice-debug.apk`다. user10에 `adb install -r --user 10`으로 설치하며 앱 삭제나 저장 데이터 초기화는 하지 않는다. `local_install`은 음원을 명시적으로 복사할 뿐 자동 발화하지 않는다. `local_speak`는 coast/mountain/city의 동일 문장, `local_greeting`은 각 인사, `stop`은 중지다. 동일 문장60초 제한을 유지하므로 연속 비교는 정상 대기 또는 별도 cold session을 사용한다.

## 완료·미구현·미검증과 다음 순서

| 구분 | 상태 |
| --- | --- |
| 완료 | 여정 레시피→실제 voice binding→새 원문 합성→WAV·metadata·캐시, 더 작은 음성 v2와 A/B 청취, Android Debug catalog/player·단일 정책 경로, 빌드·실제 emulator 이벤트·인증 PCM 증거 |
| 미구현 | 매 여행 앱에서 자동 모델 호출·선택·원자적 확정, C의 레이어/rig/새 renderer, 제품 host·서버 생성 job·컬렉션·동의/삭제 연결, Android 내 모델 runtime |
| 미검증 | v2의 사람 청취·한국어 명료도·첫 음절·귀여움·장시간 피로, 가청 시작·취소 후 무음 지연과 D 취소 후 신호 출처, 실차·통화/내비/안전음 경합, 사용자 소장 의향·운전습관 개선 |

다음은 음성 후보의 사람 청취와 D 취소 후 출력 분석을 먼저 수행한다. 제품 통합 전에 정확한 무음 동작을 확정한다. AVATAR는 C 체형·표정·레이어를, SERVER는 durable 생성·선택·컬렉션 초안의 구현을 이어갈 수 있으나 이번에는 새 구현을 지시하지 않았다. 외부 payload·담당 조율은 계속 보류한다.
