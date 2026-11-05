# Nunti 이미지 생성·참조·구조 제어 조사

확인일: **2026-11-03**. 공식 API 문서, 모델 발행자의 모델 카드·라이선스, 원저자 저장소를 읽었다. 계정·키 조회, 추론 API 호출, 설치, 모델 다운로드, 앱·코드 변경, 녹화·녹음은 하지 않았다. 가격은 USD이며 세금·실패·재시도·선별 비용을 포함하지 않는다. **문서상 지원과 Nunti에서의 실측 품질은 구분한다.**

## 권고

우선 비교할 원화 모델은 **`gpt-image-2.5-sunburst`와 `gemini-nano-banana-2.1` 두 개**다. 전자는 정밀 편집·주석 입력·네이티브 투명 출력의 조합이, 후자는 다중 참조와 명시된 1K 출력 단가가 이 작업에 맞는다. 이는 기능에 따른 실험 우선순위이며 귀여움이나 소장 욕구의 승자를 검증한 결과가 아니다. Flare는 공식적으로 존재하지만 속도 중심 대안으로 둔다. [OpenAI 생성 가이드](https://developers.openai.com/api/docs/guides/image-generation), [Google 모델 카드](https://aistudio.google.com/docs/models/gemini-nano-banana-2.1).

구조 제어 실험은 **SDXL용 ControlNet Canny + IP-Adapter SDXL** 한 조합으로 좁힌다. 경로에서 만든 구조 지도와 그림체 참조를 별도로 넣는 방식을 검증하기 좋다. 최신 모델이라는 이유로 고른 것이 아니며, 기본 모델·ControlNet·IP-Adapter의 호환성과 각각의 라이선스가 필요하다. 우리 Mac에서 속도·메모리·설치 가능성·출력 품질은 측정하지 않았다. [SDXL ControlNet 카드](https://huggingface.co/diffusers/controlnet-canny-sdxl-1.0), [IP-Adapter 원저자 예제](https://github.com/tencent-ailab/IP-Adapter).

모델을 바꾸기 전에 **스타일 참조 / 경로 구조 / 목적지 모티브**를 나누고 정지 원화 3안을 비교하는 편이 낫다. 선정된 원화에서 읽히는 형상에 맞춰 탄생 모션을 설계한다. 현재 유리 몸체에 선을 추가하는 것만으로 목적지와 형태의 관련성이 생겼다고 보아서는 안 된다.

## API 후보 비교

| 후보·실제 공개 인터페이스 | 참조·구조·편집 | 투명 출력 | 확인된 비용과 조건 | Nunti 판단 |
| --- | --- | --- | --- | --- |
| OpenAI `gpt-image-2.5-sunburst`, `gpt-image-2.5-flare`; Images API 생성·편집 및 Responses image tool | 편집 입력 최대 16장. GPT Image 2.5에 투명 PNG `markup` 주석 지원; `mask`와 동시 사용 불가. Sunburst는 정밀 편집, Flare는 빠른 생성으로 안내. ControlNet 같은 별도 경로 강제 채널은 확인하지 못함. | `background: transparent` + PNG/WebP 공식 지원. PNG라는 확장자만 요청하는 것과 다름. | 두 모델 Standard: 텍스트 입력 **$5/1M tokens**, 이미지 입력 **$8/1M**, 이미지 출력 **$30/1M**. 같은 단가라도 사용 토큰이 달라 이미지당 비용은 다를 수 있음. 정확한 1024 medium 장당 금액은 이번 조사에서 확정하지 않음. | **정밀 원화·편집 1차 후보**. 스타일·구조·소재 참조의 역할을 프롬프트에서 구분. [생성·제약](https://developers.openai.com/api/docs/guides/image-generation), [편집 계약](https://developers.openai.com/api/reference/resources/images/methods/edit), [가격](https://developers.openai.com/api/docs/pricing) |
| Google `gemini-nano-banana-2.1`; Gemini Interactions API | 생성·대화식 편집. 최대 14 참조, 인물/캐릭터 4개·객체 10개 수준의 일관성 지원 안내. 일반 이미지 참조는 구조의 엄격한 구속 조건과 다름. | 확인한 현행 생성 가이드·모델 카드에 네이티브 alpha 보장·전용 transparent 옵션 없음: **미확인**. PNG 출력 자체는 alpha 보장이 아님. | Standard 1K 이미지 출력 **$0.0336/장**(1,120 image output tokens), 2K **$0.0504**, 4K **$0.113**. 입력 **$1.50/1M tokens**, 텍스트·thinking 출력 **$7.50/1M** 별도. 무료 API tier 없음. | **가성비 비교 1차 후보**. 컷아웃이 필요하면 후처리·반투명 가장자리 품질·추가 비용까지 평가. [모델](https://aistudio.google.com/docs/models/gemini-nano-banana-2.1), [생성](https://aistudio.google.com/docs/image-generation), [가격](https://aistudio.google.com/docs/pricing#gemini-nano-banana-2.1) |
| BFL **FLUX 3 Image**; `POST /v1/flux-3-image` | 최대 10 참조, 편집, prompt 안의 bounding box로 배치·부분 편집. 박스는 위치·영역 제어이며 경로의 모든 굴곡을 고정하는 조건이 아님. | 확인한 요청 계약에서 alpha/transparent 제어 미확인. | 공식 가격은 해상도 tier별 이미지 과금, 제출 응답에 `cost` 제공. 열람한 표의 단가 숫자가 노출되지 않아 **단가 미확인**. | 비교표에 유지. 최신 공식 인덱스는 FLUX 3을 안내하므로 FLUX.2만 최신이라고 쓰지 않음. [기능](https://docs.bfl.ml/flux_3/flux3_image_overview), [실제 API](https://docs.bfl.ml/api-reference/utility/generate-an-image-with-flux-3), [가격](https://docs.bfl.ml/quick_start/pricing) |
| Recraft `recraftv4_styles` / `_pro`; 별도 `recraftv4_1` image-to-image | Styles는 1~10장으로 재사용 `style_id` 생성. **Styles 자체는 image-to-image·inpainting 미지원**. V4.1 image-to-image는 `strength` 지원하지만 해당 endpoint에 V4/V4.1 style_id 결합은 미지원. | 생성의 네이티브 alpha 미확인. 별도 `removeBackground` API는 공식 제공. | Styles 1K **$0.035/장**, Pro 2K **$0.10/장**, 새 style 생성 **$0.005**, 배경 제거 **$0.01/요청**. 같은 style_id 재사용 시 스타일 생성료 제외. | 시리즈 그림체 탐색에는 유력하나 **경로 스케치+스타일 동시 제어 모델로 오인하면 안 됨**. [지원표](https://www.recraft.ai/docs/api-reference/models/recraft-v4-styles), [image-to-image 제약](https://www.recraft.ai/docs/api-reference/tools/image-to-image), [가격](https://www.recraft.ai/docs/api-reference/pricing), [컷아웃](https://www.recraft.ai/docs/api-reference/tools/remove-background) |
| Adobe Firefly Generate Images / Image5 | 기존 Structure Reference는 outline/depth 유사성을 `strength: 1..100`으로 제어하고 Style Reference와 구분. Image5는 instruct edit를 제공하지만 API 세대 간 스키마가 호환되지 않음. | 확인한 해당 생성 문서에서 네이티브 alpha 보장 미확인. 다른 Photoshop 컷아웃 API와 혼동하지 않음. | 읽은 공식 개발 문서에서 공개 고정 이미지 단가 미확인. Client ID·Secret, 서버 인증 및 서비스 접근 권한 필요. | 구조/스타일 개념은 참고 가치가 큼. MVP 기본 후보로 확정하기 전에 정확한 endpoint 세대·접근 조건 확인 필요. [구조 참조](https://developer.adobe.com/firefly-services/docs/firefly-api/guides/concepts/structure-image-reference/), [Image5](https://developer.adobe.com/firefly-services/docs/firefly-api/guides/how-tos/cm-generate-image/feature-guide), [세대 변경](https://developer.adobe.com/firefly-services/docs/firefly-api/guides/how-tos/cm-generate-image/breaking-changes) |

OpenAI·Google·Recraft·Adobe의 위 항목은 호스팅 서비스 API이지 공개 가중치 사용 허가가 아니다. Recraft API의 출력물 권리는 스튜디오 무료 플랜 설명 대신 별도 Developer Terms의 적용을 확인해야 한다. [Recraft API 약관](https://www.recraft.ai/legal/developer-terms). Adobe의 Image5 feature guide와 migration guide에는 `modelSpecificPayload` 등 필드 안내가 서로 달라, 구현 시 실제 해당 버전의 API schema로 다시 고정해야 한다.

## 로컬·오픈웨이트 후보

| 공개 모델 | 확인한 기술 범위 | 라이선스 구분·현재 판단 |
| --- | --- | --- |
| **Qwen/Qwen-Image-2.1**, 2026-09-20 공개 | 시각 생성부 7B, 생성·편집 통합, 최대 10 참조, 원/칠/별도 마스크로 국소 편집. **네이티브 RGBA 생성·투명 레이어 편집**을 모델 카드에서 명시. CPU offload 예시 있음. | **Qwen Research License**: 비상업 연구·평가 전용이며 상업 사용은 별도 허가. 과거 Qwen 모델의 Apache-2.0을 그대로 적용하면 안 됨. HF 카드에는 현재 Inference Provider 미배포로 표시. 로컬 비교의 기술 후보이나 상용 기본 모델로 바로 채택하지 않음. [카드](https://huggingface.co/Qwen/Qwen-Image-2.1), [실제 LICENSE](https://huggingface.co/Qwen/Qwen-Image-2.1/blob/main/LICENSE) |
| **Qwen/Qwen-Image-Edit-2511** | 다중 이미지 편집·캐릭터 일관성·형상 추론 개선을 안내하고, 2장 입력의 Diffusers 예제 제공. 최신 2.1보다 앞선 모델. 네이티브 alpha 지원은 해당 카드에서 미확인. | 카드상 **Apache-2.0**. 2.1의 새 라이선스와 구분할 로컬 편집 대안. 추론 운영비·우리 Mac의 메모리/시간은 미측정. [발행자 카드](https://huggingface.co/Qwen/Qwen-Image-Edit-2511) |
| **black-forest-labs/flux-3-image-klein**, 5.6B | 최신 FLUX 3의 공개 가중치 버전. 텍스트 생성·편집·10 참조·bounding box. Distilled 16 steps / Base 50 steps. 공식 문서는 RTX 3090부터 가능하다고 안내하고 **prompt upsampler 사용을 권고**. API도 별도 제공. 네이티브 alpha 미확인. | **FLUX Kommunity License**. 비상업/비운영 또는 조건을 충족하는 Qualifying User의 상업 사용을 구분하며, 관련 회사 합산 연환산 매출 $5M 미만 조건과 추가 의무가 있음. Apache나 무조건 무료 상업 허가로 부르면 안 됨. [공식 문서](https://docs.bfl.ml/flux_3/flux3_image_klein), [발행자 LICENSE](https://huggingface.co/black-forest-labs/flux-3-image-klein/blob/main/LICENSE.md) |
| **black-forest-labs/FLUX.2-klein-4B** | 이전 세대의 4B 생성·다중 참조 편집. 발행자는 약 13GB VRAM·4-step 추론을 안내. 네이티브 alpha 미확인. | 카드상 **Apache-2.0**. 라이선스가 단순한 소형 로컬 비교 대안으로 남기되 최신 FLUX 3과 품질이 같다고 가정하지 않음. [발행자 카드](https://huggingface.co/black-forest-labs/FLUX.2-klein-4B) |

공개 가중치는 기술적으로 로컬 실행을 검토할 수 있다는 의미다. **우리 Mac에서 설치·추론·MPS·양자화·발열·처리 시간은 검증하지 않았다.** GPU·전력·저장·유지보수 비용이 있으므로 로컬 비용을 $0/장으로 쓰지 않는다. CUDA 예제나 자동 표시된 MPS 안내는 이 프로젝트에서의 실행 증거가 아니다.

## 경로·스타일·캐릭터를 제어하는 서로 다른 수단

**ControlNet**은 edge·scribble·depth 등의 공간 조건을 확산 모델에 추가한다. 원저자 구현은 Apache-2.0이지만 사용하려는 가중치와 기본 모델의 허가는 각각 확인해야 한다. SDXL Canny 카드의 라이선스는 OpenRAIL++로 표시되어 있다. SD1.5용 ControlNet을 Qwen/FLUX에 그대로 연결할 수 있다고 가정하지 않는다. [원저자 구현](https://github.com/lllyasviel/ControlNet), [SDXL Canny](https://huggingface.co/diffusers/controlnet-canny-sdxl-1.0).

**IP-Adapter**는 참조 이미지의 시각 특징을 조건으로 넣는다. 원저자는 SD1.5와 SDXL 예제, ControlNet을 함께 사용하는 구조 제어 예제를 제공한다. 참조 강도를 낮추면 다양성은 늘고 참조 일관성은 떨어질 수 있다고 안내한다. 원저자 저장소의 코드 라이선스는 Apache-2.0이며 기본 모델·이미지 encoder·FaceID 등 모든 의존물까지 같은 허가라고 일반화하지 않는다. [IP-Adapter 원저자 저장소](https://github.com/tencent-ailab/IP-Adapter).

**Sketch-to-image**는 하나의 모델명이나 범용 호환 규격이 아니다. 입력 그림을 편집하는 모델, edge 조건용 ControlNet, Structure Reference 등 구현이 다르다. Nunti에서 이 구조 입력은 손으로 다시 그린 길이 아니라 **확인한 실제 내비게이션 경로에서 만든 지도**여야 한다.

## 프롬프트와 참조 자산 구성

OpenAI 공식 이미지 프롬프팅 가이드는 입력 이미지를 번호·설명으로 구분하고, 무엇을 바꾸며 무엇을 보존할지 반복해서 명시하도록 권한다. 스케치 변환에서는 배치·비율·원근을 보존하는 지시, 연속 캐릭터 작업에서는 character anchor를 제안한다. 해당 Cookbook의 모델 기본 추천은 2026-04-21 시점이므로 **프롬프트 원칙은 참고하되 최신 모델 기본값으로 복사하지 않는다.** [공식 프롬프팅 가이드](https://developers.openai.com/cookbook/examples/multimodal/image-gen-models-prompting-guide).

Nunti의 참조 입력은 다음처럼 역할을 고정하는 것이 타당하다. 아래는 연구에 따른 제안이며 실행 결과가 아니다.

1. **구조 이미지**: 실제 경로와 주요 굴곡의 위치. 어떤 굴곡을 귀·꼬리·외곽·몸체 속 재료로 옮길지 표시한다. 원본 polyline과 대응점을 별도로 보관한다.
2. **스타일 보드**: 사용자가 선정한 소장품의 재질·비율·표면·빛. 매 여정 같은 캐릭터를 복제하는 identity reference와 분리한다.
3. **목적지 모티브**: 사용자가 입력하거나 출처를 확인한 목적지 특성·색·재료 1~2개. 검증하지 않은 랜드마크·지형을 만들어내지 않는다.
4. **편집 후 불변 조건**: 선정 후의 얼굴·실루엣·실제 경로 대응·alpha 보존. 표정만 바꿀 때는 변경 범위를 좁힌다.

프롬프트 예시의 골격은 “Image 1의 구조 대응을 유지하고, Image 2의 재질·비율·빛만 사용하며, 확인된 목적지 특성 A/B를 형태에 반영한다. 스타일 보드의 캐릭터 자체를 복제하지 않는다. 얼굴과 외곽에서 특성이 읽히는 완성 소장품 1개, 투명 배경”이다. 여기에 목적지·경로의 실제 대응 설명을 넣어야 하며, ‘귀엽게, 고퀄리티’ 같은 형용사만 늘리는 것은 설계를 대신하지 못한다.

## 공식 공개 SKILL.md의 적용 범위

OpenAI의 [imagegen/SKILL.md](https://github.com/openai/skills/blob/main/skills/.system/imagegen/SKILL.md)와 [prompting.md](https://github.com/openai/skills/blob/main/skills/.system/imagegen/references/prompting.md)는 참조 역할·보존 조건·작은 단위의 편집에 참고할 수 있다. 해당 디렉터리의 [LICENSE.txt](https://github.com/openai/skills/blob/main/skills/.system/imagegen/LICENSE.txt)는 Apache-2.0이다. Anthropic의 [canvas-design/SKILL.md](https://github.com/anthropics/skills/blob/main/skills/canvas-design/SKILL.md)는 형태·공간·재질의 아트 방향을 산출물에 적용하는 지침이며 [개별 LICENSE.txt](https://github.com/anthropics/skills/blob/main/skills/canvas-design/LICENSE.txt)는 Apache-2.0이다. 이들은 **캐릭터 이미지 모델·추론 가중치·품질 인증이 아니다.** 실제 도입 때는 움직이는 main 대신 commit과 개별 LICENSE/NOTICE를 고정하고 사용자 경로 보존 조건을 우선해야 한다. 이번에는 설치·실행하지 않았다.

## 경로 보존과 비용 평가의 한계

참조 이미지, markup, mask, ControlNet, bounding box 모두 경로의 의미·시각적 관련성을 유도하는 수단이다. 조사한 문서에서 임의 polyline의 모든 점을 출력 이미지의 픽셀에 정확히 보존한다는 보증은 찾지 못했다. OpenAI도 구조화된 배치와 반복 캐릭터 일관성의 한계를 명시한다. [공식 제한사항](https://developers.openai.com/api/docs/guides/image-generation#limitations).

정확한 경로가 필요한 부분은 원본 벡터·대응점·검증을 유지해야 한다. 모델이 재해석한 선을 실제 주행 경로와 같다고 표시하지 않는다. 동시에 정확한 금빛 선 한 겹만으로 여행과 관련된 캐릭터 디자인이 완성되는 것은 아니다. 형태의 대응, 목적지 모티브의 읽힘, 탄생 연출의 연속성을 따로 평가해야 한다.

비용은 **채택한 캐릭터 1개를 얻는 전체 비용**으로 기록한다. 비교 후보 2장, 탈락·재시도·편집·컷아웃을 모두 포함한다. 확인된 산술 예로 Google 1K 출력 2장의 이미지 출력분만 $0.0672이며 입력·thinking·컷아웃은 별도다. Recraft Styles 1K 2장과 두 장의 배경 제거는 $0.09이고, 재사용 스타일이 없으면 최초 $0.005가 추가된다. 이는 두 서비스의 결과가 동등하다는 뜻도, 투명 유리 경계가 후처리에서 유지된다는 보장도 아니다. OpenAI·FLUX의 미확정 장당 비용을 이전 세대 가격이나 0으로 채우지 않는다.

아직 검증하지 않은 것은 같은 입력의 원화 비교, 사용자 소장 선호, 목적지·경로의 인지 가능성, semi-alpha 품질, 후보 채택률, 지연, 전체 채택 비용, 우리 Mac의 로컬 추론이다. 이를 확인하기 전에 기본 공급자를 확정하거나 탄생 효과를 다시 구현하지 않는다.
