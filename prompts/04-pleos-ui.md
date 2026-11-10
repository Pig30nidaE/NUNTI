# Codex prompt 04 — Actual Pleos app UI

$nunti-pleos-ui

현재 Kotlin/Compose 차량용 앱의 화면 구조를 읽고, 제공한 Figma 파일 URL(여기에 삽입)과 공식 Pleos 디자인 에셋을 기반으로 UI 개선안을 설계해줘. 기존 Vehicle/NaviHelper/TTS/STT 연동을 깨뜨리지 말고, React 기반 시안을 그대로 앱 코드로 복사하지 말 것.

화면 상태는 4가지: PRE_TRIP(경로 및 기분 선택), REVEAL_PARKED(같은 기본 눈티의 변신 연출), DRIVING_RESTRICTED(정적 캐릭터+짧은 텍스트·음성), POST_TRIP(여정의 기억과 수집 카드). 상태 이름은 예시이며 기존 구현이나 API 이름을 변경하라는 뜻이 아니다.

Figma에는 실제 편집 가능한 프레임, 오토레이아웃, 색/폰트 변수, 컴포넌트를 사용하고, 여러 창 모드 및 주야간 대비를 확인해줘. 공식 디자인 가이드의 주행 안전, 가독성, 터치 규격을 준수하고, UI 스크린샷과 Pleos 에뮬레이터를 비교 검증해줘.

결과물: 페이지 구조, 화면 스크린샷, 디자인 토큰, Code → Figma 매핑, 코드 수정 내역, 빌드/검증 내역, 미완료 항목.
