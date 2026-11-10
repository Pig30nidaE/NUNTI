# Pleos 공식 기준과 재사용 에셋

검증일: 2026-11-10 KST. 범위: 공식 웹 문서, 배포된 2.1.5 `.fig` 원본, 실제 Figma 가져오기 및 컴포넌트 읽기. 아래의 **공식 기준**, **권고**, **키트 관측값**, **미확인**을 구분한다. Nunti 앱의 플랫폼 승인·DO 적합성을 이 조사만으로 보증하지 않는다.

## 핵심 기준

| 항목 | 확인된 내용 | 적용 범위 |
|---|---|---|
| 대비 | 텍스트·아이콘 등 시각 정보 4.5:1 이상 | Pleos UI 가이드 |
| 읽기 시간 | 핵심 정보를 1–2초 안에 파악하도록 구성 | 공식 요구 |
| 피드백 | 입력 응답 0.25초 이내, 지연 시 처리 상태 표시 | 공식 요구 |
| 실제 문자 높이 | 중요 정보 4mm 이상, 일반 정보 3mm 이상 | 물리적 글자 크기. fontSize 숫자와 같지 않음 |
| 영어 길이 | 메시지 120자 또는 24단어, 한 줄 80자, 문단 3줄 이내 | 공식 영문 페이지의 범위. 한국어 수치로 환산하지 않음 |
| 주·야간 | 밝기·대비를 환경에 맞춰 자동 변경 | 두 테마 검증 필요 |
| 주행 모션 | 동영상·움직이는 이미지·자동 스크롤 등 시선 유발 요소 지양 | Nunti 장식 모션은 주행 제한 시 정적 종료 |

