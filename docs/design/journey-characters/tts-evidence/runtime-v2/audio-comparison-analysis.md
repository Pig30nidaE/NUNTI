# 캐릭터 source와 실제 speaker PCM 비교

2026-11-02, Asia/Seoul. 새 녹음·장치 조작 없이 PM이 보존한 세 common capture와 `prototypes/journey_voice/samples-v2`의 실제 WAV를 읽었다. [9쌍 전체 측정](source-cross-comparison-v2.json)과 [packet·채널·구간 진단](source-capture-diagnostics-v2.json)에 각 입력의 해시를 보존했다. 기존 `coast-ncc.json`, `mountain-ncc.json`, `city-ncc.json`과 WAV는 변경하지 않았다.

## 측정 결과

세 capture에서 올바른 source가 아래 세 지표 모두 가장 높았다. raw waveform NCC는0.226~0.288로 낮지만 RMS envelope와 주파수대별 시간 변화는 같은 source에 훨씬 가깝다. 아래 수치는 합격 임계값이나 사람의 화자 구별 평가가 아니다.

| Capture | 비교 source | Raw waveform NCC | RMS envelope NCC | 5-band amplitude NCC |
| --- | --- | ---: | ---: | ---: |
| coast | coast | 0.27102 | 0.96533 | 0.89968 |
| coast | mountain | 0.07765 | 0.48243 | 0.27745 |
| coast | city | 0.09036 | 0.46897 | 0.34407 |
| mountain | coast | 0.12083 | 0.49303 | 0.30921 |
| mountain | mountain | 0.22635 | 0.97528 | 0.93006 |
| mountain | city | 0.05638 | 0.56341 | 0.36284 |
| city | coast | 0.16708 | 0.54965 | 0.45465 |
| city | mountain | 0.04350 | 0.62863 | 0.31405 |
| city | city | 0.28811 | 0.97962 | 0.86998 |

source는 헤더의44.1kHz·PCM16·mono이며 capture는48kHz·PCM16·stereo다. source만 명목 rate에 맞춰 선형 resample한다. sampling rate 탐색·시간 늘이기·dynamic time warping·부분 source 선별은 적용하지 않았다. raw NCC 계산은 이전 도구와 동일하며 기존 세 결과와1e-12 이내로 일치했다.

위상에 덜 민감한 두 측정은 전체 source의32ms창·10ms hop을 사용한다. RMS envelope는 각 창의 진폭 변화를 비교한다. 5-band는 Hann창 STFT의100~300/300~800/800~1600/1600~3200/3200~8000Hz amplitude에 각각 temporal NCC를 구하고, 공통 offset 하나에서 다섯 값을 평균한다. 파형의 phase를 직접 맞추지 않는다. gain은 각 NCC 정규화로 제거된다. 세 화자는 같은 문장을 말하므로 틀린 source도 일부 상관할 수 있다.

## Raw NCC가 낮은 원인 조사

확인한 사실은 다음과 같다.

- Kotlin `AndroidLocalAudioPlayer`는 WAV bytes를 MediaDataSource로 MediaPlayer에 전달한다. 확인한 코드에 `setPlaybackRate`, `setSpeed`, `setVolume` 호출은 없다. Android mixer·에뮬레이터의 내부 처리를 조사 완료했다는 뜻은 아니다.
- source 파일 길이는 coast4.02946초/mountain3.26921초/city3.70220초다. 앱의 STARTED→COMPLETED 간격은 약4.23057/3.49011/3.93800초다. 파일 전체에 큰 속도 변환이 적용됐다는 근거는 관찰하지 않았다. 콜백 간격으로 정확한 가청 속도를 판정하지 않는다.
- capture 좌우 채널의 상관은0.999975~0.999987이고 최대 차이는5LSB다. mono 평균으로 두 채널이 서로 상쇄돼 NCC가 낮아졌다는 설명과는 맞지 않는다.
- packet은 대략11ms 간격으로 수신됐지만 frames는 일정하지 않다. 조용한 구간의44~46frames, 다른 구간의511~513/719~721frames 등이 섞인다. 10초 stream이 각각7.45015/6.81010/7.19965초의 연결 PCM이 됐다. source 시간축·packet timestamp·연결 WAV 시간축을 같은 것으로 둘 수 없다.
- 고정200ms source 구간을 각 RMS-envelope 정렬 주변 ±50ms에서 따로 비교하는 진단도 수행했다. 모든 연속 구간과 낮은 상관 구간을 JSON에 기록했다. source나 capture를 재배열하지 않았다. coast source의0.4초 구간은 NCC약0.999·lag211.312ms이고,2.6~3.2초의 연속 구간들은 NCC약0.998~0.999·lag251.354ms다. 파일 전체에 하나의 sample offset을 쓰면 이런 국소 정렬 변화를 동시에 맞출 수 없다.

국소 offset 변화와 phase에 민감한 전체 waveform 비교가 낮은 raw NCC에 영향을 준다는 해석은 위 측정과 일치한다. 정확히 어느 계층에서 sample이 추가·누락되거나 시계가 달라졌는지는 확정하지 못했다. gRPC reader·emulator mixer·guest audio·resampler 중 하나를 원인으로 단정하지 않는다. 일부 구간이 높은 raw NCC를 보이고 envelope·band 특징이 해당 source와 가깝다는 결과를 근거로 sample 완전 일치까지 주장하지 않는다.

## 재실행과 판정 범위

```sh
cd /Users/pig30nidae/NUNTI
.local/journey-voice/venv/bin/python scripts/verify_catalog_pcm.py \
  --source prototypes/journey_voice/samples-v2/coast-common.wav \
  --capture docs/design/journey-characters/tts-evidence/runtime-v2/coast-common.wav \
  --phase-robust \
  --output .local/voice-runtime/coast-phase-analysis-new.json
```

세 source와 세 capture를 바꿔9쌍을 비교한다. 기존 output은 거부한다. `--phase-robust`가 없으면 종전 raw NCC만 계산한다. 계산식 확인으로 phase를 반전시킨 합성 fixture가 raw NCC−1, envelope·band NCC+1을 내는 것을 검사했다. 이것은 계산식 검사이며 실제 capture에 phase 반전이 있다는 주장은 아니다.

앱 이벤트·설치 WAV 해시·guest 출력의 신호 상승과 이 비교는 세 source의 실제 출력 연결을 뒷받침한다. 이 기록은 한국어 발음·귀여움·가청 시작 지연·취소부터 무음까지의 지연·실차 품질·운전습관 개선 효과를 평가하지 않았다. 인간 청취도 수행하지 않았다.
