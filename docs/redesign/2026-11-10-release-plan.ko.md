# 눈티 11월 10일 구현 결과

바다·도시·산길 원화, 정차 중 변신, 차량용 UI를 앱에 반영했다. 기존 운전 점수 계산과 저장 계약을 유지했고, Pleos 에뮬레이터에서 LIVE 속도·기어 수신과 급가속·급제동 기록, 여정 종료 후 보고서 저장을 확인했다. 사용자 지시에 따라 목소리 개선은 제외했다. APK 배포와 시연 준비도 완료 기준에서 제외했다.

## 원화와 변신

[두 방향 비교](../../artifacts/nunti-atelier-v3/concepts/directions.png) 중 질감이 있는 피규어 방향을 구현했다. 승인 기본 눈티의 얼굴과 새싹을 기준으로 바다색 코트와 나침반, 도시의 보머와 헤드폰, 산길의 파카와 배낭을 제작했다. 새 버전은 `skin-v2.2`다. 이전 `skin-v2.0`·`skin-v2.1` 기록은 저장 당시 그림을 사용한다.

원화는 개발 중 한 번 생성한 로컬 PNG다. 반복 운행에서 이미지 API를 호출하지 않는다. 프롬프트, 원본 해시, 소유자, 출처, 내보내기 조건과 기본형 복귀 경로는 [자산 명세](../../prototypes/avatar_generator/skin-v2/atelier/manifest.json)에 기록했다. 새 원화의 상태는 `IMPLEMENTATION_CANDIDATE`이며 사용자 승인 완료로 표시하지 않았다.

4.6초 네이티브 변신은 기본 눈티에서 시작한다. 앞뒤로 나뉜 빛 리본, 테마 입자, 의상 표면 마스크, 외곽 빛을 같은 좌표와 시간으로 합성한다. 눈과 입은 빛의 정점에서 함께 바뀐다. 새 원화를 고무처럼 늘리는 메시 변형을 제거했다. 효과의 고정 공간 분포는 자산 작업 스레드에서 한 번 계산하고 재생 중 텍스처로 재사용한다. 최종 캐릭터와 변신 캔버스는 같은 크기다.

