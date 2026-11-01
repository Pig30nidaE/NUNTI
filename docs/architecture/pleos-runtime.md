# Pleos 에뮬레이터 런타임 검증

2026-11-01, SERVER 통합 브랜치에서 직접 실행했다. **공식 Pleos Connect 2.1.0 ARM 이미지에서 아바타 렌더링과 실제 ON_DEVICE TTS 발화·오디오 출력을 확인했다.** 차량 주행 전환은 이미지의 Virtual Console 연결 문제로 미검증이다.

## 실행 환경과 범위

- macOS ARM, Android Emulator 37.2.13 / Hypervisor.Framework, API 34, RAM 4GB, cold boot.
- 장치: `emulator-5554`, Android 사용자 10. Fingerprint: `Pleos/crp_avd_arm64/crp_avd_arm64:14/RELEASE.release_connect_v2.1.0/release_connect_v2.1.0:user/test-keys`.
- 통합 앱: `ai.nunti.avatar.demo`, 실제 Pleos TextToSpeech SDK 3.3.1.
- `RuntimeProbeActivity`는 `src/debug`에만 포함하며 ranchu/goldfish 이외 장치를 거부한다. release 및 기존 Automotive 기본 화면의 fail-closed 처리는 유지한다. 진단 화면은 기본 launcher가 아니므로 아래 명시적 실행 명령을 사용한다.
- 경로·감정·발화 텍스트는 **MOCK**이다. 기존 AvatarEngine/renderer, 공용 AvatarVoiceBridge, AndroidVoiceSession과 실제 Pleos 서비스가 연결된다. 서버 HTTP/실시간 내비게이션 경로는 이번 검증 경로에 포함되지 않는다.
- Car UX listener 한 개를 공유하며 실제 CarPropertyManager의 기어·속도를 읽는다. 주차/UX를 합성 값으로 허용하지 않는다. TTS_SERVICE, CAR_POWERTRAIN, CAR_SPEED 권한 부여를 장치에서 확인했다.
- 경쟁 오디오가 없다는 조건은 초기 `dumpsys audio`의 focus owner 없음/in-call=false, AudioManager 상태 및 명시적 `confirm_quiet_test` 입력으로 설정한 **통제된 에뮬레이터 테스트 조건**이다. 실제 차량의 모든 오디오 신호를 검증한 것으로 취급하지 않는다. 호스트 마이크 입력은 비활성화했다.

## 확인 결과

| 항목 | 실제 관찰 |
| --- | --- |
| 설치·실행 | APK 설치 성공, 진단 Activity cold launch 성공 |
| 주차 상태 | gear=4(P), speed=0, UX=0, requiresDO=false, avatarVisible=true |
| 경로 아바타 | 도심 티켓/조끼, 장거리 가방, 해안 스카프/물결, 산악 물병/능선이 구분됨 |
| 감정 표정 | NEUTRAL, STARTLED, JOYFUL 눈·입 변화 확인. 합성 감정 입력 |
| 넓은 화면 | 기존 `heightIn + aspectRatio` 조합이 Canvas를 넘치게 하는 버그 발견·수정. 1682×1210 앱 창에서 겹침 해소 |
| 좁은 화면 | 실제 task bounds를 847×910으로 변경해 겹침 없음 확인. 원래 bounds로 복원 |
| SDK 연결 | 앱 로그의 ON_DEVICE initialize → audio attributes(NOTIFICATION) → listener 등록 → ko_KR 확인 |
| 최초 발화 | 요청 `probe-c062f918-29b2-455f-93b2-f4fac6e3850e`: QUEUED → STARTED(73ms) → COMPLETED |
| 최종 APK 발화 | 요청 `probe-490bbbf0-93c5-40bd-b3bc-3fd3655ee1ad`: 13:08:08.185Z QUEUED → 08.226Z STARTED(41ms) → 11.958Z COMPLETED |
| 출력 오디오 | 인증된 localhost gRPC speaker stream을 WAV로 저장. 최종 48kHz/16bit/stereo, 7.166875초, nonzero samples 293,067, peak 1,409, RMS 225.58 |
| 사용자 중지 | STARTED → CANCELLED / USER_CANCELLED |
| 진단 Activity 비표시 | 다른 Activity 진입 시 STARTED → CANCELLED / BACKGROUND, avatarVisible=false |
| 복귀 후 반복 발화 | 같은 세션의 60초 이내 동일 문장 재요청은 REJECTED / REPEATED_TEXT. 자동 재생 없음 |
| 빌드 | debug assemble/lint 통과(0 errors, 기존 warnings 3개). release 빌드 및 진단 Activity 제외 검사 통과 |

발화 문장: “안녕하세요. 눈티예요. 오늘의 여행도 함께할게요.”

73ms/41ms는 개별 요청의 submit→SDK onStart 지연이다. 최초 가청 샘플 지연이나 성능 benchmark가 아니다. WAV는 emulator가 전송한 PCM 패킷을 연결한 파일이며 wall-clock 녹음 시간과 다를 수 있다. 음성이 포함된 출력 신호와 콜백을 확인했지만 **인간 청취에 의한 발음·첫 음절·선행 묵음·음질 평가는 수행하지 않았다.** 감정별 실제 음색/속도/피치 제어도 확인한 범위가 아니다.

