# NUNTI Visual Skills Starter Kit

눈티(Nunti) 프로젝트용 Codex Skills · 프롬프트 · 디자인 계약서.

## 먼저 해야 할 일

1. [Figma 공식 Codex 플러그인](https://help.figma.com/hc/en-us/articles/39888629089175-Codex-and-Figma-Set-up-the-MCP-server)을 Codex/ChatGPT 데스크톱앱에 설치하고 Figma Education 계정을 연결합니다. 가능하면 **Remote MCP**를 사용합니다.
2. [Pleos Connect 디자인 에셋(.fig)](https://document.pleos.ai/img/Pleos_Connect_design_assets_215.fig)과 [디스플레이 가이드(.fig)](https://document.pleos.ai/img/Pleos_Connect_display_guide_215.fig)를 Figma에 Import 합니다.
3. 압축파일의 `.agents/skills/nunti-*` 폴더들을 현재 눈티 **Git 저장소**의 `.agents/skills/`로 복사합니다. `docs/`, `prompts/`, `examples/` 파일도 기존 동명 파일을 덮어쓰지 않도록 검토한 후 프로젝트에 복사합니다. 이 ZIP은 스킬을 알아서 설치하지 않습니다. 사용자 컴퓨터에서 복사해야 합니다.
4. `AGENTS.nunti.append.md`를 읽고 **기존** 저장소 `AGENTS.md` 내용과 병합합니다. 기존 파일을 덮어쓰지 마세요.
5. Codex 대화에서 `$nunti-identity`, `$nunti-route-variants`, `$nunti-birth-motion`, `$nunti-pleos-ui` 중 하나를 명시 호출하거나 자연어로 작업을 요청합니다.
6. 먼저 `prompts/01-visual-direction.md`를 실행하고, 확정된 원화가 있을 때 `prompts/02-route-variants.md` → `prompts/03-birth-motion.md` → `prompts/04-pleos-ui.md`를 실행합니다.

참고: OpenAI 공식 문서에 따르면 Codex는 현재 작업 디렉터리에서 상위 저장소 루트까지 `.agents/skills`를 찾아 로드합니다. `SKILL.md`가 인식되지 않으면 앱을 재시작합니다.

## 파일 안내

- `AGENTS.nunti.append.md` : Nunti 공통 디자인/안전 규칙
- `docs/NUNTI_DESIGN_CONTRACT.md` : 단일 소스의 캐릭터·경로·모션 데이터 계약
- `docs/REFERENCE_LINKS.md` : 검증된 공식 문서 링크와 적용 포인트
- `.agents/skills/.../SKILL.md` : 4가지 전용 워크플로
- `prompts/` : 각 단계에서 바로 복사해 실행할 프롬프트
- `examples/` : 입력·출력 예시. SDK에 모든 필드가 실제 제공된다는 뜻이 아님

## 권장 실행 순서

`원화/비주얼 규칙 → 경로 데이터 매핑 → 기존 눈티의 변신 효과 → Figma UI → Kotlin/Compose 구현 → Pleos Emulator + Virtual Console 검증`

## 안전·운영 원칙

- 플랫폼 제한이 허용하는 정차·출발 전 또는 도착 후에만 장식적 변신 애니메이션을 실행합니다. 변신 전·중·후에 같은 눈티가 식별되어야 합니다.
- 주행 상태에서는 애니메이션 및 주의를 끄는 반복 움직임을 차단합니다. 실제 적용 조건은 Pleos 및 `CarUxRestrictions`와 앱 심사 정책으로 검증합니다.
- 운전 중에는 운전자의 감정을 임의로 추정하지 말고, 명시적 선택 값이나 안전 운전 이벤트를 각각 구분해 사용합니다.
- 생성형 AI에 차량 위치/경로 데이터나 API 키를 무조건 전송하지 않습니다. 개인 식별 가능 정보는 제거하고 로컬 샘플을 우선합니다.
- 디자인 확정 전에는 새 API 요금을 쓰기보다 보유한 ChatGPT/Gemini 구독과 Figma Education으로 시안을 탐색합니다.
- AI가 생성한 이미지는 바로 벡터·스켈레톤 리깅 파일이 되는 것이 아닙니다. 레이어 분리/정리/리깅 단계가 필요할 수 있습니다.

## 공식 근거

- [Codex Skills](https://learn.chatgpt.com/docs/build-skills)
- [Figma MCP 설치](https://help.figma.com/hc/en-us/articles/39888629089175-Codex-and-Figma-Set-up-the-MCP-server)
- [Figma Motion](https://help.figma.com/hc/en-us/articles/41307983648407-Export-animations-from-Figma)
- [Pleos UI](https://document.pleos.ai/docs/connect/guide/docs-design/Introduction/intro)
- [Pleos 주행 안전](https://document.pleos.ai/en/docs/pleos-only/vehicle-app-planning-guide/driver-distraction-guideline)
