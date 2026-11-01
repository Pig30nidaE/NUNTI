# SERVER 진행 기록

상태: v1.0 제안 / 다른 모듈 승인 전. 브랜치 `server/integration-v1`.

기존 저장소는 기획 HTML 하나만 있으며 Git을 새로 초기화했다.
서버 소유 범위는 `backend/`, `contracts/v1/`, `docs/architecture/`, 이 문서와
`docs/coordination/requests/`다. 아바타 생성·감정 계산·TTS 재생·점수 알고리즘은 구현하지 않는다.

계약은 `schemaVersion: "1.0"`, camelCase, JSON Schema Draft 2020-12를 제안한다.
7개 공유 모델 및 trip 생성/배치 전송 모델을 제공한다.
`EmotionSnapshot.emotionId`를 재전송 식별자로 추가 제안한다.
`generationSeed`는 JVM/JavaScript 정수 정밀도 문제를 피하는 문자열이다.
`destination`·원본 GPS·주소는 서버 계약에서 제외하는 개인정보 최소화 제안이다.

목록에서 확인된 `아바타 생성 설계` 채팅은 개발 세션이 아니라 세션 프롬프트를 만든
기획 대화였다. 실행 중인 AVATAR/TTS 세션을 식별하지 못해 오발송하지 않고 아래 요청서를 남긴다.
다른 세션을 기다리지 않고 고정 Mock Provider로 검증한다.

합의 전 필드/열거값을 확정으로 취급하지 않는다. 확정 이후 파괴적 변경은 새 버전으로 협의한다.
