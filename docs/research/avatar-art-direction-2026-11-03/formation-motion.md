# 경로가 눈티의 몸이 되는 탄생 연출

조사일: 2026-11-03. 공식 도구 문서, 발행자의 실제 `SKILL.md`, 원논문과 현재 코드를 읽었다. 앱·서버 코드 변경, 도구 설치, 생성 API 호출, 세션 조작, 녹화는 하지 않았다. 아래 연출·수치·프롬프트는 Nunti에 대한 제안이며 이미 검증한 결과가 아니다.

## 먼저 원화를 고르고 그 몸이 만들어지는 원인을 설계한다

이번 단계는 **원화 실루엣 세 안 비교 → 한 안 선정 → 선정한 외형의 탄생 연출 비교** 순서가 적절하다. 빛과 입자를 먼저 추가하면 완성 캐릭터의 매력이 부족한 원인을 구분하기 어렵다. 모션의 목표는 사용자가 방금 확인한 경로의 굴곡을 완성 눈티에서도 찾아내고, 그 선이 재료와 부피를 얻는 순간을 보는 것이다.

핵심은 시작 그림과 끝 그림 사이의 대응이다. '왼쪽 급커브가 귀의 접힘으로 남고, 긴 완만한 구간이 몸의 둥근 옆면이 되며, 끝점이 작은 장식에 닿는다'처럼 눈으로 추적할 근거를 정해야 한다. 이 관계는 디자인 규칙이다. 화면 속 커브를 실제 산길·거리·위험도로라고 추정하는 규칙은 아니다.

추천 우선순위는 A의 **실제 윤곽 변형**과 B의 **부위별 접힘**을 선정 원화에 비교하는 것이다. C의 체적 shader는 재질 표현의 확장안으로 남긴다. 이번 문서에서 세 안 중 하나를 사용자 대신 확정하지 않는다.

## 현재 구현에서 확인한 사실

읽은 소스는 [studio.js](../../../prototypes/avatar_generator/studio.js)의 `birthAnimation()`·`strokeRoute()`와 [illustration.py](../../../backend/nunti/avatar_studio/illustration.py)의 `_route_thread()`·`_draw_route()`다.

| 현재 코드의 동작 | 시각적 의미와 남은 부분 |
|---|---|
| 로컬 렌더에서 `design.routeThread.points`가 원본 경로와 같은 점 수이며 최종 PNG 안의 선 좌표를 제공 | 원래 선과 최종 무늬의 대응 근거가 있다. 이전의 임의 spiral에 대한 지적을 현재 코드에 그대로 적용하면 부정확하다 |
| 입력 선의 점을 최종 이미지 내부 선으로 선형 보간 | 내부 선의 위치가 이어진다. 현재 PNG의 몸통·귀·발 윤곽 자체가 이 보간으로 변형되는 것은 아니다 |
| 완성 PNG를 offscreen canvas에 그리고 두꺼워지는 선을 `destination-in` 마스크로 적용 | 선에서 그림이 드러나는 연결은 있다. 몸의 부피가 생기거나 재료가 눌리는 동작은 별도 기하가 없어 표현 범위가 제한된다 |
| AI 이미지에 대응 좌표가 없으면 작은 경로로 접은 뒤 완성 이미지를 fade | AI 결과가 실제 경로의 어느 지점을 몸의 어디에 반영했는지 아직 증명하지 못한다. UI도 제안 모티브의 반영 여부를 미확인으로 표시한다 |
| 전체 4.2초, 매 프레임 glow·주변 점·이미지 공개를 함께 그림 | 무엇을 먼저 볼지 구분하는 연출이 약해질 수 있다. 이는 코드 구조를 바탕으로 한 시각적 판단이며 사용자 선호 실험 결과는 아니다 |
| `strokeRoute()`가 점 인덱스 비율로 진행 | 원본 점 간격이 다르면 펜끝 속도도 달라진다. 일정한 이동감을 원하면 선 길이로 진행값을 계산할 필요가 있다 |

