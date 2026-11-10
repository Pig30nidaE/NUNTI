# 참고 자료와 구현 연결

기존 [프로젝트 참고 자료](../REFERENCE_LINKS.md)에서 출발해 원문을 확인했다. 이번 스킨에서 적용한 디자인과 동작을 연결한다.

| 참고한 내용 | 스킨 V2에서 적용한 판단 |
|---|---|
| Duolingo 디자인 팀은 단순한 기하와 크고 읽기 쉬운 눈을 통해 서로 다른 캐릭터가 같은 디자인 언어를 쓰도록 했다. [Duolingo 캐릭터 디자인](https://blog.duolingo.com/building-character/) | 눈티도 승인 원화의 얼굴 외곽과 눈 위치, 몸의 비례를 공통 기준으로 삼았다. 머리 장식과 옷의 외곽은 크게 바꿔 흑백 비교에서 구분한다. [스킨 자산](../../prototypes/avatar_generator/skin-v2/) |
| Rive는 상태와 전이, 레이어를 구분해 재생과 인터랙션을 연결한다. [Rive State Machine Overview](https://rive.app/docs/editor/state-machine/state-machine) | 기본 자세, 경로 빛, 의상, 머리·눈, 소품, 정지 결과를 명시적 상태로 나눈다. Skip·모션 축소·주행 제한은 재생 흐름을 정적 상태로 전환하는 입력이다. 이 상태 개념을 기존 WebView Canvas 런타임에 적용한다. [Canvas 모션](../../prototypes/avatar_generator/nunti-skin-motion.js) |
| Compose의 `Transition`은 한 상태 전이에서 여러 속성을 함께 갱신한다. [Android 값 기반 애니메이션](https://developer.android.com/develop/ui/compose/animation/value-based#transition) | 경과 시간 하나에서 의상 마스크, 머리·눈 교체와 소품 움직임을 계산한다. 여러 트랙은 같은 앵커를 쓰고 4초의 마지막 합성으로 수렴한다. 기존 출발 전 화면의 Canvas를 사용해 앱 흐름에 연결한다. |
| Pleos는 플랫폼의 `CarUxRestrictions`와 변경 콜백을 바탕으로 차량 UX 제약을 적용하도록 안내한다. [주행 안전 설계](https://document.pleos.ai/en/docs/pleos-only/vehicle-app-planning-guide/driver-distraction-guideline) · [주행 제한 구현](https://document.pleos.ai/en/docs/pleos-only/vehicle-app-developer-guide/driving-restriction-development-guide) | 기존 호스트의 주차·속도·전경 확인과 주행 제한을 그대로 재생 권한으로 사용한다. 권한 변경 즉시 모션을 끝내고 허용되는 정적 화면으로 돌아간다. 데모 입력은 차량 상태의 출처가 될 수 없다. [Studio 호스트](../../android/app/src/main/kotlin/ai/nunti/app/studio/AvatarStudioActivity.kt) |

Figma에서는 기존 승인 기본형을 인스턴스로 재사용하고 새 의상·머리·눈·소품을 SVG 벡터로 배치했다. 화면의 네 카드와 여섯 상태는 오토 레이아웃으로 편집할 수 있다. 앱의 상태·픽셀·차량 제한 검증은 에뮬레이터에서 수행한다. [Figma 비교판](https://www.figma.com/design/LHLHBra8ON3OdVW0qhBnbm?node-id=42-5) · [앱 연결과 레이어 계약](SKIN_SYSTEM_V2.md)
