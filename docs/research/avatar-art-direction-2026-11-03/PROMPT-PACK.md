# 눈티 일러스트·탄생 연출 프롬프트 초안

2026-11-03. 조사 결과를 눈티에 맞춰 작성한 원본 작업 지침이다. 외부 SKILL.md 전문을 복사한 파일이나 설치된 스킬이 아니다. 아직 생성 결과로 검증하지 않았으며, 다음 시안 비교에 사용할 초안이다.

전체 제품은 운전습관 개선을 돕는 눈티다. 이번 담당 기능은 목적지·내비게이션 경로로 개인화된 아바타를 생성한다. 사용자 선택인 반투명 2.5D 기념 오브젝트의 재질감과 살아 있는 작은 동반자라는 성격을 유지한다.

## 1. 생성 전에 준비할 재료

모델에 넣는 참조 이미지의 역할을 분리한다.

| 입력 | 담을 내용 | 사용 목적 |
|---|---|---|
| 원본 경로 | 확인한 선, 시작·도착, 눈에 띄는 굴곡과 그 구간 | 여정의 기하 근거 |
| 구조 스케치 | 원본의 어느 구간이 몸통·꼬리·귀 또는 몸의 흐름이 되는지 표시한 초안 | 외형의 큰 구조 제어 |
| 스타일 보드 | 승인된 재질·눈·작은 팔다리·렌더 깊이·광원 예시 | 눈티 제품군의 공통 미감 |
| 목적지 근거 | 사용자가 입력하거나 확인한 장소 특징·방문 목적 | 목적지의 의미를 조형으로 옮길 근거 |
| 배제·보존 조건 | 확정한 identity, 해부 구조, 주요 굴곡, 캐릭터의 여백 | 반복 편집에서 유지할 제약 |

기존 로컬 캐릭터 PNG를 유일한 스타일 보드로 고정하면 기존 실루엣을 반복할 수 있다. 같은 스타일 보드에서 몸체 구조가 다른 초안을 비교한다. 실제 주소·좌표의 창작적 필요와 화면상의 형태를 구분한다. 입력에 없는 도로·풍경·주행 능력은 새로 만들어 사실로 표시하지 않는다.

