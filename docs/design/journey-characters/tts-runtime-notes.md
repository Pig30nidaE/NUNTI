# 새 캐릭터 TTS의 Android 출력 검증

2026-11-02, Asia/Seoul. 이 문서는 생성 WAV와 Android 재생을 구분해 검증하는 절차다. 기존 복원 기록과 WAV는 보존한다. [과거 복원 보고](../../handoff/restoration/2026-11-02/PM.md)는 `-no-audio` 실행의 SDK 콜백을 실제 PCM 검증으로 취급하지 않았다.

## 사용할 도구

[record_emulator_audio.py](../../../scripts/record_emulator_audio.py)는 실행 중인 에뮬레이터의 speaker `streamAudio`를 WAV로 저장한다. 호스트 마이크나 macOS 출력 장치를 녹음하지 않는다. 설치된 SDK의 실제 `emulator_controller.proto`를 매 실행 컴파일하므로 프로토콜 사본을 임의로 재구성하지 않는다.

기본 localhost 서비스의 기존 `grpc.token`을 discovery INI에서 읽어 인증한다. 토큰을 명령 인자·로그·증거 파일에 출력하지 않으며 emulator flags·allowlist·인증 설정을 수정하지 않는다. JWT만 있는 구성이나 별도 TLS 구성은 지원 대상으로 확대하지 않는다. 토큰이 없으면 실패한다.

