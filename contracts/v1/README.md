# Nunti v1 계약 — 협의 중인 1.0 초안

다른 언어에서 사용하는 기준 산출물은 이 디렉터리의 JSON Schema Draft 2020-12이다.
Python 모델은 `backend/nunti/models.py`에 있으며 내보내기 후 schema drift 테스트로 일치시킨다.
`*.schema.json`만으로 형식 검증이 가능하며 아래 관계 규칙은 추가로 검증해야 한다.
합의 없는 파괴적 변경은 금지한다. 확정된 1.0의 필드/enum/타입 변경은 새 계약 버전 협의가 필요하다.
현재 서버는 `schemaVersion: "1.0"`만 받으며 모르는 버전/추가 필드를 422로 거부한다.
느슨하게 임의 필드를 무시하는 전방 호환성을 약속하지 않는다.

## 공유 모델

| 모델 | 핵심 / 초안 결정 |
| --- | --- |
| RouteSnapshot | routeId, trip 내 단조 증가 revision, collectedAt, source 필수; 특징은 선택 |
| AvatarSpec | 외형 파츠, 문자열 seed, 규칙·리소스 버전, 음성 프로필 참조 |
| DrivingEvent | 사건 ID, 발생 시각, 외부 검증 상태/신뢰도, correlation/recovery 참조 |
| EmotionSnapshot | 아바타가 계산한 감정; 합의된 emotionId로 재전송 식별 |
| VoiceProfile | 논리적 persona/speakingStyle, locale, 엔진 지원과 별개인 희망 제어 목록 |
| SpeechRequest | 출처(contentSource)와 목적(speechPurpose)을 분리; 만료·근거 참조 포함 |
| TripReport | 외부 생성 finalText 원문, 0..100 또는 null 점수, 평가 범위와 근거 |

추가 전송 계약은 TripCreate, EventBatch, EmotionBatch다. 각 모델에 정상 `valid`,
필수 schemaVersion 누락 `missing`, 잘못된 타입/범위 `invalid` 예제가 있다.
문자열 ID는 1..128자 ASCII 토큰, 특징/감정/이벤트 이름은 1..64자 토큰이다.
길이·배치·값 범위 한도는 전송 검증 한도이며 운전 평가 임계값이 아니다.

숫자 문자열과 boolean→number 강제 변환을 허용하지 않는다. routeRevision과 시간 초는
정수 JSON 숫자로 보낸다. 시각은 시간대가 있는 RFC3339(소수점 최대 6자리)로 표현한다.
수신 시각과 이벤트 시각을 혼동하지 않는다. leap second는 현재 지원하지 않는다.
Kotlin에서도 date-time 포맷 검사와 아래 의미 규칙을 활성화해야 한다.

## 의미 규칙 및 버전 처리

- RouteSnapshot의 destination, GPS 좌표, 주소는 저장하지 않는다. 사용자 지역명 대신 필요 최소한의
  regionTags를 사용한다. routeOption은 경로 탐색 옵션이고 실제 도로 측정값이 아니다.
- roadTypeRatios의 합은 1 이하여야 한다(부동소수 오차 1e-6 허용). 잔여는 미확인 부분이다.
  각 특징의 근거는 featureEvidence의 정확한 특징 키(`roadTypeRatios`, `scenicTags.COASTAL` 등)로 연결한다.
  근거 없이 특징값이 있다는 이유로 검증된 것으로 간주하지 않는다.
- Evidence는 **소속 RouteSnapshot의 routeId/revision 및 해당 값에만 유효**하다.
  adapter는 revision/값 변경 시 재검증·재생성하고 불가능하면 근거를 제거하거나 UNKNOWN/UNVERIFIED로 표시한다.
  validity=VALID 및 VERIFIED라는 주장도 producer가 제공한 값이며 서버가 실제 도로를 확인한 것은 아니다.
  validUntil은 observedAt보다 이를 수 없다. scenic/region의 신뢰 provider 목록은 AVATAR 호스트 설정이다.
- routeId 변경 시에도 동일 trip 내 routeRevision을 증가시킨다. 중간 버전 건너뛰기는 허용한다.
  현재보다 낮은 새로운 버전은 409. 이미 저장된 과거 버전의 동일 요청은 duplicate이며 현재 버전을 되돌리지 않는다.
- AvatarSpec은 `(trip, avatarId, routeRevision)`마다 불변이다. 같은 avatarId의 revision 변경을 허용한다.
  새 아바타 저장은 현재 routeId/revision과 일치해야 한다. 과거 동일 payload 재전송은 허용한다.
  경로 갱신 직후 일치하는 아바타가 없으면 GET trip의 avatar는 null이다. 과거 외형은 DB에 보존한다.
  EmotionSnapshot은 trip/기존 avatarId에 귀속하며 MVP에서 외형 revision 지정은 필수가 아니다.
- eventId와 emotionId의 중복 범위는 `(principal, tripId, kind, id)`다. 같은 ID/같은 정규화 payload는
  duplicate, 같은 ID/다른 payload는 409. 서버는 correlationId만으로 다른 사건 ID를 병합하지 않는다.
  복구 사건은 새 eventId와 recoveryOfEventId를 가지며 자기 자신을 참조할 수 없다.
- 사건, 복구 근거, 감정 trigger, 리포트 근거의 역순 도착을 허용한다. 감정의 avatar는 먼저 저장해야 한다.
  참조 ID가 미도착했다고 검증된 사실을 새로 만들지 않는다. 리포트 조회에 unresolvedEvidenceEventIds를 표시한다.
- 배치는 전체 성공 또는 전체 rollback이다. 클라이언트는 응답 유실 시 같은 batch/ID로 재전송한다.
  서버 저장은 로컬 감정 엔진이나 TTS의 재실행을 유발하지 않는다.
- 타임라인은 발생 시각을 UTC로 정렬하고 같은 시각은 ID로 정렬한다. offset 페이지는 조회용이다.
  늦은 삽입이 진행되는 동안 페이지 경계가 이동할 수 있으므로 동기화 완료 후 처음부터 조회하고 ID로 중복 제거한다.
  변경 피드용 cursor나 WebSocket 구독 의미를 갖지 않는다.
- dataCoverage.evaluatedSeconds <= totalSeconds. 충분성 기준과 ratio의 산출 의미는 외부 점수 모듈이 정의한다.
  서버는 점수를 계산하지 않으며 null을 0으로 바꾸지 않는다. finalText를 재작성하지 않는다.
- 리포트는 trip당 하나의 불변 산출물이다. 정정/재생성 버전 정책은 후속 협의 사항이다.
- SpeechRequest.expiresAt > requestedAt. 선택 speechPurpose는 발화 목적이지 재생 허가가 아니다.
  sourceEventId/emotionId는 로컬 정책 검증에 사용한다. 만료·차량 제한·선점·재생 중복은 TTS 담당이 결정한다.
  supportedControls는 SDK 기능 보장이 아니다. 서버는 VoiceProfile/SpeechRequest를 저장하거나 재생하지 않는다.

JSON Schema 단독으로 표현하지 못하는 합계·시각 순서·참조 관계는 위 규칙과 API 검증으로 보완한다.
서버와 Android 사이 최대 거리/시간 범위가 다를 수 있다. AVATAR는 wire-valid 값도 미확인으로
대체할 수 있으며, 서버의 저장 성공이 아바타 특징 채택을 의미하지 않는다.
