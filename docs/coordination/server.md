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

초기에는 실행 중인 AVATAR/TTS 채팅을 식별하지 못해 요청서를 남겼다. 이후 두 개발 세션에서
직접 협업 메시지가 도착해 계약을 조율했다. AVATAR는 `avatar/route-emotion-v1`,
TTS는 `codex/tts-system` worktree에서 독립 개발 중이다.

합의한 사항:

- EmotionSnapshot.emotionId를 재전송 식별자로 사용한다.
- avatarId는 revision 간 유지할 수 있으며 서버는 avatarId+routeRevision으로 외형을 저장한다.
- routeRevision은 trip 내 단조 증가한다. evidence는 소속 snapshot의 route/revision/value에 귀속한다.
  변경 시 adapter가 재검증하며 UNKNOWN은 사실로 승격하지 않는다.
- SpeechRequest의 contentSource는 출처이고 선택 speechPurpose/sourceEventId/emotionId는 목적/근거다.
- 음성 persona/speakingStyle은 VoiceProfile로 참조하므로 AvatarSpec의 중복 필드는 추가하지 않는다.
- AVATAR가 신규 공통 Android Gradle 설정과 최소 app host를 작성하는 데 SERVER가 동의했고
  TTS에도 공유했다. SERVER가 Android 모듈 소유 코드를 수정하지 않는다.

현재 고정 Mock 10개와 실제 AVATAR JVM mapper 출력 10개를 서버 계약으로 검증한다.
실제 차량·음성 재생 검증과 서버 Mock 통합 검증은 구분한다.
TTS 검증 스크립트를 SERVER에서 직접 실행해 JVM 62개, 공통 JSON/AVATAR 출력 연동 8개 및
Android/Pleos 실제 바이너리 컴파일 통과를 확인했다. 서버 pytest는 91개 통과했다.

최종 통합: AVATAR f6ad9ac과 TTS 2a0ce2f 및 문서 후속 3925eb8/9c3fbe5를
server/integration-v1에 cherry-pick했다. 루트 인덱스 변경은 SERVER가 수행했다.
루트에서 서버91/AVATAR58+1,000fixtures/TTS62+연동8 및 APK·Lint 빌드를 재확인했다.
오프라인 Lint 오류0/경고3이며 실제 차량·에뮬레이터 실행은 미검증이다.

합의 전 필드/열거값을 확정으로 취급하지 않는다. 확정 이후 파괴적 변경은 새 버전으로 협의한다.
