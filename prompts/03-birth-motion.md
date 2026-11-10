# Codex prompt 03 — Nunti transformation

$nunti-birth-motion

기본 눈티가 경로·목적지·사용자가 선택한 기분에 따라 변신하는 4.3초 정도의 단발성 효과를 설계해줘. 정차·출발 전 또는 도착 후 화면에서 승인된 기본 눈티가 처음부터 보이고, 같은 눈티의 허용된 장식·강조 색·표정이 순차적으로 바뀌어 정지 상태로 마무리돼야 해. 몸과 얼굴은 모든 프레임에서 식별 가능해야 해. 기본 눈티가 사라진 뒤 다른 캐릭터가 나타나는 방식이나 효과로 몸과 얼굴을 완전히 가리는 방식은 사용하지 마.

실행할 작업:
- Figma Motion → Lottie/dotLottie → Android Compose, Rive 상태머신, Compose Canvas 세 방식을 유지보수·비용·파일 크기·성능·구현 난이도로 비교
- 기존 Pleos Kotlin 코드를 확인하고 최소 변경 경로 선정
- 디자인 계약 v0.2의 변경 가능 요소와 불변 요소를 적용하고, 최소 두 가지 시안을 제시한 뒤 선택된 방향으로 진행
- 화면별 storyboard 타임라인, easing, anchor positions, layers, 실패/skip/reduced motion 설계
- Figma 연동이 가능하다면 기존 파일을 먼저 분석하고 별도 브랜치/프레임에서 편집 가능한 연출 시안 작성
- 주행 제한이 시작되면 즉시 허용된 정적 최종 눈티로 전환하고, 준비되지 않았다면 기본 눈티로 대체; 주행 제한 중 장식 애니메이션은 절대 재생하지 않기
- 에뮬레이터와 Virtual Console 테스트 계획 세우기

사전에 만들어 둔 표정/원화가 없으면 asset manifest 및 placeholder 사용 조건을 먼저 제시하고, 완성됐다고 보고하지 마.
