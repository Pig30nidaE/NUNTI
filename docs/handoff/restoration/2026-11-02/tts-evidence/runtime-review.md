# PM Pleos 런타임 증거의 TTS 검토

2026-11-02, Asia/Seoul. TTS 담당이 PM의 새 실행 증거를 읽기 검토했다. TTS 담당의 별도 에뮬레이터 실행 결과가 아니며 기존 `tts.md`의 독립 실행 범위와 구분한다. root 파일과 실행 중인 장치는 변경하지 않았다.

## 검토 자료

기준 폴더는 `/Users/pig30nidae/NUNTI/docs/handoff/restoration/2026-11-02/pm-evidence`다. 아래 네 파일을 JSON으로 직접 파싱하고 requestId별 상태와 차량 상태 시각을 대조했다. JSONL은 누적 스냅샷이므로 같은 이벤트를 여러 독립 시험으로 세지 않았다.

| 파일 | 읽은 레코드 수 | SHA-256 |
| --- | ---: | --- |
| lifecycle-results.json | 4 | `ae8e3f2e81508b966137f60782999b0d39e048e42734c7caee4addb666a39997` |
| events-completed.jsonl | 33 | `0c48d7c594e328ce37b3edcf74e805ef7d286d0578ed6eb43ef1a6c48d57f3cc` |
| events-cancel-on-drive.jsonl | 80 | `c0ac212cd2a4a0671002ca35883216f9cf97bb1389b3d9d2ae6c55379bcab6e2` |
| events-moving.jsonl | 56 | `05c289a250ec98679e047510894eec2ddf13752a44128abacab1e559da742ca9` |

추가로 `vehicle-state-before-browser.json`, `vehicle-state-browser-open.json`, `vehicle-state-drive-zero.json`, `vehicle-state-moving.json`, `vehicle-state-reparked.json`, `vehicle-state-final.json`, `ux-moving.txt`, `events-final.jsonl`, `avd-config.ini`, `runtime-logcat.txt`를 확인했다.

## 확인한 새 결과

- 주차 ON_DEVICE 요청 `probe-886a3827-c44c-44b2-a876-f3138213a0fa`는 18:16:02.172389 KST QUEUED, 02.404385 STARTED, 06.277672 COMPLETED다. 상태·requestId·시각 순서가 일치한다. 이 요청의 231ms는 submit→SDK onStart 값이다.
- 사용자 중지 요청 `probe-21490037-918c-473b-b031-a95431eda4bf`는 STARTED 후 CANCELLED/USER_CANCELLED다. 이후 새 요청 `probe-762ea74c-3180-43de-a367-7e66532a04bc`는 REJECTED/REPEATED_TEXT다.
- background 요청 `probe-92bbfd5c-41bb-4f3c-bfe8-3ee7c9da7bce`는 STARTED 후 CANCELLED/BACKGROUND다. 복귀 후 새 요청 `probe-e7b0e569-6b16-4481-a839-630991202e7f`는 REJECTED/REPEATED_TEXT다. lifecycle 결과와 누적 원시 이벤트가 일치한다.
- D·속도0 상태에서 18:16:33.415022 KST의 새 요청 `probe-db5a10a8-e15e-4e12-9a3f-306cf79fb573`는 REJECTED/SPEECH_NOT_ALLOWED다. 앞선 실제 플랫폼 관측은 gear8·parked=false·uxKnown=true·requiresDO=true·avatarVisible=false다.
- 주차에서 시작한 `probe-086591f3-b14f-4067-8eb0-1c9e78f348d8`는 18:17:28.929259 KST STARTED 후 31.708980 CANCELLED/SPEECH_NOT_ALLOWED다. 직후 31.709889의 플랫폼 이벤트는 gear8·속도0·requiresDO=true·avatarVisible=false다. 이는 D 전환과 같은 갱신 구간의 정책 취소 증거다.
- 실제 속도값은 gear8에서 0보다 커지고 최대 15m/s까지 관측됐다. 해당 이동 플랫폼 이벤트는 requiresDO=true·avatarVisible=false를 유지한다. `ux-moving.txt`도 실제 CarUx service의 DO=true·UxR80을 기록한다.
- Console을 열기 전에는 browser clients0·emulator_active=false·gear bridge=false·DDS all=false다. 브라우저 세션이 열린 스냅샷은 clients1·emulator_active=true·gear bridge=true·DDS all=true이며 실제 gear가 Park→Drive→Park으로 바뀐다. 최종 스냅샷은 Park·속도0이다. 앱의 최종 이벤트도 gear4·requiresDO=false·avatarVisible=true로 복귀한다.
- `events-final.jsonl`에서 D 전환 취소 이후 최종 P 복귀까지 새 QUEUED/STARTED/COMPLETED는 없다. 관측 구간에서 이전 요청의 자동 재생을 보이지 않는다.

## 판정과 한계

이번 PM 실행은 공식 Pleos2.1.0/API34 에뮬레이터의 SDK 경로 완료 상태, 사용자 중지·background·반복 억제, D 전환 시 새 요청 거부·진행 요청 취소, 실제 속도 변화와 UX·화면 차단 및 P 복귀를 새로 확인했다. 과거의 Virtual Console inactive만을 현재 차단사항으로 유지할 근거는 없어졌다.

두 TTS 주행 정책 사례는 모두 D·속도0에서 발생했다. 속도>0 구간에서 별도 새 TTS 요청을 보낸 증거는 이 파일들에 없다. 주행 중 허용되는 검증 이벤트의 짧은 음성, 통화·내비·안전음의 실제 경합, 모든 주행 상태 조합의 동작까지 통과로 확대하지 않는다.

D 전환 취소와 거의 같은 시각의 `audioContext`는 UNKNOWN이며 뒤에 OPERATOR_CONTROLLED_TEST로 갱신된다. 취소 원인 코드는 SPEECH_NOT_ALLOWED로 넓은 정책 사유다. 기어·DO·오디오 신선도 중 단 하나의 입력만으로 취소가 발생했다는 분리 실험은 아니다. CANCELLED와 PLATFORM 로그 시각의 차이를 실제 오디오 중단 지연으로 계산하지 않는다.

PM은 에뮬레이터를 `-no-window -no-audio`로 실행했다고 보고했다. `avd-config.ini`의 `hw.audioInput=no`도 확인했다. 이번 검토 시 `runtime-logcat.txt`는 0바이트여서 SDK initialize·ko_KR 원시 로그를 확인한 것으로 쓰지 않는다. 앱의 ON_DEVICE 상태 이벤트와 COMPLETED를 기준으로 판단한다.

새 PCM 수집·스피커 출력·인간 청취·발음·첫 음절·선행 묵음·가청 지연·취소 후 실제 무음은 이번 증거에 포함되지 않는다. 41ms·19ms·231ms·57ms는 개별 SDK 시작 콜백 값이며 음질이나 p50/p95 성능 보증이 아니다. 경로·감정 입력은 DEBUG_EMULATOR_ONLY/MOCK_ROUTE_AND_EMOTION이다. 실제 도로·운전 이벤트·서버 HTTP·production host·HYBRID/SERVER·실차·장시간 시험은 남아 있다.
