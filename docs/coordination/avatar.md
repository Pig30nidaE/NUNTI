# AVATAR 세션 협업 기록

개발 브랜치 `avatar/route-emotion-v1`, 독립 worktree `/private/tmp/nunti-avatar`.
SERVER의 공용 작업 폴더·인덱스·소유 코드를 수정하지 않고 개발했다.

## 소유권과 합의

- AVATAR: `android/feature/avatar`, `emotion`, `navigation`, 이 문서.
- SERVER의 직접 동의를 받아 신규 `android/settings.gradle.kts`, `build.gradle.kts`, `gradle.properties`, `android/app` 작성.
- TTS도 AGP 8.10.1/Kotlin 2.2.21/JDK21/Java17/compile35/min28 설정에 동의했다.
- SERVER 소유 `contracts/v1`, backend 및 TTS/voice 내부는 수정하지 않았다.
- 메시지 협업은 사용자가 SERVER와 TTS 각각 명시적으로 허용한 후 수행했다.

## SERVER 합의

- schemaVersion `1.0`, UNKNOWN은 nullable/누락/미검증으로 표현. routeOption으로 도로 비율을 추정하지 않는다.
- Evidence는 소속 snapshot의 routeId/revision/특징값에 한정. 값/revision 변경 시 producer가 재검증한다.
- 전체 및 태그별 근거 키를 지원. 도로 비율 합 ≤1의 잔여는 UNKNOWN. 지형 provider 등록은 호스트 소유.
- avatarId는 baseCharacterId+routeId로 결정, revision 변경에도 유지. 서버는 trip/avatarId/revision별 보존.
- DrivingEvent.correlationId → incidentId, recoveryOfEventId는 현재 cause에 대응. 회복 이벤트는 별도 ID.
- EmotionSnapshot.emotionId는 결정적 digest이며 동일 재전송에 사용한다. MVP emotion에 외형 revision 필수 아님.
- 서버 wire AvatarSpec은 compact projection, 로컬에는 전체 후보·설명·audit·rule/asset digest 유지.
- SERVER가 실제 Kotlin 출력 10개를 JSON Schema/Pydantic으로 검사하고 4개 경로/아바타 API 저장·조회를 확인했다.
- 생성자가 출력한 실제 해안 tag별 근거 fixture도 AVATAR 테스트에 포함했다.

## TTS 합의

- `voiceProfileId=nunti-default-v1`, persona `COMPANION`, style hint `CALM`.
- currentEmotion은 6개 감정 enum으로 전달하며 화자/음성 ID를 여행마다 바꾸지 않는다.
- `android/app/src/voiceIntegration`은 DTO 변환만 수행한다. SDK 호출/큐/포커스/발화 허가는 TTS 소유.
- TTS가 실제 AVATAR JSON을 읽는 8개 연동 검사를 통과했다고 회신했다.
- CarUxRestrictionsManager listener는 호스트 하나만 등록하고 양쪽에 공유한다. 두 feed를 동시 생성하지 않는다.
- AndroidVoiceSession은 실제 호스트의 speechPermission, 차량 상태, 통화/내비, lifecycle 정보를 받아야 한다.
- 기본 Mock 앱은 실제 발화를 시작하지 않는다. 차량에서의 화면/발화 허가는 미확인 상태다.

## 아직 필요한 실제 입력

- NaviHelper 실 SDK response의 route 전체 거리·시간 의미(잔여값과 최초 계획값 구분), 실제 콜백 전달 조건.
- route-wide roadTypeRatios 또는 검증 GIS 교차 결과. 목적지 이름으로 대체 불가.
- 이은룡 담당의 eventType 정식 목록, verificationStatus/confidence 의미, correlation/recovery 정책.
- 차량 플랫폼 화면 카테고리 허가, Car 연결/해제, 실제 주행/주차 상태 feed 및 정책 freshness.
- 최종 디자인 파일/파츠 rig와 실제 사용자에 의한 경로별 외형 구별·동일 캐릭터 평가.

현재 실행 앱은 일반 Android Mock 뷰어다. Automotive 기기에서는 실제 host가 연결되기 전 빈 화면으로 차단한다.
핵심 순수 모듈/Compose 라이브러리는 실제 AAOS 호스트에 삽입할 수 있지만 실차 동작 검증과 같지 않다.
