# v1 계약 검토 요청

상태: 제안, 승인 대기. 현재 구현은 Mock으로 독립 검증한다.

## AVATAR 담당

- RouteSnapshot 최소 입력(routeId/revision, 시각, source)만으로 fallback 가능한지 확인.
- routeOption과 실제 roadTypeRatios를 분리한다. 특징 근거는 featureEvidence에 출처,
  verificationStatus/confidence/validity/observedAt/validUntil로 표현한다.
- AvatarSpec 출력 필드, 문자열 seed, assetVersion/ruleVersion 의미 검토.
- 이벤트는 외부 모듈이 정의한 타입 그대로 전달하며 서버는 감정 계산을 하지 않는다.
- EmotionSnapshot에 재전송용 emotionId 추가 제안. 감정 이름은 확장 가능한 토큰이다.
- 경로 변경 시 revision을 증가시킨다. AVATAR와 협의해 avatarId 유지 및 외형의 revision별 저장을 허용한다.
  이전 아바타 감정 기록은 보존한다.

## TTS 담당

- VoiceProfile/SpeechRequest 필드 및 enum 검토. supportedControls는 논리적 프로필 기능이며
  SDK 실제 지원은 런타임 adapter가 확인한다. 서버는 엔진 지원을 선언하지 않는다.
- requestId 중복 억제, expiresAt, STOPPED의 실제 차량 상태 검증은 로컬 정책 엔진 소유다.
- 재생 상태(started/completed/cancelled/failed 등), 오류 코드 및 대체 음성 정책 제안 요청.
  아직 합의되지 않아 서버 재생 상태 API를 만들지 않는다.
- 협의 결과 contentSource는 출처로 유지하고 speechPurpose/sourceEventId/emotionId를 추가했다.
  AvatarSpec의 중복 persona/voiceStyleHint 대신 VoiceProfile 참조에 동의했다.
- 기획 HTML은 주행 중 STT만 지원한다고 쓰였지만 최신 요청은 허용된 짧은 TTS를 요구한다.
  최신 요청을 우선하며 허용 조건/우선순위/만료 정책은 TTS 담당의 SDK 검증 후 합의한다.

## 이은룡 담당

- DrivingEvent.eventType 실제 목록, severity, 검증 기준, 신호 단위/주기 확인 요청.
- eventId는 사건별로 고정하고 재전송에 재사용한다. 같은 ID/다른 내용은 409이다.
  correlationId만 같은 이벤트를 서버가 동일 사건으로 임의 병합하지 않는다.
- dataCoverage(평가 가능 시간, 전체 시간, 비율, 상태, 미수신 신호)와 0..100/null 점수 제안 검토.
- finalText는 수정 없이 저장한다. 초기 report는 불변이며 정정 버전 정책은 별도 합의가 필요하다.
- 임계값, 35/35/20/10 가중치, 1분 구간, 충분성 기준은 모두 초안으로 유지한다.
