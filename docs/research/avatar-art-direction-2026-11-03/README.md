# 눈티 일러스트·소장 매력·경로 탄생 효과 조사

2026-11-03, Asia/Seoul. 사용자의 핵심 지적은 **완성 눈티를 갖고 싶지 않고, 경로·목적지에서 태어났다는 관계가 외형과 과정에 보이지 않는다**는 것이다. 이번에는 구현 범위를 늘리기보다 이 두 문제를 해결할 근거와 다음 비교 방법을 정리했다.

전체 제품 목표는 운전습관 개선을 돕는 아바타 눈티다. 사용자 담당인 목적지·경로 기반 생성에서, 개인화된 외형과 애착을 가질 이유를 만들어야 한다. 기능·파일·재생 검사가 통과한 것과 사람이 갖고 싶어 하는 디자인이 나온 것은 별도다. 이번 조사는 새 원화나 효과를 승인한 결과가 아니다.

## 현재 문제가 생긴 구조

| 실제 소스에서 확인한 내용 | 디자인에 미치는 영향에 대한 판단 |
|---|---|
| [illustration.py](../../../backend/nunti/avatar_studio/illustration.py)의 `_make_design()`은 입력 전체를 해시한 난수로 petal·pebble·sprout와 비율을 선택한다. 목적지 이름을 장소의 조형으로 해석하는 단계는 없다. | 입력이 달라 새 모습이 나오는 것과 의미 있게 그 장소를 닮는 것은 다르다. 큰 몸체의 결정에 경로·장소의 시각적 근거가 약하다. |
| 명시된 특성·목적의 일부 단어가 네 재료 계열과 작은 장식에 연결된다. 원본 경로는 몸 안의 금빛 실로 보존된다. | 연관 근거가 작은 무늬와 소품에 몰려 있다. 소품이나 설명을 가리면 목적지와 여정을 알아보기 어려울 수 있다. 사용자의 지적과 맞는 실패 가설이다. |
| [studio.js](../../../prototypes/avatar_generator/studio.js)의 `birthAnimation()`은 원본 점을 PNG 내부 실 위치로 옮기고, 두꺼워지는 마스크로 완성 PNG를 공개한다. | 같은 선의 위치는 연결되지만 몸의 윤곽·부피·귀·작은 발이 만들어지는 원인은 제한적으로 표현된다. 다음 변화는 실제 외곽이나 mesh의 변형을 비교해야 한다. |
| [image_api.py](../../../backend/nunti/avatar_studio/image_api.py)는 현재 로컬 원화와 경로 그림을 함께 참조로 보낸다. 실제 생성 품질은 아직 시험하지 않았다. | 기존의 약한 구조를 그대로 참조로 고정하면 반복될 가능성도 시험해야 한다. 이 API가 실제로 얼마나 구조를 바꾸는지는 아직 단정할 수 없다. |

위 표의 왼쪽은 구현 사실이고 오른쪽은 사용자 피드백과 소스를 종합한 디자인 판단이다. 현재 앱의 랜덤 변화를 경로 기반 의미 생성의 품질 증거로 사용하지 않는다.

## 조사 자료

| 문서 | 다룬 범위 |
|---|---|
| [소장하고 싶은 캐릭터](collectible-design.md) | 원논문 5종, Pixar·Disney·Riot 원제작 자료, 형태·재질·실루엣·애착의 근거와 한계 |
| [이미지 생성·API·로컬 모델](image-generation.md) | OpenAI·Google·BFL·Recraft·Adobe, Qwen·FLUX 공개 가중치, 구조와 스타일 제어, alpha·가격·라이선스·미확인 항목 |
| [경로가 몸이 되는 모션](formation-motion.md) | 실제 윤곽 변형·부위 접힘·체적 응결, Rive·Lottie·GSAP·Adobe·Three.js, 대응점과 runtime 조건 |
| [눈티용 프롬프트 초안](PROMPT-PACK.md) | 입력 자산 구분, 아트 디렉터·이미지 생성·모션 저작 지침, 비교할 세 조형 가설과 사람 평가 |

각 문서는 발행자 공식 문서·원저자 저장소·원논문에 링크한다. 프롬프트 모음의 인기 순위나 검증되지 않은 성공률은 추천 근거로 쓰지 않았다. 공개 자료 전체를 읽었다는 주장보다, 이번 문제를 해결하는 범위와 확인하지 못한 조건을 문서마다 구분했다.

## 적용할 스킬과 그 역할

