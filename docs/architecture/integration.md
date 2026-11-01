# AVATAR · TTS · 점수 모듈 연결 예제

소유권: SERVER는 계약/동기화만 관리한다. 아래 호출명은 **앱이 구현할 경계 인터페이스 의사코드**이며
존재를 확인한 Pleos SDK 메서드가 아니다. 실제 SDK 메서드는 각 Android adapter가 감싼다.

실제 구현 경계의 검증 결과: AVATAR가 생성한 10개 JSON을 공통 스키마로 검증했고,
4개 경로·아바타 쌍은 서버 API 저장·조회까지 통과했다. TTS의 실제 Kotlin bridge/builder로
서버 SpeechRequest·VoiceProfile·EmotionSnapshot과 AVATAR 출력의 연동 8개도 통과했다.
자세한 실행 범위와 하드웨어 미검증 항목은 `validation.md`에 기록했다.

## 앱 내 경계

```text
route = navigationAdapter.snapshot()                  // 최소 필드만 있어도 허용
avatar = avatarGenerator.generate(route)               // 로컬 실행; SERVER 알고리즘 없음
ui.showAvatar(avatar)
if consent: outbox.enqueue(trip, route, avatar)         // 이 순서로 비동기 저장

onExternalDrivingEvent(event):
    if localEventInbox.alreadyProcessed(event.eventId): return
    emotion = emotionEngine.accept(event)              // 이벤트 중복은 로컬에서도 방지
    localEventInbox.commit(event, emotion)             // 상태/중복 처리 기록을 함께 영속화
    speechPolicy.consider(event, emotion, vehicleState) // 현재 검증된 차량 상태가 재생 판단
    if consent: outbox.enqueue(event, emotion)

onExternalTripReport(report):
    ui.showReport(report)                              // 서버 응답을 기다릴 필요 없음
    speechPolicy.considerPostTrip(report.finalText)     // 원문 유지, 로컬 정책 검사
    if consent: outbox.enqueue(report)
```

서버 조회 결과를 로컬 emotionEngine 입력으로 다시 넣지 않는다. 리포트 speechRequest의 requestId도
로컬에서 고정하고 서버 응답 재시도 때문에 발화를 다시 만들지 않는다.

## 실제 HTTP payload 예제

`contracts/v1/examples`의 10개 valid JSON을 그대로 요청에 사용할 수 있다.
AVATAR는 RouteSnapshot.valid.json → 자신의 generator → AvatarSpec 스키마 검증 순서로 연결한다.
외부 이벤트의 정확한 종류는 담당자 합의가 필요하므로 HARD_BRAKING/STABLE_DRIVING은 Mock 토큰이다.
EmotionSnapshot의 intensity는 0..1 표현 강도이며 운전 위험도나 점수가 아니다.

TTS는 VoiceProfile.valid.json과 SpeechRequest.valid.json을 로컬 입력으로 읽는다.
POST_TRIP SpeechRequest.text는 TripReport.finalText와 동일하게 전달한다.
SpeechRequest는 서버의 원격 재생 명령이 아니다. speechPurpose=VERIFIED_EVENT_RESPONSE라면
TTS 모듈이 sourceEventId와 검증된 로컬 근거를 확인해야 하며 목적 값만으로 신뢰하지 않는다.

```sh
# backend/에서, 토큰 환경변수를 설정한 후 실행
curl --fail --silent --show-error http://127.0.0.1:8000/v1/trips \
  -H "Authorization: Bearer $NUNTI_DEMO_TOKEN" -H 'Content-Type: application/json' \
  --data-binary @../contracts/v1/examples/TripCreate.valid.json
curl --fail --silent --show-error -X PUT http://127.0.0.1:8000/v1/trips/trip-mock/route \
  -H "Authorization: Bearer $NUNTI_DEMO_TOKEN" -H 'Content-Type: application/json' \
  --data-binary @../contracts/v1/examples/RouteSnapshot.valid.json
```

이후 avatar PUT → EventBatch/EmotionBatch POST → TripReport PUT → report GET 순서다.
Fixture 전체 흐름은 `python -m nunti.demo --scenario 10-report --consent`로 실행한다.

## 장애 규칙

1. 전송 전 outbox에 원래 ID/payload를 영속화한다. 서버 ACK를 받은 요청만 삭제한다.
2. 연결 실패/응답 유실/408/429/5xx는 같은 요청을 재시도한다. 성공 상태가 불확실해도 새 ID를 만들지 않는다.
3. 401/403은 인증·동의 상태를 확인한다. 409는 원본과 서버 상태를 비교하고 버전/의존 관계를 해결한다.
   422는 계약 오류를 수정한다. 이런 오류를 무한 자동 재시도하지 않는다.
4. 배치 하나가 충돌하면 전체 미저장이다. 일부 성공으로 가정해 로컬 큐를 삭제하지 않는다.
5. 늦은 이벤트와 report의 미도착 근거는 기록을 보존하고 정렬/해결한다. 서버는 감정을 재계산하지 않는다.
6. 재연결 때 만료된 SpeechRequest를 재생하지 않는다. 음성 요청은 서버 outbox의 재생 대상이 아니다.

`backend/nunti/demo_outbox.py`와 `backend/tests/test_scenarios.py`에서 재시작/재전송 동작을
실행 가능한 Python 예제로 검증한다. Android UI·SDK·실제 TTS 재생의 완료를 뜻하지 않는다.