출처: [Pleos Connect UI guide](https://document.pleos.ai/en/docs/connect/guide/docs-design/Introduction/intro). 영문 페이지의 일본어 관련 문장은 언어 표기가 모호하므로 별도 수치로 채택하지 않았다.

## 타이포그래피

공식 시스템 폰트는 **Asta Sans**다. Android 접근성을 인용한 최소 12sp는 권고이며, 가독성을 위해 1.5배 이상·실제 높이 약 18–20px, 최소 18px 확보를 권한다. 12sp를 차량 UI 본문 기본 크기로 해석하지 않는다. [Pleos typography](https://document.pleos.ai/en/docs/connect/guide/docs-design/foundations/typography)

아래는 가져온 공식 키트의 텍스트 노드를 직접 읽은 값이다. `fontSize / lineHeight(PIXELS)`이며, 임의로 Android sp와 동일시하지 않는다.

| 분류 | Large | Medium | Small |
|---|---:|---:|---:|
| Headline | 60 / 80 | 56 / 72 | 48 / 64 |
| Title | 40 / 52 | 36 / 44 | 32 / 40 |
| Body | 30 / 38 | 28 / 36 | 26 / 34 |
| Label | — | 24 / 28 | 20 / 24 |

키트 예시의 weight는 Headline ExtraBold, Title ExtraBold/Bold, Body Bold, Label Regular다. 추가 허용 weight는 공식 표를 참고한다. `getLocalTextStylesAsync()`는 0개였으나 텍스트 노드·서체·행간은 보존되어 있다. 원본 버튼 medium label은 Asta Sans Bold 30, field placeholder는 Regular 30, help text는 Regular 26이다. 브라우저에 누락된 글꼴 배지가 보였으므로 생성·수정 시 실제 사용 가능 폰트와 렌더 결과를 확인해야 한다. 원본 폰트를 바꿨다고 가정하지 않는다.

## 터치와 공식 컴포넌트

[공식 basic button 문서](https://document.pleos.ai/en/docs/connect/guide/docs-design/components/actions/basic-button)는 구성·상태·크기를 설명한다. 검토한 Pleos 문서에서 **모든 앱에 적용되는 숫자형 최소 터치 영역과 간격은 확인하지 못했다**. 아래는 터치 최소 규정이 아니라 공식 키트의 실제 컴포넌트 치수다.

| 공식 컴포넌트 | 가져온 치수, Figma units | Nunti에서의 주의 |
|---|---|---|
| Basic/toggle button | Large 160×100, Medium 139×80, Small 113×64 | 문자열에 따라 폭이 달라짐 |
| Text field | Small 700×80, Medium 700×100 | help/error 높이는 추가됨 |
| Radio / checkbox | 64×64 | 시각 심볼 크기와 터치 wrapper를 분리 |
| Switch | Medium 80×48, Small 64×40 | 컨트롤 주변 터치 영역 별도 확보 |
| Segmented 3항목 | Medium 780×80, Large 880×100 | 좁은 앱 창에 원래 폭 그대로 강제하지 않음 |

Google의 자동차 UX 자료에서 제시한 76×76dp 터치 및 23dp 간격은 **AAOS 보조 기준**으로 검토할 수 있지만, Pleos 키트 자체가 해당 숫자를 규정한다고 쓰지 않는다. [Google driving UX principles](https://docs.partner.android.com/drivingux/foundations/design-principles)

## 디스플레이와 분할 창

상태 표시줄, Driving View, GNB는 플랫폼 영역이다. 앱은 허용된 앱 영역에 적응하며 시스템 오버레이가 콘텐츠를 가릴 수 있다. S는 1:1 또는 2:0, W는 2:1 또는 1:2이며 최대 두 앱을 표시한다. 3:0의 특수 카메라 예외를 일반 앱 권한으로 해석하지 않는다. [Display layout](https://document.pleos.ai/en/docs/connect/guide/docs-design/getting-started/layout), [Window policy](https://document.pleos.ai/en/docs/connect/guide/docs-design/getting-started/window)

아래는 공식 `Pleos_Connect_display_guide_215.fig`의 “Form factors / Table”을 Figma에서 읽고 스크린샷으로 대조한 값이다. 표의 열 이름 자체가 **dp**다.

| 폼 팩터 | 인치 / DPI | 전체 Resolution(dp) | 앱 Landscape(dp) | 앱 Portrait(dp) |
|---|---|---|---|---|
| Connect-S-17 (Default) | 17 / 160 | 2560×1440 | 1700×1184 | 840×1184 |
| Connect-S-14.6 | 14.6 / 200 | 2048×1152 | 1360×948 | 672×948 |
| Connect-L-12.9 | 12.9 / 160 | 1920×1080 | 1274×855 | 628×855 |
| Connect-W-Standard | 24.6 / 160 | 3840×850 | 1640×810 | 800×810 |
| Connect-W-Extended | 24.6 / 160 | 3840×1440 | 1640×1400 | 800×1400 |
| Connect-WF | 18.5 / 200 | 3072×816 | 1256×800 | 648×800 |

증거: [공식 표 캡처](official-assets/official-display-table.png), [노드 원문](official-assets/readback-details.json). 표의 이름·값을 그대로 기록했다. 실제 장치의 px, density, insets 및 multiwindow 앱 bounds와 일치 여부는 별도 런타임 측정 대상이다.

Driving View는 운전자 가까운 고정 시스템 영역이며 앱이 숨기거나 닫지 않는다. 앱 화면의 portrait/landscape 전환에서 핵심 기능을 유지하고, 백그라운드에서는 화면 갱신·애니메이션·불필요한 센서 작업을 중단한다. [App structure and screen model](https://document.pleos.ai/en/docs/pleos-only/vehicle-app-planning-guide/app-structure-screen-model)

## 주행 제한의 확정 범위

플랫폼의 `CarUxRestrictionsManager` 리스너와 받은 active restrictions를 적용한다. 국가/차종/버전에 따라 제한이 달라질 수 있으므로 앱이 지역을 추정해 우회하지 않는다. DO 선언도 제한 플래그를 무시할 권한은 아니다. [Driving restriction implementation](https://document.pleos.ai/en/docs/pleos-only/vehicle-app-developer-guide/driving-restriction-development-guide)

공식 정책 표의 플래그는 NO_DIALPAD=1, NO_FILTERING=2, LIMIT_STRING_LENGTH=4, NO_KEYBOARD=8, NO_VIDEO=16, LIMIT_CONTENT=32, NO_SETUP=64다. DO 미선언 앱은 주행 중 사용이 제한될 수 있다. 실제 Nunti 허용 상태는 매니페스트·기기 정책·런타임을 확인해야 한다. [Regional driving restriction policy](https://document.pleos.ai/en/docs/pleos-only/vehicle-app-planning-guide/driving-restiction-policy)

장식적·반복적 모션, 복잡한 메뉴와 필수 터치 조작을 줄이고, 제한 시 영상 시작·재개를 막는다. Nunti 변신은 정차 단계에서만 재생하며 제한 전환·백그라운드·재진입 시 자동 재개하지 않는 설계가 필요하다. 이는 공식 방향을 Nunti에 적용한 구현 판단이다. [Driver distraction guideline](https://document.pleos.ai/en/docs/pleos-only/vehicle-app-planning-guide/driver-distraction-guideline)

Nunti가 음악/지도 등의 주행 허용 예외에 자동 해당한다고 판단하지 않는다. [App category](https://document.pleos.ai/en/docs/pleos-only/vehicle-app-planning-guide/app-category). 공식 [Animation](https://document.pleos.ai/en/docs/connect/guide/docs-design/foundations/animation) 문서가 앱 상태 설명용 모션을 다뤄도 Nunti의 4초 장식 연출을 주행 중 허용한다는 뜻은 아니다.

## 실제 다운로드 및 Figma 재사용

기존 저장소에는 공식 링크가 있었으나 `.fig` 원본은 없었다. 공식 UI 가이드의 다운로드 링크에서 아래 두 파일을 받아 원본 바이트를 보관했다. 두 파일은 ZIP 컨테이너이며 `canvas.fig`, `meta.json`, `thumbnail.png`, `images/`를 포함한다.

| 파일 | 바이트 | 원본 URL |
|---|---:|---|
| Pleos_Connect_design_assets_215.fig | 2,477,386 | [공식 디자인 키트](https://document.pleos.ai/img/Pleos_Connect_design_assets_215.fig) |
| Pleos_Connect_display_guide_215.fig | 44,427,926 | [공식 디스플레이 키트](https://document.pleos.ai/img/Pleos_Connect_display_guide_215.fig) |

서버 Last-Modified는 두 파일 모두 2026-10-29 UTC다. ZIP metadata의 export 시각은 디자인 2026-10-16, 디스플레이 2026-09-30이다. 파일명 2.1.5와 이 시각을 구분한다. 해시는 [manifest.json](official-assets/manifest.json)에 기록한다.

실제 TOZI 초안으로 가져오기 성공:

- [공식 디자인 키트 원본](https://www.figma.com/design/ZZ4WoyC5NQvducpb2Iv8Uw) — Foundation, Components 두 페이지.
- [공식 디스플레이 키트 원본](https://www.figma.com/design/QWCJAx4Sp0UWawRDuOOjsv) — Form factors & Display 페이지.
- [Nunti Redesign 페이지](https://www.figma.com/design/LHLHBra8ON3OdVW0qhBnbm?node-id=15-4) — basic button, field, switch, checkbox, segmented의 **5개 native COMPONENT_SET / 60개 variant COMPONENT**를 복사했다. 세트 ID는 각각 18:132, 18:269, 18:404, 18:460, 18:587이다.

MCP에는 `.fig` import API가 없지만 Chrome 네이티브 파일 선택기로 실제 import가 가능했다. Figma 데스크톱 앱은 실행 목록에 있었으나 앱 제어 연결에 실패했다. 브라우저 확장의 file-URL 접근 권한을 바꾸지 않고 네이티브 선택기로 완료했다. 미공개 source key의 `importComponentByKeyAsync`는 Component not found였고, 일반 Figma copy/paste로 native 세트·베리언트·Auto Layout을 보존했다. 공개 라이브러리·멤버십·권한 변경은 하지 않았다.

[원본/복사본 ID·속성·치수](official-assets/imported-components.json), [복사한 버튼 세트 캡처](official-assets/copied-native-buttons.png). 일부 원본 semantic color alias가 어두운 라벨로 렌더되어 복사만으로 대비가 보장되지 않는다. Nunti semantic 변수에 명시적으로 연결하고 낮/밤 대비를 검증한다. 원본 키트는 수정하지 않았다.

## 출처와 이용 범위

소유자/출처: Pleos/현대자동차그룹 공식 배포 자료. 다운로드는 공식 UI 가이드에서 제공된다. 별도의 오픈소스 라이선스나 재배포 허용문은 확인하지 못했다. 프로젝트 내부의 출처가 있는 디자인 참조·앱 설계 재사용을 위해 보관하며, 이 문서는 원본의 독립 공개·판매·재라이선스 권리를 부여하지 않는다. 배포 전 이용 범위가 필요하면 해당 약관과 계약을 확인한다. [Pleos Playground 이용 약관](https://developers.pleos.ai/playground/external/use-policy?locale=en-US&partnerId=672505ad-2e37-4500-8162-000bcfc05b5c)

유료 이미지/영상 모델 API 호출: **0회**. 다운로드, Figma 가져오기, 컴포넌트 복사만 수행했다.

