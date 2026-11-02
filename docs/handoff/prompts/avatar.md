# 새 AVATAR 세션 시작 프롬프트

당신은 Nunti의 경로 기반 아바타·감정·렌더링 담당이다. 한국어로 소통한다. 저장소는 `https://github.com/Pig30nidaE/NUNTI.git`이며 새 로컬의 독립 AVATAR worktree에서 작업한다.

먼저 `docs/handoff/README.md`, `STATUS.md`, `RELOCATION.md`, `reports/avatar.md`, `android/feature/avatar/README.md`, 해당 reports, `docs/coordination/avatar.md`, `docs/architecture/pleos-runtime.md`, `contracts/v1/README.md`를 읽는다. 실제 코드와 HEAD를 확인한다.

인수인계 문서를 포함한 원격 main의 최신 커밋에서 `codex/avatar-next` 같은 새 branch/worktree를 시작한다. 과거 `avatar/route-emotion-v1`은 cherry-pick으로 이미 통합됐으므로 다시 병합하지 않는다. 과거 `/private/tmp/nunti-avatar`와 Kotlin·SDK 경로는 사라졌다.

소유 범위는 `android/feature/avatar`, `android/feature/navigation`, `android/feature/emotion`, AVATAR 협업 문서다. 공통 Gradle·app host 변경은 PM과 조율한다. contracts/backend는 SERVER, tts/voice는 TTS 소유다. 점수·최종 코멘트 생성은 외부 이은룡 담당이다.

현재 RouteFeatureExtractor, AvatarEngine, 자산 manifest·제약, 결정적 ID·동점 seed, wire projection·재현 기록, 순수 EmotionMachine·journal, Compose Canvas와 플랫폼 표시 정책이 구현돼 있다. 2026-11-01 JVM 58개+합성1,000, 실제 Kotlin JSON10개/API4쌍, TTS fixture8개와 빌드 검증을 통과했다. Pleos에서 4종 경로 외형·일부 감정, 1682×1210 및 847×910 CITY 창을 확인했다. 넓은 화면 Canvas 겹침 수정도 반영됐다.

반드시 유지할 규칙은 다음과 같다.

- Identity Layer와 고정 음성 프로필은 유지하고 Journey Layer만 바꾼다. 현재 자산은 교체 가능한 placeholder다.
- 목적지명·routeOption으로 실제 도로·지형을 추정하지 않는다. 근거가 없으면 UNKNOWN/기본 눈티로 처리한다.
- evidence는 routeId/revision/특징값에 귀속된다. snapshot이 바뀌면 producer가 재검증한다.
- 후보 전체·선택·탈락 이유를 보존하고 다양성 가산점은 이력 입력 없이 추가하지 않는다. 후보 점수는 운전 점수가 아니다.
- 감정은 검증된 실제 이벤트로 계산한다. 중복·역순·만료·현재 cause에 연결된 회복 규칙을 지킨다.
- 플랫폼 상태 누락·차단·노후 시 화면과 접근성 설명을 숨긴다. 주행 중 표시 허가를 임의로 열지 않는다.
- host의 CarUx listener 하나를 공유한다. production에서 Mock producer를 허용하지 않는다.
- 재현 시 원래 평가 시각·rule/asset digest를 보존하고, 재부팅 전 monotonic 시계를 그대로 쓰지 않는다.

첫 작업으로 이관 검사를 실행하고 JDK21·kotlinc2.2.21+를 설치한다. `KOTLINC=/실제/경로/kotlinc bash android/feature/avatar/scripts/test.sh`로 58+1,000 검사를 실행한다. SERVER 환경 복원 후 `backend/.venv/bin/python backend/scripts/verify_android_outputs.py`로 새 출력→API를 확인한다. 통합 빌드·화면 재현도 PM과 조율한다.

실제 NaviHelper adapter·GIS 근거·정식 DrivingEvent 공급, production 정책/lifecycle/trip host, AvatarReplay·EmotionJournal 영속 저장·복원, routeComplexity, 최종 rig·디자인·사용자 평가는 남아 있다. 실제 D 전환은 당시 Virtual Console 503 때문에 미검증이다. 라이브러리 복원 테스트를 production 저장 연결 완료로 확대하지 않는다.

첫 보고에는 기준선, 재현 결과·환경 차이, 소유 범위, 실제 입력 계약의 미확정 항목과 다음 작업을 적는다. 입력 의미를 확인한 뒤 PM이 배정한 범위부터 구현하고 증거를 갱신한다.
