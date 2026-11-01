# 기술 선택 및 근거 · 2026-11-01

## 선택

고정 identity + 2D 파츠 + Kotlin 규칙 엔진 + 순수 감정 상태 머신을 채택한다.
MVP는 AI 이미지 생성이나 3D 런타임 없이 실제 생성 근거와 반복 재현을 먼저 검증한다.

| 접근 | 장점 | 제약 / 이번 판단 |
| --- | --- | --- |
| Kotlin 규칙/가중 후보 평가 | 근거 추적, 버전 재현, offline, unit test | 실제 경로/사람 평가로 가중치를 보정해야 함. 채택 |
| Compose Canvas + 파츠 scene | 작은 자산, 표정 교체, 동일 rig, normalized 크기 | 예술적 자산은 추가 제작 필요. 채택 |
| VectorDrawable | 디자이너 벡터로 교체 가능, 밀도 독립 | 조합/표정 anchor를 별도로 유지해야 함. provider 후속 구현 경로 |
| 전체 이미지 생성 | 풍부한 장면·스타일 탐색 | 얼굴/실루엣 흔들림, seed만으로 공급자 버전 재현 불충분, offline/지연/자산 QA. 실시간 생성에서 제외 |
| 고정 reference 기반 이미지 생성 | 동일 캐릭터 시안과 파츠 후보 제작에 활용 가능 | 생성 결과를 고정 assetVersion으로 검수·배포해야 함. 추후 디자인 단계에 한정 |
| 3D rig + 의상 | 입체 포즈, 조명, camera 표현 | 모델링/rig/GPU/가려짐/주의 분산 검증 비용. MVP 이득이 검증되지 않아 제외 |

위 비교는 제품 요구에 따른 엔지니어링 판단이며 특정 이미지 모델의 품질 벤치마크를 수행한 것은 아니다.

## 실제로 확인한 데이터와 아직 없는 데이터

공식 [NaviHelper Routes](https://document.pleos.ai/en/docs/pleos-only/connect-sdk-pleos/NaviHelper/routes)는 경로 옵션과 reroute 요청을 설명한다.
HIGHWAY는 고속도로 우선 옵션이다. 도로 비율의 측정값을 뜻하지 않는다.
[Event listeners](https://document.pleos.ai/en/docs/pleos-only/connect-sdk-pleos/NaviHelper/event-listeners)는 route/state/trip/driving 관련 콜백을 나열하고 실제 전달이 내비 구현에 따라 달라질 수 있다고 설명한다.

공개 RouteStateInfo/TripInfo 참조에서 이 환경으로 읽을 수 있었던 문서 본문에는 거리·시간 필드의 상세 의미/단위가 나타나지 않았다.
따라서 `distanceMeters`와 `estimatedDurationSeconds`는 **계약으로 받을 수 있는 후보**이며 실 SDK에서 확인된 필드라고 주장하지 않는다.
NaviHelper 실제 binary/API 검증을 담당 호스트가 완료한 뒤 source registry를 등록해야 한다.

| 특징 | MVP 처리 | 근거 필요 |
| --- | --- | --- |
| 거리/시간 category | nullable 값 + verified evidence, 설정 분류 | 전체 경로 값/단위 검증 |
| 우세 도로 | ratio validation, ≥0.60 분류 | 도로 구간 분류 및 거리 가중 집계 |
| 해안/산악 | route와 지형의 교차 근거가 있는 태그만 | 별도 GIS/검증 provider, MVP Mock |
| 지역 | 검증 태그 추출만, 지역별 디자인 없음 | 경로의 실제 통과 영역 |
| 복잡도 | UNKNOWN | geometry/turn 정의 및 근거 미제공 |

## 차량 표시와 구현 경계

[Compose Graphics](https://developer.android.com/develop/ui/compose/graphics/draw/overview)의 Canvas/DrawScope로 공통 scene을 그린다.
좌표는 고정 viewBox 기준으로 uniform scale하며 화면 크기별 scene 데이터는 동일하다.

[Pleos 개발 환경 문서](https://document.pleos.ai/en/docs/connect/guide/getting-started/application-development/setup-connect-sdk-emulator)는 min API 28, Gradle 8 이상을 명시한다.
이번 소스는 compile35/min28로 구성했다. 최신 라이브러리 자동 추적 대신 검증 가능한 Kotlin2.2.21/Compose1.8.3을 고정했다.

[AAOS UX restrictions](https://source.android.com/docs/automotive/driver_distraction/car_uxr)와
[CarUxRestrictions API](https://developer.android.com/reference/android/car/drivingstate/CarUxRestrictions)를 확인했다.
제한은 runtime으로 확인해야 하며 화면의 허용 여부는 앱이 임의 선언할 수 없다.
실제 manager를 받는 binding은 초기 읽기/listener/refresh/해제를 제공하지만 연결·권한·주차 확인은 호스트 책임이다.
기본 주행 정책은 표시 중지이며, 승인된 정적 화면에서도 표정/외형/상호작용을 고정한다.

## 가중치 제안의 의미

관련성×5 + 근거 신뢰도×2 + 제약 통과 일관성×1 − 위반 수×100, 다양성 0으로 시작했다.
위반 후보는 점수와 무관하게 최종 선택에서 제외한다. 초기 대표 Fixture에서 다음 의도를 만족하는 가장 단순한 값을 사용했다.
도심 근거 → 도시 의상, 장거리 근거 → 가방, 명시 지형 근거 → 지형 장식, 근거 없음 → base.
지형 관련성 1.4, 일반 관련성1.0, 장거리의 고속도로 가산0.25/긴시간 가산0.10은 지형의 구체성을 우선하는 제안이다.
임계값/가중치를 실제 데이터에서 학습·최적화했다고 주장하지 않는다. holdout 경로/사용자 평가 전까지 실험 설정이다.