공식 [gRPC 보안 문서](https://android.googlesource.com/platform/external/qemu/+/0ad64c577d2304561b8dab72ab38d535a4c061a9/android/android-grpc/docs/)는 loopback transport와 bearer/JWT 인증을 구분한다. [emulator 설정 소스](https://android.googlesource.com/platform/external/qemu/+/emu-master-dev/android-qemu2-glue/qemu-setup.cpp)와 로컬 37.2.13의 실제 discovery를 확인했다. 인증 없는 서비스로 바꾸는 `-grpc` 실행이나 인증 파일 비우기는 이 절차에 포함하지 않는다.

## 준비와 실행

전용 venv는 `/Users/pig30nidae/NUNTI/.local/voice-runtime/venv`에 설치했다. 전역 Python을 수정하지 않았다. 설치한 버전은 `grpcio==1.85.1`, `grpcio-tools==1.85.1`, `protobuf==7.36.2`, `setuptools==84.2.1`, `typing_extensions==4.16.0`이다. 환경을 다시 구성할 때는 다음 명령을 실행한다.

```sh
cd /Users/pig30nidae/NUNTI
/opt/homebrew/bin/python3.12 -m venv .local/voice-runtime/venv
.local/voice-runtime/venv/bin/python -m pip install --no-cache-dir grpcio==1.85.1 grpcio-tools==1.85.1 protobuf==7.36.2 setuptools==84.2.1 typing_extensions==4.16.0
.local/voice-runtime/venv/bin/python scripts/record_emulator_audio.py --inspect
```

에뮬레이터 시작·차량 Console·APK 설치는 PM 런타임 절차를 따른다. 이미 실행 중이면 중복 실행하지 않는다. 오디오를 켜고 호스트 마이크 입력은 별도로 끈다. 새 캐릭터의 발화는 실제 P·속도0과 허용된 UX 상태에서 실행한다. 녹음을 먼저 시작하고 `CAPTURING` 메시지가 나온 다음 발화를 요청한다. 진단 Activity·기존 RuntimeProbe 조작은 해당 APK의 실제 기능 범위에 맞춘다.

```sh
cd /Users/pig30nidae/NUNTI
.local/voice-runtime/venv/bin/python scripts/record_emulator_audio.py \
  --serial emulator-5554 --seconds 20 \
  --output .local/voice-runtime/captures/character-01.wav
```

같은 경로의 덮어쓰기는 거부한다. 재검사할 때 새 파일 이름을 사용한다. 필요하면 `--discovery /실제/pid_숫자.ini`로 특정 discovery를 지정할 수 있다. INI 내용을 화면에 출력하거나 증거 폴더에 복사하지 않는다.

| 산출물 | 확인하는 것 |
| --- | --- |
| `character-01.wav` | guest speaker가 전달한 48kHz·16bit·stereo PCM. 기본 포맷이며 `--rate`로 제한된 대체 sampling rate 지정 가능 |
| `character-01.packets.jsonl` | packet별 emulator epoch timestamp, 수신 monotonic/epoch timestamp, WAV frame 위치, peak·nonzero 개수 |
| `character-01.summary.json` | WAV 해시·포맷·길이·신호 수·peak·RMS, stream 결과, SDK proto 해시. 인증 토큰은 없음 |

정상 종료 deadline은 `DEADLINE_EXCEEDED`로 기록한다. nonzero PCM이 있으면 exit0, 무신호는 exit2, 연결·인증·포맷 오류는 exit1이다. 오류나 중단 때 남은 WAV를 성공으로 간주하지 않는다. 성공한 summary의 source·packet 수·신호 통계와 실제 파일을 함께 확인한다.

여기서 exit0는 raw PCM 수신 판정이다. 조용한 baseline에도 아주 작은 nonzero 신호가 관찰되므로 이를 TTS 발화 성공 판정으로 사용하지 않는다. sandbox에서 localhost 연결이 막히면 장치나 인증을 바꾸지 말고 동일 읽기 명령의 loopback 접근 권한으로 재실행한다.

## 증거의 단계

1. 생성 WAV의 정상 포맷·nonzero 신호는 합성 파일이 있다는 증거다. Android에서 재생했다는 증거가 아니다.
2. Android 큐·provider의 STARTED/COMPLETED는 호출 경로와 생명주기 증거다. 실제 소리가 출력됐다는 증거는 아니다.
3. 인증된 emulator speaker PCM과 앱 요청·실제 audio asset hash의 대응은 guest 출력 경로의 증거다. 다른 앱·시스템의 소리도 포함되므로 조용한 조건에서 하나씩 재생하고 요청 시각·텍스트·voice binding·asset hash를 함께 보존한다.
4. 한국어 발음·첫 음절·소장하고 싶은 캐릭터와의 어울림은 사람이 직접 들어서 판정한다. 자동 PCM 통계로 청취를 대체하지 않는다.

WAV는 받은 packet을 순서대로 연결한다. packet이 오지 않은 시간을 silence로 채우지 않으므로 WAV 위치나 전체 길이를 wall-clock 지연으로 사용하지 않는다. 재생 요청부터 첫 음성, 취소부터 실제 무음까지의 시간은 packet timestamp와 별도로 기록한 요청·취소 시각을 같은 시계 기준에 맞춰 분석한다. `nonzero != audible speech`이므로 노이즈를 제외할 임계값과 연속 무음 구간을 정의해야 한다. 이 도구의 통계에는 청취 임계값 판정이 없다.

## 이 도구에서 직접 확인한 범위

- Python3.9 stdlib로 `--help`와 `--analyze` 실행을 확인했다.
- 전용 Python3.12 venv에서 실제 SDK 37.2.13 proto 컴파일과 `streamAudio` server-streaming 계약을 확인했다. proto SHA-256은 `564e00a929e7e4a7af78269a738ea715f32d88c0fc9f92659bb8a1251c9d558f`다.
- PM이 시작한 emulator-5554의 discovery에서 localhost8554와 기존 토큰의 존재를 확인했다. `--inspect`는 실제 연결·녹음을 하지 않는다.
- 보존된 `tts-final.wav`를 새 분석기로 읽어 기존 기록과 동일한 344,010frames·7.166875초·nonzero293,067·peak1,409·RMS225.578936을 확인했다. 이는 과거 파일 분석이며 새 TTS 청취가 아니다.
- fixture INI에서 토큰이 inspect 출력에 노출되지 않고 토큰 없는 설정을 거부하는 것을 검사했다.
- PM이 실행한 audio ON 에뮬레이터에 2초 기준 stream을 연결해 실제 기존 token 인증과 183packet 수신을 확인했다. sandbox loopback 제한 뒤 동일 명령의 허용 재실행에서 성공했다. 장치 제어·발화 trigger는 하지 않았다. `baseline-20261102-01.wav`는 8,235frames·0.1715625초·nonzero12,078·peak2·RMS1.449326이다. 이는 극미량 배경 신호이며 새 TTS 발화 증거가 아니다. 2초 stream과 0.1715625초 WAV의 차이도 실제로 관찰했다. 파일은 `.local/voice-runtime/captures/`에 있다.

새 캐릭터 APK의 PCM 녹음 결과는 별도 실행 증거에 기록한다. 이 문서의 도구 준비 완료를 새 APK의 오디오 검증 완료로 확대하지 않는다.

## 생성 WAV와 guest 출력 비교

[verify_catalog_pcm.py](../../../scripts/verify_catalog_pcm.py)는 전체 source WAV가 capture 안에서 가장 비슷한 위치를 측정한다. 기존 `.local/journey-voice/venv`의 NumPy2.3.5를 사용한다. 두 입력은 PCM16으로 읽고 채널을 평균해 mono로 만든다. source만 capture sample rate에 선형 resample한 뒤 FFT cross-correlation을 각 capture window의 분산으로 정규화한다. 이 NCC는 gain 차이를 허용하는 파형 비교다.

```sh
cd /Users/pig30nidae/NUNTI
.local/journey-voice/venv/bin/python scripts/verify_catalog_pcm.py \
  --source prototypes/journey_voice/samples/coast-common.wav \
  --capture .local/voice-runtime/captures/character-01.wav \
  --output .local/voice-runtime/captures/character-01-correlation.json
```

결과에는 실제 두 파일의 SHA-256, 원래 포맷·peak·RMS, resample 후 frame 수, 최적 window의 frame·PCM초 위치, NCC·fitted gain·잔차 RMS를 기록한다. 통과 임계값이나 음성 품질 판정은 두지 않는다. exit0는 계산을 마쳤다는 뜻이다. capture가 resample한 source 전체보다 짧거나 비교할 신호 변화가 없으면 계산할 수 없음을 반환한다. 부분 source를 임의로 골라 수치를 높이지 않는다.

같은 capture에 올바른 source와 다른 source를 각각 비교하면 구별 근거를 보탤 수 있다. 최고 NCC 하나만으로 유일한 출처·통계적 유의성을 입증하지 않는다. Android resampler·필터·clock drift·packet 손실은 NCC를 낮출 수 있다. PCM 위치를 가청 시작·취소 지연으로 해석하지 않는다.

`--phase-robust` 옵션은 기존 raw NCC를 유지하면서 고정32ms창·10ms hop의 RMS envelope와5-band STFT amplitude의 temporal NCC를 함께 출력한다. [새 v2 실제 출력9쌍 비교](tts-evidence/runtime-v2/audio-comparison-analysis.md)는 낮은 raw NCC·다른 source 대조·연결 PCM의 국소 offset 변화를 함께 기록했다. phase에 덜 민감한 지표가 높다는 이유로 원래 raw 수치를 숨기거나 청취 합격을 판정하지 않는다.

도구 검사는 실제 `coast-common.wav`를 선형 resample하고 gain0.25·앞쪽4,800frames·stereo48000을 적용한 합성 fixture로 수행했다. 정확한4,800frame 위치·gain0.25·NCC0.9999998을 복원했다. 이는 계산식 검사이며 실제 Android 녹음 증거와 구분한다.

## 앱의 세 캐릭터와 생명주기 자동 검사

[verify_character_voice_runtime.py](../../../scripts/verify_character_voice_runtime.py)는 설치된 debug `RuntimeProbeActivity`의 실제 intent와 app-private JSONL을 사용한다. 새 APK 설치·실제 P 상태·활성 Console 준비 후 실행한다. 기존 output directory는 거부한다.

```sh
cd /Users/pig30nidae/NUNTI
python3 scripts/verify_character_voice_runtime.py \
  --adb .local/pm-tools/sdk/platform-tools/adb --serial emulator-5554 \
  --manifest .worktrees/tts/android/app/src/debug/assets/journey-voice/manifest.json \
  --output-dir .local/voice-runtime/character-runtime-01 \
  --record-python .local/voice-runtime/venv/bin/python
```

`--record-python`을 생략하면 앱 이벤트·파일 검사는 수행하고 PCM 녹음은 하지 않는다. 옵션을 넣으면 각 common clip을 별도10초 stream으로 녹음하고 `CAPTURING` 이후 발화를 요청한다. 대화형 도구로 시작할 때는 `yield_time_ms:1000`으로 받고 진행 결과를 polling한다.

이 도구는 hardware/fingerprint와 현재 user10을 확인한다. 매 case는 app force-stop으로 세션을 새로 만들고 실제 Car 연결·P·속도0·UX known/제한 없음·명시한 quiet test 조건을 기다린다. `local_install` 후 private 파일6개의 실제 bytes를 읽어 manifest 해시와 비교한다. 세 캐릭터의 `LOCAL_REQUEST`와 QUEUED voice metadata·LOCAL_FILE provider·STARTED→COMPLETED를 검사한다. 같은 세션의 두 번째 동일 문장은 REPEATED_TEXT여야 한다. 별도 두 세션에서는 USER_CANCELLED와 BACKGROUND, 복귀 후 자동 재발화 없음과 반복 억제를 검사한다. 자동 재생 관찰 시간은 각 case에 기록하며 무한한 안정성 검증으로 부르지 않는다.

프로필·화자·해시는 전달한 manifest에서 읽는다. v1 값을 코드에 고정하지 않는다. app-private 불변 voice binding은 지우지 않으므로 기존 캐릭터 ID에 새로운 캐스팅을 덮으면 정상적으로 변경을 거부할 수 있다. debug 저장소 초기화나 새 캐릭터 결정은 PM이 별도로 한다. 장치 상태·권한·P 입력이 없을 때 mock으로 통과시키지 않는다.

`verification.json`과 `runtime-events.jsonl`에 실제 기록을 보존한다. 실패도 JSON으로 남긴다. PCM은 source clip과 매핑하지만 NCC 판정은 위 별도 도구로 수행한다. helper의 성공은 app event·설치 파일 identity 검증이며 실제 음성의 귀여움·품질·주행 기능의 출시 판정은 아니다.

작성 시에는 `--help`, 문법, 현재 manifest의6개 WAV·text digest, 실제 Kotlin probe의 action/event 필드 대조까지만 실행했다. 이 절차를 작성하면서 장치 제어나 추가 발화를 수행하지 않았다. 실제 앱 실행 결과는 PM의 새 실행 증거로 확인한다.