[Pokémon의 진화 연출](https://legends.pokemon.com/en-us/mega-pokemon)에서 준비·집중·공개의 순서를, [Astro Bot](https://www.playstation.com/en-us/games/astro-bot/)에서 복장별 구분과 주인공 정체성 유지를, [Effekseer 예제](https://effekseer.github.io/en/contributes/MAGICALxSPIRAL/index.html)에서 앞뒤 입자 구성을 참고했다. 해당 캐릭터를 모사한 자산은 사용하지 않았다. 기존 Effekseer 자산은 [크레딧](../NUNTI_VFX_ASSET_CREDITS.md)을 따른다.

## 차량 UI

실제 앱 창 1683×1210과 분할 창 830×1209~1210에서 입력·변신·주행·도착 화면을 확인했다. 차량 시스템 내비게이션과 운전 정보 영역은 유지했다. 목적지·풍경·길·직접 고른 기분을 먼저 보여주고 선택 입력과 생성 설정은 접었다. 완성 화면의 반복 설명은 여행 기록으로 옮겼다.

Noto Sans KR, 제목 38~48px, 본문 22~26px, 일정한 행간, 밝은 배경과 짙은 청록색을 사용한다. 야간 색상도 같은 구조를 따른다. 검사한 일반 텍스트 10쌍은 4.5:1 이상, 입력·보조 버튼 경계 6쌍은 3:1 이상이다. [대비 결과](../../artifacts/nunti-atelier-v3/verification/contrast.json)

Figma에는 공식 Pleos 버튼·입력·스위치 인스턴스, 색상 변수, 오토 레이아웃으로 [출발 전](https://www.figma.com/design/LHLHBra8ON3OdVW0qhBnbm?node-id=55-14)과 [완성 화면](https://www.figma.com/design/LHLHBra8ON3OdVW0qhBnbm?node-id=55-97)을 만들었다. 실제 캡처와 대조해 제목 영역과 캐릭터 캡션 공간을 조정했다. [Pleos 디자인 가이드](https://document.pleos.ai/en/docs/connect/guide/docs-design/Introduction/intro), [Pleos 실제 화면](https://www.hyundaimotorgroup.com/ko/story/pleos-connect-next-generation-infotainment-system), [Polestar 화면 구성](https://www.polestar.com/en-ae/polestar-4/infotainment/)을 참고했다.

## 점수와 저장

기존 `JourneyService → PleosSignalSource → JourneySession → ScoreEngine` 흐름을 유지했다. `JourneyService`와 `AvatarStudioActivity`는 이번 작업 시작 시 사본과 동일하다. 음성 초안은 앱 소스에서 제외했다. `JourneyRuntime`에는 새 스킨 버전의 번들 경로만 추가했다.

LIVE 검증에서 공식 콘솔의 D·30km/h가 서비스에 30.000002km/h로 수신됐다. 이어 65km/h 가속과 8km/h 제동 입력에서 급가속 2건·급제동 1건을 기록했다. 17샘플의 최종 점수는 18.18점, 평가 가능한 범위는 55%였다. 안전벨트 미착용과 의도적인 급격한 속도 변화가 포함된 검증 입력이다. 미수신 항목은 점수에서 제외됐다. [LIVE 결과](../../artifacts/nunti-atelier-v3/runtime-live/journey-finished.json)

## 검증 결과와 범위

- 생성·저장·재열기, 같은 입력의 동일 결과, 중복 터치, 이전 버전 보존을 확인했다.
- 건너뛰기, 사용자·OS 모션 축소, 앱 이탈, D·30km/h 전환에서 모션이 중단됐다. 복귀 시 자동 재생하지 않았다.
- 최종 이미지 디코딩 실패 시 기본 눈티로 복귀하고 해당 상태를 저장했다.
- 모의 모드에서 네이티브 경계가 생성 POST를 차단했고 시나리오 중 원격 생성 호출은 없었다.
- 넓은 창·좁은 창·주간·야간·주행·도착 캡처를 확인했다. 좁은 창의 보조 버튼 잘림을 수정했다.
- DEMO와 LIVE 모두 여정 종료 후 보고서를 저장했다. 검증 후 차량 상태와 기존 기록을 복원했다.
- 앱 단위 검사, score 검사·lint, 생성·보관함·내비·스킨 JS 검사를 통과했다.

[기능 검증 29항목](../../artifacts/nunti-atelier-v3/runtime-final/report.json) 이후 효과 계산과 여백·문구를 보정했다. 보정한 빌드는 [LIVE·화면 검증](../../artifacts/nunti-atelier-v3/runtime-live/report.json)과 [세 테마 최종 녹화](../../artifacts/nunti-atelier-v3/motion-final/report.json)로 확인했다.

에뮬레이터의 녹화 없는 재생 측정은 313프레임 중 지연 29프레임, 9.27%였다. GPU 시간 중앙값은 12ms, 90백분위는 17ms, PSS는 약 169MiB였다. 실차의 고정 60fps를 보증하는 측정은 아니다. [프레임 원본](../../artifacts/nunti-atelier-v3/runtime-live/performance-gfxinfo.txt) · [메모리 원본](../../artifacts/nunti-atelier-v3/runtime-live/performance-memory.txt)

`MOCK_SKIN_MODE=true`를 유지했다. 운행별 이미지 생성 API 활성화는 [Skin V2 계약](SKIN_SYSTEM_V2.md)에 따른 별도 사용자 승인 범위다. 실차 성능과 모든 차량 신호의 제공 여부는 이번 에뮬레이터 검증 결과에 포함하지 않는다.

원화 패키지는 `python3 scripts/package_nunti_atelier.py`로 다시 만든다. 기기 검증은 `scripts/verify_nunti_skin_v2_runtime.mjs`, `scripts/verify_nunti_atelier_display.mjs <새 출력 폴더> --live`, `scripts/record_nunti_atelier.mjs <새 출력 폴더>`에 남겼다. [작업 전 계획](../../artifacts/nunti-atelier-v3/plan-before-v3.md)과 [시작 시 소스 사본](../../artifacts/nunti-atelier-v3/implementation-start.tar.gz)은 보존했다.
