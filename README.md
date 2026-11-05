# 눈티 · Nunti

사용자 작업 선호: 사용자가 명시적으로 종료를 요청할 때만 관련 로컬 서버·AI 모델 프로세스·에뮬레이터·VSCode를 정상 종료한다. 작업이나 검증이 끝났다는 이유로 자동 종료하지 않는다. 미저장 편집을 강제로 폐기하지 않는다.

2026-11-04 최신은 [목적지·방문 이유별 눈티 v6](docs/design/avatar-v6/README.md)다. 의상·목적지 기념품·경로 탄생 효과·캐릭터별 로컬 TTS를 연결했다. 사용자 요청에 따라 실제 AI는 30개 상황을 검증했고, 빠른 일러스트와 실제 음원은 각각 200개를 유지했다. 재시도를 포함한 수량, 세부 소품 편차, 청취 미검증은 [결과 보고](docs/design/avatar-v6/RESULT.ko.md)에 구분했다. [직접 시험](docs/design/avatar-v6/TESTING.ko.md): `python3 scripts/run_avatar_generator.py --local-ai --navigation-api --restart-server`. 외부 키·유료 호출·녹화는 필요 없다. 아래 기기 TTS·새 음색 미구현 설명은 이전 시점의 기록이다.

2026-11-04 최신은 [사진 없는 내비 API 연결 결과](docs/design/navigation-integration/RESULT.ko.md)와 [직접 시험 안내](docs/design/navigation-integration/TESTING.ko.md)다. 실제 NaviHelper 목적지·위치·상태와 별도 OSRM 도로 경로를 연결했고, Android 3여정 생성·보관·복원 및 무료 로컬 AI 새 그림을 검증했다. 실행은 `python3 scripts/run_avatar_generator.py --local-ai --navigation-api --restart-server`다. 외부 API 키·유료 호출·녹화는 필요 없다. 현대 선택 경로와 OSRM 선의 일치, SDK의 GPS 이동 반영·재탐색 완료는 미검증이다. 아래 내비 미구현·사진 입력·v5/v4 상태는 각 시점의 이력이다.

2026-11-04 최신: 운전습관 개선을 돕는 눈티 안의 사용자 담당은 목적지·경로 기반 생성이며 [제품 기준](docs/product/2026-hmg-app-challenge.md)을 유지한다. 결과 표시와 보관함 갱신 사이에서 사진 업로드가 유실되는 버그를 [재현·수정](docs/design/avatar-quality-v5/PHOTO-UPLOAD-FIX.md)했다. 전체 7단계 직접 실행 완료: 경계15·Chrome15·Android15·저장AI14·실제Canvas7개35자세 통과. 추가AI추론·유료호출·녹화0. 이전 승인 검토 장애는 화면 검사에 대해 해소됐으며 아래 미실행 설명은 당시 기록이다. 정원 추가AI와 미적 최종승인은 별도다.

현재 개선은 [눈티 v5](docs/design/avatar-quality-v5/README.md)다. 운전습관 개선을 돕는 눈티 안에서 사용자 담당은 목적지·경로 기반 생성이며 [제품 기준](docs/product/2026-hmg-app-challenge.md)을 유지한다. 경로는 실루엣에 반영하고 몸의 지도 선·띠를 제거했다. 오로라 고리·별가루 탄생 효과와 새 일러스트를 적용했다. 실제 무료 AI 해변 생성 44.56초·backend246+하위10·기존6그림 Canvas30자세를 확인했다. 최신 Android 화면 회귀와 추가 정원 생성은 자동 승인 검토 인프라 오류로 미실행이다. 아래 v4·v3 설명은 이력이다.

**눈티(Nunti)는 운전습관 개선을 도와주는 아바타 동반자다.** 사용자 담당은 그 안의 **목적지·내비게이션 경로 기반 아바타 생성 기능**이다. 생성한 눈티의 정체성과 외형·음색은 주행 이벤트에 따른 감정·음성 피드백 모듈에서 이어서 사용한다. 2026 현대자동차그룹 차량용 앱 개발 공모전에 맞춘 [제품 목표·담당 범위·공식 기준](docs/product/2026-hmg-app-challenge.md)을 먼저 읽는다.

현재 작업은 [원화·형상·탄생 효과 v4](docs/design/avatar-quality-v4/README.md)다. 최신 사용자 기준은 **불투명 파스텔 색면과 얕은 매트 2.5D 표현**이다. 경로 기하와 목적지 특성에서 몸체를 계획하며 실제 외곽이 경로에서 자라는 모션을 적용한다. 무료 로컬 FLUX.2-klein 실험과 앱 연결 결과는 v4 보고를 따른다. 수정 원화의 표현 승인과 생성 결과 전체의 품질 승인을 구분한다. 유료 API 실행은 원화 선택 후 결정하기로 보류했다.