| 스킬·워크플로우 | 다음 작업에서 적용할 부분 | 현재 확인한 상태 |
|---|---|---|
| [OpenAI imagegen](https://github.com/openai/skills/blob/main/skills/.system/imagegen/SKILL.md)와 [prompting.md](https://github.com/openai/skills/blob/main/skills/.system/imagegen/references/prompting.md) | 구조·스타일·편집 대상을 구분하고 보존 조건을 명시. 한 번에 한 문제를 고치며 시안을 비교 | 공식 파일과 개별 Apache-2.0 확인. 로컬에도 제공된 스킬. 이번엔 지침을 프롬프트 초안에 반영했고 생성하지 않음 |
| [Anthropic canvas-design](https://github.com/anthropics/skills/blob/main/skills/canvas-design/SKILL.md) | 형태·재질·색·구성을 일관된 아트 방향과 정지 비교 보드로 정리 | 공식 파일과 개별 Apache-2.0 확인. 캐릭터 생성 전용 스킬은 아니며, 주제의 미묘한 암시를 강조하는 지침보다 이번의 경로 연관성 요구를 우선 |
| [LottieFiles motion-design](https://github.com/LottieFiles/motion-design-skill/blob/main/skills/motion-design/SKILL.md) | 주인공이 되는 움직임, 예비 동작·타이밍·easing·뒤따르는 동작을 스토리보드에 적용 | 공식 파일·MIT 확인. 생성 모델이나 편집 도구와 구분. 설치하지 않음 |
| [Rive rive skill](https://github.com/rive-app/skills/blob/main/skills/rive/SKILL.md) | 원화 선정 뒤 벡터·mesh·bone·state machine을 저작하고 runtime에서 재생 | 공식 파일·MIT 확인. CLI/Editor·runtime 문서로 연결하는 짧은 지침. 임의 PNG 자동 rig를 보장하지 않음 |
| [Anthropic frontend-design](https://github.com/anthropics/skills/blob/main/skills/frontend-design/SKILL.md) | 승인된 일러스트가 돋보이는 화면의 배치·시각적 위계 | 실제 공식 파일 확인. 이번 핵심인 캐릭터 조형을 대신하지 않으므로 후속 UI 보조로 둠 |
| 현재 제공된 Superdesign | 재질·실루엣·레이아웃 시안을 같은 보드에서 비교할 때 사용 | 이 세션에서 제공된 스킬. 연결·생성은 실행하지 않음. 이미지 모델·소장 매력 평가와 역할을 구분 |

외부 스킬은 이번에 자동 설치하지 않았다. 실제 설치할 때는 검토한 commit과 개별 라이선스를 고정한다. 스킬의 라이선스와 참조 이미지·모델 가중치·호스팅 API·편집 도구의 사용권은 각각 확인한다.

## 이미지 생성에서 먼저 비교할 후보

실측한 품질 순위가 아니라 공식 기능을 기준으로 정한 실험 우선순위다. 최종 공급자 선택은 같은 입력의 채택 품질과 총비용으로 한다.

| 순서 | 후보 | 먼저 비교할 이유 | 남은 확인 |
|---|---|---|---|
| 정밀 원화·편집 | OpenAI `gpt-image-2.5-sunburst` | 주석·참조·정밀 편집과 네이티브 투명 출력을 함께 평가 가능. [공식 모델](https://developers.openai.com/api/docs/models/gpt-image-2.5-sunburst) | 계정 접근·경로 반영·실루엣 다양성·한국 사용자 취향·채택당 비용 |
| 가성비 비교 | Google `gemini-nano-banana-2.1` | 다중 참조·캐릭터 일관성·빠른 이미지 편집을 비교. [공식 모델](https://aistudio.google.com/docs/models/gemini-nano-banana-2.1) | 네이티브 alpha는 확인하지 못함. 반투명 가장자리의 컷아웃 품질과 추가 공정 포함 |
| 구조 제어 실험 | SDXL ControlNet Canny + IP-Adapter SDXL | 경로에서 만든 구조 지도와 스타일 참조를 서로 다른 조건으로 제어하는 방식을 시험. [ControlNet 카드](https://huggingface.co/diffusers/controlnet-canny-sdxl-1.0), [IP-Adapter](https://github.com/tencent-ailab/IP-Adapter) | 호환 모델·가중치 허가·우리 Mac의 메모리/속도·API 대비 품질 모두 실측 전 |

FLUX 3, Qwen, Recraft, Adobe도 [비교표](image-generation.md)에 남겼다. Recraft V4 Styles의 image-to-image 미지원, Qwen 최신 모델의 연구용 라이선스, Adobe API 세대별 제어 차이처럼 실제 채택에 영향을 주는 조건을 확인했다. 상용 API만 가능하다는 결론은 아니다. 로컬 추론도 설치·하드웨어·시간 비용과 결과 품질을 함께 비교해야 한다.

## 단계적으로 개선할 순서

1. **입력의 의미와 형태를 분리한다.** 경로의 대표 굴곡, 확인된 목적지 소재, 방문 목적을 각각 구조·재질·자세의 근거로 만든다. 원본 경로와 창작된 형상을 따로 보관한다.
2. **한 여정으로 정지원화 세 안을 비교한다.** 길에서 자란 생명체, 목적지의 작은 정령, 살아 있는 여정 테라리움이 [첫 비교 가설](PROMPT-PACK.md)이다. 색만 다르게 만들지 않고 큰 실루엣과 구성부터 달리한다. 세 안은 고정 카탈로그가 아니다.
3. **갖고 싶은 외형과 연관성을 함께 고른다.** 설명을 가린 상태에서 원본 경로의 굴곡을 짚어 보고, 목적지 인상·귀여움·보관 의향을 따로 평가한다. 선정 뒤 서로 다른 여정으로 확장해 일반화 여부를 본다.
4. **선정 외형의 탄생 과정만 비교한다.** 실제 윤곽이 부푸는 안과 신체 부위로 접히는 안을 같은 최종 외형으로 비교한다. 대응점과 중간 자세를 준비한 뒤 물성·빛·입자를 더한다.
5. **선정안만 앱으로 옮긴다.** 새 여정 다양성·동일 요청 재사용·복원 identity·차량 표시 게이트를 유지하며 성능을 측정한다. 음색과 감정 피드백은 선정된 캐릭터 성격에 맞춰 이어서 검증한다.

첫 판단은 **예쁜 효과가 생겼는가**보다 **설명 없이도 이 여정에서 태어난 캐릭터로 읽히고, 실제로 보관하고 싶은가**다. 이미지 모델의 자체 평점·서로 다른 SHA·성공한 geometry 검사는 사람의 그 판단을 대신하지 못한다. 운전습관 개선 효과도 별도 제품 검증으로 유지한다.

이번에 완료한 것은 인터넷 조사·현재 소스의 원인 검토·스킬과 API 비교·눈티용 프롬프트 및 실험 계획이다. 새 그림·모션 시안 생성, 모델 설치, 앱 변경, 유료 호출, 녹화·음성 녹음은 하지 않았다.