현재 버전은 `studio.js` SHA-256 `47f99ec6bb8f55c73917e23f37f97ad20956af4faf841b2a1191048aa47457ab`, `illustration.py` SHA-256 `b56fde1313c315c30816d38764dcc7a60a0f13f3438ea7ace21364aa774e1c6a`에서 조사했다. 이 조사는 새 시각 QA나 재생 성능 측정이 아니다.

## 공식 사례에서 가져올 수 있는 작업 방식

### 대응점을 먼저 정하고 중간 형상을 만든다

Adobe Animate의 shape hints는 시작·끝 도형에서 대응할 지점을 지정한다. 눈의 위치를 따로 대응시키는 예를 들며, 복잡한 변형에는 시작·끝 두 장만 두기보다 중간 형상을 만들라고 안내한다. Nunti에는 '입력 선 → 접힌 재료 → 아직 얼굴 없는 몸 → 완성 눈티'의 중간 자세를 먼저 고르는 방식으로 적용할 수 있다. 비트맵 하나를 넣으면 부위가 자동으로 분해되는 기능이라는 뜻은 아니다. [Adobe 공식 shape tweening](https://helpx.adobe.com/animate/desktop/animation/shape-tweening.html)

GSAP MorphSVG는 시작점의 대응이 어긋나면 중간에 뒤집힘·교차가 생길 수 있다고 설명한다. subpath 대응을 제어하는 `map`, 회전·길이 기반의 `type:'rotational'`, 복잡한 경우 path를 나누어 제어하는 방식을 제공한다. `shapeIndex`는 닫힌 path에만 적용된다. 따라서 열린 내비 경로에 곧바로 적용할 수 있다고 설명하면 안 된다. 열린 중심선의 대응을 직접 유지하거나, 일관된 폭과 끝단으로 닫힌 외곽을 만든 뒤 morph를 설계해야 한다. [GSAP 공식 MorphSVG](https://gsap.com/docs/v3/Plugins/MorphSVGPlugin/)

펜끝의 이동과 선의 변형도 구분해야 한다. GSAP MotionPath는 경로를 따라 위치·방향을 움직이고, 선분별 속도 차이를 줄이는 해상도 조절을 문서화한다. 이는 선을 몸체로 만드는 연산 자체는 아니다. [GSAP 공식 MotionPath](https://gsap.com/docs/v3/Plugins/MotionPathPlugin/)

### 그림을 가리는 것과 재료를 변형하는 것은 다르다

Rive Mesh는 이미지 위의 삼각형 정점이 움직일 때 내부 픽셀도 변형한다. 정점은 timeline이나 bone으로 제어할 수 있고, alpha를 바탕으로 contour를 추출하는 도구도 있다. 선정한 원화를 실제로 눌렀다 펴거나 귀·몸통의 움직임을 분리하는 제작 방식의 근거다. [Rive 공식 Meshes](https://rive.app/docs/editor/manipulating-shapes/meshes)

ARAP 원논문은 2D 삼각형 mesh의 일부 점을 handle로 고정하고 나머지 점의 왜곡을 줄이는 변형을 다룬다. 연구에서는 사전 계산 뒤 상호작용하는 방식을 제시한다. Nunti에는 얼굴 영역을 보호하고 몸만 탄성 있게 변형하는 설계의 참고가 된다. 이 연구가 임의 PNG의 귀·얼굴을 자동 인식하거나 Pleos에서 실시간 성능을 보장하는 것은 아니다. 저자 페이지의 BibTeX 제목은 본문과 달라 참고문헌은 실제 연결된 논문 제목을 따른다. [Igarashi·Moscovich·Hughes 원논문 PDF](https://cs.brown.edu/people/jhughes/papers/Igarashi-ASM-2005/paper.pdf)

Rive의 Follow Path Constraint 역시 오브젝트의 위치·방향을 선에 붙이는 기능이다. '선을 따라 이동'과 '그 선이 새로운 몸의 윤곽으로 변형'을 별도 작업으로 잡아야 한다. [Rive 공식 Follow Path](https://rive.app/docs/editor/constraints/follow-path-constraint)

### 빛을 넣기 전에 무게·예비 동작·시선을 정한다

Disney Animation은 timing, clear staging, squash and stretch, anticipation, follow-through와 secondary action을 캐릭터 연기의 원리로 소개한다. Nunti에서는 본격적인 부풀기 전 재료가 살짝 당겨지고, 몸이 먼저 멈춘 뒤 귀가 늦게 따라오며, 완성 후 한 번만 작게 안착하는 식으로 적용할 수 있다. 귀여움의 정답이나 소장 욕구를 보장하는 공식은 아니다. [Disney Animation 제작 과정](https://www.disneyanimation.com/process/animation/)

Adobe의 원리 설명도 staging에서 카메라·시선·행동의 초점을 다루고, anticipation을 관객이 다음 동작을 읽도록 준비하는 요소로 설명한다. 처음부터 전체 glow·입자·캐릭터를 동시에 움직이기보다 한 선의 움직임을 먼저 보게 하는 근거로 사용할 수 있다. [Adobe 12 principles](https://www.adobe.com/creativecloud/animation/discover/principles-of-animation.html)

## 구조가 다른 세 연출안

아래는 선정할 원화와 동일한 최종 외형에 적용해 비교할 안이다. 공개 자료에서 그대로 가져온 상용 사례가 아니라, 앞의 제작 원리를 Nunti에 적용한 제안이다.

| 안 | 경로가 바뀌는 대상 | 끝에 남는 시각적 근거 | 실제 제작 방식 | 주요 한계 |
|---|---|---|---|---|
| A. 한 줄이 말랑한 몸으로 부푼다 | 열린 경로 중심선과 그 양쪽 외곽이 부드러운 하나의 실루엣으로 변형 | 커브 두 곳이 몸 옆면과 귀의 굴곡으로 남고 원래 선은 내부 금빛 심으로 보존 | Canvas·SVG의 제어점 또는 저해상도 2D mesh. 경로 길이 매개변수와 의미 있는 굴곡의 대응을 함께 저장 | 모든 긴 경로를 문자 그대로 튜브로 만들면 길쭉한 벌레가 된다. 얼굴 공간과 몸의 부피 제약을 두고 중간 자세를 설계해야 함 |
| B. 한 줄이 접혀 귀·몸통·발이 된다 | 서로 연결된 경로 구간이 관절·접힘 단위로 이동하며 부위를 구성 | 시작 구간·큰 굴곡·마지막 구간이 각각 어느 부위가 되었는지 추적 가능 | Rive bone·mesh 또는 같은 의미의 앱 기하. 3–5개 부위 handle과 중간 자세를 저작 | 곡선이 교차하는 경로에서 구간 대응이 모호하다. AI 원화라면 부위별 영역·handle을 함께 준비해야 함 |
| C. 선을 따라 유리 재료가 응결한다 | 경로상의 재료 밀도가 커져 실제 표면·두께를 형성 | 원래 흐름이 표면의 능선과 내부 굴절선으로 남고 몇 지점이 실루엣 돌기로 성장 | SDF·mesh·shader의 밀도/표면 변화. 법선과 광원을 이용한 2.5D 또는 3D shading | GPU 비용과 투명 표면의 정렬·굴절 처리가 큼. 하나의 고정 몸체를 PNG mask로만 공개하면 이 안의 차이가 사라짐 |

A와 B는 전체 경로를 쪼개 무관한 입자로 흩뜨리지 않는다. 경로가 실제 연결된 내비 선이라는 사실과 입력 순서를 보존한다. 얼굴은 승인된 원화의 표정·색을 지키고 변형 중 과도하게 늘이지 않는다. 귀·몸통·발의 비율을 보장하는 규칙은 디자인 문법이며, 완성 캐릭터 세 개 중 하나를 선택하는 카탈로그로 만들지 않는다.

C의 재질 참고로 Three.js `MeshPhysicalMaterial`은 단순 opacity와 물리적 transmission을 구분하고 clearcoat·iridescence·thickness를 제공한다. 문서도 기능을 켤수록 픽셀당 비용이 늘며 environment map을 권한다고 설명한다. `morphAttributes`와 `morphTargetInfluences`는 기하 변형에 사용할 수 있지만 새 여정마다 맞는 정점 대응을 준비해야 한다. [Three.js 재질](https://threejs.org/docs/pages/MeshPhysicalMaterial.html), [BufferGeometry](https://threejs.org/docs/pages/BufferGeometry.html), [Mesh morph weights](https://threejs.org/docs/pages/Mesh.html)

## 원화 선정 뒤 비교할 5.2초 스토리보드

다음 시간은 실험 시작값이다. 생성 API 지연이나 이미 측정한 최적 재생 길이가 아니다. 원화·기하·대응점이 준비된 뒤에만 이 탄생 시간을 시작한다.

| 시간 | 주된 동작 | 시선과 물성의 목표 |
|---|---|---|
| 0–0.8초 | 확인한 실제 경로를 그대로 보여 주고 한 펜끝이 시작→끝으로 이동 | 출발과 도착을 알아볼 시간. 원본의 눈에 띄는 굴곡 두 곳을 관찰하게 함 |
| 0.8–1.15초 | 선이 작은 힘을 받아 살짝 당겨지거나 한쪽 끝이 들림 | anticipation. 다음 변화의 원인이 같은 재료임을 전달 |
| 1.15–2.8초 | A는 외곽이 부풀고, B는 연결된 부위가 접히며, C는 재료의 두께가 생김 | 완성 그림을 미리 fade하지 않고 실제 변화의 대상을 보여 줌 |
| 2.8–3.7초 | 승인한 얼굴과 재질의 하이라이트가 읽힘 | 얼굴이 주인공이 되는 순간. 주변 모션은 줄임 |
| 3.7–4.5초 | 몸이 작게 안착하고 귀·장식은 조금 늦게 멈춤 | 같은 재료가 움직인 무게와 follow-through |
| 4.5–5.2초 | 원래 굴곡이 남은 부위를 잠깐 보여 주고 완료 | 사용자가 연관성을 찾는 시간. 음성은 자동으로 시작하지 않음 |

경로가 이미 안내 화면에 충분히 보였다면 첫 구간을 줄이는 변형도 비교한다. 반복 재생과 보관함 복원에는 긴 탄생을 강제하지 않는다. reduced motion은 승인한 정적 외형과 원래 경로를 보여 주고 필수 동작만 최소화한다.

## 적용할 프롬프트

다음은 이번 조사의 제안 프롬프트다. 아직 모델·MCP에 실행하지 않았다. 설명용 영화 한 편보다 **같은 원화·같은 경로의 key pose와 대응점**을 먼저 요청한다.

### 실루엣 선정 후 모션 디렉터에게

```text
선정된 눈티 원화와 확인된 내비 경로를 참조한다.
목표 감정은 '내가 방금 본 길에서 작은 생명이 태어났다'는 놀라움과 애착이다.
같은 최종 외형에 대해 A 부풀기, B 부위별 접힘, C 재료 응결의 세 구성을 비교하라.
각 안은 0%, 22%, 50%, 76%, 100%의 다섯 key pose로 제시한다.
각 pose 위에 동일한 route point ID와 의미 있는 굴곡 2~3개의 이동을 표시한다.
최종 실루엣·얼굴·색은 선정 원화를 유지한다.
원래 선이 사라진 뒤 완성 이미지를 단순 fade하는 구성을 제외한다.
한 번에 주로 움직이는 대상은 하나로 두고, 귀·작은 장식은 뒤따라 멈추게 한다.
모든 변화는 같은 장면과 카메라에서 이어지고 마지막에는 완성 외형으로 정확히 돌아온다.
각 안마다 변형되는 기하, 대응표, 재질, 예비 동작, 착지, 실패하기 쉬운 경로를 설명하라.
귀여움·소장 욕구는 사람이 원화와 동작을 보고 판단하도록 미확정으로 남겨라.
```

### Rive 또는 벡터 모션 저작자에게

```text
승인 원화와 승인 key pose만 사용한다. 임의 캐릭터를 새로 선택하지 않는다.
source route를 열린 중심선으로 유지하고 final contour와 혼동하지 않는다.
중심선·최종 외곽·얼굴 보호 영역·귀·몸통 handle·그림자를 분리한다.
같은 point ID와 굴곡 landmark를 중간 자세까지 연결하고, 뒤집힘과 갑작스런 구간 교체를 검사한다.
한 progress 값으로 준비완료→탄생→안착을 scrub할 수 있게 설계한다.
0, .22, .5, .76, 1에서 correspondence와 얼굴의 왜곡을 검사할 기준을 제공한다.
새 경로에 필요한 사전 계산과 매 프레임 연산을 분리하고, 보관 복원은 원래 완성 자세를 사용한다.
출력에는 layer/handle 목록, correspondence 표, timeline과 runtime에서 필요한 기능을 포함한다.
실차 성능과 임의 PNG 자동 rig를 검증했다고 표시하지 않는다.
```

영상 생성 모델에 같은 brief를 줄 수는 있다. 그 결과는 연출 후보의 참고이며 실제 앱용 변형 데이터와 구분한다. 최종 앱에 영상을 사용하는 경우에도 입력별 영상 비용·대기시간·다운로드·보관·투명 배경·최종 얼굴 일치·중단과 복귀를 따로 검증해야 한다. 영상 한 편을 얻었다는 사실이 새 경로마다 같은 품질의 실시간 morph를 구현했다는 증거는 아니다.

## 실제 확인한 공식 skills와 MCP

| 항목 | 발행·라이선스·실제 파일 | 우리에게 유용한 부분 | 과장하면 안 되는 부분 |
|---|---|---|---|
| motion-design | LottieFiles, MIT. [실제 SKILL.md](https://github.com/LottieFiles/motion-design-skill/blob/main/skills/motion-design/SKILL.md), [LICENSE](https://github.com/LottieFiles/motion-design-skill/blob/main/LICENSE) | 감정 목표·hero·시간·easing·주/보조 모션을 먼저 정하는 checklist. 원화 선정 후 storyboard 검토에 바로 참고 가능 | 디자인 지침 모음이다. 자체 편집 도구나 귀여움 검증기·자동 경로 변형기는 아니다. UI micro-motion 수치를 캐릭터 탄생 전체에 그대로 강제하지 않음 |
| rive | Rive, Inc.의 `rive-app/skills`, MIT. [실제 SKILL.md](https://github.com/rive-app/skills/blob/main/skills/rive/SKILL.md), [LICENSE](https://github.com/rive-app/skills/blob/main/LICENSE) | 짧은 discovery 지침이다. 기존 .riv는 runtime, 새 그래픽은 CLI·프로젝트 안내로 연결. 사람과 agent가 같은 파일을 다루는 작업 방식 | skill만으로 Editor·CLI가 설치되거나 연결되지 않는다. 임의 PNG의 부위 인식·자동 rig·실차 성능을 보장하지 않는다. 이번 조사에서 설치하지 않음 |

LottieFiles의 공식 Creator MCP는 열려 있는 Creator 브라우저 탭과 연결해 장면·path·keyframe·mask를 편집하는 workflow다. motion-design skill은 어떤 모션을 만들지 안내하며 MCP는 실제 편집 동작을 제공한다. 두 역할을 구분한다. [Lottie Creator MCP 공식 문서](https://docs.lottiefiles.com/en/creator/13_ai-tools/lottie-creator-mcp)

Rive 공식 MCP는 Windows·macOS Desktop Editor에서 scene, path, bone chain, animation, state machine, script·shader 편집을 지원한다고 안내한다. 런타임에서 매 이동마다 에디터를 켜고 MCP로 캐릭터를 만드는 방식을 입증하는 문서는 아니다. [Rive MCP 공식 문서](https://rive.app/docs/editor/ai/mcp)

Rive CLI의 공식 시작 문서는 프로젝트 생성, `.riv` 빌드와 runtime 사용 흐름을 제시한다. 앱에 매번 CLI·에디터를 포함해야 한다는 뜻은 아니다. 저작 단계와 앱 재생 단계를 분리한다. [Rive CLI 시작 문서](https://rive.app/docs/cli/getting-started)

## 실시간 앱 통합에서 남는 조건

1. **새 PNG 교체와 새 rig 생성은 별도다.** Rive는 runtime의 이미지 교체를 지원한다. 그러나 다른 귀 위치·실루엣을 가진 PNG마다 같은 mesh가 자연스럽게 맞는지는 별도 문제다. 현재의 얼굴 포함 PNG 계약을 유지할지, 다음 버전에서 부위·contour·handle을 같이 생성할지 원화 선정 뒤 결정한다. [Rive Loading Assets](https://rive.app/docs/runtimes/web/loading-assets)
2. **같은 animation 파일도 runtime 지원을 확인한다.** Rive 공식 문서는 기능·renderer에 따른 지원 차이를 안내한다. 일부 기능에는 Rive Renderer가 필요하며 layer mask는 GPU Canvas 조건이 있다. 이 프로젝트의 Android WebView에서 해당 기능은 아직 시험하지 않았다. [Rive Feature Support](https://rive.app/docs/feature-support)
3. **Lottie의 mask·trim path는 체적 시뮬레이션이 아니다.** 공식 안내는 shape·transform·trim path·mask를 지원 범위로 들고, effect·blend mode는 주의 대상으로 구분하며 3D layer와 대부분의 왜곡 효과를 피하라고 안내한다. 에디터의 glow를 그대로 모든 플레이어에 옮길 수 있다고 가정하지 않는다. [LottieFiles 지원 기능 안내](https://help.lottiefiles.com/supported-after-effects-features)
4. **지오메트리는 준비할 때 한 번 계산한다.** 다음 프로토타입의 시작 예산으로 128–256개 중심선 표본, 의미 있는 landmark 2–3개, 작은 mesh를 제안한다. 이 수치는 측정 결과가 아니다. 실제 원화·경로에서 변형 품질을 본 뒤 결정한다. 최종 PNG·원본 경로·correspondence·완성 자세를 함께 보관해야 재시도와 복원에서 정체성이 유지된다.
5. **성능을 보기 전 품질 원인을 분리한다.** 새 원화, 새 모션, 새 재질을 동시에 바꾸지 않는다. 같은 원화와 같은 경로에서 A/B를 비교하고, 선택한 구조에 재질을 얹은 뒤 Pleos에서 frame time·메모리·gate 중단·복귀를 측정한다. 60fps의 전체 프레임 예산 약 16.7ms 또는 30fps의 약 33.3ms는 목표 예산이지 현재 달성 성능이 아니다.

## 단계별 실험과 판정

| 단계 | 준비물과 시간 범위 | 통과 기준 |
|---|---|---|
| 1. 원화 판단 | 동일한 세 여정에 실루엣 세 안. 모션 없음. 제작 작업량은 원화 담당의 시안 범위로 별도 산정 | 사용자에게 실제로 갖고 싶은 외형이 선택됨. 외형에 동의하기 전 glow로 문제를 가리지 않음 |
| 2. key pose 비교 | 선정 원화 하나와 같은 경로로 A/B의 다섯 pose. 5.2초 타임라인은 서술만 준비 | 원래 굴곡이 어디로 이동했는지 설명 없이 두 곳 이상 찾을 수 있음. 중간에 얼굴이 늘거나 조각나지 않음 |
| 3. 단일 실시간 prototype | 선택한 한 구조를 scrub 가능한 기하로 구현. 설치·구현 일정은 runtime 선택 후 산정 | 0–1 전체에서 점·부위가 연속이고 마지막 외형이 승인 원화와 일치. 경로 세 종류와 점 밀도 차이에 대응 |
| 4. 재질·앱 검증 | 선택 모션에만 반투명 하이라이트와 착지 추가. 최초 4.5–5.5초와 짧은 반복판을 비교 | 실제 장치 성능·정차 gate·reduced motion·복원이 통과하고 자동발화가 없음 |

사람 평가에는 '어느 굴곡이 어디에 남았나요?', '같은 선이 몸이 되었다고 느꼈나요?', '완성된 모습을 보관하고 싶나요?'를 나눠 묻는다. 모델이 높은 cute 점수를 주거나 기하 테스트가 통과했다는 이유로 소장 욕구를 승인하지 않는다. 이 조사에서는 아직 시안 비교·모션 재생·사람 평가를 수행하지 않았다.