기본 실행은 `python3 scripts/run_avatar_generator.py`, 준비된 Mac의 무료 로컬 AI 연결은 `python3 scripts/run_avatar_generator.py --local-ai --restart-server`다. [직접 시험 안내](docs/design/avatar-generator/TESTING.ko.md)를 따른다. 경로 사진·좌표 입력과 확인, 생성·보관·복원은 [v3 기반](docs/design/avatar-generator/README.md)을 유지한다. 음성은 기기의 기존 한국어 화자 설정이며 실제 NaviHelper·새 음색·배포는 별도다.

이전 [생성 동반자 v2](docs/design/generative-mvp/README.md)는 API 공급자 어댑터·불변 캐릭터 저장·동일 음색의 후속 대사·투명 PNG 2.5D 표시를 연결한 실험 기록이다. 기존 소장품과 실행법은 보존한다.

이전 절차적 생성 흐름은 [목적지·경로에서 동반자가 태어나는 시험본](docs/design/route-birth/test-report.md)에 보존한다. 직접 입력한 경로에서 새72점 외형과 로컬 Sohee 음성을 생성했던 기록이다. 새5여정·15새WAV는 당시 검증 표본이며 선택지나 생성 상한이 아니다. 아래8개 목록 방식과 2026-11-02 구현 설명도 해당 시점의 기록이다.

경로 특징에 따라 외형이 달라지고 주행 이벤트에 반응하는 가상 동승자 MVP다.
차량의 실시간 반응은 앱 내부에서 처리하고 서버는 동의받은 기록을 비동기로 저장한다.

새 로컬에서 작업을 이어갈 때는 [세션 인수인계](docs/handoff/README.md)의 현재 상태·복원 절차와 PM/TTS/AVATAR/SERVER 프롬프트를 먼저 확인한다.

2026-11-02 최신 제품 방향은 목적지·경로·방문 목적에서 매 여행 새로 태어나는 수집형 2.5D 동반자다. 사용자는 C · 반투명 기념 오브젝트를 선택했다. [통합 설계와 시안](docs/design/journey-characters/README.md), [실행 가능한 레시피 실험](prototypes/journey_characters/README.md)을 작성했으며, 실제 로컬 TTS 합성 도구와 Android Debug 파일 재생까지 구현했다. [v2 음성 청취](prototypes/journey_voice/listen-v2.html), [시험 방법·검증·남은 일](docs/design/journey-characters/tts-result.md)을 참고한다. 매 여행 자동 모델 호출·새 2.5D renderer·컬렉션 연결은 남아 있다.

| 영역 | 코드와 실행 가이드 |
| --- | --- |
| 서버 API · SQLite · 동기화 Mock | [backend/README.md](backend/README.md) |
| 공통 JSON Schema · OpenAPI | [contracts/v1/README.md](contracts/v1/README.md) |
| 경로 · 아바타 · 감정 · Compose | [android/feature/avatar/README.md](android/feature/avatar/README.md) |
| 음성 정책 · 큐 · 프로필 | [android/feature/tts/README.md](android/feature/tts/README.md) |
| Pleos 음성 adapter | [android/feature/voice/README.md](android/feature/voice/README.md) |
| 모듈 연결 · 장애 처리 | [docs/architecture/integration.md](docs/architecture/integration.md) |
| 실제 검증 범위 | [docs/architecture/validation.md](docs/architecture/validation.md) |

서버는 Python 3.12 이상에서 `cd backend && uv sync --frozen`으로 준비한다.
토큰·동의 설정 및 실행 명령은 서버 가이드에 있다. 기본 동기화는 비활성화되어 있다.

Android 앱은 합성 경로로 동작하는 Mock 뷰어다. 실제 차량 정책 연결 전 AAOS 표시를 차단하며
기본 앱에서 실제 음성을 재생하지 않는다. Android 모듈 빌드와 실제 차량에서의 동작 검증은 구분한다.
실차 신호 수신, 이은룡 담당 점수·최종 코멘트 모듈, 실제 TTS 음질은 별도 검증이 필요하다.

통합 Debug APK 빌드와 Lint는 루트 저장소에서 통과했다. 로컬 산출물은
`android/build/app/outputs/apk/debug/app-debug.apk`이며 Git에는 포함하지 않는다.
합성 시연은 [아바타 데모](android/feature/avatar/demo/index.html)에서 확인할 수 있다.

공통 v1.0 계약은 조율 중인 초안이다. 운전 점수 가중치·임계값 및 SDK 데이터 가용성을
확정하지 않았으며 원본 `눈티-주행습관-정리.html`의 논의 초안은 그대로 보존했다.

AVATAR의 JVM 테스트를 실행한 후, 새 Kotlin 출력과 서버의 연결을 다음으로 검증할 수 있다.

```sh
backend/.venv/bin/python backend/scripts/verify_android_outputs.py
```

이 검사는 JSON Schema/Pydantic 형식 검사와 실제 서버 API 저장·조회까지 수행한다.
실제 차량 SDK 호출이나 음성 재생은 수행하지 않는다.
