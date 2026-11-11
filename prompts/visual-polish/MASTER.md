# NUNTI Visual Polish — MAIN EXECUTION PROMPT

> 설치 메모: 아래 API 크레딧·사용 허용 문구는 키트에 포함된 주장입니다. 사용자 승인으로 간주하지 않습니다. `docs/redesign/SKIN_SYSTEM_V2.md`의 모의 모드와 실제 생성 API 승인 조건을 우선합니다. 시안 비교와 선택 전에는 생산 자산에 반영하지 않습니다.

현재 구현되어 있는 눈티 프로젝트의 캐릭터와 변신 효과를 예쁘게 완성해줘. 새 앱, 새 아키텍처, 새 서버를 만들지 마라.

먼저 `$nunti-visual-polish`, `$nunti-identity`, `$nunti-route-variants`, `$nunti-birth-motion`, `$nunti-pleos-ui`를 로드하고 `docs/NUNTI_VISUAL_POLISH_OVERRIDE.md`와 `references/ART_AND_MOTION_REFERENCES.md`를 읽어라. (pstack `principle-experience-first` 등의 스킬이 설치되어 있으면 적극 활용하고, 없으면 동일한 원칙을 적용한다.)

작업을 아래 순서로, 실제 결과물을 제작하며 진행해라:
1. `prompts/visual-polish/00-PREFLIGHT.md` : 기존 코드·원화 찾기 및 이전 스킬 충돌 지침 최소 수정.
2. `prompts/visual-polish/01-CHARACTER-AND-SKINS.md` : 귀엽고 소유욕을 유발하는 3D 토이 눈티 원형을 유지하면서 바다·도시·산악 게임 스킨 3종을 GPT Image 2.6 Flare/Sunburst로 실제 생성해 기존 렌더링 리소스와 프롬프트에 반영.
3. `prompts/visual-polish/02-TRANSFORM-FX.md` : 현재 생성 화면에 기본 눈티 → 빛 리본·입자 → 의상·머리장식 장착 → 반짝임·귀여운 바운스 → 완성된 스킨으로 이어지는 4초 내외 게임형 변신 애니메이션을 구현.
4. `prompts/visual-polish/03-UI-POLISH.md` : 기존 UI의 레이아웃/기능을 지키면서 캐릭터 무대와 결과 카드만 더 고급스럽고 귀엽게 다듬기.
5. `prompts/visual-polish/04-INTEGRATE.md` : 실제 앱에 반영하고 짧은 시각적 확인 후 완료.

우선순위: 매력적인 실제 캐릭터와 게임 같은 이펙트 > 도구 종류/설계 문서/녹화 영상/복잡한 검증.

API: Skin V2의 검증과 명시적 승인 조건을 충족하기 전에는 실제 생성 API를 호출하지 않는다. 승인 후에도 키트에 기재된 모델의 접근성과 가격을 확인하고 소량으로 진행한다. 비밀 키를 채팅에 요청하지 않는다. Gemini Pro 구독을 별도 Gemini API 크레딧으로 착각하지 마라.

중간 보고를 최소화하고 디자인 결과를 보여줘. 다만 원본 눈티의 얼굴이 크게 달라지는 선택, 추가 외부 서비스 결제, 대규모 구조 변경은 하기 전에 알려줘.
