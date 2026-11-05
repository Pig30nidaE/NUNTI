# PM의 새 Pleos 런타임 증거 검토

2026-11-02 18:19 KST, AVATAR의 읽기 검토다. PM이 실행한 공식 Pleos 에뮬레이터에서 P→D·속도 증가→P 복귀에 따른 화면 차단·복귀와 진행 중 발화 취소를 확인했다. AVATAR가 에뮬레이터를 직접 조작하거나 다시 실행한 결과는 아니다. 독립 복원 보고서 `avatar.md`는 당시 실행 범위를 유지한다.

## 직접 확인한 자료

원본 디렉터리는 `/Users/pig30nidae/NUNTI/docs/handoff/restoration/2026-11-02/pm-evidence`다. PM 소유 파일은 수정하지 않았다.

- `events-moving.jsonl`, `events-reparked.jsonl`, `events-cancel-on-drive.jsonl` 전체를 JSON으로 읽었다.
- `parked.png`, `moving.png`, `reparked.png`를 직접 열어 비교했다.
- `vehicle-state-moving.json`, `vehicle-state-reparked.json`의 실제 gear·speed·DDS·browser 상태와 `ux-moving.txt`를 대조했다.
- 통합 소스 `RuntimeProbeActivity.kt`가 실제 CarPropertyManager의 gear·`PERF_VEHICLE_SPEED`와 Car UX 상태를 읽어 표시 정책을 계산하는 지점을 확인했다.

[runtime-review.json](runtime-review.json)에 검토 시점의 원본 SHA-256, 표본 수, 대표 상태와 취소 요청을 보존했다. [review_runtime.py](review_runtime.py)를 실행해 로그 관계와 결과를 다시 확인했다. 명령은 아래와 같으며 종료 코드는 0이다.

```sh
python3 docs/handoff/restoration/2026-11-02/avatar-evidence/review_runtime.py \
  --evidence /Users/pig30nidae/NUNTI/docs/handoff/restoration/2026-11-02/pm-evidence
```

세 이벤트 파일은 56개, 71개, 80개의 누적 snapshot이다. 앞 파일이 뒷 파일의 정확한 prefix임을 확인했다. 같은 기록을 독립 실행 세 번이나 중복 표본으로 세지 않았다. 최종 snapshot의 고유 Drive 상태 36개 중 30개가 speed>0이었고, 36개 모두 `requiresDO=true`, `avatarVisible=false`, `reason=PLATFORM_BLOCKED`였다.

## 표시 정책과 화면 관찰

| 단계 | 실제 로그·플랫폼 값 | 직접 연 화면의 관찰 |
| --- | --- | --- |
| 최초 P 주차 | `gear=4`, `speed=0`, `parked=true`, `uxKnown=true`, `requiresDO=false`, `avatarVisible=true`, `PARKED_STATIC_MVP` | `parked.png`에 P·0km/h, CITY 아바타, 제목·Mock 경로 설명이 표시된다. 얼굴·몸체·표식과 도시형 의상·티켓을 구분할 수 있다. 제목·설명·캐릭터가 겹치지 않는다 |
| D 전환 | 18:16:13.187565 KST, `gear=8`, `speed=0`, `parked=false`, `requiresDO=true`, `avatarVisible=false` | 속도가 생기기 전 D 상태부터 앱 정책이 차단을 기록했다 |
| 이동 | 첫 speed>0 기록은 18:16:37.397012 KST, `gear=8`, `speed=1.6666667`. 후속 이동 표본도 모두 차단 | `moving.png`에는 D·18km/h와 플랫폼의 "주행 중에는 사용할 수 없습니다." 화면이 보인다. Nunti의 제목·설명·캐릭터·진단 조작 UI는 화면에서 보이지 않는다 |
| P 복귀 | 18:17:14.811264 KST, `gear=4`, `speed=0`, `parked=true`, `requiresDO=false`, `avatarVisible=true`, `PARKED_STATIC_MVP` | `reparked.png`에서 P·0km/h와 같은 CITY 아바타·설명이 다시 나타난다. 배치가 유지되며 겹침이 없다 |

