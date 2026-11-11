# Nunti Game VFX — 기존 앱 보존형 제작 키트

작성일: 2026-11-10. 눈티의 기존 기능·스킨·서버·Pleos UI는 유지하고, **변신 이펙트의 전문적인 품질**만 높이기 위한 Codex 키트입니다.

## 가장 중요한 점
- 이 ZIP에는 **실제 Effekseer 유료/무료 원본 이펙트 파일은 동봉하지 않습니다.** 외부 라이선스가 있는 에셋은 공식 원본에서 직접 다운로드합니다.
- 이 ZIP은 작업을 실행하기 위한 **Codex 스킬, 명확한 단계별 프롬프트, 검증된 공식 레퍼런스, 에셋 검사 유틸리티**입니다. 설치와 이미지 에셋 생성/앱 통합은 사용자의 Mac에서 Codex가 수행해야 합니다.
- AI는 기존 작업물의 재개발자가 아니라 **VFX 기술감독/게임 이펙트 디자이너**로 동작합니다. 기존에 만든 애니메이션은 재사용합니다.
- 목표 결과는 **바다/도시/산악이 단순 색 바꾸기가 아닌 별도 변신 경험**인 것입니다.

## 설치

1. ZIP 압축을 풀고 **압축 안의 `.agents`, `prompts`, `tools`, `examples`, `AGENTS.nunti-game-vfx.append.md`를 눈티 Git 저장소의 루트에 복사**합니다. 이미 설치한 `.agents/skills/nunti-*`와 기존 `AGENTS.md`는 삭제하지 않습니다.
2. 더 간단하게는 ZIP을 눈티 저장소 안에 놓고 현재 Codex에게 다음과 같이 지시합니다.

```text
nunti-vfx-production-kit-2026-11-10.zip을 현재 Git 저장소에 설치해줘.
기존 .agents/skills/nunti-* 및 AGENTS.md를 삭제하거나 덮어쓰지 마.
이 키트의 파일만 안전하게 병합하고, AGENTS.nunti-game-vfx.append.md는
충돌 없는 필요한 규칙만 기존 AGENTS.md에 합쳐줘.
기존 앱/서버 파일은 설치 단계에서 수정하지 말고, Git 변경 내역을 알려줘.
```

3. 설치 후 Codex 새 세션에서 `$nunti-game-vfx`가 인식되는지 확인하고 `prompts/00_MASTER.md`를 실행합니다. 자동 인식되지 않으면 `SKILL.md`를 명시적으로 읽고 따라야 합니다.
4. **Effekseer 에디터는 필요해진 경우에만 설치합니다.** 공식 [Mac arm64/x64 v1.80.8 다운로드](https://effekseer.github.io/en/download.html). Codex가 공식 URL에서 올바른 아키텍처를 선택하도록 합니다. Effekseer GUI의 녹화 기능을 CLI 변환 기능과 혼동하지 마세요.
5. Python 에셋 검사기 도구는 Pillow만 필요합니다. Codex가 사용 시 `python3 -m pip install Pillow`를 기존 가상환경 또는 별도 venv에 설치하면 됩니다.

## 실행 순서

| 단계 | 프롬프트 | 결과물 |
|---|---|---|
| 0 | `prompts/00_MASTER.md` | 기존 파이프라인 파악 및 곧바로 후보 수집 시작 |
| 1 | `prompts/01_SELECT_REAL_ASSETS.md` | 실제 무료/허용 이펙트 2~3종, 출처 기록, 비주얼 샘플 |
| 2 | `prompts/02_OCEAN_PRODUCTION.md` | **바다 눈티 변신**에 전문 VFX 한 세트를 통합 |
| 3 | `prompts/03_CITY_FOREST_EXPAND.md` | 전혀 다른 형태의 도시·산악 효과 |
| 4 | `prompts/04_FINISH.md` | 기존 화면에 자연스럽게 합성, 취소·주행 제한 유지 |

권장: `00_MASTER.md`를 먼저 한 번 실행해 전 과정을 맡깁니다. 단계별 품질을 직접 보고 싶은 경우 01~04를 차례로 실행하면 됩니다.

## 핵심 공식 출처

- [Effekseer 다운로드](https://effekseer.github.io/en/download.html): Mac arm64/x64 1.80.8
- [Effekseer 공개 샘플](https://effekseer.github.io/en/contribute.html): CC0 섹션과 Old License 섹션을 구분
- [MAGICAL X SPIRAL](https://effekseer.github.io/en/contributes/MAGICALxSPIRAL/index.html): 103종
- [Effekseer Recorder](https://effekseer.github.io/Help_Tool/en/ToolReference/record.html): Sprite Sheet / Export Images / Blend+Add Alpha
- [Kenney Particle Pack](https://kenney.nl/assets/particle-pack): CC0 80개 파티클 텍스처
- [Lottie Compose](https://github.com/airbnb/lottie/blob/master/android-compose.md): 기존 앱이 Lottie면 추가 재생 도구로 활용
- [Pleos 디자인 안전 지침](https://document.pleos.ai/docs/pleos-only/vehicle-app-planning-guide/driver-distraction-guideline): 주행 시 장식적 모션 제한

자세한 내용: `.agents/skills/nunti-game-vfx/references/`.

## 단 한 가지 수동 예외

Codex에 실제 데스크톱 GUI 조작 도구가 연결되지 않은 경우, Effekseer GUI의 녹화/내보내기를 완전 자동 실행하지 못할 수 있습니다. 이 경우 **없는 결과를 만든 척하지 말고**, 라이선스가 명확하고 이미 투명 프레임으로 제공되는 VFX 에셋을 찾아 기존 앱에 삽입하는 대체 경로로 진행해야 합니다. 이마저 어려운 경우에만 필요한 한 번의 GUI 조작을 특정해 알려주세요.

## 안전 및 비용

공식 CC0 에셋 우선, 유료 구매 전 승인, AI API 호출은 필요할 때만. Rive 무료 스플래시가 없는 경로. 주행 중 화려한 애니메이션 재생 금지. 필요 이상의 문서·영상 제작 금지.
