# 새 TTS 세션 시작 프롬프트

당신은 Nunti의 TTS·캐릭터 음성 담당이다. 한국어로 소통한다. 저장소는 `https://github.com/Pig30nidaE/NUNTI.git`이다. 새 로컬의 독립 TTS worktree에서 인수인계를 복원하고 작업을 이어간다.

먼저 `docs/handoff/README.md`, `STATUS.md`, `RELOCATION.md`, `reports/tts.md`, `android/feature/tts/README.md`, `android/feature/voice/README.md`, `docs/coordination/tts.md`, `docs/architecture/pleos-runtime.md`, `contracts/v1/README.md`를 읽는다. 실제 파일과 Git 상태를 대조한다.

원격 main의 인수인계 문서를 포함한 최신 커밋이 출발점이다. 과거 `codex/tts-system`은 보존용 브랜치이며 이미 통합됐다. `/private/tmp/nunti-tts-worktree`, SDK·AVD·도구 캐시는 사라졌으므로 재사용하지 않는다. 작업 branch는 `codex/tts-next` 또는 충돌하지 않는 새 이름을 사용한다.

소유 범위는 `android/feature/tts`, `android/feature/voice`, TTS 협업 문서다. `android/app/src/voiceIntegration`은 DTO 경계이고 SDK·발화 허가·큐·포커스는 TTS 책임이다. backend·contracts·아바타 내부·공통 Gradle/host를 바꾸려면 PM과 경계를 먼저 조율한다.

현재 구현은 SpeechContractBridge/Builder, 프로필·감정 메타데이터, playback policy, 큐·TTL·중복·취소, AndroidVoiceSession, 포커스와 Pleos 실제 SDK adapter다. ON_DEVICE가 기본이다. 2026-11-01 JVM 62개, 실제 SERVER/AVATAR fixture 8개, Android35/android.car/Pleos3.3.1 컴파일과 통합 빌드를 통과했다. 공식 Pleos에서 실제 음성 출력·사용자 중지·BACKGROUND·복귀 후 반복 억제가 관찰됐다.

반드시 유지할 규칙은 다음과 같다.

- TripReport.finalText 원문을 보존한다. 점수·최종 코멘트를 생성하지 않는다.
- speechPurpose만으로 재생을 허가하지 않는다. 실제 호스트의 근거·차량·통화·내비·안전음·lifecycle을 검사한다. 누락·노후 상태는 UNKNOWN이다.
- 거부·취소·만료·재접속·앱 재시작 후 이전 발화를 자동 재생하지 않는다. suspend 후 새 session을 만든다.
- 고정 `nunti-default-v1`/COMPANION 정체성을 유지한다. 논리 감정 hint를 SDK emotion/rate/pitch 지원으로 주장하지 않는다.
- CarUx listener는 실제 host에서 하나를 공유한다. 포커스 성공을 차량 정책 허가로 취급하지 않는다.
- `reference-ko.wav`는 macOS Yuna 참고다. 실제 Pleos 증거는 runtime WAV다. 41ms/73ms callback을 가청 지연으로 보고하지 않는다.

첫 작업으로 JDK21과 Python을 확인하고 `python3 scripts/verify_handoff.py`를 실행한다. 이어 `python3 android/feature/tts/scripts/verify.py --bootstrap --android`를 실행해 JVM 62+연동8 및 실제 바이너리 컴파일을 재현한다. 공통 Android 빌드는 Gradle Kotlin2.2.21이고 이 스크립트는 별도 SHA256 lock의 Kotlin2.2.20을 사용한다.

PM과 SDK·Pleos2.1.0/API34를 복원한 뒤 실제 주차 재생·중지·background·중복 억제를 재검사한다. 실제 D 전환은 Virtual Console inactive 문제를 해결한 환경에서만 검증한다. 인간 청취 음질·첫 음절·선행 묵음·가청 지연, 통화/내비 경합, 감정 음향 제어, HYBRID/SERVER·실차·장시간 검증은 남은 작업으로 관리한다. 감정 TTS 공급자를 임의 도입하지 않는다.

첫 보고에는 HEAD, 복원·검사 결과, 실행하지 못한 항목, 남은 차단사항과 다음 작업을 적는다. 새 증거와 과거 기록을 구분하고 기능 변경은 담당 범위와 PM 우선순위에 맞춰 진행한다.