Console 이동 snapshot은 `actual.gear=Drive`, `speed_kph=18`, gear bridge와 controls DDS 준비 true를 기록한다. 복귀 snapshot은 Park·0과 같은 준비 상태를 기록한다. 두 snapshot 모두 `browser.active=true`, `clients=1`, `timeout_ms=3000`이다. 새 증거는 과거 `emulator_inactive` 상태와 다르다. 브라우저 heartbeat가 준비 상태를 바꿨다는 실행 순서의 원인 판정은 PM 기록을 따른다.

`ux-moving.txt`의 실제 CarUxRestrictionsManagerService도 `DO:true`, `UxR:80`과 0→80 전환을 기록한다. 따라서 합성 policy만 주입한 단위 테스트가 아니라, 에뮬레이터의 차량 API와 UX 상태 변화에 대해 debug host와 플랫폼 화면이 반응한 결과로 판단한다. 화면 차단과 P 복귀에 관해서는 과거 미검증 상태를 이번 에뮬레이터 실행 범위에서 갱신할 수 있다.

## 주행 전환 시 발화 취소

`events-cancel-on-drive.jsonl`의 동일 요청 `probe-086591f3-b14f-4067-8eb0-1c9e78f348d8`은 다음 순서다. 시각은 UTC 로그를 KST로 옮겼다.

| KST 시각 | 관찰 |
| --- | --- |
| 18:17:28.872359 | `QUEUED`, `mode=ON_DEVICE` |
| 18:17:28.929259 | `STARTED`, `startLatencyMs=57` |
| 18:17:31.708980 | `CANCELLED`, `reason=SPEECH_NOT_ALLOWED` |
| 18:17:31.709889 | `gear=8`, `speed=0`, `requiresDO=true`, `avatarVisible=false`, `PLATFORM_BLOCKED` |

이는 이미 STARTED한 요청이 D 전환과 함께 정책 취소됐다는 callback 증거다. 별도 D 상태 요청도 18:16:33.415022에 `REJECTED/SPEECH_NOT_ALLOWED`를 기록했다. 취소 callback과 PLATFORM 로그의 출력 순서를 차량 전환 반응시간이나 실제 무음 지연으로 해석하지 않는다.

## 해석의 한계와 남은 항목

- `PROBE_CREATED`는 `DEBUG_EMULATOR_ONLY`, `MOCK_ROUTE_AND_EMOTION`을 명시한다. 실제 차량 하드웨어, production host, NaviHelper·GIS·운전 이벤트의 제품 연결은 이번 증거의 범위 밖이다.
- 이동 화면은 플랫폼이 앱 영역 전체를 막는 화면이다. Nunti의 renderer 내부 subtree와 접근성 트리가 실제로 제거됐는지는 이 화면만으로 독립 검증할 수 없다. 앱 로그의 `avatarVisible=false`와 플랫폼 차단을 각각 확인한 결과다.
- 주차·복귀 화면은 CITY 한 조합이다. 모든 테마·감정·창 크기·회전·접근성 instrumentation을 검사한 결과가 아니다.
- 정책 누락·노후·Car 연결 유실이나 재부팅을 이번 런타임에서 의도적으로 재현하지 않았다. 해당 항목의 새 차량 런타임 검증은 남는다.
- 로그의 speed와 Console·계기판의 km/h는 서로 다른 값·시점이다. 속도가 변하는 실행이므로 특정 설정 속도를 지속 유지한 시험으로 묶지 않는다.
- 에뮬레이터는 `-no-audio` 조건이다. 새 PCM·WAV 수집, 실제 가청 출력, 취소 후 무음 지연, 발음·첫 음절·선행 묵음·음질 청취 증거는 없다. `STARTED`나 57ms는 실제 가청 시작을 뜻하지 않는다.

이번 후속 관찰의 완료 범위는 공식 에뮬레이터의 차량 상태와 UX 변화, 화면 차단·복귀, 발화 허가 거부·진행 중 취소다. 실제 입력 adapter와 journal 영속 host의 미구현 상태는 독립 복원 보고서와 같다.
