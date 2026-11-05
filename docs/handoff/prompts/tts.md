# 새 TTS 세션 시작 프롬프트

최신 시각 개선은 [v5](../../design/avatar-quality-v5/README.md)다. 운전습관 개선을 돕는 눈티 안의 사용자 담당은 목적지·경로 기반 생성이며 [제품 기준](../../product/2026-hmg-app-challenge.md)을 유지한다. 몸 표면 경로를 지우고 새 원화·오로라 효과를 적용했으며 음성 코드는 변경하지 않았다. 기기 화자 설정과 새 음색·Anna 재현을 구분한다. 녹화·스피커 녹음은 명시 요청 때만 한다. 아래 v4·v2는 이력이다.

최신 시각 구현은 [v4](../../design/avatar-quality-v4/README.md)다. 운전습관 개선을 돕는 눈티 안의 사용자 담당은 목적지·경로 기반 생성이며 [제품 기준](../../product/2026-hmg-app-challenge.md)을 유지한다. 불투명 파스텔 표현과 무료 로컬 이미지 모델을 연결했으나 음성은 기존 기기 한국어 화자 설정 미리 듣기다. 새 음색 생성·Anna 재현을 완료했다고 보고하지 않는다. 기존 v2 음색 바인딩·후속 대사·queue는 보존한다. 녹화·스피커 녹음은 명시 요청 때만 한다. 아래 v3·v2 설명은 과거 기록이다.

최신은 [생성기 v3](../../design/avatar-generator/README.md)다. 운전습관 개선을 돕는 눈티 중 사용자 담당은 목적지·경로 기반 생성이며 [제품 기준](../../product/2026-hmg-app-challenge.md)을 유지한다. v3는 이미지 완료와 기기 화자의 미리 듣기를 분리한다. 음성 설명·속도·높이를 보관하며 새 음색을 생성한 상태가 아니다. v2 DesignedVoice·소장품·queue를 변경하지 않았다. 아래 보고는 과거 기록이다.

제품 목표는 운전습관 개선을 도와주는 아바타 눈티다. 사용자 담당인 목적지·경로 기반 생성 기능과 전체 제품을 구분하는 [제품 기준](../../product/2026-hmg-app-challenge.md)을 우선한다. 캐릭터의 음색 정체성을 주행 이벤트에 따른 음성 피드백에서도 유지한다. 이미지·음성 준비 상태 분리는 생성 파이프라인의 설계이며 전체 제품의 TTS를 후순위로 정하는 결정이 아니다.

2026-11-03 최신 기준은 [생성 동반자 v2](../../design/generative-mvp/README.md), [검증 보고](../../design/generative-mvp/test-report.md), [현황](../STATUS.md)이다. TTS는 DesignedVoice·manifest3의 공급자/모델/음색 바인딩, 전체 WAV 검증, 기존 queue와 반복 억제를 유지하는 catalog 확장을 구현했다. Android 샘플 재생·후속 대사·취소·복원을 확인했다. Anna는 선호 기준이며 새 API 음색의 품질 승인이 아니다. 실제 계정·새 음색 한국어 품질은 미검증이다. 아래 72점·Sohee와 고정 기본 음성 설명은 과거 기록이다.

최신 생성 흐름은 [목적지·경로에서 동반자가 태어나는 시험본](../../design/route-birth/test-report.md)을 따른다. 앱에서 목적지·특성·목적과 직접 그린 경로를 입력하면, 기존16윤곽 선택 없이 새72점 외형과 로컬 Sohee 음성을 생성한다. 경로 trace→몸체 morph→얼굴 등장, 런타임 음원 수신, 도착·보관·복원을 연결했다. 새5여정·15새WAV는 검증 표본이며 선택지나 생성 상한이 아니다. PC 모델/로컬 bridge가 필요하고 외부 API·계정은 사용하지 않는다. Anna 선호는 유지한다. 지도·내비 입력·폭넓은 자유 서술 해석·Android 추론·실차·사람의 품질 평가는 남았다. 아래8개 목록 방식은 이전 검증본이다.

이전 v2 기준선은 [TTS 실제 구현·시험 결과](../../design/journey-characters/tts-result.md)에 보존한다. 최신 상태는 위 생성 연동 보고를 따른다. v2 PC 합성·Android Debug 파일 재생과 실제 emulator 정책 이벤트까지 완료했다. 사용자 음성 피드백은 "전체적으로 더 작고 귀여운 느낌"이다. 새 2.5D 시각·매 여행 자동 모델 호출·제품 host 연결은 남았다. 아래 과거 기준선과 완료된 복원은 반복하지 않는다.

