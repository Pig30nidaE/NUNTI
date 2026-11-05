# D 전환 취소와 출력 PCM 관측

2026-11-02. 기존 WAV·packet·`started.json`·`first-attempt.json`을 읽어 [새 분석 JSON](cancel-pcm-observations.json)을 작성했다. 원본과 장치 상태는 변경하지 않았다.

동일한 `coast-greeting` 요청은 STARTED11:35:35.654689Z 뒤 CANCELLED/SPEECH_NOT_ALLOWED11:35:40.996326Z를 기록했다. 실제 플랫폼은 D·속도0·requiresDO=true로 바뀌었다. 여기까지는 앱 이벤트의 실제 관찰이다.

Guest UTC와 packet epoch를 **보정 없이 명목 비교**하면 취소 부근의 신호가 감소한 뒤 큰 출력이 다시 나타난다. 약+0.119~+0.236초에는 peak0 packet들이 있고, +0.248초부터 다시 출력이 커져 +0.284초 packet은 peak1,034다. +0.5~+0.75초 구간의 RMS는 약288이다. 마지막 peak>8 packet은11:35:41.833700Z이며, 녹음 마지막11:35:42.018218Z packet의 peak는4다. 이전 quiet baseline peak2로 완전히 돌아왔다고 판정하지 않는다.

강한 후속 출력과 source의 이어지는 tail도 제한적으로 비교했다. STARTED→CANCELLED의5.341637초를 명목 source 위치로 두고 그 뒤의500ms 구간3개를 모두 측정했다. 실제 음성 시작 지연과 재생 시계 정렬을 모르므로 이 위치가 정확한 source 중단점이라는 주장은 아니다.

| Source 구간 시작 | Source RMS | 명목 취소 후 전체 PCM과 band NCC | 명목+0.2~+0.8초 강한 출력과 band NCC |
| --- | ---: | ---: | ---: |
| 5.3416초 | 1,263.43 | 0.22380 | 0.13362 |
| 5.8416초 | 698.43 | 0.63032 | 0.34119 |
| 6.3416초 | 9.59 | 0.81102 | 0.16787 |

고정32ms창·10ms hop의 동일한 envelope/band 도구를 사용했다. sampling rate 탐색·시간 늘이기는 하지 않았다. 전체 후속 PCM과 가장 높은 값을 낸 마지막 source 구간은 매우 작은 감쇠 구간이다. 단순 감쇠 모양이 비슷하다는 수치로 남은 TTS라고 식별할 수 없다. 강한 출력 구간만 비교한 결과도 source tail의 연속 재생을 확정하지 못한다.

남은 TTS·D 전환/시스템 음·혼합 출력 중 무엇인지는 미검증이다. Guest/host clock offset·drift와 capture buffer 지연도 보정하지 않았다. **정확한 취소→무음 지연과 완전 무음은 검증하지 않았다.** 앱의 취소 이벤트와 player stop/release 구현을 실제 스피커의 무음 증거로 확대하지 않는다. 사람의 청취도 수행하지 않았다.
