# feature:score · 주행습관 점수 (이은룡)

구간(1분)별 평가 → 유효 시간/기회 수 가중 평균. 미수신 신호는 분모에서 제외(만점·0점 아님), 평가 가능한 영역만 35/35/20/10 배점으로 재정규화한다. 모든 임계값은 논의용 초안.

| 패키지 | 내용 |
| --- | --- |
| `ai.nunti.score` | `ScoreEngine`, `VehicleSample`, `DrivingEvent`, `Emotion`, 시연 `Scenarios` (순수 Kotlin) |
| `ai.nunti.score.live` | `PleosSignalSource`(Vehicle SDK), `NaviSignalSource`(NaviHelper), `RawSpeedProbe`(차속 직접 구독) |
| `ai.nunti.score.ui` | 시연·실시간 점수 화면 (Compose) |
| `ScoreActivity` | 런처 진입점 `눈티 점수`, `distractionOptimized` 선언 |

- 사용 신호·권한·에뮬레이터 한계: [score-signals-api.md](../../../docs/architecture/score-signals-api.md)
- 테스트: `./gradlew :feature:score:testDebugUnitTest` (JDK 21 필요)
- 아바타 연결 지점: `ScoreEngine.emotion(report, finished)` → `ai.nunti.score.Emotion`. AVATAR의 `ai.nunti.emotion` 패키지와 이름이 겹치니 한 파일에서 둘을 `*`로 가져오지 말 것.
- 차속은 공개 Vehicle SDK 2.3.2에 없어 서비스 직접 구독(비공식)을 쓴다. 기획서에 명시 필요.

## 눈티 아바타 (기준 캐릭터)

- 기준 시트: `docs/design/avatar-v6/assets/nunti-base-character.png` (후드·새싹 안테나·민트 스카프·파란 별 뱃지의 아기 눈티).
- 점수 화면의 감정 표시는 이모지 대신 이 시트의 컷을 쓴다 (`ui/NuntiFace.kt`, `res/drawable-nodpi/nunti_*.png`): 중립=눈 감은 컷, 걱정=놀란 컷, 안도=한숨 돌리는 웃음 컷, 기쁨=손 흔드는 서 있는 컷.
- 서버의 AI 아바타 생성은 같은 시트를 참조 이미지 2로 쓰고 프롬프트(`local-journey-character-8`)에서 "입는 주체는 항상 이 눈티"로 고정한다. 의상·소품·자세·목적지 가방만 여정에 따라 바뀐다. 실제 로컬 FLUX 생성은 이 환경에서 실행하지 않았다.