최신 요구는 [여정 캐릭터 브리프](../../product/journey-character-brief.md)와 [C 방향 통합 설계](../../design/journey-characters/README.md)다. 매 여행 생기는 새 캐릭터 특성에 맞는 실제 음성을 목표로 한다. [복원 결과](../restoration/2026-11-02/PM.md)와 [새 음성 제안](../../design/journey-characters/tts-proposal.md)을 먼저 읽고 완료된 복원을 반복하지 않는다. 외부 feed 조율은 보류한다.

당신은 Nunti의 TTS·캐릭터 음성 담당이다. 한국어로 소통한다. 저장소는 `https://github.com/Pig30nidaE/NUNTI.git`이다. 새 로컬의 독립 TTS worktree에서 인수인계를 복원하고 작업을 이어간다.

먼저 `docs/handoff/README.md`, `STATUS.md`, `RELOCATION.md`, `reports/tts.md`, `android/feature/tts/README.md`, `android/feature/voice/README.md`, `docs/coordination/tts.md`, `docs/architecture/pleos-runtime.md`, `contracts/v1/README.md`를 읽는다. 실제 파일과 Git 상태를 대조한다.

원격 main의 인수인계 문서를 포함한 최신 커밋이 출발점이다. 과거 `codex/tts-system`은 보존용 브랜치이며 이미 통합됐다. `/private/tmp/nunti-tts-worktree`, SDK·AVD·도구 캐시는 사라졌으므로 재사용하지 않는다. 작업 branch는 `codex/tts-next` 또는 충돌하지 않는 새 이름을 사용한다.

소유 범위는 `android/feature/tts`, `android/feature/voice`, TTS 협업 문서다. `android/app/src/voiceIntegration`은 DTO 경계이고 SDK·발화 허가·큐·포커스는 TTS 책임이다. backend·contracts·아바타 내부·공통 Gradle/host를 바꾸려면 PM과 경계를 먼저 조율한다.

현재 구현은 SpeechContractBridge/Builder, 프로필·감정 메타데이터, playback policy, 큐·TTL·중복·취소, AndroidVoiceSession, 포커스와 Pleos 실제 SDK adapter다. ON_DEVICE가 기본이다. 2026-11-01 JVM 62개, 실제 SERVER/AVATAR fixture 8개, Android35/android.car/Pleos3.3.1 컴파일과 통합 빌드를 통과했다. 공식 Pleos에서 실제 음성 출력·사용자 중지·BACKGROUND·복귀 후 반복 억제가 관찰됐다.

반드시 유지할 규칙은 다음과 같다.

- TripReport.finalText 원문을 보존한다. 점수·최종 코멘트를 생성하지 않는다.
- speechPurpose만으로 재생을 허가하지 않는다. 실제 호스트의 근거·차량·통화·내비·안전음·lifecycle을 검사한다. 누락·노후 상태는 UNKNOWN이다.
- 거부·취소·만료·재접속·앱 재시작 후 이전 발화를 자동 재생하지 않는다. suspend 후 새 session을 만든다.
- 기존 MVP의 `nunti-default-v1`은 현재 비교 기준이다. 새 캐릭터별 검수한 voice binding을 선택하고 캐릭터 내부에서는 화자를 보존한다. 논리 감정 hint를 SDK emotion/rate/pitch 지원이나 실제 음색 변화로 주장하지 않는다.
- CarUx listener는 실제 host에서 하나를 공유한다. 포커스 성공을 차량 정책 허가로 취급하지 않는다.
- `reference-ko.wav`는 macOS Yuna 참고다. 실제 Pleos 증거는 runtime WAV다. 41ms/73ms callback을 가청 지연으로 보고하지 않는다.

첫 작업으로 JDK21과 Python을 확인하고 `python3 scripts/verify_handoff.py`를 실행한다. 이어 `python3 android/feature/tts/scripts/verify.py --bootstrap --android`를 실행해 JVM 62+연동8 및 실제 바이너리 컴파일을 재현한다. 공통 Android 빌드는 Gradle Kotlin2.2.21이고 이 스크립트는 별도 SHA256 lock의 Kotlin2.2.20을 사용한다.

PM과 SDK·Pleos2.1.0/API34를 복원한 뒤 실제 주차 재생·중지·background·중복 억제를 재검사한다. 실제 D 전환은 Virtual Console inactive 문제를 해결한 환경에서만 검증한다. 인간 청취 음질·첫 음절·선행 묵음·가청 지연, 통화/내비 경합, 감정 음향 제어, HYBRID/SERVER·실차·장시간 검증은 남은 작업으로 관리한다. 감정 TTS 공급자를 임의 도입하지 않는다.

첫 보고에는 HEAD, 복원·검사 결과, 실행하지 못한 항목, 남은 차단사항과 다음 작업을 적는다. 새 증거와 과거 기록을 구분하고 기능 변경은 담당 범위와 PM 우선순위에 맞춰 진행한다.