## 남은 플랫폼 제한

공식 Virtual Console `GET /vehicle/state`는 `emulator_active=false`, `bridge_ready=false`, `dds_ready.all=false`를 반환했다. `PUT /vehicle/gear?gear=Drive`는 HTTP 503 `{"error":"emulator_inactive"}`였다. 따라서 시도 당시 기어는 P, UX는 0으로 그대로였으며 **D/30km/h 전환·실제 주행 UX 제한·재주차 복귀를 통과로 기록하지 않는다.**

공식 문서의 `cmd hmg_car_service ... driving_regulation on/off`도 이 이미지에는 서비스가 없어 실패했다. 일반 `cmd car_service help`는 user build 제한으로 거부됐다. 시스템 이미지/권한을 바꾸거나 보호를 우회하지 않았다. 앞으로 활성화된 차량 시뮬레이터 또는 검증 장치에서 이 경로를 다시 실행해야 한다.

`wm size` 변경은 Pleos 고정 패널을 재배치하지 않아 작은 창 검증에 부적합했다. 대신 `am task resize`와 실제 bounds를 사용했다. 모든 화면 크기 변경은 복원했다.

## 재실행

현재 세션의 임시 SDK는 `/private/tmp/nunti-pleos-runtime/sdk`, AVD는 `/private/tmp/nunti-pleos-runtime/avd`에 있다. SDK/시스템 이미지는 저장소에 포함하지 않았다. 설치 다운로드의 SHA-1은 공식 feed와 비교했고 ZIP CRC 검증을 거쳐 해제했다. 디스크 하한에 도달한 첫 해제는 중단·정리했고, 성공 후 다운로드 ZIP만 삭제했다.

```sh
export ANDROID_HOME=/private/tmp/nunti-pleos-runtime/sdk
export ANDROID_USER_HOME=/private/tmp/nunti-pleos-runtime/user
export ANDROID_AVD_HOME=/private/tmp/nunti-pleos-runtime/avd
"$ANDROID_HOME/emulator/emulator" -avd Nunti_Pleos_2_1 -no-snapshot -memory 4096 -gpu host

"$ANDROID_HOME/platform-tools/adb" -s emulator-5554 install -g -r android/build/app/outputs/apk/debug/app-debug.apk
"$ANDROID_HOME/platform-tools/adb" -s emulator-5554 shell am start -W -f 0x14000000 \
  -n ai.nunti.avatar.demo/ai.nunti.app.RuntimeProbeActivity --ez confirm_quiet_test true
"$ANDROID_HOME/platform-tools/adb" -s emulator-5554 shell am start -f 0x14000000 \
  -n ai.nunti.avatar.demo/ai.nunti.app.RuntimeProbeActivity --es probe_action speak --ez confirm_quiet_test true

python3 android/scripts/verify_runtime_probe.py \
  --adb "$ANDROID_HOME/platform-tools/adb" --serial emulator-5554 \
  --output /private/tmp/nunti-runtime-lifecycle.json
```

실행 중인 AVD가 있으면 emulator 명령을 다시 실행하지 않는다. `0x14000000`의 CLEAR_TOP은 같은 task에 남은 기본 MainActivity 위로 진단 화면을 복귀시킨다. 재현 스크립트는 진단 앱을 재시작하고 중지/백그라운드/중복 발화 이벤트를 검사한다.

## 증거

[최종 화면](validation-evidence/pleos-runtime/final-parked.png), [좁은 task](validation-evidence/pleos-runtime/narrow-task.png), [수정 전 화면](validation-evidence/pleos-runtime/initial.png), [최종 출력 음성](validation-evidence/pleos-runtime/tts-final.wav).

[구조화 이벤트](validation-evidence/pleos-runtime/events.jsonl), [초기 SDK 원시 로그](validation-evidence/pleos-runtime/tts-initial-app-log.txt), [lifecycle 결과](validation-evidence/pleos-runtime/lifecycle-results.json), [권한](validation-evidence/pleos-runtime/package-permissions.txt), [실제 UX](validation-evidence/pleos-runtime/ux-state.txt), [Virtual Console 상태](validation-evidence/pleos-runtime/vehicle-state-inactive.json), [APK SHA-256](validation-evidence/pleos-runtime/apk-provenance.json).

초기 전체 crash buffer의 `ai.umos.inputmethod` 예외는 에뮬레이터 내장 IME의 부팅 오류다. 수집한 로그에서 Nunti 프로세스의 치명적 예외는 확인되지 않았다.

공식 자료: [설치·cold boot/4GB 안내](https://document.pleos.ai/en/docs/connect/guide/getting-started/application-development/setup-connect-sdk-emulator), [Virtual Console](https://document.pleos.ai/en/docs/connect/guide/getting-started/application-development/use-vehicle-emulator), [Pleos ADB 테스트 명령](https://document.pleos.ai/en/docs/pleos-only/vehicle-app-developer-guide/adb-command-reference-guide), [Android emulator speaker stream](https://developer.android.com/studio/run/emulator-console).