참조의 역할을 이름 붙이고, 구체적인 부위·재질·구도·보존 조건을 쓰며 한 번에 한 변화를 비교하는 방법은 [OpenAI imagegen 프롬프팅 지침](https://github.com/openai/skills/blob/main/skills/.system/imagegen/references/prompting.md)을 참고했다. 구조와 스타일 참조를 나누는 실제 제어는 [Adobe Firefly 구조 참조](https://developer.adobe.com/firefly-services/docs/firefly-api/guides/concepts/structure-image-reference/)와 [스타일 참조](https://developer.adobe.com/firefly-services/docs/firefly-api/guides/concepts/style-image-reference/)를 비교한다. 특정 모델의 참고 이미지 입력이 픽셀 단위 구조 보존을 보장한다는 뜻은 아니다.

## 2. 아트 디렉터에게 줄 지침

```text
당신은 눈티의 캐릭터 아트 디렉터다.
제품의 목적은 운전습관 개선을 돕는, 애착을 느낄 수 있는 작은 동반자다.
이번 작업은 목적지와 경로에서 태어나는 반투명 2.5D 아바타의 원화 설계다.

입력:
- 확인된 원본 경로 이미지와 점 목록
- 목적지 이름, 확인된 장소 특징, 방문 목적
- 승인된 눈티 스타일 보드

먼저 입력에서 시각적 근거를 뽑아라.
각 근거에 source_type, 원문 또는 route 구간, 확신 정도를 적어라.
그 후 구조적으로 다른 캐릭터 초안 세 개를 설계하라.

각 초안에는 다음을 포함하라.
1. 한 문장으로 읽히는 캐릭터의 정체성과 성격
2. 원본 경로의 대표 굴곡 2~3개와 대응하는 몸의 큰 구조
3. 목적지 특징이 몸체 구조나 재질의 조직에 반영되는 방식
4. 방문 목적이 자세·표정·움직임의 성격에 반영되는 방식
5. 작은 화면에서도 구분되는 실루엣과 시선이 머무는 표정
6. 손에 올려놓고 싶은 촉감, 두께, 투명도, 표면 표현
7. 같은 눈티로 감정 상태를 표현할 때 유지할 identity

출력은 예쁜 형용사의 나열보다 구체적인 형태와 대응 관계를 우선한다.
색·작은 장식만 바뀌는 안을 서로 다른 구조로 세지 않는다.
경로를 그대로 배에 새긴 문양만으로 주요 구조의 대응을 완료하지 않는다.
실제 근거와 창작적 해석을 구분한다.
세 안은 비교 시안이며 실제 제품의 캐릭터 선택지나 생성 한도가 아니다.
```

이는 눈티를 위한 설계 제안이다. 굴곡 개수나 세 안이라는 수는 검증된 심리 법칙이 아니다. 전체 경로를 억지로 해부학에 끼워 넣어 귀여움과 가독성을 해치면, 대표 구간을 선별하고 무엇을 생략했는지 기록한다.

## 3. 이미지 모델에 줄 공통 프롬프트

중괄호 부분은 위 아트 디렉션 결과와 실제 스케치로 채운다. 텍스트만으로 구조 보존을 약속하지 않고, 모델이 제공하는 구조·참조 제어와 함께 사용한다.

```text
Use case: stylized-concept / sketch-to-render.
Asset: one original, living 2.5D collectible travel companion for Nunti.

Image 1 is the approved structural sketch derived from the confirmed route.
Image 2 is the material and facial-language reference, not a character to copy.
Image 3 is the original route, provided for geometric comparison.

Character concept: {identity and temperament}.
Primary silhouette: {large body masses and their relationship}.
Route correspondence: {route segment A -> specific body curve;
segment B -> tail or ear arc; destination endpoint -> visual focal point}.
Destination evidence: {verified feature -> structural or material decision}.
Journey purpose: {purpose -> restrained pose and expression}.

Render a tiny companion with {specific proportions}, a clear friendly gaze,
{specified small limbs}, and a readable outline at thumbnail size.
Use {approved translucent material}, with visible thickness, controlled internal
refraction, soft contact shadow, and a small number of deliberate highlights.
Give the body a clear front surface so the eyes and expression remain readable.

Preserve the specified route-derived contour landmarks and the sketch's body
structure. Keep the approved eye placement and anatomy during refinements.
Use one dominant destination motif integrated into the body.
Frame the complete character with usable transparent margins. No typography.
Deliver an actual alpha-channel PNG when the selected model supports it;
otherwise declare the background-removal step separately.
```

투명 출력은 모델별 계약을 따른다. 일반적인 배경색 요청과 실제 RGBA 출력을 구분한다. 특정 모델에서 지원하지 않는 파라미터를 공통 프롬프트 지침만 보고 API에 보내지 않는다.

## 4. 같은 여정으로 비교할 세 조형 가설

다음은 새 원화의 비교 방향이며 사용자 승인된 최종 디자인이 아니다. 비교 때에는 동일한 목적지·경로·목적을 사용한다.

| 방향 | 형태의 핵심 | 경로와 목적지가 보이는 위치 | 주요 확인점 |
|---|---|---|---|
| 길에서 자란 유리 생명체 | 경로가 두께를 얻으며 몸통의 흐름과 꼬리로 자람 | 주요 굴곡이 외곽과 큰 덩어리에 남고, 목적지가 조직·재질을 정함 | 설명 없이 원본 경로를 찾아볼 수 있는가 |
| 목적지의 작은 정령 | 장소 특징이 캐릭터의 생김새를 만들고 경로가 자세와 신체 흐름을 정함 | 바다라면 파도 같은 몸의 겹침, 정원이라면 싹의 성장 구조처럼 통합 | 작은 소품을 떼어도 목적지의 인상이 남는가 |
| 살아 있는 여정 테라리움 | 투명한 작은 몸 안에 여정의 공간이 층으로 들어 있음 | 주요 경로가 내부 공간의 뼈대가 되고 목적지가 작은 환경을 구성 | 살아 있는 표정과 작은 신체가 장식물보다 먼저 읽히는가 |

예를 들어 입력이 해변·파도·휴식이라고 확인됐다면, 파도에서 온 몸의 겹침과 낮고 편안한 자세를 설계할 수 있다. 장소 이름만 보고 특정 건물·지역 상징을 사실처럼 추가하지 않는다. 실제 생성 모델의 결과와 비용은 이 비교를 실행할 때 확인한다.

## 5. 탄생 모션 디렉터에게 줄 지침

```text
승인된 캐릭터 외형과 원본 경로의 대응표를 사용해 탄생 과정을 설계하라.
전체 캐릭터는 편집 가능한 레이어 또는 mesh와 함께 준비됐는지 먼저 확인하라.

스토리보드에는 다음 네 순간을 포함하라.
- 출발과 목적지가 보이는 원래 경로가 하나의 주인공으로 등장한다.
- 눈에 띄는 경로 구간이 계속 보이는 채로 몸의 대응 부위로 이동한다.
- 그 구간이 두께·부피·재질을 얻어 캐릭터의 실제 일부가 된다.
- 표정과 작은 호흡이 생기고, 원래 경로와 완성 캐릭터를 비교할 수 있다.

각 순간에 원래 점이 어디로 이동하는지, 무엇이 보존되는지 기록하라.
주 움직임과 보조 움직임의 순서를 정하고 가장 중요한 전환에 시선을 모아라.
입자·빛·흔들림은 그 인과관계를 보조한다.
처리 중 상태와 준비가 완료된 뒤 재생되는 연출을 구분하라.
주차·foreground 조건을 잃으면 표시와 소리를 멈추고 같은 identity로 복귀하라.
reduced-motion에서는 대응 관계를 읽을 수 있는 정적 비교를 제공하라.

출력: 장면별 스케치, 대응 좌표/부위표, timing/easing 초안,
필요 자산 목록, 모바일 runtime 구현 방식, 아직 확보되지 않은 자산.
```

타이밍과 장면의 주역을 정하는 데 [LottieFiles motion-design](https://github.com/LottieFiles/motion-design-skill/blob/main/skills/motion-design/SKILL.md)을 참고한다. 편집 가능한 벡터·mesh의 실제 변형은 [Rive의 스킬·문서](https://github.com/rive-app/skills/blob/main/skills/rive/SKILL.md)와 구현 조건을 확인한다. 완성 PNG 한 장이 자동으로 신체별 rig가 된다고 가정하지 않는다.

## 6. 시안 평가와 다음 단계 진입 기준

아래는 제안하는 내부 평가 방식이다. 귀여움·소유욕을 자동으로 보장하는 지표가 아니다.

1. **실루엣 비교.** 재질과 색을 가려도 세 초안이 다른 구조로 읽히는지 본다.
2. **작은 크기 비교.** 64·128px에서 눈, 표정, 큰 형태가 남는지 확인한다.
3. **목적지 연관.** 설명을 가린 원화만 보고 후보 장소 중 어디와 어울리는지 고르게 한다.
4. **경로 연관.** 완성 외형에서 원본의 대표 굴곡을 직접 짚게 한다. 텍스트 설명을 읽고 나서만 알 수 있는 경우를 구분한다.
5. **분리 비교.** 목적지를 고정하고 경로만 바꾸는 비교, 경로를 고정하고 목적지 특징만 바꾸는 비교를 한다. 이미지 모델의 확률 변동을 의미 변화와 혼동하지 않는다. seed 미지원 모델은 같은 기준 이미지의 편집과 반복 표본을 쓴다.
6. **갖고 싶은가.** 같은 크기·배경·조명으로 제시하고 귀여움, 개별성, 보관 의향과 그 이유를 사용자에게 묻는다. 모델의 자체 점수는 보조다.
7. **모션 인과.** 빛·입자 없이도 경로가 몸이 되는 과정이 읽히는지 확인한 뒤 보조 효과를 더한다.

정지원화의 형태와 연관성이 확인된 뒤 선정안의 모션을 만든다. 이후 앱·음성·운전 피드백을 연결한다. 운전습관 개선 효과는 이 미적 평가와 별도의 제품 검증으로 남긴다.
